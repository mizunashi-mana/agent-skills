---
description: Analyze recent Claude Code transcripts to detect per-turn token consumption hot spots (cache miss spikes, oversized tool_result, output bloat, MCP definition weight) and suggest concrete remediation across five categories — tool-call rewrites (offset/limit, Grep substitution), subagent delegation, cache strategy, MCP unloading, and conversation breakpoints. Use when sessions feel token-heavy, you want to find which turns consume the most tokens and why, or you need actionable rewrites for the worst-offending tool calls.
allowed-tools: Bash, Read, Write, Glob, Grep
---

# detect-token-hotspots

## 概要

ユーザーの transcript JSONL を分析し、**トークン消費の hot spot**（特に消費の激しいターン・反復パターン）を検出する特化スキル。`agent-coach` の観点 1 が「サマリ提示」止まりなのに対し、本スキルは:

1. ターン単位で usage 4 種（input / output / cache_creation / cache_read）と `tool_result` サイズを集計
2. 複数軸（cache miss / tool_result 肥大 / output 過多）で hot spot ターン TOP N を抽出
3. クロスセッションで反復する高消費パターン（同一ファイル再 Read、巨大 Bash 出力、MCP 定義肥大、サブエージェント未活用）を集約
4. 改善提案を 5 カテゴリ（**A. ツール呼び出し置換 / B. サブエージェント委譲 / C. cache 戦略 / D. MCP 切り離し / E. 断点**）に分類して具体的な書き換え案を提示

`agent-coach` の総合健康診断で「トークン消費が主因らしい」とわかった後の**深掘り**として呼び出すのが想定ユースケース。単独でも動く。

`detect-context-rot` との違い: rot はセッション後半の劣化現象（時系列）に焦点を当て、改善提案は断点 / MEMORY 移行 / Compact Instructions が主軸。本スキルは**ターン単位の単発消費**と**カテゴリ別の書き換え**が主眼で、巨大 Read を `offset/limit` に直す等の**ツール呼び出し方法**まで踏み込む。両スキルは補完関係。

## 前提条件

- macOS / Linux 環境（transcript パスは `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`）
- 分析対象セッションが少なくとも 1 件存在すること（クロスセッション傾向のため 3 件以上推奨。1〜2 件しかない場合は単一セッション分析にフォールバック）
- （任意）プロジェクトの `CLAUDE.md`・`~/.claude/CLAUDE.md`・`~/.claude/settings*.json`・`<repo>/.claude/settings*.json` が読めると、MCP 切り離し提案の根拠として利用可能 MCP 一覧をクロスチェックできる

## 手順

### 1. 分析対象セッションの決定

- **対象プロジェクト**: 現在の cwd に対応する `~/.claude/projects/<encoded-cwd>/`。`Glob` または `ls ~/.claude/projects/ | grep <repo-basename>` で実在ディレクトリを特定する
- **対象セッション**: そのディレクトリ配下の `*.jsonl` を mtime 降順で**最新 5〜10 セッション**
- **除外**: 実行中セッション（mtime 最新の 1 件）。ユーザーが明示指定した場合は除外しない
- **件数の調整**: ユーザーから指定があれば従う

候補セッション一覧（ファイル名 / mtime / サイズ / 概算ターン数 / 概算トークン総計）を簡潔に提示してから処理に進む。

### 2. JSONL の構造把握（hot spot 検出に使うフィールド）

| 場所 | 用途 |
| --- | --- |
| `type == "assistant"` の `message.usage` | トークン内訳（input / output / cache_creation / cache_read） |
| `assistant.message.content[]` のうち `type == "tool_use"` | このターンで呼ばれたツール名・引数 |
| 直後の `user.message.content[]` のうち `type == "tool_result"` | ツール出力本体（文字数集計対象） |
| `type == "system"` の reminder | MCP / スキル / サブエージェント定義テキスト（文字数 = 定義オーバーヘッド） |
| `type == "permission-mode"` | モード切替（auto / plan / default 等） |
| 各レコードの timestamp / 記録順 | ターン番号 N の決定 |

