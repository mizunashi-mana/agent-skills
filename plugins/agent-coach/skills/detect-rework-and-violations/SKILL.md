---
description: Analyze recent Claude Code transcripts to detect rework loops (direction corrections, redo cycles, post-completion supplements), instruction violations against project rules (CLAUDE.md, skill definitions, memory files, system reminders), and cross-session repeated additional instructions that the user keeps re-issuing every session. Then propose concrete remediation across six categories — prompt rewrites, rule wording improvements, Hook-based deterministic enforcement, rewind workflow advice, skill description fixes, and promotion of repeated user instructions to memory/CLAUDE.md/skill templates. The core goal is to minimize how often the user has to repeat the same additional instructions across sessions. Use when the user feels work needs frequent redoing, the model ignores established rules, the user keeps giving the same correction every session, you want to audit how often the model went off-track, or you need actionable rewrites for prompts and rules.
allowed-tools: Bash, Read, Write, Glob, Grep
---

# detect-rework-and-violations

## 概要

ユーザーの transcript JSONL を分析し、以下 3 種を検出する特化スキル:

1. **手戻り**（方向修正・差し戻し・**完了寸前の追加指示** post-completion supplement）
2. **指示違反候補**（CLAUDE.md / SKILL.md / memory / system reminder のルール違反。ただし**直前 slash command で許可された行動は除外**）
3. **クロスセッション反復追加指示**（複数セッションで繰り返し出ている同一の追加指示。**本スキルの主目的**「追加指示の最小化」の中心ターゲット）

最終ゴールは、ユーザーが**毎回同じ追加指示を出さなくて済むようにすること**。単発の手戻り・違反だけでなく「何度も繰り返される追加指示」を集約して memory / CLAUDE.md / skill template への昇格候補として提示する。

主因は 6 種に分類: 曖昧プロンプト / ルール埋没 / 検証なし完了 / トリガミス / コンテキストロット起因 / **反復指示**。改善は 6 カテゴリ: A プロンプト書き換え / B ルール明文化 / C Hook 化 / D 巻き戻し運用 / E skill description 改善 / **F 反復指示の昇格**。

なお rot 起因（履歴肥大による初期指示忘却）が根本原因の場合は、本スキルの B/C 改善より先にコンテキストロット側の対処（断点 / MEMORY 化 / Compact Instructions）を優先する。

## 前提条件

- macOS / Linux 環境（transcript パスは `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`）
- 分析対象セッションが 1 件以上（パターン抽出には 3 件以上推奨。1〜2 件のときは「単発の手戻り / 違反」報告にフォールバック）
- ルール抽出元として `<repo>/CLAUDE.md`・`~/.claude/CLAUDE.md`・memory ファイル・skill 定義が読めると精度が上がる

## 関連リソース

- `reference/implementation.md` — Python ヒアドキュメント実装の骨格と最小サンプル
- `reference/promotion-templates.md` — F カテゴリの memory ファイル / CLAUDE.md / skill template 修正の雛形

## 手順

### 1. 分析対象セッションの決定

- **対象プロジェクト**: 現在の cwd に対応する `~/.claude/projects/<encoded-cwd>/`
- **対象セッション**: そのディレクトリ配下の `*.jsonl` を mtime 降順で**最新 5〜10 件**
- **除外**: 実行中セッション（mtime 最新の 1 件）。ユーザー明示指定時は除外しない
- **件数調整**: ユーザー指定があれば従う

候補一覧（ファイル名 / mtime / サイズ / 概算ターン数）を簡潔に提示してから処理に進む。

#### 1.1 セッショントピックの抽出（**レポート読解性のため必須**）

セッション ID（UUID）だけ提示しても**読み手が中身を識別できない**ため、各セッションに「**何をしていたか**」を 1 行で添える。本スキルのレポート全体（事例リスト・反復指示クラスタ・統計サマリ）でこの topic を併記すること。

抽出ロジック（優先順位順、最初に見つかったものを採用）:

1. **`<command-name>/autodev-start-new-task</command-name>` または類似の topic-defining コマンド**（`/autodev-start-new-project`, `/autodev-start-new-survey`, `/autodev-discussion`, `/autodev-create-issue`, `/autodev-replan`, `/autodev-steering`, `/init`）の `<command-args>` 内容 → `「<args 抜粋 80 字>」`
2. **`<command-name>/autodev-create-pr</command-name>` または `/autodev-import-review-suggestions` / `/autodev-review-pr`** → `<command> (branch: <branch 名>)` （branch から topic を推測）
3. その他の `<command-name>`（`/detect-context-rot`, `/recommend-bash-allowlist`, `/security-review`, `/review` 等）→ コマンド名を topic とする
4. 自由入力の最初の user 発話（`Base directory for this skill:` で始まるテンプレ本文や `<bash-*>` / `<local-command-*>` で始まるブロックは除外）→ 冒頭 80 字

