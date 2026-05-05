---
description: Analyze recent Claude Code transcripts to detect context rot signals (turn count growth, repeated reads, fading initial instructions, bloated tool results, cache miss patterns) and suggest concrete remediation -- where to /clear, when to switch to Plan mode, which investigations to delegate to subagents, what to migrate into MEMORY.md, and which CLAUDE.md Compact Instructions to add. Use when sessions feel unfocused, the model forgets earlier context, you want to diagnose long sessions, or harvest repeated patterns into structured memory.
allowed-tools: Bash, Read, Write, Glob, Grep
---

# detect-context-rot

## 概要

ユーザーの transcript JSONL を分析し、**コンテキストロット**（履歴肥大による応答品質の劣化）を検出する特化スキル。`agent-coach` の観点 4 が「サマリ提示」にとどまるのに対し、本スキルは:

1. セッション別タイムラインで **rot 始点ターン候補**を推定
2. クロスセッションで反復される情報を **MEMORY.md / CLAUDE.md 化候補**として抽出
3. 改善を 5 カテゴリ（**A. 断点 / B. Plan 化 / C. Subagent 委譲 / D. MEMORY 移行 / E. Compact Instructions**）に分類した上で具体的な雛形を提示

`agent-coach` の総合健康診断で「コンテキストロットが主因らしい」とわかった後の**深掘り**として呼び出すのが想定ユースケース。単独でも動く。

## 前提条件

- macOS / Linux 環境（transcript パスは `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`）
- 分析対象セッションが少なくとも 3 件存在すること（クロスセッション傾向のため。1〜2 件しかない場合は単一セッション分析にフォールバック）
- （任意）プロジェクトの `CLAUDE.md`・`~/.claude/CLAUDE.md`・既存 `MEMORY.md` が読めると、移行候補の重複判定がより正確

## 手順

### 1. 分析対象セッションの決定

- **対象プロジェクト**: 現在の cwd に対応する `~/.claude/projects/<encoded-cwd>/`。`Glob` または `ls ~/.claude/projects/ | grep <repo-basename>` で実在ディレクトリを特定する
- **対象セッション**: そのディレクトリ配下の `*.jsonl` を mtime 降順で**最新 5〜10 セッション**（rot は単一セッションでも見えるが、クロスセッション傾向を出すには複数必要）
- **除外**: 実行中セッション（mtime 最新の 1 件）。ユーザーが明示指定した場合は除外しない

候補セッション一覧（ファイル名 / mtime / サイズ / 概算ターン数）を簡潔に提示してから処理に進む。

### 2. JSONL の構造把握（rot 検出に使うフィールド）

| 場所 | 用途 |
| --- | --- |
| `type == "user"` | ユーザー指示の取得（初期指示・修正指示） |
| `type == "assistant"` | 応答 + `message.usage`（トークン）+ `message.content[]` の `tool_use` |
| `type == "system"` | system reminder。CLAUDE.md / 利用可能スキル一覧の取得 |
| `assistant.message.usage.cache_creation_input_tokens` | cache miss 量。蓄積で rot を見る |
| `assistant.message.usage.cache_read_input_tokens` | cache hit。減ると劣化シグナル |
| `tool_use` の `name` / `input` | 反復シグナルの識別（同一引数で同ツール再呼び出し） |
| 直後の `user.tool_result.content` 文字数 | 巨大ツール出力の判定 |
| 各レコードの timestamp（または記録順） | ターン番号 N の決定 |

**1 ファイル全文 Read は避ける**。1MB 超のファイルは `Bash` で `wc -l` → 必要箇所のみ `sed -n` または `python3` で集計する。実装ヒントは末尾参照。

### 3. シグナル抽出（セッション別）

各シグナルは独立して計算し、後段の **rot 始点推定** で統合する。

#### 3.1 量的シグナル（ターン単位の系列）

各 assistant ターン N に対して以下を記録:

- `usage.cache_creation_input_tokens`（累積も）
- `usage.cache_read_input_tokens`（累積も）
- `usage.input_tokens` / `output_tokens`
- 直近 `tool_result` の文字数合計（このターンに紐づく tool_use への返答）

#### 3.2 反復シグナル

- **同一ファイル再 Read**: `Read` の `input.file_path` が同セッション内で 2 回以上、かつ `offset/limit` が同一または重複 → カウント
- **同一 Bash 反復**: `Bash` の `input.command` が完全一致 or 正規化（`cd ... &&` 剥がし、空白圧縮）後一致で 2 回以上 → カウント
- **似た Grep/Glob 反復**: 同一 `pattern` または同一 `glob` で 3 回以上 → カウント

各反復について「初回ターン N1, 再出現 N2, N3, ...」を記録。