**1 ファイル全文 Read は避ける**。1MB 超のファイルは `Bash` で `wc -l` → `python3` ヒアドキュメントで集計する（実装ヒント参照）。

### 3. ターン単位の指標抽出

各 assistant ターン N について以下を記録:

#### 3.1 usage 内訳

- `input_tokens`
- `output_tokens`
- `cache_creation_input_tokens`（cache miss 量。これが大きいほど「新規読み込み」）
- `cache_read_input_tokens`（cache hit 量。これが大きいほど「キャッシュ再利用」）
- 派生: **cache miss 比率** = `cache_creation / (cache_creation + cache_read + 1)`（0 除算避け）

#### 3.2 ツール呼び出し → ツール結果の対応

このターンの `tool_use` ブロック（複数ある場合あり）と、直後の user メッセージの `tool_result` を `tool_use_id` で突合:

- ツール名（`Read` / `Bash` / `Grep` / `Glob` / `Agent` / `Skill` / `mcp__*` / `Write` / `Edit` 等）
- 引数の要約（Read の `file_path`、Bash の `command` 先頭、Agent の `subagent_type` 等）
- `tool_result.content` の文字数合計（文字列なら `len()`、配列なら各 part の `text` を連結して `len()`）

#### 3.3 ターン総量の近似

- ターン N の「ツール出力負荷」 = そのターンに紐づく全 tool_result サイズ合計
- 大半の cache_creation はツール出力やシステム定義の差分から来るため、tool_result サイズと cache_creation_input_tokens は相関しがち

### 4. 複数軸での hot spot 抽出

軸ごとに独立して TOP N（既定 N = 10）を抽出する。

#### 軸 A: cache_creation スパイク

- `cache_creation_input_tokens` が大きい順に上位 10 ターン
- ターン N、ツール名、引数要約、cache_creation 値、直前ターンとの差分を記録
- **解釈**: cache miss が多発しているターン。原因候補は (i) 巨大 tool_result の挿入、(ii) 5 分以上の中断による cache 失効、(iii) システム reminder の差し替え

#### 軸 B: tool_result サイズ過多

- ターンに紐づく tool_result 文字数合計が大きい順に上位 10 ターン
- ツール名別の内訳（Read / Bash / Agent / mcp / Grep）
- 単一 tool_result が 5000 文字 / 100 行を超えるイベントを別途列挙

#### 軸 C: output_tokens 過多

- `output_tokens` が大きい順に上位 10 ターン
- assistant のテキスト出力が長い（説明文・コード生成・大きなレポート）
- **解釈**: ユーザー側で「短くしてほしい」「要約して」を指示できるシグナル

#### 軸 D: cache miss 比率（系列）

- ターン単位の cache miss 比率を時系列でプロット（テキスト表で代用可: `[##__#####_]` のような簡易ヒストグラム）
- セッション後半で急に miss 比率が上がっていれば「断点 or 大きな差し替えイベント」のサイン

#### 軸 E: 連続消費区間

- 連続する 5 ターン以上で cache_creation が継続的に高い（各ターン > セッション平均 × 1.5）区間
- **解釈**: 重い調査フェーズ。サブエージェント委譲の候補

### 5. クロスセッション傾向の抽出

複数セッションを横断して以下を集計:

#### 5.1 反復ファイル Read

- ファイルパス別に「総 Read 回数」と「累積 tool_result 文字数」
- 同一 cwd 内で 5 回以上 Read されているファイル
- そのうち `offset/limit` 指定なしの全文取得が多いもの → **書き換え候補**

#### 5.2 反復 Bash 出力

- Bash コマンドの prefix（最初の 1〜2 トークン）別に「総実行回数」と「累積 tool_result 文字数」
- 単発の出力が大きいコマンドパターン（`cat`, `find`, `git log` 全件、`pytest -v` 全出力 等）
- → 出力絞り（`| head`, `--max-count`, ファイルへの書き出し + grep）の候補

