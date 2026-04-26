---
description: Analyze recent Claude Code transcripts and suggest improvements to the user's prompts, skill definitions, memory entries, and context management. Use when the user asks for feedback on prompts/skills, says interactions feel inefficient, suspects context rot, notices skills not triggering, or wants to optimize token usage based on actual usage history.
allowed-tools: Bash, Read, Glob, Grep, WebFetch
---

# agent-coach

## 概要

ユーザーの Claude Code 利用履歴（transcript JSONL）を分析し、5 つの観点から改善提案を行うスキル。runtime に Claude が transcript を直接読み、Anthropic 公式のプロンプトエンジニアリング／スキル設計のベストプラクティスに照らして報告する。前処理スクリプトは持たない（Claude の判断で柔軟に分析する）。

5 観点:

1. **トークン消費 hot spot** — どこでトークンを使っているか
2. **方向修正多発プロンプト** — ユーザーが何度も修正しているプロンプト
3. **指示違反** — スキル/メモリの指示が守られていないケース
4. **コンテキストロット** — 履歴肥大による劣化のシグナル
5. **スキル未活用** — 使われるべきスキルが triggering されていないケース

## 前提条件

- macOS / Linux 環境（transcript パスは `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`）
- 分析対象セッションが少なくとも 1 件存在すること
- WebFetch が許可されていること（Anthropic 公式ドキュメント参照のため）

## 手順

### 1. 分析対象の決定

ユーザーから対象指定があれば従う。指定がなければ以下のデフォルトで進める:

- **対象プロジェクト**: 現在の cwd を `/` → `-` 変換した `~/.claude/projects/-Users-...-<repo>/` ディレクトリ
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

### 3. 5 観点の分析

各 jsonl ファイルを Read で読み込む（大きい場合は `Bash` で `python3 -c` を組み立てて集計しても良い。ただし複雑な前処理は避け、Claude の判断で重要箇所を抽出する）。

#### 観点 1: トークン消費 hot spot

集計内容:

- セッション全体の input/output/cache の合計
- `iterations` 単位で `cache_creation_input_tokens` が大きい assistant ターンの上位 5 件
- ツール結果が肥大しているターン（直前の `tool_use` の名前 + 直後の `tool_result` の文字数で推定）

**改善提案の方向性:**

- 巨大ファイルの全文 Read → `offset/limit` または Grep への置換
- 同じ Bash コマンドの繰り返し → 1 回の集約コマンドへ
- サブエージェント未活用な調査 → Explore / general-purpose agent への委譲
- 5 分以上空いた連続ターン → cache miss の可能性、ScheduleWakeup 設計の見直し

#### 観点 2: 方向修正多発プロンプト

検出シグナル（ユーザーメッセージ中）:

- 否定・修正語: `no`, `not that`, `instead`, `actually`, `stop`, `wait`, `違う`, `そうじゃなくて`, `やめて`, `いや`
- 同一アシスタントターンへの即時返信で短いユーザーメッセージ（< 50 文字）
- 同じトピックでユーザーが 3 ターン以内に再指示を出している

検出後、**元のユーザープロンプト**（修正前のもの）を特定し、なぜ Claude が誤解したかを分析する。

**改善提案の方向性:**

- Anthropic Prompt engineering ガイドの該当原則に沿って書き換え案を提示
  - 参照: <https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview>
  - 主要原則: Be clear and direct / Use examples / Give Claude a role / XML タグで構造化 / chain-of-thought
- 曖昧な指示語（"いい感じに", "適切に"）の具体化
- 期待する出力形式・粒度の明示

報告では「元プロンプト」「Claude の解釈」「ユーザーの修正」「改善案」をセットで示す。

#### 観点 3: 指示違反（スキル/メモリ）

対象:

- プロジェクトの `CLAUDE.md`, `.claude/skills/*/SKILL.md`, `.claude/skills/*/skill.md`
- ユーザーの `~/.claude/CLAUDE.md`, `~/.claude/projects/.../memory/*.md`（存在すれば）
- 当該セッション中の `<system-reminder>` で配布された skill 定義

これらに記載されたルール（"必ず X する", "Y してはいけない"）と、transcript 中の Claude の行動を突き合わせ、違反事例を抽出する。

**改善提案の方向性:**

