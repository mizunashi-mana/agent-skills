---
description: Analyze recent Claude Code transcripts and suggest improvements to the user's prompts, skill definitions, memory entries, and context management. Use when the user asks for feedback on prompts/skills, says interactions feel inefficient, suspects context rot, notices skills not triggering, or wants to optimize token usage based on actual usage history.
allowed-tools: Bash, Read, Glob, Grep, WebFetch
---

# agent-coach

## 概要

ユーザーの Claude Code 利用履歴（transcript JSONL）を分析し、6 つの観点から改善提案を行うスキル。runtime に Claude が transcript を直接読み、Anthropic 公式ベストプラクティスとリポジトリ内サーベイに照らして報告する。前処理スクリプトは持たない（Claude の判断で柔軟に分析する）。

観点:

0. **シークレット流出**（重大度: Critical）— transcript に混入した認証情報の検出 → 即マスク + ローテーション警告
1. **トークン消費 hot spot** — どこでトークンを使っているか
2. **方向修正多発プロンプト** — ユーザーが何度も修正しているプロンプト
3. **指示違反** — スキル/メモリの指示が守られていないケース
4. **コンテキストロット** — 履歴肥大による劣化のシグナル
5. **スキル未活用** — 使われるべきスキルが triggering されていないケース

## 前提条件

- macOS / Linux 環境（transcript パスは `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`）
- 分析対象セッションが少なくとも 1 件存在すること
- （任意）WebFetch が利用できれば、Anthropic 公式ドキュメントを参照して提案の根拠を強化できる。利用不可でも分析自体は実施可能
- （任意）リポジトリに `.ai-agent/surveys/20260426-claude-code-best-practices/` が存在する場合は、最優先の根拠リファレンスとして参照する

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