#### 5.3 MCP / システム定義オーバーヘッド

- `type == "system"` レコードのうち「Available tools」「following skills」「following deferred tools」セクションの文字数
- 特に `mcp__*` ツール定義の合計文字数（active MCP が多いと数千〜数万文字が毎ターン input に乗る）
- セッション間で文字数が大きく違えば「MCP 構成差」がトークン差の主因

#### 5.4 サブエージェント未活用な重い調査

- 連続消費区間（軸 E）のうち main コンテキストで実行されたもの
- そのターン群で `Agent` ツール呼び出しが 0 回 → サブエージェント委譲候補

#### 5.5 中断起因の cache miss

- 同一セッション内で隣接 assistant ターンの timestamp 差が 5 分以上
- 直後のターンで cache_read が急減 / cache_creation が急増 → **キャッシュ失効**シグナル

### 6. 改善提案カテゴリへのマッピング

検出した finding を以下 5 カテゴリに振り分ける。1 つの finding が複数カテゴリに該当することもある（その場合は最も即効性のあるカテゴリに main で配置し、他は補足参照）。

#### A. ツール呼び出し置換（最も即効性が高い）

- 適用条件: 軸 B / 5.1 / 5.2 で「不要に大きな出力」を取り込んでいる
- 出力例:
  - `Read(file_path="/path/big.log")` → `Read(file_path="/path/big.log", offset=0, limit=200)` または `Grep(pattern="ERROR", path="/path/big.log")`
  - `Bash(command="git log")` → `Bash(command="git log --oneline -30")`
  - `Bash(command="find . -name '*.ts'")` → `Glob(pattern="**/*.ts")`
  - `Read` 全文取得が大きすぎる → 必要な関数だけ `Grep -n` でアタリ → 該当行の `offset/limit` で再 Read
- 書き換え後の推定削減トークンも併記する（tool_result 文字数 × 0.25 を目安に概算）

#### B. サブエージェント委譲

- 適用条件: 軸 E / 5.4 で「連続消費区間に Agent 呼び出しが無い」
- 出力例:
  - `Agent(subagent_type=Explore, prompt="<元の調査内容を要約>", description="<タスク>")`
  - 「ターン N〜N+5 のリポジトリ探索は Explore に委譲推奨。main 側に戻ってくる結果は subagent の最終レポートのみ」
- description / prompt の雛形 1 行を提示

#### C. cache 戦略

- 適用条件: 軸 A / 軸 D / 5.5 で「cache miss が頻発」
- 出力例:
  - 5 分以上の中断 → 短時間で続けるか、いったん `/clear` して新セッションで再開
  - 巨大 tool_result の都度挿入 → サブエージェント委譲（B）または事前にファイル化して `Read` で部分参照
  - 長期セッション後半で miss 比率上昇 → `/compact` で古いツール出力を圧縮

#### D. MCP 切り離し

- 適用条件: 5.3 で「不要 MCP の定義が毎ターン input に乗っている」
- 出力例:
  - `~/.claude/settings.json` または `<repo>/.claude/settings.json` の `disabledMcpServers` に該当 MCP 名を追加
  - 例: 当該プロジェクトで Gmail / Calendar を使っていなければ `disabledMcpServers: ["claude_ai_Gmail", "claude_ai_Google_Calendar"]`
- 切ったときの推定削減（system reminder 文字数）も併記

#### E. 断点（/clear・/compact）

- 適用条件: 軸 D / 5.5 で「セッション後半に miss 比率上昇」または累積 cache_read が 200K を超えても続いている
- 出力例:
  - 「ターン N 以降は別トピックなので /clear」
  - 「成果物保持が必要なら `/compact 修正済みファイル一覧と最新指示を保持`」