- ルールが曖昧 → 具体例・反例を追加
- ルールが埋もれている → 配置場所の見直し（CLAUDE.md の冒頭へ移動、専用 memory ファイル化）
- ルールに `why` が無い → 「**Why:**」「**How to apply:**」セクションを追加（`auto memory` 仕様準拠）
- skill description が triggering ロジックを含んでいない → "Use when ..." を追加

#### 観点 4: コンテキストロット

検出シグナル:

- 1 セッションのターン数が 50 を超える
- 後半で初期指示・初期ファイルへの参照が消失する（同じファイルを Read し直す等）
- 同じツール（特に Read / Bash の `ls`）が同一引数で繰り返される
- 巨大な tool_result（> 5000 文字）が複数ターン間隔で何度も入る

**改善提案の方向性:**

- 長期タスクは `Plan` モードで方針確定 → 実行ターンを短く保つ
- 調査は `Agent(subagent_type=Explore)` に委譲してメインコンテキストを汚さない
- 区切りが付いたら `/clear` または `/compact` で明示的にリセット
- 長期記憶は `MEMORY.md` 経由の memory ファイル化（auto memory 仕様）

#### 観点 5: スキル未活用

手順:

1. 当該セッション内で配布された利用可能スキル一覧を `<system-reminder>` から抽出（`The following skills are available for use with the Skill tool:` の節を grep）
2. ユーザーの各リクエストについて、本来トリガすべきスキル候補を判定
3. 実際に `Skill` ツールが呼ばれたかを確認
4. 未起動だったケースを抽出

**改善提案の方向性:**

- スキルの `description` フロントマターに「Use when ...」のトリガ条件が不足 → 追加案を提示
- description が抽象的 → 具体的キーワード・シナリオを追加
- 似た description のスキルが競合 → 区別を明示
- skill-creator の triggering 最適化を案内

### 4. レポート生成

以下の構造で出力する（Markdown）:

```markdown
# Agent Coach レポート

対象: <セッションID 一覧 / 期間>

## サマリ
- 合計トークン消費: input N / output M / cache_read K
- 観点別 finding 数: hot spot N件 / 方向修正 N件 / 指示違反 N件 / コンテキストロット N件 / スキル未活用 N件

## 1. トークン消費 hot spot
（上位 N 件、ターン番号と内訳、改善提案）

## 2. 方向修正多発プロンプト
（事例ごとに 元プロンプト / 解釈 / 修正 / 改善案）

## 3. 指示違反
（違反したルール / 違反箇所 / 改善案）

## 4. コンテキストロット
（シグナル / 該当ターン / 改善案）

## 5. スキル未活用
（リクエスト / 本来トリガすべきスキル / description 改善案）

## 推奨アクション TOP3
（最も影響の大きい改善 3 つを優先順位付き）
```

長くなる場合は重大度の高い 3〜5 項目に絞る。冗長な引用は避け、ターン番号・行番号で参照する。

### 5. ベストプラクティス参照

提案の根拠を強化したい場合に、以下を WebFetch して該当原則を抽出する（必須ではない。レポートが生煮えと感じた場合のみ）:

- Prompt engineering: <https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview>
- Claude Code skills: <https://code.claude.com/docs/en/skills>
- Memory tool: <https://docs.anthropic.com/en/docs/build-with-claude/memory>

参照したらレポートに引用元を付記する。

## 注意事項

- **transcript には機密情報が含まれる可能性がある**。レポートに API キーや個人情報が紛れ込まないよう、引用は最小限に。秘匿シグナル（`sk-`, `Bearer `, `password=` 等）を見つけたらマスクする
- **自分自身のセッションを分析しないこと**（ユーザー明示対象時を除く）。Claude が自身の sessionId を直接取得する手段はないので、mtime 最新の jsonl を実行中セッションとみなして除外する
- **巨大 JSONL の全文 Read を避ける**。1 ファイル 1MB を超える場合は `Bash` で `wc -l` → 必要箇所のみ `sed -n` で抽出、または python での集計を併用する
- **改善提案は具体的に**。「もう少し明確に書いてください」ではなく、書き換え後のプロンプト例まで提示する
- **断定を避ける**。トークン消費・コンテキストロットは閾値判断で誤検出があり得る。「この可能性があります」のトーンを基本にする