**詳細根拠**: [05-failure-patterns-and-signals.md §5.4](../../../../.ai-agent/surveys/20260426-claude-code-best-practices/05-failure-patterns-and-signals.md#54-検出と提案の優先順位) / [06-coach-checklist.md Tier 1](../../../../.ai-agent/surveys/20260426-claude-code-best-practices/06-coach-checklist.md#観点横断-提案優先順位の決定)

#### 観点 1: トークン消費 hot spot

集計内容:

- セッション全体の input/output/cache の合計
- `iterations` 単位で `cache_creation_input_tokens` が大きい assistant ターンの上位 5 件
- ツール結果が肥大しているターン（直前の `tool_use` の名前 + 直後の `tool_result` の文字数で推定）
- システム reminder の MCP ツール定義文字数 / アクティブツール数（fabymetal の目安: 設定済み MCP 20〜30、有効化 10 以下、アクティブツール 80 以下）

**改善提案の方向性:**

- 巨大ファイルの全文 Read → `offset/limit` または Grep への置換
- 同じ Bash コマンドの繰り返し → 1 回の集約コマンドへ
- サブエージェント未活用な調査 → Explore / general-purpose agent への委譲
- 5 分以上空いた連続ターン → cache miss の可能性
  （prompt cache TTL = 5 分。`ScheduleWakeup` の `delaySeconds` は 270 秒以下に保つか、5 分以上待つなら 1200 秒以上にまとめて 1 回だけ cache miss にする設計が望ましい）
- アクティブ MCP / ツール過多 → `disabledMcpServers` で本セッション不要なものを切ることで定義トークンを節約

**詳細根拠**: [01-context-and-session.md §1.5](../../../../.ai-agent/surveys/20260426-claude-code-best-practices/01-context-and-session.md#15-トークン-hot-spot-の典型パターンと対策) / [06-coach-checklist.md 観点1](../../../../.ai-agent/surveys/20260426-claude-code-best-practices/06-coach-checklist.md#観点-1-トークン消費-hot-spot)

#### 観点 2: 方向修正多発プロンプト

検出シグナル（ユーザーメッセージ中）:

- 否定・修正語: `no`, `not that`, `instead`, `actually`, `stop`, `wait`, `違う`, `そうじゃなくて`, `やめて`, `いや`
- 同一アシスタントターンへの即時返信で短いユーザーメッセージ（< 50 文字）
- 同じトピックでユーザーが 3 ターン以内に再指示を出している
- Claude 側の応答に "Wait, you mean..." のような確認パターンが現れる

検出後、**元のユーザープロンプト**（修正前のもの）を特定し、なぜ Claude が誤解したかを分析する。

**改善提案の方向性:**

- Anthropic Prompt engineering ガイドの該当原則に沿って書き換え案を提示
  - 主要原則: Be clear and direct / Use examples / Give Claude a role / XML タグで構造化 / chain-of-thought
- 曖昧な指示語（"いい感じに", "適切に"）の具体化
- 期待する出力形式・粒度の明示

報告では「元プロンプト」「Claude の解釈」「ユーザーの修正」「改善案」をセットで示す。

**運用提案（必須）**: 補正が 2 回以上続いたパターンを検出したら、以下も併せて提案する:

> このタイプの補正が 2 回続いた時点で `Esc Esc`（または `/rewind`）で巻き戻し、上記の改善プロンプトで再開する方が効率的です。
>
> 公式 best practices: "After two failed corrections, `/clear` and write a better initial prompt incorporating what you learned."

**詳細根拠**: [02-prompt-design.md §2.6](../../../../.ai-agent/surveys/20260426-claude-code-best-practices/02-prompt-design.md#26-共通アンチパターンと書き換え案) / [06-coach-checklist.md 観点2](../../../../.ai-agent/surveys/20260426-claude-code-best-practices/06-coach-checklist.md#観点-2-方向修正多発プロンプト)

#### 観点 3: 指示違反（スキル/メモリ）

対象:

- プロジェクトの `CLAUDE.md`, `.claude/skills/*/SKILL.md`, `.claude/skills/*/skill.md`
- ユーザーの `~/.claude/CLAUDE.md`, `~/.claude/projects/.../memory/*.md`（存在すれば）
- 当該セッション中の `<system-reminder>` で配布された skill 定義

これらに記載されたルール（"必ず X する", "Y してはいけない"）と、transcript 中の Claude の行動を突き合わせ、違反事例を抽出する。

**改善提案の方向性（文面改善）:**

- ルールが曖昧 → 具体例・反例を追加
- ルールが埋もれている → 配置場所の見直し（CLAUDE.md の冒頭へ移動、専用 memory ファイル化）
- ルールに `why` が無い → 「**Why:**」「**How to apply:**」セクションを追加（`auto memory` 仕様準拠）
- skill description が triggering ロジックを含んでいない → "Use when ..." を追加

**ハーネス化の判断基準（重要）:**

文面改善（Why / How to apply / 配置変更）でも繰り返し違反される場合、または違反の影響が大きい場合は、文面ではなく **Hook で決定論的に強制** することを提案する。CLAUDE.md は advisory、Hook は deterministic（公式）。

| 状況 | 提案する Hook パターン |
| --- | --- |
| 同じルール違反が 3 回以上 | PreToolUse / PostToolUse Hook 化 |
| 「コミット前にテスト」のような完了ゲート系 | Stop Hook で未テスト時にブロック |
| 危険コマンド（`rm -rf`, `git push --force` 等）の実行検出 | PreToolUse Safety Gate |
| リンタ違反パターンが繰り返される | PostToolUse Quality Loop で自動注入 |

提案には Hook の最小スニペット例（`.claude/settings.json` の `hooks` フィールド形式）を含めると、ユーザーがすぐ実装できる。

**詳細根拠**: [03-extensions.md](../../../../.ai-agent/surveys/20260426-claude-code-best-practices/03-extensions.md) / [04-harness-engineering.md §4.4](../../../../.ai-agent/surveys/20260426-claude-code-best-practices/04-harness-engineering.md#44-hook-4-パターン再掲) / [06-coach-checklist.md 観点3](../../../../.ai-agent/surveys/20260426-claude-code-best-practices/06-coach-checklist.md#観点-3-指示違反claudemd--skill--memory)

#### 観点 4: コンテキストロット

量的目安:

- 1M モデルでも **30〜40 万トークン**付近から性能劣化が観測される（Thariq）
- 200K モデル（Opus 等）では実効上限が **70K 程度**に縮むケースもある（fabymetal）
- コンテキスト使用率 **60% 超**で次セッション化を検討（fabymetal）
- `/context` で常時可視化推奨

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

**詳細根拠**: [01-context-and-session.md §1.6](../../../../.ai-agent/surveys/20260426-claude-code-best-practices/01-context-and-session.md#16-コンテキストロットの典型シグナル) / [06-coach-checklist.md 観点4](../../../../.ai-agent/surveys/20260426-claude-code-best-practices/06-coach-checklist.md#観点-4-コンテキストロット)

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

**詳細根拠**: [03-extensions.md §3.3](../../../../.ai-agent/surveys/20260426-claude-code-best-practices/03-extensions.md#33-skill-の設計) / [06-coach-checklist.md 観点5](../../../../.ai-agent/surveys/20260426-claude-code-best-practices/06-coach-checklist.md#観点-5-スキル未活用)

### 4. レポート生成

各 finding について以下の項目を **必須** とする:

1. **重大度**: Critical / Warning / Info
2. **シグナル**: 具体的にターン番号 / 行番号 / ファイル参照
3. **根拠**: 公式 docs またはリポジトリ内サーベイへの引用 + リンク
4. **可能性の高い原因**
5. **改善案**: 具体的なプロンプト書き換え / 設定変更
6. **誤検出の可能性**: 「ただし、〜の場合は問題ありません」の脚注

レポート全体構造（Markdown）:

```markdown
# Agent Coach レポート

対象: <セッションID 一覧 / 期間>

## サマリ
- 合計トークン消費: input N / output M / cache_read K
- 観点別 finding 数: シークレット N件 / hot spot N件 / 方向修正 N件 / 指示違反 N件 / コンテキストロット N件 / スキル未活用 N件

## 0. シークレット流出
（finding ごとに 上記 6 項目。無ければ「該当なし」）

## 1. トークン消費 hot spot
（finding ごとに 6 項目）

## 2. 方向修正多発プロンプト
（事例ごとに 元プロンプト / 解釈 / 修正 / 改善案 + 6 項目）

## 3. 指示違反
（finding ごとに 6 項目 + 必要なら Hook 化提案）

## 4. コンテキストロット
（6 項目）

## 5. スキル未活用
（6 項目）

## 推奨アクション TOP3
（Tier 表に従って優先度をつける、後述）
```

#### 推奨アクション TOP3 の優先度ルール

以下の Tier に従って優先度をつける（上位が必ず TOP3 に入る）:

| Tier | 内容 |
| --- | --- |
| **Tier 1（必ず TOP3）** | シークレット流出 / 危険コマンド検出 / 同じミスが 3 回以上反復 |
| **Tier 2（影響大なら TOP3）** | 補正ループ（2 回以上） / 検証なしの「完了」宣言 / スキル未活用 3 件以上 |
| **Tier 3（運用改善）** | ターン数過多 / ファイル全文 Read / cache miss |

判断基準: **ユーザーがすぐに行動でき、複数セッションにわたって効果が継続するもの** を上に置く。

**詳細根拠**: [06-coach-checklist.md 観点横断: 提案優先順位の決定](../../../../.ai-agent/surveys/20260426-claude-code-best-practices/06-coach-checklist.md#観点横断-提案優先順位の決定)

長くなる場合は重大度の高い 3〜5 項目に絞る。冗長な引用は避け、ターン番号・行番号で参照する。

### 5. ベストプラクティス参照

提案の根拠は以下の優先順位で参照する:

1. **リポジトリ内サーベイ**（存在すれば最優先）: `.ai-agent/surveys/20260426-claude-code-best-practices/` 配下の各ファイル。観点別に整理済みで参照効率が高い
2. **公式ドキュメント**（必要なら WebFetch）:
   - Best practices: <https://code.claude.com/docs/en/best-practices>
   - Skills: <https://code.claude.com/docs/en/skills>
   - Hooks: <https://code.claude.com/docs/en/hooks>
   - Memory: <https://code.claude.com/docs/en/memory>
3. **コミュニティ記事**: サーベイ README に一次ソース一覧あり

参照したらレポートに引用元を付記する。

## 注意事項

- **transcript には機密情報が含まれる可能性がある**。観点 0 として独立検出 + マスク + ローテーション警告を必須とする
- **自分自身のセッションを分析しないこと**（ユーザー明示対象時を除く）。Claude が自身の sessionId を直接取得する手段はないので、mtime 最新の jsonl を実行中セッションとみなして除外する
- **巨大 JSONL の全文 Read を避ける**。1 ファイル 1MB を超える場合は `Bash` で `wc -l` → 必要箇所のみ `sed -n` で抽出、または python での集計を併用する
- **改善提案は具体的に**。「もう少し明確に書いてください」ではなく、書き換え後のプロンプト例まで提示する
- **断定を避ける**。トークン消費・コンテキストロットは閾値判断で誤検出があり得る。「この可能性があります」のトーンを基本にする。シグナル単体で結論せず、複数シグナルが揃ったときに「可能性」として提案