- `detect-context-rot` の結果と整合させる（同じセッションを見ているはずなので一致するのが望ましい）

### 7. レポート生成

レポートは画面に直接ダンプせず、ファイルに書き出す。

1. 出力ディレクトリ: **`.ai-agent/tmp/<YYYYMMDD>-token-hotspots/`**（cwd 基準）。存在しなければ `mkdir -p`
2. レポート本文: `<出力ディレクトリ>/report.md` を `Write` で書き出す
3. 画面には以下のみ表示:
   - レポートファイルパス
   - セッション別 hot spot サマリ（最大 5 セッション分、トークン総計と TOP1 ターンの主因）
   - 推奨アクション TOP3（A〜E から効果順）

#### レポート構造（ファイル本文）

````markdown
# Token Hotspot 検出レポート

対象: <セッション一覧 / 期間>
分析範囲: 最新 N セッション (<earliest> 〜 <latest>)

## TL;DR

- 全体トークン: input <I> / output <O> / cache_creation <C> / cache_read <R>
- 検出 hot spot: 軸 A <a> 件 / 軸 B <b> 件 / 軸 C <c> 件
- 主因: <ツール出力肥大 / cache miss / MCP 定義過多 など上位 2 つ>
- → 推奨アクション TOP3 は末尾

---

## セッション別 hot spot

### `<session-id>` (<turns> turns, total <T> tokens)

#### TOP 5 ターン

| ターン | usage (in/out/c-create/c-read) | ツール | 引数要約 | 主因軸 |
| ---: | --- | --- | --- | --- |
| 42 | 1.2K / 0.8K / 38K / 5K | Read | `/big/file.log` 全文 | B (tool_result 肥大) |
| 51 | 0.9K / 0.5K / 22K / 12K | Bash | `git log` 全件 | B + A (cache miss) |
| 67 | 8K / 14K / 3K / 200K | (assistant text) | (大きな実装出力) | C (output 過多) |
| ... | | | | |

#### cache miss 比率タイムライン

```
turn:  10  20  30  40  50  60  70  80
miss:  ##  #_  __  #_  ##  ###  ####  ####
```
→ ターン 60 以降で miss 比率が上昇。断点 or 重い調査の流入。

(セッション数だけ繰り返し。最大 5 セッション。それ以上は「その他のセッション」に圧縮)

---

## クロスセッション傾向

### 反復ファイル Read（ツール置換候補）

| ファイル | 通算 Read | 累積文字数 | offset/limit 比率 | 提案 |
| --- | ---: | ---: | ---: | --- |
| `<path>` | 12 | 480K | 0% | offset/limit 指定 / Grep 置換 |

### 反復 Bash 出力（出力絞り候補）

| コマンド prefix | 通算実行 | 累積文字数 | 提案 |
| --- | ---: | ---: | --- |
| `git log` | 8 | 320K | `--oneline -30` を既定に |
| `find .` | 5 | 180K | `Glob` ツール置換 |

### MCP / システム定義オーバーヘッド

- system reminder 平均文字数: <X> chars/turn
- うち MCP 定義: <Y> chars (<MCP 名> が <z>%)
- 不要そうな MCP: <候補>（プロジェクトで未使用の場合）

### サブエージェント未活用な重い調査

- セッション `<id>` ターン N〜M: 連続 K ターンで cache_creation 高位、Agent 呼び出し 0 回 → Explore 委譲推奨

### 中断起因の cache miss

- セッション `<id>` ターン N: 直前との timestamp 差 <X> 分、cache_read が <Y>% 減 → 断点運用推奨

---

## 改善提案

### A. ツール呼び出し置換

| ターン | 現状 | 書き換え後 | 推定削減 |
| --- | --- | --- | ---: |
| `<sid>:42` | `Read("/big/file.log")` | `Read("/big/file.log", offset=0, limit=200)` または `Grep("ERROR", path=...)` | ~30K tok |
| `<sid>:51` | `Bash("git log")` | `Bash("git log --oneline -30")` | ~15K tok |

