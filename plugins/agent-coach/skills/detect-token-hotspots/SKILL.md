---
description: Analyze recent Claude Code transcripts to detect per-turn token consumption hot spots (single-turn cache miss spikes, multi-turn cc plateaus from parallel tool calls / ToolSearch, oversized tool_result, output bloat, MCP definition weight) and suggest concrete remediation across five categories — tool-call rewrites (offset/limit, Grep substitution, CLAUDE.md inlining of small repeat-read docs, heredoc redirect-to-tmp), subagent delegation, cache strategy, MCP unloading, and conversation breakpoints. Use when sessions feel token-heavy, you want to find which turns consume the most tokens and why, or you need actionable rewrites for the worst-offending tool calls.
allowed-tools: Bash, Read, Write, Glob, Grep
---

# detect-token-hotspots

## 概要

ユーザーの transcript JSONL を分析し、**トークン消費の hot spot**（特に消費の激しいターン・反復パターン）を検出する特化スキル。本スキルは:

1. ターン単位で usage 4 種（input / output / cache_creation / cache_read）と `tool_result` サイズを集計
2. 複数軸（cache miss スパイク / **N 連続ターン cc plateau** / tool_result 肥大 / output 過多）で hot spot ターン TOP N を抽出
3. クロスセッションで反復する高消費パターン（同一ファイル再 Read、巨大 Bash 出力、MCP 定義肥大、サブエージェント未活用）を集約
4. 改善提案を 5 カテゴリ（**A. ツール呼び出し置換 / B. サブエージェント委譲 / C. cache 戦略 / D. MCP 切り離し / E. 断点**）に分類して具体的な書き換え案を提示

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

Claude Code v2.1.x 系の transcript で参照する主なレコード:

| 場所 | 用途 |
| --- | --- |
| `type == "assistant"` の `message.usage` | トークン内訳（`input_tokens` / `output_tokens` / `cache_creation_input_tokens` / `cache_read_input_tokens`）+ `cache_creation.ephemeral_1h_input_tokens` / `ephemeral_5m_input_tokens` |
| `assistant.message.content[]` のうち `type == "tool_use"` | このターンで呼ばれたツール名・引数（`name`, `input`, `id`） |
| 後続 `user.message.content[]` のうち `type == "tool_result"` | ツール出力本体（`tool_use_id` で突合、`content` の文字数を集計） |
| `type == "attachment"` の `attachment.type == "deferred_tools_delta"` | **MCP / 標準 deferred tool の登録**。`addedNames` 配列にツール名を列挙。MCP overhead はここから推定（`mcp__<server>__<tool>` の形式） |
| `type == "user"` の `<command-name>/<command-args>` 埋め込み | slash command 呼び出し（セッショントピック識別に使う） |
| `type == "system"` の `subtype == "turn_duration"` | ターン所要時間メタデータ（reminder ではない、注意） |
| `type == "permission-mode"` | モード切替（auto / plan / default 等） |
| `type == "file-history-snapshot"` / `type == "last-prompt"` / `type == "pr-link"` | 集計対象外。スキップ可 |
| 各レコードの `timestamp` / 記録順 | ターン番号 N の決定 |

注意:

- **`type == "system"` は MCP/スキル定義を含まない**（v2.1.x 以降）。MCP overhead は `attachment.deferred_tools_delta.addedNames` から推定する
- ターン番号は `type == "assistant"` を 1 件 1 ターンとして counter で振る。**parallel tool_use を 1 ターンに集約しない**（後述の Axis A.2 plateau 検出で 1 ターン 1 invocation 扱いが必要）
- **1 ファイル全文 Read は避ける**。1MB 超は `Bash` で `wc -l` → `python3` ヒアドキュメントで集計する（実装ヒント参照）

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

cache_creation には **2 つの異なるパターン**がある。両方を独立に集計する。

##### A.1 単発スパイク

- `cache_creation_input_tokens` が大きい順に上位 10 ターン（直前ターンと cc 値が異なるもの）
- ターン N、ツール名、引数要約、cache_creation 値、直前ターンとの差分を記録
- **解釈**: 単一ターンで大きな cache miss。原因候補は (i) 巨大 tool_result の挿入、(ii) 1 時間以上の中断による cache 失効、(iii) attachment / system 構成の差し替え

