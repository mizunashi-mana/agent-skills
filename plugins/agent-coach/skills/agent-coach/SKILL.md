---
description: Analyze recent Claude Code transcripts and suggest improvements to the user's prompts, skill definitions, memory entries, and context management. Use when the user asks for feedback on prompts/skills, says interactions feel inefficient, suspects context rot, notices skills not triggering, or wants to optimize token usage based on actual usage history.
allowed-tools: Bash, Read, Write, Glob, Grep, WebFetch
---

# agent-coach

## 概要

ユーザーの Claude Code 利用履歴（transcript JSONL）を分析し、6 つの観点から改善提案を行うスキル。runtime に Claude が transcript を直接読み、Anthropic 公式ベストプラクティスと本スキル付属のリファレンスに照らして報告する。前処理スクリプトは持たない（Claude の判断で柔軟に分析する）。

観点:

0. **シークレット流出**（重大度: Critical）— transcript に混入した認証情報の検出 → 即マスク + ローテーション警告
1. **トークン消費 hot spot** — どこでトークンを使っているか
2. **方向修正多発プロンプト** — ユーザーが何度も修正しているプロンプト
3. **指示違反** — スキル/メモリの指示が守られていないケース
4. **コンテキストロット** — 履歴肥大による劣化のシグナル
5. **スキル未活用** — 使われるべきスキルが triggering されていないケース

具体的な書き換えテンプレ・Hook スニペット・量的目安は付属の [reference/handbook.md](reference/handbook.md) を必要に応じて参照する。

## 前提条件

- macOS / Linux 環境（transcript パスは `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`）
- 分析対象セッションが少なくとも 1 件存在すること
- （任意）WebFetch が利用できれば、Anthropic 公式ドキュメントを参照して提案の根拠を強化できる。利用不可でも分析自体は実施可能

## 手順

### 1. 分析対象の決定

ユーザーから対象指定があれば従う。指定がなければ以下のデフォルトで進める:

- **対象プロジェクト**: 現在の cwd に対応する `~/.claude/projects/<encoded-cwd>/` ディレクトリ。エンコーディングは概ね `/` → `-` の置換だが、`.`・`_`・大文字・Unicode 等の扱いはバージョン依存で確実ではないため、`ls ~/.claude/projects/ | grep <repo-basename>` または `Glob` で実在ディレクトリを特定するのを推奨
- **対象セッション**: そのディレクトリ配下の最新 3 セッション（mtime 降順）の `.jsonl`
- **除外**: agent-coach 実行中のセッション。Claude は自分の `sessionId` を直接取れないため、ヒューリスティックとして **mtime が最新（実行中に書き込まれているもの）の jsonl を 1 件除外** する。ただしユーザーが「直近のやり取りを見て」等と現在セッションを明示対象にした場合は除外しない

ユーザーに「対象セッション一覧（ファイル名・mtime・サイズ・概算ターン数）」を提示し、必要なら範囲調整を確認する。

### 2. JSONL の構造把握

各行が独立した JSON オブジェクト。主な `type`:

| type | 内容 |
| --- | --- |
| `user` | ユーザー入力（`message.content` が文字列または配列） |
| `assistant` | Claude の応答。`message.usage` にトークン数、`message.content` にテキスト/tool_use ブロック |
| `system` | システムメッセージ（reminder 等） |
| `attachment` | 添付ファイル |
| `file-history-snapshot` | ファイル状態スナップショット |
| `last-prompt` | 最終プロンプト記録 |

`assistant.message.usage` の主要フィールド:

- `input_tokens`: 純粋な input
- `cache_creation_input_tokens`: キャッシュ作成分
- `cache_read_input_tokens`: キャッシュヒット分
- `output_tokens`: 出力
- `iterations[]`: ツール反復ごとの内訳

ツール呼び出しは `message.content[]` のうち `type == "tool_use"` のブロック。ツール結果は次の `user` メッセージの `tool_result` ブロック。

### 3. 観点別の分析