除外する noise 系コマンド: `/clear`, `/compact`, `/help`, `/rewind`, `/fast`（topic にならない）。これらは飛ばして次の候補を見る。

実装は `reference/implementation.md` の `extract_topic` を参照。

候補一覧の提示時にも topic を併記する:

```
session    branch                                  topic
b277cc6e   main                                    /autodev-start-new-task「recommend-bash-allowlist を実際に使用してみて評価」
301d1256   main                                    /autodev-start-new-task「agent-coach スキル自体は削除しましょう」
29734a5f   feature/add-bash-allowlist-...          /autodev-create-pr (branch: add-bash-allowlist-recommender-skill)
...
```

### 2. JSONL 構造（参照する主要フィールド）

| 場所 | 用途 |
| --- | --- |
| `type == "user"` の `message.content` | ユーザー入力（修正指示・元指示・否定語・命令キー） |
| `type == "assistant"` の `message.content[]` の `text` | Claude の応答テキスト（確認 / 完了宣言パターン） |
| `type == "assistant"` の `message.content[]` の `tool_use` | 実行された行動（違反判定の対象） |
| user message 内の `<system-reminder>` ブロック | session に注入された system prompt 由来ルール（最重要抽出元） |
| 各レコードの timestamp / 順序 | ターン番号、隣接性 |

**1 ファイル全文 Read は避ける**。1MB 超は `Bash` で `python3` ヒアドキュメントで集計する（`reference/implementation.md` 参照）。

### 3. ルールの構造化抽出

「ルール」とは `必ず X する` / `Y してはいけない` / `Use when ...` のような **assistant の行動を制約する記述**。違反検出の左辺。

#### 3.1 抽出元の優先順位

| 優先 | ファイル / 場所 | 役割 |
| --- | --- | --- |
| 1 | session JSONL の `<system-reminder>` ブロック内 `# claudeMd`、Bash tool 説明、Auto Mode 宣言 | system prompt 由来のルールが最も確実に抽出できる |
| 2 | `~/.claude/CLAUDE.md` | グローバル user 設定（コミット運用 / `--no-verify` 禁止 / emoji 禁止 / Read 優先など恒久ルール） |
| 3 | `<repo>/CLAUDE.md`、`<repo>/.claude/CLAUDE.md` | プロジェクト固有ルール |
| 4 | `~/.claude/projects/<encoded-cwd>/memory/*.md` | auto memory（feedback / project / user / reference） |
| 5 | `<repo>/.claude/skills/**/SKILL.md`、`plugins/*/skills/**/SKILL.md` | skill 個別の Use when / SKIP 条件、手順内の禁止条文 |

**1 を見ずに 2〜5 だけ見ると、Bash tool 説明由来の `cd <current-directory>` 禁止のような重要ルールを取り逃す**。

語彙パターン（日英混在）:

- 肯定: `必ず`, `しなければならない`, `MUST`, `IMPORTANT`, `Always`
- 否定: `してはいけない`, `禁止`, `NEVER`, `Never`, `Don't`, `避ける`
- 条件: `〜のとき`, `〜の場合`, `Use when`, `When ...`, `If ...`
- 区別: `〜と区別する`, `Distinct from`, `Not for`, `SKIP when`

各ルールを `(出典, 抜粋, 否定/肯定, 適用条件)` の組で保持。

#### 3.2 ユーザーが session 中に動的に与えたルール

「以後は X しないで」「次回からは Y を使って」と発話されたら、その時点以降の**新規ルール**として動的に追加する。

### 4. シグナル抽出

#### 4.1 手戻りシグナル

否定語 (a) だけでは穏やか・建設的口調のユーザー（特に日本語話者）の追加指示を取り逃す。**(b)〜(g) を必ず併用**:

- **(a) 否定・修正語**: `no`, `not that`, `instead`, `actually`, `stop`, `wait`, `revert`, `undo`, `違う`, `そうじゃなくて`, `やめて`, `いや`, `じゃなくて`, `戻して`, `元に戻して`, `やり直し`
- **(b) 短い即時返信**: 直前 assistant ターンへの即応で 50 文字未満（不満の即時表明）
- **(c) 同一トピック再指示**: 直近 3 ターン以内にユーザーが同じ対象を再度言及して別の指示
- **(d) 完了後の差し戻し**: 完了宣言の次の user 入力に否定・修正語が含まれる
- **(e) post-completion supplement（完了寸前の追加指示）**: assistant が**完了宣言・PR 作成・コミット・最終 Write/Edit** の直前直後に来るユーザー入力で、**否定語を含まないが追加要件を出している**もの。命令キー `してください` / `しましょう` / `お願い` / `含めて` / `に変更` / `please` / `also` などを含み、内容が「言語を変える」「もっと含める」「追加で X して」のような**増分追加指示**。**否定語が無いため (a) からは漏れるが、ユーザーの軌道修正コストとしては (a) と同等以上に重要**。クロスセッション分析（4.5）でこの (e) パターンが横断的に多いと、F カテゴリの主たる材料になる
- **(f) assistant の確認パターン**: assistant 応答に `Wait, you mean ...?` / `Did you mean ...?` / `Let me clarify ...` / `すみません、もう一度確認` 等
- **(g) `/rewind` / `Esc Esc`**: 巻き戻し操作の痕跡

各シグナル検出時、**直前の元プロンプト**を 1 つ前の `type == "user"` から特定し、紐付けて保持する。

#### 4.2 指示違反シグナル

3 で抽出したルール各 R について、当該セッションの assistant 行動を走査:

- ルールが「必ず X する」型 → 該当文脈で X が行われていない `tool_use` シーケンス
- ルールが「Y してはいけない」型 → 該当文脈で Y が `tool_use` または assistant text に出現
- skill description の Use when / SKIP when → 該当ユーザー入力時に当該 skill を呼ばずに別手段で対応

代表例:

| ルール | 違反シグナル |
| --- | --- |
| 「コミットは指示時のみ」 | ユーザー指示なしで `git commit` 実行 |
| 「`--no-verify` は使わない」 | `git commit --no-verify` / `--no-gpg-sign` の使用 |
| 「テスト追加・実行」 | 実装後に `pytest` / `npm test` を実行せず終了 |
| 「コメントは書かない」 | 新規コード追加で `//`, `#` コメント挿入 |
| 「README は要求時のみ」 | `*.md` の `Write` 新規作成（要求なし） |
| skill description Use when ... | 該当ケースで Skill ツール未呼び出し（generic 実装） |
| **template が「`/<other-skill>` を起動する」と指示している** | 該当文脈で `<command-name>/<other-skill></command-name>` も `Base directory for this skill: .../<other-skill>` も無く、generic 実装で代替している（**トリガミス + ルール埋没の複合違反**。例: `/autodev-start-new-task` が「PR は `/autodev-create-pr` を使用する」と指示しているのに直接 `git commit` + `gh pr create` を実行） |

##### 4.2.1 slash command コンテキストガード（**必須**）

ルール違反候補を確定する前に、**直前 N ターン以内（推奨 N = 20、または最後の `<command-name>` 出現以降）にユーザーが起動した slash command** を特定し、template 本文で当該アクションが許可・要求されていないかを確認する。許可されているなら違反扱いしない。

具体的には:

1. `type == "user"` の `message.content` で以下のいずれかを時系列で集める。直近のものを「現在のフレーム」とする:
   - `<command-name>/<name></command-name>` を含むレコード（slash command 起動の正規形）
   - **`Base directory for this skill: <path>/skills/<name>` を含むレコード**（slash command 起動時に template 本文と一緒に注入される自由貼付け版。`<command-name>` が無いので 1 のみだと取りこぼす）
2. 同 user message の text ブロック内 template 本文を読む。違反ルールに該当する行為が template 内で「実行する」と明示されていれば**許可済み**として違反候補から除外
3. `<command-args>` のユーザー追加要望も個別許可になっていないか確認
4. **直前ユーザー発話の明示指示**も確認: 違反ターン直前の user 発話が「コミットして」「PR にしましょう」「task README も含めて」のような該当アクションを直接要求しているなら、それも「ユーザー明示指示」として違反候補から除外する。命令キーマッチ（`コミット` / `PR` / `commit` / `push`）+ 動詞語尾（`して` / `しましょう` / `してください`）で判定

代表的な「slash command が許可している行動」:

| slash command | 許可される行動 |
| --- | --- |
| `/autodev-create-pr` | `git add` / `git commit` / `git push -u` / `gh pr create` |
| `/autodev-start-new-task` | `git checkout -b <task-name>`、タスクディレクトリ・README.md の `Write` |
| `/autodev-import-review-suggestions` | レビュー指摘に対するファイル `Edit` / `Write` |
| `/autodev-replan` / `/autodev-steering` | 該当ドキュメントの `Edit` / `Write` |
| `/autodev-switch-to-default` | `git checkout main` / `git pull` |

**4.2.1 を入れずに違反検出を回すと `/autodev-create-pr` 経由のコミットを毎回違反として誤報告する**（実測: 試用時に 14 件中 10 件が当該誤検出）。violation 候補ごとに「直前 slash command フレーム」と「template 内でのアクション許可有無」を 1 行で記録し、レポートの判定根拠に書き出す。

#### 4.3 3 点組の組み立て

各イベントを 1 レコードに:

```
{
  "kind": "rework" | "violation",
  "session": "<id>", "turn": <int>,
  "rule_or_signal": "<ルール文 or 修正語パターン>",
  "user_original": "<元プロンプト抜粋>",
  "claude_action": "<assistant の応答 / tool_use 要約>",
  "user_correction": "<修正プロンプト抜粋>",   // rework のみ
  "rule_source": "<出典>",                       // violation のみ
  "slash_command_frame": "<command-name or null>", // violation のみ
}
```

#### 4.4 誤検出を避ける条件

- 否定語が過去の話題への言及（"yesterday I said no to ..."）なら手戻りではない
- ルール文の「IMPORTANT」が一般的注意であって個別アクションを禁じていない場合は違反扱いにしない
- ユーザーが一旦容認した行動（assistant が確認 → ユーザー OK）後の方針変更は手戻りに数えない
- 計画的な「ステップ 2 として行います」を完了後の差し戻しと誤判定しない
- **slash command 経由で許可された行動**は違反扱いにしない（4.2.1 を必ず適用）
- **guarded read** (`cat <file> 2>/dev/null`、pipeline `|` の一部、heredoc delimiter、`< file` リダイレクトと組み合わせた `cat`) は「Read を使え」ルールの違反扱いにしない（`Read` はファイル不在時にエラー → `cat ... 2>/dev/null` は妥当な代替）
- `git status`, `git diff`, `git log`, `git rev-parse`, `gh pr view` のような **read-only 情報収集 Bash** はコミット系 slash command 配下でなくても違反扱いしない
- `Write` で新規 `*.md` を作っても、パスが `.ai-agent/tasks/`, `.ai-agent/projects/`, `.ai-agent/surveys/`, `.ai-agent/tmp/`, `<repo>/<skills-dir>/**/SKILL.md`, `<repo>/.ai-agent/tmp/**/report.md` 配下なら autodev / agent-coach 系 skill 由来の正当な作成として違反扱いしない

**断定を避ける**: ルール本文の解釈には幅があるため、複数シグナルが揃ったときに「違反候補」のトーンで提示する。レポートには必ず**判定根拠**（なぜ違反と見なしたか）と**反証材料**（誤検出の可能性）を 1 行ずつ添える。

#### 4.5 クロスセッション反復追加指示の集約（**本スキルの主目的**）

ユーザーが**毎回同じ追加指示を出している**ことを検出するのが本スキルの中心ロジック。手戻り 4.1.(e) の post-completion supplement や違反 4.2 が単発の事象だが、(e) の追加指示が**複数セッションで反復**しているなら、それは「skill / template / memory に組み込まれていない暗黙ルール」のシグナル。

##### 集約手順

1. **候補抽出**: 各セッションから「ユーザー実発話のうち 10〜300 文字、命令キーを含むもの」を集める。命令キー例:
   - 日本語: `してください`, `お願い`, `しないで`, `避けて`, `しましょう`, `ましょう`, `にして`, `に変えて`, `に直して`, `に変更`, `追加して`, `含めて`, `含めましょう`, `必ず`, `ではなく`
   - 英語: `please`, `don't`, `must`, `always`, `never`, `instead`, `also`, `make sure`, `prefer`
   - スラッシュコマンド起動 (`<command-name>`) や bash 入出力ブロック (`<bash-input>` / `<bash-stdout>` / `<local-command-*>`) は除外
2. **クラスタリング**（同セッション内のクラスタ化は除外）:
   - **substring n-gram 一致 (Jaccard)**: 文字 4-gram 集合を作って閾値 0.30 以上のペアをクラスタ化
   - **キーフレーズ一致**: 名詞・固有名詞らしい連続文字列（英数 + 日本語混在 3 文字以上）を抽出し、共通キーフレーズが 2 つ以上あるペアもクラスタ化
   - 例: `PRタイトルと本文を日本語にしましょう` と `PRタイトル、説明も日本語にしてください` は n-gram Jaccard が低くても、キーフレーズ `PRタイトル` + `日本語` の共通でクラスタ化