#### 3.3 巨大ツール出力シグナル

- `tool_result` 単体の文字数 > 5000
- `Read` で `limit` 指定なしの全文取得が大きいファイルを返した（行数 > 500）
- `Bash` 出力が 100 行 / 5000 文字を超える

各イベントのターン番号と推定文字数を記録。

#### 3.4 指示忘却シグナル

- セッション冒頭の `system` reminder / CLAUDE.md / 最初のユーザー指示で示されたルール（"必ず X する", "Y してはいけない", "出力は Z 形式"）を抽出
- 後半（rot 始点候補以降）でこれらに違反している assistant 行動があれば記録
- 例: 「コミットは指示時のみ」とあるのに勝手に commit、「テスト不要」とあるのにテストを書き始める、等

#### 3.5 断点欠落シグナル

- セッション全体のターン数が 50 を超え、かつ `/clear` を示す user メッセージや明示的な `/compact` 痕跡が無い
- 累積トークンが 200K を超えたまま継続している
- Plan モードに入った形跡が無い長期実装（assistant が `ExitPlanMode` を呼ばずに 30 ターン以上連続実装）
- 重い調査ターン（巨大 tool_result 連発）が `Agent(subagent_type=Explore)` を呼ばず main で行われた

### 4. rot 始点ターン推定

セッションごとに以下 3 候補のうち**最も早い**ターンを「rot 始点候補」とする。3 候補すべてが揃わないこともあるので、揃った候補のみで判定する。

1. **トークン屈曲点**: 累積 `cache_creation_input_tokens` の傾きが、セッション前半 30 ターン（ターン数が少なければ前半 1/3）の平均増加率の **2 倍**を初めて超えたターン
2. **反復出現点**: 反復シグナル（3.2）で「再出現 N2」が初めて検出されたターン
3. **巨大出力連発点**: 巨大ツール出力シグナル（3.3）が **3 ターン以内に 2 回以上**続けて発生し始めたターン

候補が複数あれば最も早いターンを採用。**始点後**の挙動として「指示忘却（3.4）」「断点欠落（3.5）」が現れたらレポートに併記する。

**注意**: 始点はあくまで推定。長い設計議論セッション、データ集計セッション等は rot ではない場合がある。レポートでは「可能性」のトーンを基本とし、誤検出条件を併記する（手順 7）。

### 5. クロスセッション傾向の抽出

複数セッションを横断して以下を集計:

- **反復ファイル**: 全セッション通算で 5 回以上 Read されているファイル → MEMORY.md / reference 化候補
- **反復コマンド**: 全セッション通算で 5 回以上 Bash 実行されているコマンド（or その引数なしバージョン）→ skill 化候補 / hook 化候補
- **反復指示違反**: 同じルール違反が複数セッションで起きている → CLAUDE.md / memory ルール化が必要 / 既存ルールの言い回し改善
- **平均 rot 始点**: 何ターン目あたりで rot に入りやすいか
- **平均ターン数 / 平均トークン**: rot に入る前に切るべき目安

### 6. 改善提案カテゴリへのマッピング

検出した finding を以下 5 カテゴリに振り分ける。1 つの finding が複数カテゴリに該当することもある（その場合は最も即効性のあるカテゴリに main で配置し、他は補足参照）。

#### A. 断点（/clear・/compact）

- 適用条件: 単一セッションで rot 始点後に**異なるトピック**へ遷移している、または始点後 20 ターン以上経過
- 出力: 「セッション X のターン N 以降は /clear 推奨」+ 根拠
- /compact を選ぶ目安: 後段でも前半成果物（テスト結果・修正ファイル一覧）が必要な場合は `/compact <保持指示>`

#### B. Plan モード化

- 適用条件: 30 ターン以上の連続実装で、初期に Plan 確定がなく途中で方針修正が複数回入った場合
- 出力: 「次回類似タスクは ExitPlanMode 後に実装開始すべき」候補ターン提示

#### C. Subagent 委譲

- 適用条件: 巨大ツール出力（3.3）が 3 件以上 main コンテキストに入っている、または重い調査が複数ターンに分散
- 出力: 「ターン N の調査は Agent(subagent_type=Explore) 候補」+ 推奨プロンプト雛形 1 行

#### D. MEMORY.md 移行候補

- 適用条件: クロスセッション反復ファイル / 反復コマンド / 反復ユーザー説明
- 出力: memory ファイル雛形（type は user / project / reference / feedback の中から内容で判定）

```markdown
---
name: <kebab-case-name>
description: <one-line>
type: <user | project | reference | feedback>
---

<本文>
```