### B. サブエージェント委譲

| セッション | ターン区間 | 推奨呼び出し |
| --- | --- | --- |
| `<sid>` | 60〜68 | `Agent(subagent_type=Explore, prompt="<要約>", description="...")` |

### C. cache 戦略

- セッション `<sid>` ターン N: 5 分以上の中断あり → 連続作業 or `/clear` 新セッション
- セッション `<sid>` 全体: cache_read 累積 250K → `/compact` で古いツール出力を圧縮

### D. MCP 切り離し

```json
{
  "disabledMcpServers": [
    "<未使用の MCP 名>"
  ]
}
```
根拠: <MCP 名> は本プロジェクトのいずれのターンでも未呼び出し。system reminder の <X>% を占めている

### E. 断点（/clear・/compact）

| セッション | 推奨ターン | 理由 |
| --- | --- | --- |
| `<sid>` | N (/clear) | 別トピック遷移かつ累積トークン > 200K |

---

## 統計サマリ

- セッション数: <N>
- ターン総数: <合計>
- トークン総計: input <I> / output <O> / cache_creation <C> / cache_read <R>
- hot spot 検出件数: 軸 A <a> / 軸 B <b> / 軸 C <c> / 軸 D 区間 <d> / 軸 E 区間 <e>
- 平均 cache miss 比率: <X>%

## 誤検出の可能性

- 大きな実装出力（軸 C）はユーザー意図のコード生成なら正常
- 巨大 tool_result（軸 B）でも一回だけならコスト許容範囲のことが多い
- cache miss 比率上昇は実装フェーズの自然な変化のこともある（巨大ファイル新規作成等）
- MCP 定義文字数は「全く使わない MCP」のときだけ削減対象（少しでも使うなら残す）

## 推奨アクション TOP3

1. **<アクション>** — <1 行の why と how>
2. **<アクション>** — <1 行の why と how>
3. **<アクション>** — <1 行の why と how>
````

#### TOP3 の優先度

| Tier | 内容 |
| --- | --- |
| Tier 1（必ず TOP3） | 単一ターンで cache_creation > 50K / 全 MCP のうち未使用 MCP が定義オーバーヘッドの 30% 超 / 反復 Read の累積 500K 超 |
| Tier 2（影響大なら TOP3） | 連続消費区間 5 ターン以上で Agent 未呼び出し / 5 分以上の中断後の miss 比率急増 / 単発の巨大 tool_result 100K 超 |
| Tier 3（運用改善） | 軽微な反復コマンド / 単発の output 過多 / 軽微な MCP 過多 |

判断基準: **書き換え 1 つで継続的に効果が出るもの** を上に。MCP 切り離し（D）や反復ファイルの offset/limit 化（A）はセッション横断で効くので Tier 1 に上がりやすい。

#### finding が少ないとき

検出が 1〜2 件しかないときは、軸別に章立てせず **「気づいたこと」セクション 1 つ + TOP3** に圧縮する。空でも構造を埋めるために finding を水増ししないこと。

### 8. 実装ヒント

`Bash` で `python3` ヒアドキュメントを使うと一気に集計できる。骨格例:

```python
import json, glob, os, re
from collections import Counter, defaultdict

SESSIONS = sorted(
    glob.glob(os.path.expanduser("~/.claude/projects/<encoded-cwd>/*.jsonl")),
    key=os.path.getmtime, reverse=True
)[1:11]  # 実行中除外して 10 件

def tool_result_len(content):
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(len(p.get("text", "")) for p in content if isinstance(p, dict))
    return 0

def per_turn(path):
    """ターンごとに usage と紐づく tool_result サイズを返す。"""
    pending = {}  # tool_use_id -> (turn_idx, name, input_summary)
    turns = []   # [{turn, usage, tools: [(name, args, result_len)], ts}]
    turn_idx = 0
    for line in open(path):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = rec.get("type")
        if t == "assistant":
            turn_idx += 1
            usage = rec.get("message", {}).get("usage", {})
            entry = {
                "turn": turn_idx,
                "usage": {k: usage.get(k, 0) for k in (
                    "input_tokens", "output_tokens",
                    "cache_creation_input_tokens", "cache_read_input_tokens",
                )},
                "tools": [],
                "ts": rec.get("timestamp"),
            }
            turns.append(entry)
            for block in rec.get("message", {}).get("content", []):
                if block.get("type") == "tool_use":
                    pending[block.get("id")] = (turn_idx, block.get("name"), block.get("input", {}))
        elif t == "user":
            content = rec.get("message", {}).get("content")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        tid = block.get("tool_use_id")
                        info = pending.pop(tid, None)
                        if info is None:
                            continue
                        ti, name, args = info
                        size = tool_result_len(block.get("content"))
                        # 対応する assistant turn にぶら下げる
                        for tt in turns:
                            if tt["turn"] == ti:
                                tt["tools"].append((name, args, size))
                                break
    return turns

def cache_miss_ratio(turn):
    u = turn["usage"]
    cc = u["cache_creation_input_tokens"]
    cr = u["cache_read_input_tokens"]
    return cc / (cc + cr + 1)

def hotspots(turns, k=10):
    by_cache_creation = sorted(turns, key=lambda t: -t["usage"]["cache_creation_input_tokens"])[:k]
    by_tool_result   = sorted(turns, key=lambda t: -sum(s for _, _, s in t["tools"]))[:k]
    by_output        = sorted(turns, key=lambda t: -t["usage"]["output_tokens"])[:k]
    return by_cache_creation, by_tool_result, by_output

# クロスセッション集約
file_reads = Counter()
file_read_chars = Counter()
bash_prefix = Counter()
bash_prefix_chars = Counter()

for path in SESSIONS:
    for turn in per_turn(path):
        for name, args, size in turn["tools"]:
            if name == "Read":
                fp = args.get("file_path", "")
                file_reads[fp] += 1
                file_read_chars[fp] += size
            elif name == "Bash":
                cmd = (args.get("command") or "").strip()
                head = " ".join(cmd.split()[:2]) if cmd else ""
                bash_prefix[head] += 1
                bash_prefix_chars[head] += size
```

完全実装は不要 — Claude が transcript を読み取り上記指標を集計できれば良い。集計が複雑になりすぎたら**1〜2 セッションだけ手で読み込み**、定性的に finding を作っても十分価値がある（このスキルのゴールは「ユーザーが次の書き換えを選べる」こと）。

## 注意事項

- **transcript には機密情報が含まれる可能性がある**。レポートに引用する Bash コマンド例やファイルパスにシークレット類が混入していないか軽くチェックし、疑わしければマスクする（`agent-coach` 観点 0 と同じ方針）
- **自分自身のセッションを分析しないこと**（ユーザー明示対象時を除く）。mtime 最新の jsonl を実行中セッションとみなして除外する
- **巨大 JSONL の全文 Read を避ける**。1 ファイル 1MB を超える場合は `python3` ヒアドキュメントで集計する
- **hot spot は閾値ヒューリスティック**。「これは無駄」と断定せず「削減候補」のトーンで提示し、誤検出条件を必ず併記する
- **`detect-context-rot` との関係**: rot は時系列劣化、本スキルは点 + 集約。両方検出される finding（巨大 tool_result 等）はカテゴリ E（断点）で整合させる
- **改善提案は具体的に**。「Read を絞ってください」ではなく「`Read(path, offset=0, limit=200)` または `Grep(pattern=..., path=...)` への置換」まで提示する
- **MCP 切り離し提案は慎重に**。「全く使われていない MCP」のみ対象とし、わずかでも呼び出されている MCP は残す
- **レポートはファイルに書き出し**、画面には TL;DR + TOP3 + パスのみ表示する
