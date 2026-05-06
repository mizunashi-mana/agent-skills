# detect-token-hotspots スキルの実使用評価と改善

## 目的・ゴール

`plugins/agent-coach/skills/detect-token-hotspots/SKILL.md` を実際の transcript に対して使用し、

1. SKILL.md の手順通りにレポートを生成できるか（手順の曖昧さ・不足の検出）
2. **トークン消費の傾向をちゃんと分析できているか**（軸 A〜E と クロスセッション 5.1〜5.5 で全体像を捉えているか、見逃しが無いか）
3. **トークン消費が激しい部分を見逃していないか**（hot spot の網羅性）
4. **傾向がちゃんと見れているか**（単発 hot spot に留まらず、反復・分布・原因の傾向まで踏み込めているか）
5. **レポートが調査経緯を知らなくても分かりやすいか**（背景・根拠・改善案がレポート単体で理解できるか）
6. **このスキル自体のトークン消費量**（SKILL.md 本体サイズ、試用時の集計負荷、レポート生成負荷）

を評価し、明らかになった問題点を SKILL.md に反映する。

## 実装方針

1. **試用**: 現在の `agent-skills` リポジトリの transcript（最新 5〜10 セッション）に対して SKILL.md の手順をそのまま追体験する。
2. **評価軸**:
   - 手順の網羅性（hot spot 検出のステップが詰まる箇所はないか）
   - 軸の網羅性（軸 A〜E + クロスセッション 5.1〜5.5 で実トランスクリプトの「重い部分」がほぼ全て拾えるか、新たな軸が必要か）
   - 検出された hot spot の判定妥当性（誤検出が混入していないか、人手で読んで納得できるか）
   - 傾向把握の深さ（単発ターンの羅列に終わらず、原因・分布・反復まで言えているか）
   - レポートの可読性（分析過程を知らない人が読んで「なぜそう判定したか / 何をすればいいか」が分かるか）
   - **スキル自体のトークン消費量**（SKILL.md 本体サイズ、試用時の Bash/Python 集計負荷、レポート出力サイズ）
3. **改善対象**: SKILL.md のみ（必要に応じて reference/ 切り出し）。実装スクリプトを残す方針ではない（スキルはあくまで「手順書」）。
4. **作業成果物**:
   - `.ai-agent/tmp/20260506-token-hotspots/report.md` — 試用で生成された実レポート
   - 評価メモ（このタスクの README 作業ログ）
   - SKILL.md 修正差分

## 完了条件

- [x] SKILL.md の手順通りにレポートを生成できた
- [x] レポート内の指摘について 1 件ずつ正誤確認・誤検出の有無を評価
- [x] 「分析過程を知らない人が読んでわかるか」観点でレポート構造を評価
- [x] スキル自体のトークン消費量（SKILL.md 本体サイズ + 試用時の集計負荷）を評価
- [x] 評価で見つかった問題点を作業ログにリストアップ
- [x] 修正可能な問題点について SKILL.md を更新
- [x] `python3 scripts/validate-skills.py` が通る
- [ ] PR を作成（`/autodev-create-pr`）

## 作業ログ

### 2026-05-06: タスク開始

- 関連ドキュメント確認: `plan.md`（Phase 2 = 品質改善・標準化フェーズ）、`structure.md`（agent-coach プラグインに分類）、過去の同種評価タスク `20260506-evaluate-recommend-bash-allowlist` / `20260506-evaluate-detect-rework-and-violations` を参照。
- transcript 候補: `~/.claude/projects/-Users-mizunashi-Workspace-MyWork-agent-skills/` に 27 セッション存在。

### 2026-05-06: 試用と評価

試用レポート: `.ai-agent/tmp/20260506-token-hotspots/report.md`（`report-prev-trial.md` は 5/6 0:12 時点の前回試用結果として比較用に残す）

データ: 最新 10 セッション（実行中 1 件と <5KB 1 件を除外）= 1119 ターン、cc=3.29M、cr=97.9M、overall miss%=3.25。

#### 検出された SKILL.md の問題点

**[A] 手順 2 の JSONL 構造表が現在の Claude Code (v2.1.119) と乖離している (Critical)**