##### A.2 N 連続ターン cc plateau（**見落としやすい**）

- **連続する 2 ターン以上で cc 値が完全一致** している区間を検出（差が 1% 以内）
- 各 plateau の (start_turn, end_turn, plateau_cc, N, tools_in_segment) を記録
- 累積 cost = `plateau_cc × N` を併記
- **解釈**: モデル billing の特性で「**ほぼ同じ prompt 状態の API call が立て続けに発生したとき、各 invocation が同じ cc を billed される**」という挙動。代表ケース:
  - **(i) ToolSearch 直後の deferred tool schema load**: ToolSearch で新しいツール schema が context に追加されると、その直後 1〜数ターンが (cache 反映前のため) 同 cc を billed される。例: `b277cc6e:t43-44` で ToolSearch → cc=76,537 が 2 連続
  - **(ii) 連続する複数 assistant メッセージで類似ツール呼び出し**: TaskCreate / TaskUpdate / Bash などを harness が複数の別 assistant メッセージで連発すると、N 連続ターン分が同じ cache 状態のまま billed される。例: `c3261d15:t29-35` で TaskCreate ×6 + Bash → cc=43,070 が 7 連続 = **301K cc**。注: これは「1 assistant メッセージ内の parallel tool_use」とは別物（後者も同様の plateau になり得るが、ターン分割の挙動が違う）
  - **(iii) 起動直後の system prompt 確立**: セッション最初の数ターンで同 cc 値が並ぶ。介入対象外
  - **(iv) Read/Bash 連続でも同 cache 状態が短時間に発生したケース**: 例 `48004602:t13-16` の Read+Bash plateau (cc=46,286 × 4)。tool 構成が TaskCreate/Write/Edit 主体でなくても plateau になり得る。ToolSearch 起因なら (i)、そうでなければ harness の billing 都合と解釈
- **重要**: 単発スパイクと違い、plateau の cc 値そのものは「正常な cache write 量」と解釈すべき場合がある。N 倍の billing は不可避コストで、ユーザーが直接削減できないことが多い。ただし **(i) は ToolSearch 呼び出しを序盤にまとめる**ことで部分削減できる
- 1 セッション内で plateau cost 合計 (≥ 100K) が cc 累計の 30% 超を占める場合、改善提案 C「cache 戦略」で言及

#### 軸 B: tool_result サイズ過多

- ターンに紐づく tool_result 文字数合計が大きい順に上位 10 ターン
- ツール名別の内訳（Read / Bash / Agent / mcp / Grep）
- 単一 tool_result が 5000 文字 / 100 行を超えるイベントを別途列挙

#### 軸 C: output_tokens 過多

- `output_tokens` が大きい順に上位 10 ターン
- assistant のテキスト出力が長い（説明文・コード生成・大きなレポート）
- **解釈**: ユーザー側で「短くしてほしい」「要約して」を指示できるシグナル

#### 軸 D: cache miss 比率（系列）

- ターン単位の cache miss 比率を 10 ビンに集約してプロット（テキスト: `[##__#####_]`、`#` = miss% > 5%）
- セッション後半で急に miss 比率が上がっていれば「断点 or 大きな差し替えイベント」のサイン
- **典型パターン**: 起動 (turn 1-3) は cc が高く 1-2 ビンが `#` になる。これは system prompt + skill description + attachment の cache 確立で**不可避**。ビン 4 以降の `#` のみ介入対象

#### 軸 E: 連続消費区間（サブエージェント委譲候補）

- 連続する 5 ターン以上で cache_creation が継続的に高い（各ターン > セッション平均 × 1.5）区間
- **解釈**: 重い調査フェーズ。サブエージェント委譲の候補
- **除外条件（誤検出回避）**:
  - 区間内のツール呼び出しの **>50% が `TaskCreate` / `TaskUpdate` / `TaskList`** の場合は「タスク設定」として除外
  - 区間内のツール呼び出しの **>50% が `Write`** の場合は「成果物生成」として除外