判定例:
- ファイル X を毎回 Read → `reference` 型 + ファイルの位置とその役割を記録
- ユーザーが毎回同じ前提（「自分は Go 専門で React は初めて」）を説明 → `user` 型
- 毎回同じ修正指示が来る → `feedback` 型（**Why:** / **How to apply:** を含める）

#### E. CLAUDE.md Compact Instructions

- 適用条件: compaction で消えていそうな項目が rot 後半で再質問されている、または long session の運用が常態化している
- 出力: CLAUDE.md 末尾に追加する雛形

```markdown
## Compact Instructions
- 保持: 修正済みファイル一覧、実行したテストコマンドと結果、ユーザーの最新指示
- 削除: ツール出力の生ダンプ、デバッグ用ログ、繰り返し読んだファイルの全文
```

実プロジェクトの状況に合わせて「保持」「削除」項目をカスタマイズする。

### 7. レポート生成

レポートは画面に直接ダンプせず、ファイルに書き出す。

1. 出力ディレクトリ: **`.ai-agent/tmp/<YYYYMMDD>-context-rot/`**（cwd 基準）。存在しなければ `mkdir -p`
2. レポート本文: `<出力ディレクトリ>/report.md` を `Write` で書き出す
3. 画面には以下のみ表示:
   - レポートファイルパス
   - セッション別 rot 始点候補（最大 5 セッション分、ターン番号と主因シグナル）
   - 推奨アクション TOP3（A〜E から効果順）

#### レポート構造（ファイル本文）

````markdown
# Context Rot 検出レポート

対象: <セッション一覧 / 期間>
分析範囲: 最新 N セッション (<earliest> 〜 <latest>)

## TL;DR

- <K> / <N> セッションで rot 始点候補を検出
- 主因: <反復 Read / 巨大ツール出力 / 断点欠落 / 指示忘却 など上位 2 つ>
- クロスセッション傾向: <反復ファイル M 件 / 反復コマンド L 件>
- → 推奨アクション TOP3 は末尾

---

## セッション別タイムライン

### `<session-id>` (<turns> turns, <input/output/cache> tokens, mode: <auto|default|...>)

| 範囲 | フェーズ | 主なシグナル |
| --- | --- | --- |
| ターン 1〜N1 | 健全 | <代表的な行動> |
| ターン N1 | rot 始点候補 | <トークン屈曲 / 反復 / 巨大出力> |
| ターン N1〜N2 | 兆候 | <反復項目を 1〜2 行> |
| ターン N2〜end | 顕在化 | <指示忘却 / 検証なし完了 など> |

推奨断点: ターン X (/clear) ／ Plan 移行: ターン Y ／ Subagent: ターン Z

(セッション数だけ繰り返し。最大 5 セッション。それ以上は「その他のセッション」に圧縮)

---

## クロスセッション傾向

### 反復ファイル（MEMORY.md 化候補）
| ファイル | 通算 Read | 主な用途 | 移行型 |
| --- | ---: | --- | --- |
| `<path>` | 12 | <要約> | reference |

### 反復コマンド
| コマンド | 通算実行 | 用途 | 提案 |
| --- | ---: | --- | --- |
| `<cmd>` | 7 | <要約> | hook 化 / skill 化 / そのまま |

### 反復指示違反
- ルール「<...>」が <n> セッションで違反 → CLAUDE.md 言い回し改善 / 専用 memory ファイル化

### 全体指標
- 平均ターン数: <X>
- 平均トークン総計: <Y>
- 平均 rot 始点ターン: <Z>（rot 検出セッションのみ）

---

## 改善提案

### A. 断点（/clear・/compact）
| セッション | 推奨ターン | 理由 |
| --- | --- | --- |

### B. Plan モード化
| セッション | 推奨ターン | 理由 |
| --- | --- | --- |

### C. Subagent 委譲
| セッション | ターン | 推奨呼び出し |
| --- | --- | --- |
| <id> | N | `Agent(subagent_type=Explore, prompt="...")` |

### D. MEMORY.md 移行候補

#### 候補 1: <name>
雛形:
```markdown
---
name: <name>
description: <one-line>
type: <type>
---

<本文>
```
根拠: <反復回数>, <代表セッション>

(候補ごとに繰り返し)

### E. CLAUDE.md Compact Instructions

```markdown
## Compact Instructions
- 保持: <カスタマイズした項目>
- 削除: <カスタマイズした項目>
```

根拠: <どのセッションで何が消えたか>

---

## 統計サマリ
- セッション数: N
- ターン総数: <合計>
- トークン総計: input <I> / output <O> / cache_creation <C> / cache_read <R>
- rot 検出件数: <K> / <N> セッション
- finding 件数: 反復 <a> / 巨大出力 <b> / 指示忘却 <c> / 断点欠落 <d>