3. **絞り込み**: **2 セッション以上**で出現したクラスタのみを「反復追加指示」として採用
4. **トピック要約**: 各クラスタにトピック名を付ける（例: 「PR タイトル/本文を日本語に」「task README を PR に含める」）

クラスタごとに「**昇格先**」を決定する。詳細・雛形は `reference/promotion-templates.md` 参照。

10 セッション分析しても 2 セッション以上の反復クラスタが 0 件なら、**「クロスセッション反復追加指示は検出されなかった」と明示**してフォールバックする。

### 5. パターン化（主因分類）

| 主因 | シグナル | 代表的改善カテゴリ |
| --- | --- | --- |
| **曖昧プロンプト** | 元プロンプトに具体性が乏しい / Claude が `Wait, you mean ...?` を返した | A |
| **ルール埋没** | ルール出典が CLAUDE.md の中盤以降 / system reminder の長文末尾 / 違反が複数セッションで反復 | B |
| **検証なし完了** | 「完了」宣言の直後に差し戻し / テスト・動作確認の `tool_use` が無いまま finish | C または B |
| **トリガミス** | 該当 skill の Use when にマッチしているのに Skill 未呼び出しで generic 対応 | E + 必要なら B |
| **コンテキストロット起因** | 違反ターンが session 後半に集中 / 初期指示が消失している | D + コンテキストロット側の対処（断点 / MEMORY 化 / Compact Instructions）を優先 |
| **反復指示** | 4.5 のクラスタが複数セッション横断で見つかった / post-completion supplement が複数セッションで反復 | **F** |

#### セッション横断の傾向

- 同一ルールが複数セッションで違反 → ルール文言改善 + Hook 化が候補
- 同一プロンプトパターンで複数回手戻り → プロンプト雛形化 / skill 化候補
- 完了後差し戻しが頻発 → 完了ゲート Hook（Stop）を提案
- **同一の追加指示が複数セッションで反復** (4.5) → **F カテゴリを最優先で提案**。これが本スキルの主成果物

### 6. 改善提案カテゴリへのマッピング

検出した 3 点組とクラスタを以下 6 カテゴリに振り分け、**書き換え後の文面まで提示**する。「もっと明確に」だけで終わらせない。

#### A. プロンプト書き換え（曖昧 → 具体）

雛形:

```
[元] "認証直して"
[改善後] "src/auth/login.ts:42 の `if (user.email)` が falsy 値を見落としている。
         `if (user?.email != null)` に修正し、tests/auth.test.ts:120 の
         `it('rejects empty email')` をパスさせて確認。他のテストはそのまま。"
```

押さえるポイント: ファイルパス + 行番号で対象を一意化 / 期待挙動と検証方法を 1 行で / 触らない範囲を明示。

#### B. ルール明文化（埋没 → 上位配置・専用 memory ファイル）

雛形 1 — CLAUDE.md 冒頭への昇格:

```markdown
## IMPORTANT — must follow

- コミットは明示的指示時のみ。`git commit` を勝手に呼ばない。
  - **Why:** 過去にレビュー前のコミットで CI を汚した経緯があるため
  - **How to apply:** ユーザーが「コミットして」と言うまで `git status` 提示で止まる
```

雛形 2 — 専用 memory ファイル化（auto memory 仕様）:

```markdown
---
name: no-auto-commit
description: コミットはユーザー明示指示時のみ
type: feedback
---

`git commit` をユーザー指示なしで実行しない。

**Why:** 過去にレビュー前コミットで CI を汚し、revert 対応が発生した。
**How to apply:** ユーザーが「コミットして」と言うまで `git status` の提示で止まる。
```

#### C. Hook 化（決定論的強制）

ルール違反が **3 回以上反復**、または影響が大きいときに昇格提案する。CLAUDE.md は advisory、Hook は deterministic。

| 状況 | Hook 種別 | 例 |
| --- | --- | --- |
| 完了前のテスト未実行 | Stop | `scripts/require-tests-passed.sh` で exit 2 |
| 危険コマンド実行 | PreToolUse Safety Gate | `Bash` matcher + `git push --force` 等のブロック |
| `--no-verify` 使用 | PreToolUse | `Bash` matcher、`--no-verify` を含む command を exit 2 |
| リント違反 | PostToolUse Quality Loop | フォーマッタ自動実行 + 違反箇所を additionalContext に注入 |
| 同一ルール違反 N 回 | PostToolUse | 違反検出ごとに reminder 注入 |