- **除外しない条件**: `Edit` が混在していても、**`Edit` が <30% かつ `Read` / `Bash` / `Grep` / `Glob` が支配的**な区間は「修正のための調査 + 局所適用」として委譲対象に残す（例: `Edit×1 + Read×3` は調査の方が主目的なので委譲価値あり）
- 委譲が真に効くのは **`Read` / `Bash` / `Grep` / `Glob` が支配的**な調査区間

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

抽出元は **`type == "attachment"` の `attachment.type == "deferred_tools_delta"`**（`type == "system"` ではない）。1 セッションあたり 1〜数件の delta レコードに `addedNames` 配列で全 deferred tool 名が列挙される。

- `addedNames` から `mcp__<server>__<tool>` 形式を抽出 → MCP server 別に集計
- セッションごとに「露出 MCP server リスト」「合計 deferred tool 数」「name list の総 chars」を記録
- セッション横断で集計し、**全セッションで `mcp__*` ツール呼び出しが 0 件の MCP** を「未使用」候補として列挙

注意:

- v2.1.x の Claude Code は **MCP/deferred ツールの schema を遅延ロード**（必要時に `ToolSearch` で fetch）するため、未使用 MCP が context に乗せるのは **名前リスト ~5KB/セッション** のみ。schema 量は乗らない
- したがって「不要 MCP 切り離し」の効果は中程度（数 KB / セッション）。Tier 1 推奨アクションに昇格させるのは「**全セッションで呼び出し 0 件**」かつ「**deferred tool 数の 30% 以上を占める MCP**」のみ

#### 5.4 サブエージェント未活用な重い調査

- 連続消費区間（軸 E）のうち main コンテキストで実行されたもの
- そのターン群で `Agent` ツール呼び出しが 0 回 → サブエージェント委譲候補

#### 5.5 中断起因の cache miss

- 同一セッション内で隣接 assistant ターンの timestamp 差が 5 分以上のギャップを抽出
- **判定**: 直後のターンの `cache_creation_input_tokens` が直前ターンより大きく増え、`cache_read_input_tokens` が急減した時のみ "失効シグナル"

注意（誤検出回避）:

- 現行 Claude Code は `cache_creation.ephemeral_1h_input_tokens` を主に使用（1 時間 TTL）。**5 分のギャップでは cache はほぼ確実に維持される**ため、5 分閾値だけだと誤検出が多い
- 検出時は usage の `cache_creation.ephemeral_1h_input_tokens` と `ephemeral_5m_input_tokens` を併用し、**「1h cache を再書き込みしている」場合のみ TTL 切れと判定**。30 分以上 + 1h 系も増えている場合に絞ると精度が上がる
- 観測データでは 16 分ギャップ後でも next miss% < 1% の事例があるため、5 分閾値は**情報提供レベル** に留め、TOP3 推奨にはあげない
- **目安レンジ**: <30 min は表で表示しない（ノイズ）、30-60 min は注記のみ、>60 min かつ 1h 系再書き込みありで初めて TTL 切れ疑い

### 6. 改善提案カテゴリへのマッピング

検出した finding を以下 5 カテゴリに振り分ける。1 つの finding が複数カテゴリに該当することもある（その場合は最も即効性のあるカテゴリに main で配置し、他は補足参照）。

#### A. ツール呼び出し置換（最も即効性が高い）

適用条件: 軸 B / 5.1 / 5.2 で「不要に大きな出力」を取り込んでいる。書き換え後の推定削減トークンも併記する（tool_result 文字数 × 0.25 を目安に概算）。サブカテゴリ:

##### A-i 大きいファイルの Read 絞り込み

- `Read(file_path="/path/big.log")` → `Read(file_path="/path/big.log", offset=0, limit=200)` または `Grep(pattern="ERROR", path="/path/big.log")`
- 必要な関数だけ `Grep -n` でアタリを付ける → 該当行を `offset/limit` で再 Read
- 適用例: 10KB+ の SKILL.md / 設定ファイル / log file

##### A-ii 小サイズ project metadata の反復 Read → CLAUDE.md inline