## 誤検出の可能性
- 長い設計議論セッションは rot ではない場合あり（`/context` で実使用率を確認推奨）
- 巨大ツール出力でもユーザー意図の調査タスクなら問題ない
- 反復 Read でも頻繁に変わるファイルなら正常

## 推奨アクション TOP3
1. **<アクション>** — <1 行の why と how>
2. **<アクション>** — <1 行の why と how>
3. **<アクション>** — <1 行の why と how>
````

#### TOP3 の優先度

| Tier | 内容 |
| --- | --- |
| Tier 1（必ず TOP3） | rot が 3 セッション以上で再現 / 指示忘却が複数セッション / 平均ターン数 80 超 |
| Tier 2（影響大なら TOP3） | 単一セッション rot で 30 ターン以上の被害 / 巨大ツール出力 5 件以上 / 反復 Read 5 回以上の単一ファイル |
| Tier 3（運用改善） | 軽微な反復コマンド / cache miss 単発 / 単発の指示忘却 |

判断基準: **複数セッションにわたって効果が継続するもの**を上に。Compact Instructions（E）と MEMORY.md 移行（D）は中長期で効くので Tier 1 に上がりやすい。

### 8. 実装ヒント

`Bash` で `python3` ヒアドキュメントを使い一気に集計するのが効率的。骨格例:

```python
import json, glob, os, re
from collections import Counter, defaultdict

SESSIONS = sorted(
    glob.glob(os.path.expanduser("~/.claude/projects/<encoded-cwd>/*.jsonl")),
    key=os.path.getmtime, reverse=True
)[1:11]  # 実行中除外して 10 件

def per_turn_metrics(path):
    cache_creation = []
    tool_result_sizes = []
    file_reads = Counter()
    bash_cmds = Counter()
    for line in open(path):
        rec = json.loads(line)
        if rec.get("type") == "assistant":
            usage = rec.get("message", {}).get("usage", {})
            cache_creation.append(usage.get("cache_creation_input_tokens", 0))
            for block in rec.get("message", {}).get("content", []):
                if block.get("type") == "tool_use":
                    if block["name"] == "Read":
                        file_reads[block["input"].get("file_path")] += 1
                    elif block["name"] == "Bash":
                        bash_cmds[block["input"].get("command", "").strip()] += 1
        elif rec.get("type") == "user":
            for block in rec.get("message", {}).get("content", []) if isinstance(rec.get("message", {}).get("content"), list) else []:
                if block.get("type") == "tool_result":
                    content = block.get("content", "")
                    size = len(content) if isinstance(content, str) else sum(len(p.get("text", "")) for p in content if isinstance(p, dict))
                    tool_result_sizes.append(size)
    return cache_creation, tool_result_sizes, file_reads, bash_cmds

def rot_inflection_turn(cache_series):
    """累積系列の傾きが前半平均の 2 倍を超えた最初のターン。"""
    if len(cache_series) < 10:
        return None
    half = len(cache_series) // 3
    early_rate = sum(cache_series[:half]) / max(half, 1)
    for i in range(half, len(cache_series)):
        if cache_series[i] > early_rate * 2:
            return i
    return None
```

完全実装は不要 — Claude が transcript を読み取り上記指標を集計できれば良い。集計が複雑になりすぎたら**1 ファイル / 1 セッションだけ手で読み込み**、定性的に finding を作っても十分価値がある（このスキルのゴールは「ユーザーが次の行動を選べる」こと）。

## 注意事項

- **transcript には機密情報が含まれる可能性がある**。レポート作成時、コマンド例やファイルパスにシークレット類が混入していないか軽くチェックし、疑わしければマスクする（agent-coach の観点 0 と同じ方針）
- **自分自身のセッションを分析しないこと**（ユーザー明示対象時を除く）。mtime 最新の jsonl を実行中セッションとみなして除外
- **巨大 JSONL の全文 Read を避ける**。1 ファイル 1MB を超える場合は `python3` での集計を併用
- **rot 始点はあくまで推定**。閾値ヒューリスティックなので「可能性」のトーンを基本に、誤検出条件を必ず併記する
- **agent-coach との関係**: 総合健康診断で「コンテキストロットが主因らしい」とわかった後の深掘りツール。観点 4 の TL;DR と矛盾しないこと（同じセッションを見ているはずなので、検出傾向は一致する想定）
- **改善提案は具体的に**。「もう少し短く運用してください」ではなく「ターン N で /clear、Plan 移行はターン M、MEMORY.md 雛形は以下」まで提示する
- **レポートはファイルに書き出し**、画面には TL;DR + TOP3 + パスのみ表示する