- SKILL.md は `type == "system"` の reminder = MCP/スキル/サブエージェント定義テキスト として記述
- 実態: `type == "system"` は `subtype == "turn_duration"` の **メタデータ**のみ（10 セッション中 4-8 件、各 ~45 chars）
- MCP / deferred tools の実体は `type == "attachment"` の `attachment.type == "deferred_tools_delta"`（1 セッションあたり 1-2 レコード、addedNames 配列に名前を列挙）
- 影響: 手順 5.3「MCP / システム定義オーバーヘッド」を SKILL.md 通りに `system` レコードから抽出すると **ほぼ何も拾えない**

**[B] 軸 A の「cc スパイク」が単一ターン前提で書かれており、N 連続ターン plateau パターンを言語化していない (Critical)**

- 観測データで最大の cc は単発スパイクではなく**複数ターンに渡る同値プラトー**:
  - `b277cc6e:t43-44`: ToolSearch 直後に cc=76,537 が 2 ターン連続 (= 153K)
  - `c3261d15:t29-35`: TaskCreate ×6 + Bash で cc=43,070 が 7 ターン連続 (**= 301K = セッション cc 累計の 64%**)
  - `48004602:t13-16`: 起動 + ToolSearch で cc=46,286 が 4 ターン連続
- 原因は (i) ToolSearch で deferred tool schema を新規ロード、(ii) parallel tool_use 群の billing 仕様（並列でも各 invocation が同じ cc 量を billed される）
- SKILL.md は (i)/(ii) を明示せず、軸 A の解釈を「単一ターンの cache miss」に閉じている

**[C] 軸 E (連続消費区間) で TaskCreate / TaskUpdate batch を「サブエージェント委譲候補」と誤分類**

- 観測の Axis E 区間 11 件中、過半が TaskCreate/TaskUpdate batch (調査ではなくタスク設定)
- 例: `c3261d15 t29-35` (TaskCreate ×6, cc 累計 301K)、`a9ae8bc9 t13-21` (TaskCreate ×4 + setup, cc 累計 213K)
- これらに `Agent` を提案するのは妥当ではない (タスク細分化は人/AI 判断が要)
- SKILL.md は 5.4 で「Agent 呼び出し 0 → 委譲候補」とだけ書いており、tool 構成の除外条件がない

**[D] 5.5「中断起因 cache miss」シグナルが弱い**

- 5+ min ギャップを 4 件検出したが、いずれも次ターン miss% は 0.05〜3.42% で **TTL 切れ起因の miss は 0 件**
- 現在の Claude Code は `ephemeral_1h_input_tokens` (1h cache) がデフォルト有効
- SKILL.md は「5 分以上の中断 → cache 失効」と書いているが、1h ephemeral 前提では誤検出シグナル
- 本データでは 16.6 min ギャップ後でも next miss% = 0.05% (cache 維持)

**[E] 改善提案 A (ツール呼び出し置換) で "プロジェクトメタデータ小ファイルの反復 Read" 像が弱い**

- `.ai-agent/structure.md` (7,766c) を 11 セッションで 11 回全文 Read。offset 化率 18%
- これは「offset/limit を付ける」より **CLAUDE.md にサマリを inline する**のが正解（毎セッション cache に乗るため Read 不要に）
- SKILL.md の category A は「offset/limit / Grep 置換 / Glob 置換」しか書いておらず、CLAUDE.md inline 化の選択肢が無い

**[F] 改善提案 A で "巨大 Bash heredoc 出力" の置換例が無い**

- 観測で `python3 - <<PY ... PY` が 31 回、累計 56KB。単発 10,902c の出力が tool_result に直接混入する
- Bash には offset/limit が無いので、`> /tmp/result.json` に書き出して `Read(file_path, limit=120)` で部分参照する書き換えが有効
- SKILL.md には Bash 系の書き換え例として「`git log --oneline -30`」「`Glob` 置換」「`| head`」しか無く、heredoc 大出力パターンが落ちている

**[G] 手順 8 の実装ヒント Python 骨格が古い JSONL 形式前提**

- `type == "system"` から reminder を読む実装になっているが、現行形式では `attachment.type == "deferred_tools_delta"` を見るべき
- Python 骨格コードが ~95 行 = SKILL.md 全 22.8KB のうち ~30% を占有
- 「**完全実装は不要**」と注記されているのに本体に長い code block を残しているのは progressive disclosure に反する

**[H] レポート可読性: 用語凡例が無い**