- 適用条件: **<10KB の小ファイル**（例: `.ai-agent/structure.md`、`steering/plan.md`、`CONTRIBUTING.md` 概要）が**複数セッションで毎回 Read されている**（5 セッション以上）
- 書き換え: ファイル全文を Read し続ける代わりに、**主要部分の要約を `CLAUDE.md` に inline** する。CLAUDE.md は cache に乗るため毎セッション追加 Read コストが消える
- 詳細が必要なときだけ `Read(path, offset=N, limit=80)` で部分参照
- 出力例（提案レベルで何を書くか）:
  - 「`structure.md` (7,766c × 11 セッション = 累計 70KB) → CLAUDE.md に "## ディレクトリ構成 (要約)" として 10-15 行で抜粋。詳細参照時のみ部分 Read」
  - 「`plan.md` の `## 現在のフェーズ` 3-5 行を CLAUDE.md に inline」

inline 例（10-15 行を目安に提案する）:

```markdown
## ディレクトリ構成 (要約)

- `src/` - アプリ本体（言語: TypeScript / フレームワーク: Next.js）
- `tests/` - 単体・結合テスト（vitest）
- `scripts/` - CI/CD 補助スクリプト
- `docs/` - 設計ドキュメント（更新頻度低）

詳細は `docs/structure.md` を `Read(file_path=..., offset, limit)` で部分参照。

## 現フェーズ

Phase 2「品質改善」進行中。直近の主要 issue: #N1 (CI 高速化), #N2 (型エラー削減)
```

つまり「ファイル全体を要約」ではなく「**毎タスク開始時に必ず参照される章だけ抽出 + 詳細参照のヒント**」が目安。

##### A-iii Bash 系の出力絞り

- `Bash("git log")` → `Bash("git log --oneline -30")`
- `Bash("find . -name '*.ts'")` → `Glob(pattern="**/*.ts")`
- `Bash("grep -rn ...")` → `Grep(pattern, path, output_mode="content", -n=true, head_limit=30)`
- 適用例: 単発で 5KB+ の Bash 出力

##### A-iv 巨大 Bash heredoc 出力 → ファイル経由

- 適用条件: `python3 - <<PY ... PY` 等の heredoc で **5KB+ の JSON / dump を直接出力**している（Bash には offset/limit が無いため、出力丸ごと tool_result に乗る）
- 書き換え:
  ```bash
  python3 - <<'PY' > /tmp/result.json
  ... 集計コード ...
  PY
  ```
  ↓
  ```
  Read(file_path="/tmp/result.json", limit=120)
  ```
- 効果: tool_result の 60-80% 削減 + 後続ターンで `Grep`/再 `Read` で部分参照可能になる
- 適用例: 集計用 heredoc、巨大 SQL dump、JSON ダンプ

#### B. サブエージェント委譲

- 適用条件: 軸 E / 5.4 で「連続消費区間に Agent 呼び出しが無い」
- 出力例:
  - `Agent(subagent_type=Explore, prompt="<元の調査内容を要約>", description="<タスク>")`
  - 「ターン N〜N+5 のリポジトリ探索は Explore に委譲推奨。main 側に戻ってくる結果は subagent の最終レポートのみ」
- description / prompt の雛形 1 行を提示

#### C. cache 戦略

適用条件: 軸 A / 軸 D / 5.5 で「cache miss が頻発」。サブカテゴリ:

- **巨大 tool_result の都度挿入** → サブエージェント委譲（B）または事前にファイル化して `Read` で部分参照（A-iv）
- **長期セッション後半で miss 比率上昇** → `/compact` で古いツール出力を圧縮
- **ToolSearch 連発による A.2 plateau** → 同セッションで複数回 deferred ツールをロードしている場合、序盤に `ToolSearch("select:Tool1,Tool2,Tool3")` で **必要分をまとめて一度にロード**。中盤以降の追加 ToolSearch を減らせば plateau billing コストを削減できる
- **30 分以上の中断 + 1h cache 失効シグナル** → 短時間で続けるか、いったん `/clear` して新セッションで再開
- 5 分程度の中断は 1h ephemeral cache が効くため介入不要（5.5 の注意参照）

#### D. MCP 切り離し

- 適用条件: 5.3 で「全セッション 0 呼び出しの MCP が deferred tools の 30%+ を占めている」
- 出力例:
  - `<repo>/.claude/settings.json` または `~/.claude/settings.json` の `disabledMcpServers` に該当 MCP 名を追加
  - 例: 当該プロジェクトで Gmail / Calendar を使っていなければ `disabledMcpServers: ["claude_ai_Gmail", "claude_ai_Google_Calendar"]`
