# 反復指示の昇格テンプレ集（改善カテゴリ F）

クロスセッション反復追加指示を検出したとき、以下のいずれかの昇格先に書き出す。SKILL.md 本体の手順 6-F から参照される。

## F-1. memory ファイル化（feedback type）

ユーザー個人の好み / プロジェクト固有の運用ルールが session 横断で繰り返される場合、`~/.claude/projects/<encoded-cwd>/memory/<name>.md` に書き出す（プロジェクト依存ならこのパス、リポジトリ非依存なら `~/.claude/memory/`）。

雛形:

```markdown
---
name: <短い名前>
description: <一行説明>
type: feedback
---

<ルール本文>

**Why:** <反復している証拠（セッション ID とターン番号 2 件以上）>。
**How to apply:** <どの局面で何をするか / 何をしないか>。
```

実例（試用で見つかった反復指示「PR タイトル/本文を日本語に」を昇格する場合）:

```markdown
---
name: pr-language
description: PR タイトル・本文・コミットメッセージは日本語で書く（このリポジトリのプロジェクト言語）
type: feedback
---

このリポジトリでは PR タイトル / 本文 / コミットメッセージを日本語で書く。

**Why:** /autodev-create-pr 直後にユーザーが「日本語にしてください」と追加指示を入れた事例が複数セッションで観測された（例: 301d1256 t118 / 4203e1e9 t76）。
**How to apply:** /autodev-create-pr 実行時、CLAUDE.md / steering ドキュメントが日本語であることを確認し、日本語で本文を生成する。
```

## F-2. プロジェクト CLAUDE.md への昇格

プロジェクト全体の運用ルールであれば `<repo>/CLAUDE.md` の冒頭近くに「IMPORTANT — must follow」として追加。`B. ルール明文化` の雛形と同形式:

```markdown
# プロジェクト名

## IMPORTANT — must follow

- <ルール本文>
  - **Why:** <反復している証拠>
  - **How to apply:** <どこで効かせるか>
```

## F-3. slash command / skill template の修正

特定の slash command（`/autodev-create-pr` など）の挙動を補正する追加指示が反復している場合は、**skill 本体の手順に組み込む**のが最も効果的。advisory な memory より skill 内の手順のほうが decisive。

修正対象の決定:

1. ユーザー環境で動いている skill 実体は通常 `plugins/<plugin>/skills/<skill>/SKILL.md` （配布元）
2. 本リポジトリ内では `plugins/autodev/skills/autodev-init/templates/skills/<skill>/SKILL.md` （新規セットアップで展開されるテンプレート）も合わせて修正する
3. 該当 skill の手順本文に、反復指示の内容を**最初から含めた手順**として書き込む

実例（試用で見つかった反復指示「task README の更新も PR に含める」を昇格する場合）:

```diff
 # /autodev-create-pr 手順
 ...
 1. git status / git diff / git log で差分を把握
+   - 特に `.ai-agent/tasks/<task-name>/README.md` に未コミット変更があれば、本 PR に含める
+     （タスクの完了条件チェックや PR URL 反映を毎回ユーザーに追加指示させない）
 2. 差分から PR タイトル・本文を起こす
+   - PR タイトル・本文の言語は CLAUDE.md / steering ドキュメントの言語に合わせる
 3. ...
```

## F-4. グローバル `~/.claude/CLAUDE.md` への昇格

リポジトリ非依存な好み（出力スタイル、口調、tool 使用方針）は `~/.claude/CLAUDE.md` に追加。雛形は B と同形式だが Why に「複数リポジトリで反復」を書く。

## F カテゴリ提案時の注意

- **必ず昇格先を 1 つだけ提案**（複数候補があれば優先順位を 1 行で説明）。複数の昇格先が同時に提案されるとユーザーが選択コストを負う
- 反復指示の **証拠（セッション ID + ターン番号）** を最低 2 件添える。1 件しかない反復は F の対象ではなく単発の手戻り (A 系) で扱う
- **ユーザーの環境で実体が読み込まれるパスに修正を入れる**こと。本リポジトリで開発している skill は `plugins/<plugin>/skills/<skill>/SKILL.md` が配布元、ユーザー機ではマーケットプレイス経由のインストール先が実体。`.claude/skills/` の symlink は本リポジトリ自体の試用用なので、ここだけ書き換えても他環境には伝わらない

## 昇格先の選択基準

| 内容のタイプ | 昇格先 |
| --- | --- |
| プロジェクト固有の運用ルール（PR の言語、コミット粒度、ブランチ命名） | F-1 memory（projects 配下）または F-2 プロジェクト CLAUDE.md |
| ユーザー個人の好み（出力スタイル、口調、レポート形式） | F-1 memory（リポジトリ非依存）または F-4 グローバル CLAUDE.md |
| 特定 skill / slash command の挙動補正（PR 文面、タスク README 取り込み等） | **F-3 skill template の修正**（最強。手順に組み込めば二度と追加指示が要らない） |
| 単発タスク特有の文脈 | 昇格不要 |