- 「cc」「cr」「miss%」「Axis A〜E」を初出時に説明せず使い始めている
- 「分析過程を知らない人が読んで分かるか」観点で、TL;DR の冒頭に 1 行用語定義（`cc = cache_creation_input_tokens (cache miss 量)` 等）が欲しい

**[I] スキル自体のトークン消費量**

- SKILL.md 本体: 22.8KB / 447 行 / ~3,700 tok
  - 同等の detect-rework-and-violations は 475 行に圧縮済み（reference/ への分離後）
  - detect-context-rot は 12.5KB
  - 本スキルは長い実装ヒントが原因で重い
- 試用 1 回の Bash heredoc 出力: 集計 + hotspots + raw inspect の 4 回で各 1-15KB → 累計 ~30-50KB
- 出力レポートサイズ: 12-15KB (`report.md` ~14KB)
- 改善方針: 実装ヒント Python 骨格を `reference/implementation.md` に切り出し → 本体は ~16KB に収まる見込み

**[J] 軽微 (今回スコープ外)**

- J1. セッション起動コスト (turn 1-3) を専用カテゴリ化していない（タイムラインで `#####.....` パターンとして毎回出るが、不可避コストである旨を 1 行で済ませて良い）
- J2. miss% 計算式 (cc / (cc + cr + 1)) のテストデータが提示されていない
- J3. レポート画面表示用の TL;DR + TOP3 の文字数上限が無い

#### 改善対象 (SKILL.md 修正で対応)

優先度 1 (Critical / 解釈を間違える):

- A: 手順 2 の構造表を v2.1.119 形式に更新 (`attachment.type == "deferred_tools_delta"` を主な MCP オーバーヘッド源として記述)
- B: 軸 A を「A.1 単発スパイク」「A.2 N 連続 plateau」の 2 サブカテゴリに分割。plateau の原因 (parallel tool_use, ToolSearch schema load) を明記
- C: 軸 E に「>50% が TaskCreate/TaskUpdate/TaskList の区間は task setup として除外」を追加
- E: 改善提案 A に「小サイズ project metadata の反復 Read → CLAUDE.md inline」サブカテゴリを追加
- F: 改善提案 A に「巨大 Bash heredoc 出力 → /tmp/ に書き出して Read で部分参照」を追加
- G: 実装ヒント Python 骨格を `reference/implementation.md` に切り出し、deferred_tools_delta 抽出を追加。本体は短いポインタに圧縮

優先度 2 (品質改善):

- D: 5.5 を「1h ephemeral cache 前提では 5 分閾値は誤検出が多い。検出時は cache_creation.ephemeral_1h_input_tokens を併用」に更新
- H: レポート雛形の TL;DR 冒頭に 1 行用語定義を追加。各 Axis 初出時に 1 行注釈

優先度 3 (今回見送り):

- J1, J2, J3: 軽微なので影響が小さい

### 2026-05-06: 適用した修正サマリ

`plugins/agent-coach/skills/detect-token-hotspots/SKILL.md` への変更:

1. **概要 / description フロントマター** — A.2 plateau の検出と A-ii (CLAUDE.md inline) / A-iv (heredoc redirect) サブカテゴリを description に追加
2. **手順 2（JSONL 構造）** — Claude Code v2.1.x 形式に更新。`type=system` は `subtype=turn_duration` の**メタデータ**であり MCP/skill 定義は含まれない旨を明記。MCP overhead の抽出元は `type=attachment` の `attachment.type=deferred_tools_delta` の `addedNames`
3. **手順 4 軸 A** — A.1 単発スパイクと **A.2 N 連続 cc plateau** に分割。代表ケース 3 種 (ToolSearch deferred load / parallel tool_use batch / 起動直後) と実例 (`b277cc6e:t43-44 cc=76,537×2`、`c3261d15:t29-35 cc=43,070×7=301K`) を併記
4. **手順 4 軸 D** — 起動 (turn 1-3) の高 cc は「不可避コスト」として明示
5. **手順 4 軸 E** — TaskCreate / TaskUpdate / TaskList が >50% の区間は「task setup」として委譲対象から除外。Write のみ / Edit のみも除外
6. **手順 5.3** — 抽出元を `attachment.deferred_tools_delta` に修正。schema は遅延ロードのため実コストは name list ~5KB/session に限定される旨を明記
7. **手順 5.5** — 1h ephemeral cache 前提では 5 分閾値は誤検出が多いため**情報提供レベル**に格下げ。usage の `cache_creation.ephemeral_1h_input_tokens` を併用判定する条件を追加
8. **手順 6.A** — A-i (大ファイル offset/limit) / **A-ii (小サイズ project metadata の反復 Read → CLAUDE.md inline)** / A-iii (Bash 出力絞り) / **A-iv (巨大 heredoc 出力 → /tmp 経由)** に細分化
9. **手順 6.C** — ToolSearch 連発による A.2 plateau 対策（序盤にまとめロード）を追加。5 分 / 30 分の閾値を区別
10. **手順 6.D** — `disabledMcpServers` 提案の根拠を deferred tool 名前リスト基準に更新。`<repo>/.claude/settings.json` での無効化が安全である旨を追加
11. **手順 7（レポート構造）** — 「調査経緯を知らない人が単独で読める」要件を明示。TL;DR 冒頭に `cc / cr / miss%` の用語凡例。各 Axis の 1 行注釈。セッションごとの slash command + args によるトピック識別
12. **手順 7（誤検出セクション）** — A.1/A.2/B/C/D の各誤検出条件を分けて記述。5 分ギャップは TOP3 推奨対象外
13. **手順 7（TOP3 優先度）** — A-ii や ToolSearch 起因 plateau を追加。Tier 1/2 に新カテゴリを反映
14. **手順 8（実装ヒント）** — 約 95 行の Python 骨格を `reference/implementation.md` に切り出し。本体は短いポインタ + 軽量フォールバック手順 (5 ステップ) に圧縮
15. **注意事項** — A.2 plateau 判定の 2 軸確認、自分自身が A-iv パターンに該当しないように heredoc 巨大出力時の `/tmp` 経由を明示

新規ファイル:

- `plugins/agent-coach/skills/detect-token-hotspots/reference/implementation.md` — Python ヒアドキュメント実装の骨格 (v2.1.x JSONL 対応版、`per_turn` / `cc_plateaus` / `heavy_segments` / `cross_session_aggregates` / `gap_events` / 軽量フォールバック)

サイズ変化:

- SKILL.md: 14,817 → 19,439 chars (+4,622, ~+1,150 tok)
  - 加算分の主因は A.2 plateau 解説、A サブカテゴリ 4 分割、JSONL 構造表更新、用語凡例追加
  - 約 95 行の Python heredoc を reference/ に切り出した分は ~3KB の純減
  - 全体としては「概念の追加」が「コード切り出しによる削減」を上回る純増
- reference/implementation.md: 9,898 chars (新規、遅延ロードのため通常 prompt には乗らない)
- 行数: 447 → 483 (+36)

検証結果: `python3 scripts/validate-skills.py` → 23 ファイル 0 error。

### 2026-05-06: fresh-agent 第 2 ラウンド検証は中断

修正後 SKILL.md を独立 fresh-agent (general-purpose) で同一 10 セッションに対して試用させようとしたが、Anthropic API のレート制限（13:30 Asia/Tokyo リセット）に当たって 11 tool uses で停止。`.ai-agent/tmp/20260506-token-hotspots/report-fresh.md` は未生成。

代替検証として、本会話セッション内で生成した `report.md` (5/6 10:05、自分自身が改訂版 SKILL.md 由来の方針で書いた) と、独立した別エージェントが事前に生成していた `report-prev-trial.md` (5/6 0:12、改訂前 SKILL.md 由来) を比較:

- 改訂版で初めて検出: A.2 plateau 7 区間（特に `c3261d15:t29-35` 7 連続 cc=43,070 = 累計 301K）。改訂前は単発 cc TOP リストに紛れて見逃していた
- 改訂版で除外: TaskCreate-dominated な 4 区間（Axis E から自動除外）。改訂前は Agent 委譲候補に並んでいた誤検出
- 改訂版で新規提案: A-ii (`structure.md` を CLAUDE.md inline) と A-iv (heredoc → /tmp 経由)
- 改訂版の凡例 (`cc / cr / miss%`) と各 Axis 1 行注釈は読み手の単独理解を助ける

→ fresh-agent 検証は次回別セッションで実施可能（PR レビュー時の追補で構わない）。