- 切ったときの推定削減（deferred_tools_delta の `addedNames` 名前リスト分の chars）も併記
- **プロジェクト固有の用途**を考慮し、リポジトリ単位 (`<repo>/.claude/settings.json`) で無効化する方が安全（global で切ると他プロジェクトに影響）

#### E. 断点（/clear・/compact）

- 適用条件: 軸 D / 5.5 で「セッション後半に miss 比率上昇」または累積 cache_read が 200K を超えても続いている
- 出力例:
  - 「ターン N 以降は別トピックなので /clear」
  - 「成果物保持が必要なら `/compact 修正済みファイル一覧と最新指示を保持`」

### 7. レポート生成

レポートは画面に直接ダンプせず、ファイルに書き出す。

1. 出力ディレクトリ: **`.ai-agent/tmp/<YYYYMMDD>-token-hotspots/`**（cwd 基準）。存在しなければ `mkdir -p`
2. レポート本文: `<出力ディレクトリ>/report.md` を `Write` で書き出す
3. 画面には以下のみ表示:
   - レポートファイルパス
   - セッション別 hot spot サマリ（最大 5 セッション分、トークン総計と TOP1 ターンの主因）
   - 推奨アクション TOP3（A〜E から効果順）

#### レポート構造（ファイル本文）

レポートは「**調査経緯を知らない人が単独で読んで判断できる**」必要がある。以下を必ず満たす:

- TL;DR の冒頭に **用語凡例** を 1 行で配置 (`cc / cr / miss%` の意味)
- 各 Axis (A/B/C/D/E) の初出時に **1 行の注釈** を併記（軸名の意味）
- 各セッションに **トピック識別** (slash command 起動時はその名前 + args) を併記。`<sid>` だけだと識別不能
- 推奨アクション TOP3 は **why / how の各 1 行**

````markdown
# Token Hotspot 検出レポート

対象プロジェクト: `<repo>` (cwd: `<cwd>`)
分析範囲: 最新 N セッション (<earliest> 〜 <latest>)
（実行中の `<sid>...` を除外）

| sid | mtime | turns | 主トピック |
| --- | --- | ---: | --- |
| `<sid>` | MM/DD HH:MM | <N> | `/<slash-cmd>「<args>」` または最初のユーザー指示 |
| ... |

## TL;DR

用語: cc = `cache_creation_input_tokens` (cache 新規書き込み量) / cr = `cache_read_input_tokens` (cache hit 量) / miss% = cc / (cc + cr)

- 全体トークン: input <I> / output <O> / cache_creation <C> / cache_read <R>
- overall miss%: <X>% （健全 < 5% / 注意 5-10% / 過大 > 10%）
- 検出 hot spot: A.1 単発スパイク <a1> 件 / A.2 plateau <a2> 件 / B 巨大 tool_result <b> 件 / C 大 output <c> 件 / E 連続区間 <e> 件
- 主因（上位 2 つ）: <ツール出力肥大 / plateau billing / MCP 定義過多 等>
- → 推奨アクション TOP3 は末尾

---

## セッション別 hot spot

軸の凡例（初出時に併記）:
- A.1 = 単発 cache_creation スパイク / A.2 = N 連続 cc plateau (parallel batch / ToolSearch 由来)
- B = tool_result サイズ過多 (Read/Bash 出力肥大) / C = output_tokens 過多 (assistant text 生成大)
- E = 連続消費区間 (5 ターン以上 cc 高位、サブエージェント委譲候補)

### `<session-id>` (<turns> turns, MM/DD HH:MM, `/<slash-cmd>「<args>」`)

cc=<C> / cr=<R> / out=<O> / miss% = <X>

#### TOP 5 ターン