```json
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "Bash", "hooks": [ { "type": "command", "command": "scripts/safety-gate.sh" } ] }
    ],
    "Stop": [
      { "hooks": [ { "type": "command", "command": "scripts/require-tests-passed.sh" } ] }
    ]
  }
}
```

#### D. 巻き戻し運用（補正ループの脱出）

補正が **2 回続いた**時点で、続けて修正するより `Esc Esc`（または `/rewind`）で巻き戻し → A の改善プロンプトで再開するほうが効率的。

レポートに含めるテンプレ:

> セッション `<id>` ターン N〜N+2 で同一トピックの補正が 3 回続いています。次回類似ケースは 2 回目で `Esc Esc` → 改善プロンプトで再開してください。
> 改善プロンプト雛形: 「<A で生成した具体プロンプト>」

#### E. skill description 改善（トリガミス）

トリガミス起因のとき、該当 skill の description フロントマターを書き換える:

```yaml
description: <既存の説明>. Use when <user-keyword-1>, <user-keyword-2>, or <pattern> — for example "<代表ユーザー入力>". Distinct from <other-skill>: this handles <specific-aspect>.
```

本スキルでは「違反として顕在化したケース」のみ E に分類し、description 抜粋 + 1 行の修正案にとどめる。description 自体の総点検は本スキルの範囲外。

#### F. 反復指示の昇格（**本スキルの主出力カテゴリ**）

4.5 のクラスタリングで「複数セッションで繰り返されている追加指示」が見つかったとき、以下のいずれかの昇格先に移して**今後は追加指示無しで効くようにする**ことを提案する:

- **F-1. memory ファイル化** (feedback type) — ユーザー個人の好み / プロジェクト固有の運用ルール
- **F-2. プロジェクト CLAUDE.md** — プロジェクト全体の運用ルール
- **F-3. slash command / skill template の修正** — 特定 skill の挙動補正（**最強。手順に組み込めば二度と追加指示が要らない**）
- **F-4. グローバル `~/.claude/CLAUDE.md`** — リポジトリ非依存な好み

雛形・実例・修正対象パスの選び方は `reference/promotion-templates.md` を参照。

提案時の注意:

- **必ず昇格先を 1 つだけ提案**（複数候補があれば優先順位を 1 行で説明）
- **証拠（セッション ID + ターン番号）** を最低 2 件添える。1 件しかない反復は F の対象外（A 系で扱う）
- **配布元 `plugins/<plugin>/skills/<skill>/SKILL.md` を修正する**こと（`.claude/skills/` の symlink だけ書き換えても他環境に伝わらない）

### 7. レポート生成

レポートは画面ダンプせずファイルに書き出す。**分析過程を知らない人が読んでも一人で判断できる**ことを念頭に書く:

- (a) 各 finding に **判定根拠**（なぜ違反/手戻り/反復指示と見なしたか）と **反証可能性**（誤検出の可能性が残るか）を 1〜2 行ずつ添える
- (b) TL;DR の主因内訳には**専門用語の 1 行注釈**を併記する（「rot 起因 = コンテキストロット起因。履歴肥大で初期指示が忘却された結果の違反」など）
- (c) 推奨アクションは「<何を> を <どこに> に追加 / 修正」と**具体的な対象パスまたは雛形 diff まで書く**

1. 出力ディレクトリ: **`.ai-agent/tmp/<YYYYMMDD>-rework-violations/`**（cwd 基準）。存在しなければ `mkdir -p`
2. レポート本文: `<出力ディレクトリ>/report.md` を `Write` で書き出す
3. 画面表示はファイルパス + 検出件数（rework: N / violation: M / 反復追加指示: K 種）+ 主因 TOP2 + 推奨アクション TOP3 のみ

#### レポート構造

````markdown
# Rework & Violation 検出レポート

対象: <セッション一覧 / 期間>
分析範囲: 最新 N セッション (<earliest> 〜 <latest>)
抽出ルール: <K> 件

## TL;DR