各 jsonl ファイルを Read で読み込む（大きい場合は `Bash` で `python3 -c` を組み立てて集計しても良い。ただし複雑な前処理は避け、Claude の判断で重要箇所を抽出する）。

**観点 0 を最優先で実行する**。シークレット検出があれば即座にレポート冒頭に配置し、推奨アクション TOP3 にも必ず含める。

#### 観点 0: シークレット流出（重大度: Critical）

検出シグナル:

- API キー: `sk-`, `sk_live_`, `pk_live_`, `xox[a-z]-`, `ghp_`, `gho_`, `ghs_`, `AIza` 等のプレフィックス
- 認証ヘッダ: `Authorization: Bearer ...`, `Cookie: session=...`
- 秘密値: `password=`, `secret=`, `api_key=`, `token=` の右辺
- 環境変数ダンプ中の `AWS_SECRET_ACCESS_KEY` 等のキー名

検出時の対応:

1. レポートには **マスクした形** でしか引用しない（例: `sk-***xxx`、末尾 4 文字のみ）
2. 該当ファイル名・ターン番号は明示する（ユーザーが原本を確認できるように）
3. ユーザーに対して「該当認証情報は流出した可能性があるためローテーションを検討してください」と明示警告
4. **必ず推奨アクション TOP3 に含める**