| ターン | usage (in/out/cc/cr) | ツール | 引数要約 | 主因軸 |
| ---: | --- | --- | --- | --- |
| 42 | 1.2K / 0.8K / **38K** / 5K | Read | `/big/file.log` 全文 (28KB) | B |
| 51 | 0.9K / 0.5K / 22K / 12K | Bash | `git log` 全件 | B |
| 67 | 8K / **14K** / 3K / 200K | (assistant text) | SKILL.md 生成 | C |
| 43-44 | 各 1.2K / 0.3K / **76K×2** / 15K | TaskCreate | ToolSearch 直後の plateau | A.2 (N=2, 累計 152K) |

#### cache miss 比率タイムライン（10 ビン）

```
<sid>: ##__#####_
```

凡例: 10 文字連結の固定幅。各文字は 10 ビン中の 1 ビンの miss 比率を表す。`#` = miss% > 5%, `.` (または `_`) = miss% ≤ 5%。
→ ターン後半（ビン 7-10）で `#` が連続する場合は断点 or 重い調査の流入の可能性。先頭 1-2 ビンの `#` は起動コストで介入対象外。

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

### MCP / システム定義オーバーヘッド（5.3、`attachment.deferred_tools_delta` 由来）

| MCP / source | tool 数 | 露出セッション数 | 全期間呼び出し回数 |
| --- | ---: | ---: | ---: |
| `<mcp-server>` | <N> | <S>/全 | **0** （未使用） |
| ... |

- 1 セッション当たりの `addedNames` 名前リスト総 chars: <X> 程度
- 全セッション 0 呼び出しかつ deferred tool 数の 30%+ を占める MCP: <候補>（D で切り離し提案対象）
- 注意: schema は遅延ロード方式のため schema 量は context に乗らない。実コストは name list ~5KB/session に限定

### サブエージェント未活用な重い調査（5.4）

| セッション | ターン区間 | 連続 K | cc 累積 | 主ツール | 性質 | Agent 推奨? |
| --- | --- | ---: | ---: | --- | --- | --- |
| `<id>` | t<N>-t<M> | K | <CC> | Read+Bash | 調査 | ○ Explore 委譲推奨 |
| `<id>` | t<N>-t<M> | K | <CC> | TaskCreate ×K | task setup | × (除外: A.2 で言及) |

A.2 plateau や TaskCreate 連発の区間は **委譲対象外** として明示する。

### 中断起因の cache miss（5.5）

| セッション | ターン | gap | 直後 miss% | 1h cache 増分 | 評価 |
| --- | ---: | ---: | ---: | ---: | --- |
| `<id>` | <N> | <X> min | <Y>% | <Z> | cache 維持 / TTL 切れ疑い |

5+ min ギャップでも cache 維持される事例が多いため、**情報提供レベル** に留め、TOP3 推奨にはあげないこと。

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
根拠: <MCP 名> は本プロジェクトのいずれのターンでも未呼び出し。deferred tool 名前リスト (`attachment.deferred_tools_delta.addedNames`) のうち <X>% を占めている

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

- **A.1 単発スパイク**: セッション起動の最初 1-3 ターンは system prompt + skill description + attachment の cache 確立で必ず高 cc になる。介入対象外
- **A.2 plateau**: parallel tool_use batch (TaskCreate ×N、parallel Bash) は不可避コスト。直接削減はできないが、**ToolSearch 由来の plateau** だけは「序盤にまとめてロード」で部分削減可能
- **大きな実装出力（軸 C）**: `Write(...SKILL.md)` 等のコード生成は本質的に短縮不可。ユーザー意図のものは「無駄」ではない
- **巨大 tool_result（軸 B）**: 一回だけならコスト許容範囲のことが多い
- **cache miss 比率上昇**: 実装フェーズの自然な変化のこともある（巨大ファイル新規作成等）
- **MCP 定義**: schema は遅延ロードなので「全く使わない MCP」のときだけ削減対象（少しでも使うなら残す）。実削減量は名前リスト ~5KB/session に限定
- **5+ min ギャップ**: 1h ephemeral cache が効くため誤検出多。TOP3 推奨に上げない

## 推奨アクション TOP3

1. **<アクション>** — <1 行の why と how>
2. **<アクション>** — <1 行の why と how>
3. **<アクション>** — <1 行の why と how>
````

#### TOP3 の優先度