- 手戻り: <N> 件（うち post-completion supplement <p> 件）/ 指示違反候補: <M> 件（うち誤検出 <fp> / 真の違反 <real>）
- **クロスセッション反復追加指示: <K> 種**（合計 <O> 件、各 ≥2 セッションで反復）
- 主因内訳:
  - 曖昧プロンプト <a>（元プロンプトに具体性が乏しい）
  - ルール埋没 <b>（CLAUDE.md / reminder の長文末尾でルール見落とし）
  - 検証なし完了 <c>（テスト/動作確認なしの完了宣言からの差し戻し）
  - トリガミス <d>（Skill 未呼び出しで generic 対応）
  - コンテキストロット起因 <e>（履歴肥大で初期指示忘却）
  - **反復指示 <f>**（複数セッションで同じ追加指示が繰り返されている）
- 反復違反ルール TOP3 / 推奨アクション TOP3 は末尾

## セッション一覧（読解用）

| セッション | branch | topic（要約） |
| --- | --- | --- |
| `<id1>` | main | /autodev-start-new-task「<引数抜粋>」 |
| `<id2>` | feature/... | /autodev-create-pr (branch: ...) |
| ... | ... | ... |

## クロスセッション反復追加指示（**最重要 — 追加指示の最小化に直結**）

### 反復指示 1: 「<トピック名>」 (<出現セッション数> セッション / <件数>件)

**事例**:
| セッション | topic | ターン | 発話抜粋 |
| --- | --- | --- | --- |
| `<id1>` | <topic 要約> | N1 | "..." |
| `<id2>` | <topic 要約> | N2 | "..." |

**判定根拠**: 4.5 の n-gram + キーフレーズ一致でクラスタ化。共通キーフレーズ: <キー 1>, <キー 2>。
**反証可能性**: <例: 偶然似た文言だが文脈が違う / 単発タスク特有の文脈>
**昇格先 (F)**: <F-1 / F-2 / F-3 / F-4>
**推奨修正**:

```diff
<具体的な diff か memory ファイル雛形>
```

(反復指示が 0 件なら「クロスセッション反復追加指示は検出されませんでした」と明示)

## 手戻りパターン

### パターン 1: <名前 — 例: post-completion supplement> (<件数>件 / 主因: <...>)

**起きていること**:
- セッション `<id1>` (topic: <要約>) ターン N1: 元 "<元プロンプト>" → Claude は <要約> → ユーザー "<修正>"

**判定根拠**: <例: assistant が「PR 作成しました」直後にユーザーから「task README も含めて」が来た>
**反証可能性**: <例: 段階的計画の「次ステップ」を誤判定した可能性>

**改善案 (A)**:
```
[元] <元プロンプト>
[改善後] <具体プロンプト雛形>
```
**運用案 (D)**: 2 回目の補正で `Esc Esc` → 上記改善プロンプトで再開推奨

(最大 3 パターン)

## 指示違反パターン

### 違反 1: 「<ルール文>」 (<件数>件 / 出典: <...>)

| セッション | topic | ターン | tool_use 抜粋 | 直前 slash command | 判定 |
| --- | --- | --- | --- | --- | --- |
| `<id1>` | <要約> | N1 | <抜粋> | `<command-name>` または なし | 真の違反 / 誤検出（理由） |

**現状のルール文**: > <抜粋>
**判定根拠**: <例: tool_use Bash で `git commit -m ...`、ユーザーが「コミットして」と直前に指示していない>
**反証可能性**: <例: 直前 N ターン以内に /autodev-create-pr 起動があり template で commit 許可済みなら誤検出>
**主因**: <ルール埋没 / 検証なし完了 / rot 起因 / トリガミス / 反復指示>
**改善案 (B)**:
```markdown
<書き換え後の CLAUDE.md / memory ファイル雛形>
```
**Hook 化案 (C, 反復 3 回以上のみ)**:
```json
{ "hooks": { ... } }
```

(最大 3 違反。それ以上は「その他の違反」に圧縮)

## クロスセッション傾向

- 反復違反ルール: <ルール> が <n> セッションで違反 → B + C 推奨
- 反復手戻りパターン: <パターン> が <n> セッションで再現 → A の雛形プロンプトを CLAUDE.md に追加候補
- 完了宣言後差し戻し率: <X>%（rework 中の割合）→ Stop Hook 候補
- post-completion supplement の頻度: <Y> 件 / <N> セッション

## 統計サマリ

- セッション数 <N> / ターン総数 <合計>
- 手戻り件数 <rework_total>（うち post-completion supplement <p>）
- 指示違反候補件数 <violation_total>（うち誤検出 <fp> / 真の違反 <real>）
- 反復追加指示クラスタ数 <K>
- ルール抽出元: system reminder <s> / `~/.claude/CLAUDE.md` <g> / `<repo>/CLAUDE.md` <p> / memory <m> / SKILL.md <k>