詳細パターンと警告テンプレ → [reference/handbook.md#観点-0-シークレット検出パターン](reference/handbook.md#観点-0-シークレット検出パターン)

#### 観点 1: トークン消費 hot spot

集計内容:

- セッション全体の input/output/cache の合計
- `iterations` 単位で `cache_creation_input_tokens` が大きい assistant ターンの上位 5 件
- ツール結果が肥大しているターン（直前の `tool_use` の名前 + 直後の `tool_result` の文字数で推定）
- システム reminder の MCP ツール定義文字数 / アクティブツール数

**改善提案の方向性:**

- 巨大ファイルの全文 Read → `offset/limit` または Grep への置換
- 同じ Bash コマンドの繰り返し → 1 回の集約コマンドへ
- サブエージェント未活用な調査 → Explore / general-purpose agent への委譲
- 5 分以上空いた連続ターン → cache miss の可能性
- アクティブ MCP / ツール過多 → `disabledMcpServers` で本セッション不要なものを切ることで定義トークンを節約

量的目安と書き換えテンプレ → [reference/handbook.md#観点-1-トークン消費-hot-spot](reference/handbook.md#観点-1-トークン消費-hot-spot)

本観点で finding が複数出たり、ターン単位の hot spot 抽出・カテゴリ別の書き換え案（offset/limit 化、サブエージェント委譲、MCP 切り離し等）まで深掘りしたい場合は、深掘り専用の `detect-token-hotspots` スキル（同プラグイン同梱）を案内する。

#### 観点 2: 方向修正多発プロンプト

検出シグナル（ユーザーメッセージ中）:

- 否定・修正語: `no`, `not that`, `instead`, `actually`, `stop`, `wait`, `違う`, `そうじゃなくて`, `やめて`, `いや`
- 同一アシスタントターンへの即時返信で短いユーザーメッセージ（< 50 文字）
- 同じトピックでユーザーが 3 ターン以内に再指示を出している
- Claude 側の応答に "Wait, you mean..." のような確認パターンが現れる

検出後、**元のユーザープロンプト**（修正前のもの）を特定し、なぜ Claude が誤解したかを分析する。

**改善提案の方向性:**

- Anthropic Prompt engineering ガイドの該当原則に沿って書き換え案を提示
- 曖昧な指示語（"いい感じに", "適切に"）の具体化
- 期待する出力形式・粒度の明示
- 補正が 2 回以上続いていたら `Esc Esc`（`/rewind`）での巻き戻し運用を併せて提案

報告では「元プロンプト」「Claude の解釈」「ユーザーの修正」「改善案」をセットで示す。

書き換え cookbook → [reference/handbook.md#観点-2-方向修正の書き換え-cookbook](reference/handbook.md#観点-2-方向修正の書き換え-cookbook)

本観点で finding が複数出たり、3 点組（元プロンプト → Claude 解釈 → ユーザー修正）の集約や指示違反との横断分析（5 カテゴリの改善提案: プロンプト書き換え / ルール明文化 / Hook 化 / 巻き戻し運用 / skill description 改善）まで深掘りしたい場合は、深掘り専用の `detect-rework-and-violations` スキル（同プラグイン同梱、観点 3 と統合）を案内する。

#### 観点 3: 指示違反（スキル/メモリ）

対象:

- プロジェクトの `CLAUDE.md`, `.claude/skills/*/SKILL.md`, `.claude/skills/*/skill.md`
- ユーザーの `~/.claude/CLAUDE.md`, `~/.claude/projects/.../memory/*.md`（存在すれば）
- 当該セッション中の `<system-reminder>` で配布された skill 定義

これらに記載されたルール（"必ず X する", "Y してはいけない"）と、transcript 中の Claude の行動を突き合わせ、違反事例を抽出する。

**改善提案の方向性（文面改善）:**

- ルールが曖昧 → 具体例・反例を追加
- ルールが埋もれている → 配置場所の見直し（CLAUDE.md の冒頭へ移動、専用 memory ファイル化）
- ルールに `why` が無い → 「**Why:**」「**How to apply:**」セクションを追加
- skill description が triggering ロジックを含んでいない → "Use when ..." を追加

**ハーネス化の判断:** 文面改善でも繰り返し違反される、または影響が大きい場合は **Hook で決定論的に強制** することを提案する。CLAUDE.md は advisory、Hook は deterministic。

判断表と Hook スニペット例 → [reference/handbook.md#観点-3-指示違反--文面改善-vs-hook-化](reference/handbook.md#観点-3-指示違反--文面改善-vs-hook-化)

本観点で finding が複数出たり、ルール構造化抽出 → 違反検出 → 主因分類（曖昧プロンプト / ルール埋没 / 検証なし完了 / トリガミス / rot 起因）と 5 カテゴリの改善提案（プロンプト書き換え / ルール明文化 / Hook 化 / 巻き戻し運用 / skill description 改善）まで深掘りしたい場合は、深掘り専用の `detect-rework-and-violations` スキル（同プラグイン同梱、観点 2 と統合）を案内する。

#### 観点 4: コンテキストロット

検出シグナル（以下はあくまで目安。長い設計議論セッションなど、ターン数や応答サイズが大きくても問題ない場合もあるので、シグナル単体での断定は避ける）:

- 1 セッションのターン数が 50 を超える
- 後半で初期指示・初期ファイルへの参照が消失する（同じファイルを Read し直す等）
- 同じツール（特に Read / Bash の `ls`）が同一引数で繰り返される
- 巨大な tool_result（> 5000 文字）が複数ターン間隔で何度も入る

**改善提案の方向性:**

- 長期タスクは `Plan` モードで方針確定 → 実行ターンを短く保つ
- 調査は `Agent(subagent_type=Explore)` に委譲してメインコンテキストを汚さない
- 区切りが付いたら `/clear` または `/compact` で明示的にリセット
- 長期記憶は `MEMORY.md` 経由の memory ファイル化（auto memory 仕様）
- `CLAUDE.md` に "Compact Instructions" セクションを追加して保持項目を制御

量的目安と Compact Instructions サンプル → [reference/handbook.md#観点-4-コンテキストロット](reference/handbook.md#観点-4-コンテキストロット)

本観点で finding が複数出たり、クロスセッションでの傾向確認・MEMORY.md 移行候補の抽出までしたい場合は、深掘り専用の `detect-context-rot` スキル（同プラグイン同梱）を案内する。

#### 観点 5: スキル未活用

手順:

1. 当該セッション内の `type == "system"` エントリ（または `user` メッセージの `tool_result.content`）から、`The following skills are available for use with the Skill tool:` で始まる節を抽出して利用可能スキル一覧を取得する。`type` を絞らず全行 grep するとヒット数が膨らみトークンを浪費するので注意
2. ユーザーの各リクエストについて、本来トリガすべきスキル候補を判定
3. 実際に `Skill` ツールが呼ばれたかを確認
4. 未起動だったケースを抽出

**改善提案の方向性:**

- スキルの `description` フロントマターに「Use when ...」のトリガ条件が不足 → 追加案を提示
- description が抽象的 → 具体的キーワード・シナリオを追加
- 似た description のスキルが競合 → 区別を明示
- skill-creator の triggering 最適化を案内

Use when... テンプレ → [reference/handbook.md#観点-5-スキル-description-改善](reference/handbook.md#観点-5-スキル-description-改善)

本観点で finding が複数出たり、未トリガパターンの集約・description 書き換え案の生成・サブエージェント未トリガまで深掘りしたい場合は、深掘り専用の `detect-missed-skill-triggers` スキル（同プラグイン同梱）を案内する。

### 4. レポート生成

レポートのゴールは **「ユーザがすぐに次の行動を選べる」** こと。観点別に finding を網羅列挙するのではなく、**傾向（パターン）と対策**を主軸に据える。

#### レポートの出力先（ファイル化必須）

レポート全体は長くなるため、画面に直接ダンプせず必ずファイルに書き出す:

1. 出力ディレクトリは **`.ai-agent/tmp/<YYYYMMDD>-agent-coach/`**（cwd 基準）
2. ディレクトリが存在しなければ `mkdir -p` で作成する
3. レポート本文を `.ai-agent/tmp/<YYYYMMDD>-agent-coach/report.md` として `Write` で書き出す
4. 画面には以下のみ表示する:
   - レポートファイルのパス
   - TL;DR セクション（傾向 3 件 + 誘導 1 行）
   - 推奨アクション TOP3

これにより画面が見やすく、過去レポートも追跡可能になる。

#### 出力構造（ファイル本文）

```markdown
# Agent Coach レポート

対象: <セッション一覧と期間>

## TL;DR

直近のセッションには **N つの傾向** が見えました:

- 🔴 **<傾向 A 名>**: <ワンライナー>
- 🟡 **<傾向 B 名>**: <ワンライナー>
- 🟢 **<傾向 C 名>**: <ワンライナー>

→ すぐに試せる対策 TOP3 は末尾。

---

## 傾向 A: <名前> 🔴

**起きていること**: <2-3 行のパターン記述。代表事例 2-3 件をターン番号で参照>

**なぜ問題か**: <1-2 行。reference/handbook.md 該当節 / 公式ドキュリンクを inline で>

**対策**:
1. **<具体的アクション>** — <1 行の how>
2. **<具体的アクション>** — <1 行の how>
3. （必要なら Hook 化提案 1 行）

---

## 傾向 B: <名前> 🟡

(同じ 3 ブロック)

## 傾向 C: <名前> 🟢

(同じ 3 ブロック)

---

## その他の気づき

(Info レベルの finding を 1 行ずつ。最大 5 件)

- L186 (4479fcdb): <1 行で内容>
- L294 (a17f0634): <1 行で内容>

## 統計サマリ

- トークン: input N / output M / cache_read K
- ターン: <セッション ID> = N user / M assistant
- 検出件数: 傾向 3 / その他 5 / シークレット 0

## 誤検出の可能性

- <傾向 A は ... の場合は正常>
- <傾向 B は ... の場合は正常>

## 推奨アクション TOP3

1. **<アクション>** — <1 行の why と how>
2. **<アクション>** — <1 行の why と how>
3. **<アクション>** — <1 行の why と how>
```

#### 傾向の作り方

5 観点（0〜5）は **分析の lens** であり、レポートの章タイトルではない。同じ **根本原因** または同じ **対策** に当てはまる finding を 1 つの傾向にまとめる:

- 例: 観点 1 (hot spot) と観点 4 (context rot) で見つかった巨大ツール出力が、両方とも「Subagent 委譲」で対処できるなら → 傾向「**ツール出力の肥大化**」1 つにまとめる
- 例: 観点 2 (方向修正) の事例 3 件が全て「完了後の差し戻し」なら → 傾向「**完了後の方向修正**」1 つにまとめる
- 例: 観点 3 (指示違反) と観点 4 (context rot) が同じ「CLAUDE.md ルールが埋もれている」起因なら → 傾向「**CLAUDE.md の肥大化**」1 つにまとめる

**傾向は最大 3 つまで**。重大度バッジは 🔴 Critical / 🟡 Warning / 🟢 Info で示す。それ以上の finding は「その他の気づき」に 1 行ずつ。

#### 各セクションの長さ規約

| セクション | 長さの目安 |
| --- | --- |
| TL;DR | 傾向 3 件 × 各 1 行 + 誘導 1 行 |
| 各傾向セクション | 「起きていること」「なぜ問題か」「対策」の 3 ブロックのみ。合計 12〜20 行 |
| その他の気づき | 1 finding = 1 行、最大 5 件 |
| 統計サマリ | 3〜4 行 |
| 誤検出の可能性 | 各傾向につき 1 行 |
| 推奨アクション TOP3 | 各 1〜2 行、合計 6 行以内 |

**やらないこと**:

- 観点 0〜5 を全部見出しにして finding を網羅列挙すること
- 各 finding に 6 項目（重大度・シグナル・根拠・原因・改善案・誤検出）の長尺テンプレを埋めること
- 傾向セクション内に大きな比較表を置くこと（情報過多になる）

#### TOP3 の優先度

各傾向の対策の中から最も効果の高い 3 つを末尾で再掲する。Tier 表は以下:

| Tier | 内容 |
| --- | --- |
| **Tier 1（必ず TOP3）** | シークレット流出 / 危険コマンド検出 / 同じミスが 3 回以上反復 |
| **Tier 2（影響大なら TOP3）** | 補正ループ（2 回以上） / 検証なしの「完了」宣言 / スキル未活用 3 件以上 |
| **Tier 3（運用改善）** | ターン数過多 / ファイル全文 Read / cache miss |

判断基準: **ユーザーがすぐに行動でき、複数セッションにわたって効果が継続するもの** を上に置く。

判断基準の詳細 → [reference/handbook.md#推奨アクション-top3-の-tier](reference/handbook.md#推奨アクション-top3-の-tier)

#### finding が少ないとき

検出が 1〜2 件しかないときは、傾向化せず **「気づいたこと」セクション 1 つ + TOP3** に圧縮する。空でも構造を埋めるために finding を水増しすることは厳禁。

### 5. ベストプラクティス参照

提案の根拠は以下を順に参照する:

1. **付属リファレンス**: [reference/handbook.md](reference/handbook.md) — 書き換えテンプレ・Hook スニペット・量的目安・一次ソースリスト
2. **公式ドキュメント**（必要なら WebFetch）:
   - Best practices: <https://code.claude.com/docs/en/best-practices>
   - Skills: <https://code.claude.com/docs/en/skills>
   - Hooks: <https://code.claude.com/docs/en/hooks>
   - Memory: <https://code.claude.com/docs/en/memory>

参照したらレポートに引用元を付記する。

## 注意事項

- **transcript には機密情報が含まれる可能性がある**。観点 0 として独立検出 + マスク + ローテーション警告を必須とする
- **自分自身のセッションを分析しないこと**（ユーザー明示対象時を除く）。Claude が自身の sessionId を直接取得する手段はないので、mtime 最新の jsonl を実行中セッションとみなして除外する
- **巨大 JSONL の全文 Read を避ける**。1 ファイル 1MB を超える場合は `Bash` で `wc -l` → 必要箇所のみ `sed -n` で抽出、または python での集計を併用する
- **改善提案は具体的に**。「もう少し明確に書いてください」ではなく、書き換え後のプロンプト例まで提示する
- **断定を避ける**。トークン消費・コンテキストロットは閾値判断で誤検出があり得る。「この可能性があります」のトーンを基本にする。シグナル単体で結論せず、複数シグナルが揃ったときに「可能性」として提案
- **レポートはファイルに書き出し**、画面には TL;DR + TOP3 + パスのみ表示する