| Tier | 内容 |
| --- | --- |
| Tier 1（必ず TOP3） | 反復 Read の累積 500K 超（A-i / A-ii）/ Agent 呼び出し率 < 1% で 5 ターン以上の調査区間あり（B 委譲）/ 全セッション 0 呼び出しかつ deferred tools の 30% 占める MCP（単一 / D）/ **0 呼び出し MCP 群を合算して deferred tools の 30%+ を占める場合**（合算 / D） |
| Tier 2（影響大なら TOP3） | A.2 plateau の累積 cc が累計の 30% 超かつ ToolSearch 起因（→ C: ToolSearch まとめロード）/ 単発の巨大 tool_result 100K 超（A-i または A-iv）/ 5 セッション以上で同小ファイル全文 Read（A-ii） |
| Tier 3（運用改善） | 軽微な反復コマンド / 単発の output 過多 / 軽微な MCP 過多 / 5 分ギャップ後の軽微 miss |

判断基準: **書き換え 1 つで継続的に効果が出るもの** を上に。MCP 切り離し（D）や反復ファイルの offset/limit 化（A-i）/ CLAUDE.md inlining（A-ii）はセッション横断で効くので Tier 1 に上がりやすい。

A.1 単発スパイクや A.2 plateau は「不可避コスト」が多く、TOP3 に上げる前に「ユーザーが実際に減らせるか」を判定する。

#### finding が少ないとき

検出が 1〜2 件しかないときは、軸別に章立てせず **「気づいたこと」セクション 1 つ + TOP3** に圧縮する。空でも構造を埋めるために finding を水増ししないこと。

### 8. 実装ヒント

`Bash` で `python3` ヒアドキュメントを使うと一気に集計できる。骨格コード（v2.1.x JSONL 対応版、A.2 plateau / Axis E TaskCreate 除外 / `attachment.deferred_tools_delta` 抽出含む）は **`reference/implementation.md`** に切り出した。必要に応じて参照すること。

軽量代替: 集計が複雑になりすぎたら **1〜2 セッションだけ手で読み込み**、定性的に finding を作っても十分価値がある（このスキルのゴールは「ユーザーが次の書き換えを選べる」こと）。

具体的には:

1. `Glob` で対象ディレクトリの jsonl をリストアップ → mtime 上位 1〜2 件を選ぶ
2. `Bash("wc -l <session>.jsonl")` でターン規模を見る
3. `python3 -c 'import json; ...'` のワンライナーで `cc/cr` 累計を出す
4. 重そうなターン番号だけ `python3` で個別 dump し、tool_use 内容を確認
5. 質的 finding を組み立てる（特定 SKILL.md を頻繁に読んでいる、TaskCreate を多用、等）

## 注意事項

- **transcript には機密情報が含まれる可能性がある**。レポートに引用する Bash コマンド例やファイルパスにシークレット類が混入していないか軽くチェックし、疑わしければマスクする（API キー、認証ヘッダ、環境変数ダンプ中の secret 等）
- **自分自身のセッションを分析しないこと**（ユーザー明示対象時を除く）。mtime 最新の jsonl を実行中セッションとみなして除外する
- **巨大 JSONL の全文 Read を避ける**。1 ファイル 1MB を超える場合は `python3` ヒアドキュメントで集計する
- **hot spot は閾値ヒューリスティック**。「これは無駄」と断定せず「削減候補」のトーンで提示し、誤検出条件を必ず併記する
- **改善提案は具体的に**。「Read を絞ってください」ではなく「`Read(path, offset=0, limit=200)` または `Grep(pattern=..., path=...)` への置換」まで提示する
- **MCP 切り離し提案は慎重に**。「全セッション 0 呼び出し」のみ対象とし、わずかでも呼び出されている MCP は残す。schema は遅延ロードのため実削減量は ~5KB/session
- **A.2 plateau の根拠は「N 連続ターンで cc 値が一致」と「直前ターンに ToolSearch / parallel tool_use」の両方を確認**。単に N 連続で cc が高いだけでは A.2 と断定しないこと（誤検出回避）
- **集計ヒアドキュメントの巨大出力は `> /tmp/foo.json` に書き出して `Read(limit=...)` で部分参照** する（自分自身が A-iv パターンに該当しないように）
- **レポートはファイルに書き出し**、画面には TL;DR + TOP3 + パスのみ表示する