## 誤検出の可能性

- 否定語含むユーザー入力でも、過去の話題引用なら手戻りではない
- ルール文が一般的注意であって個別アクションを禁じていない場合は違反ではない
- 段階的計画の「次ステップ」を完了後差し戻しと誤判定する可能性
- **slash command 経由で許可されたアクションを違反扱いした可能性**（4.2.1 の slash command コンテキストガードで除外したもの以外）
- guarded read (`cat ... 2>/dev/null` 等) を `cat` の不適切利用扱いした可能性
- rot 起因の違反は文面改善より先にコンテキストロット側の対処（断点 / MEMORY 化 / Compact Instructions）を優先

## 推奨アクション TOP3

1. **<アクション>** — <1 行 why と how>。対象パス `<具体的なファイル>`、変更概要 <1 行>
2. ...
3. ...
````

#### TOP3 の優先度

| Tier | 内容 |
| --- | --- |
| Tier 1（必ず TOP3） | **クロスセッション反復追加指示が 2 セッション以上で出ている** (F カテゴリ。本スキルの主目的) / 同一ルール違反が 3 回以上反復 / 危険コマンド系違反（`--no-verify`, `git push --force`, `rm -rf`） / 完了後差し戻しが 3 回以上 |
| Tier 2（影響大なら TOP3） | 補正ループ 2 回以上の単一パターン / 単一セッション違反 5 件以上 / トリガミス起因違反が複数セッションで反復 |
| Tier 3（運用改善） | 単発の手戻り / 軽微な文面違反 / SKIP 条件追加で済むもの |

判断基準: **書き換え + 1 アクションで複数の手戻り/違反/反復指示が解消できるもの**を上に。F の昇格は**ユーザー側の追加指示コストを永続的にゼロにする**ため Tier 1 として最優先で TOP3 に入れる。

#### finding が少ないとき

検出が 1〜2 件のときはパターン化せず**「気づいたこと」セクション 1 つ + TOP3** に圧縮。空でも構造を埋めるために finding を水増ししない。クロスセッション反復が 0 件のときも**観測事実として「検出されなかった」を残す**。

### 8. 実装ヒント

`Bash` で `python3` ヒアドキュメントで集計する。完全実装は不要 — Claude が transcript を読み取り、3 点組の組み立てとパターン化、クロスセッションクラスタリングができれば良い。骨格コード・最小サンプル・代替手段（手で目視 + Grep）は `reference/implementation.md` を参照。

## 注意事項

- **transcript には機密情報が含まれる可能性がある**。引用前に API キー / 認証ヘッダ / 環境変数ダンプ中の secret 等が混入していないか軽くチェックし、疑わしければマスクする
- **自分自身のセッションを分析しない**（ユーザー明示時を除く）。mtime 最新の jsonl を実行中とみなして除外
- **巨大 JSONL の全文 Read を避ける**。1MB 超は `python3` ヒアドキュメントで集計
- **ルール抽出は完全ではない**。違反判定は複数シグナルが揃ったときに「違反候補」のトーンで提示
- **誤検出条件を必ず併記**。「補正ループ確定」ではなく「補正ループ候補」が基本トーン
- **slash command コンテキストガード必須**（4.2.1）。これを省くと `/autodev-create-pr` 経由のコミット等を毎回違反として誤報告する
- **post-completion supplement (4.1.e) を見落とさない**。否定語を含まない追加指示は (a) からは漏れるが、ユーザーの軌道修正コストとしては最も高頻度。クロスセッション分析と組み合わせて F カテゴリの主材料にする
- **rot 起因の可能性に注意**: 違反が session 後半に集中、または初期 reminder のルールが消失している場合、本スキルの B/C 改善より先にコンテキストロット側の対処で根治する
- **改善提案は具体的に**: 書き換え後の文面 / Hook スニペット / 巻き戻し操作 / memory ファイル雛形 / skill template 修正 diff まで提示
- **Hook 化は慎重に**: CLAUDE.md の文面改善で十分なケースで Hook を提案すると運用が重くなる。3 回以上反復または影響が大きいケースに限定
- **F カテゴリの修正対象パスに注意**: `plugins/<plugin>/skills/<skill>/SKILL.md` （配布元）に入れる。`.claude/skills/` の symlink だけ書き換えても他環境に伝わらない
- **レポートはファイル書き出し**、画面には TL;DR + TOP3 + パスのみ表示
