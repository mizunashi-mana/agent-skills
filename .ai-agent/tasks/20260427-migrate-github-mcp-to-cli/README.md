# GitHub MCP から gh CLI への置換

## 目的・ゴール

各スキルで使用している GitHub MCP ツール (`mcp__github__*`) を `gh` CLI 呼び出しに置き換える。

これにより、スキルの動作前提から GitHub MCP サーバーのインストールを取り除き、`gh` CLI さえあれば動作する状態にする。

> **メモ**: ユーザーの当初依頼には `playwright-mcp -> playwright CLI` も含まれていたが、現状のリポジトリには playwright-mcp を使っているスキルがないため、本タスクでは GitHub MCP の置換のみを扱う。

## 対象スコープ

### `plugins/autodev/skills/autodev-init/templates/skills/`（公開テンプレート）

- `autodev-create-issue/SKILL.md`
- `autodev-create-pr/SKILL.md`
- `autodev-import-review-suggestions/SKILL.md`
- `autodev-import-review-suggestions/SKILL.local.md`
- `autodev-review-pr/reviewer-spawn-prompt.md`
- `autodev-switch-to-default/SKILL.md`

### `plugins/merge-dependabot-bump-pr/skills/merge-dependabot-bump-pr/`

- `SKILL.md`

### `.claude/skills/`（リポジトリ内開発用ミラー）

- 上記と同じスキル群

## 置換マッピング

| MCP ツール | gh CLI 置換 |
| ---------- | ----------- |
| `mcp__github__issue_write` (create) | `gh issue create --title <title> --body <body> --label <l1,l2>` |
| `mcp__github__create_pull_request` | `gh pr create --title <title> --body <body> --base <base>` |
| `mcp__github__update_pull_request` | `gh pr edit <number> --title <title> --body <body>` |
| `mcp__github__pull_request_read` (get) | `gh pr view <number> --json ...` |
| `mcp__github__pull_request_read` (get_diff) | `gh pr diff <number>` |
| `mcp__github__pull_request_read` (get_review_comments) | `gh api repos/{owner}/{repo}/pulls/{n}/comments` (＋ 必要なら `--paginate`) |
| `mcp__github__add_reply_to_pull_request_comment` | `gh api -X POST repos/{owner}/{repo}/pulls/{n}/comments/{id}/replies -f body=...` |
| `mcp__github__pull_request_review_write` (create pending) | `gh api -X POST repos/{owner}/{repo}/pulls/{n}/reviews -f body=...`（event 省略で pending） |
| `mcp__github__add_comment_to_pending_review` | pending review 作成時に `comments[]` 配列で送信、もしくは個別に追加 |
| `mcp__github__pull_request_review_write` (submit_pending) | `gh api -X POST repos/{owner}/{repo}/pulls/{n}/reviews/{review_id}/events -f event=APPROVE\|REQUEST_CHANGES\|COMMENT -f body=...` |
| `mcp__github__merge_pull_request` | `gh pr merge <number> --merge` |
| `mcp__github__list_pull_requests` | `gh pr list --json ...` |
| `mcp__github__get_latest_release` | `gh release view --json ...` |
| `mcp__github__get_release_by_tag` | `gh release view <tag> --json ...` |
| `mcp__github__search_issues` | `gh search issues --repo {owner}/{repo} <query> --json ...` |
| `mcp__github__get_file_contents` | `gh api repos/{owner}/{repo}/contents/{path}?ref={ref}` |
| `mcp__github__list_commits` | `gh api repos/{owner}/{repo}/compare/{base}...{head}` または `gh api repos/{owner}/{repo}/commits` |

## 実装方針

1. 各スキルの本文（手順記述）から MCP ツール名・引数構造を gh CLI 相当に書き換える
2. フロントマターの `allowed-tools` から `mcp__github__*` を取り除き、必要な `Bash(gh ...)` 系を追加する
3. `gh api` の経路で送るリクエストは、複雑なペイロード（review コメント等）には `--input -` を使い JSON を標準入力で渡す書き方を採用する
4. `.claude/skills/` 配下の開発用コピーも同等の書き換えを行う
5. `scripts/validate-skills.py` で lint を通す
6. README / structure.md など外部参照ドキュメントに MCP 前提の記述があれば差分に合わせて更新する

## 完了条件

- [x] 上記スコープの全ファイルから `mcp__github__*` への参照が消えている
- [x] 各スキルの `allowed-tools` フロントマターに `gh` 系 Bash パターンが網羅されている
- [x] `python3 scripts/validate-skills.py` がエラーなしで通る（19 files, 0 errors）
- [x] `grep -r "mcp__github" plugins/ .claude/ template/` の結果が空
- [ ] 主要スキルの代表的な手順を 1 件、実コマンドで動作確認する（PR 作成・レビュー投稿の試運転は次回 PR レビューサイクルで実機確認する）
- [ ] PR を作成する

## 作業ログ

- 2026-04-27 タスク開始。トリアージで「単一 PR 完結タスク」と判定。playwright-mcp は対象スキルに未使用のため除外。
- 2026-04-27 6 スキル × (公開テンプレート + `.claude/skills/` ミラー) を gh CLI 系に書き換え。
  - `autodev-create-issue`: `mcp__github__issue_write` → `gh issue create --body-file -`
  - `autodev-create-pr`: `mcp__github__create_pull_request` / `update_pull_request` → `gh pr create --body-file -` / `gh pr edit --body-file -`
  - `autodev-import-review-suggestions`（SKILL.md / SKILL.local.md）: `pull_request_read` → `gh api repos/{owner}/{repo}/pulls/{n}/comments`（必要なら GraphQL `reviewThreads`）、`add_reply_to_pull_request_comment` → `gh api -X POST .../comments/{id}/replies`
  - `autodev-review-pr/reviewer-spawn-prompt.md`: pending review + コメント追加 + submit の 3 段階を、`gh api -X POST .../reviews` の 1 リクエスト（`event` + `comments[]`）に統合
  - `autodev-switch-to-default`: `merge_pull_request` → `gh pr merge --merge`
  - `merge-dependabot-bump-pr`: `list_pull_requests` / `pull_request_read` / `merge_pull_request` / `get_release_by_tag` / `get_latest_release` / `search_issues` / `list_commits` を `gh pr list --author "app/dependabot"` / `gh pr view` / `gh pr diff` / `gh pr merge` / `gh release view` / `gh search issues` / `gh api .../compare/{base}...{head}` に置換
- 2026-04-27 lint で `autodev-switch-to-default/SKILL.md` のフロントマターが先頭ダブルクォートで始まり YAML 解析失敗 → `allowed-tools` 値全体を単一引用符で囲んで scalar 化する形に修正。
- 2026-04-27 最終確認: `grep -r "mcp__github" plugins/ .claude/ template/` 空、`python3 scripts/validate-skills.py` 0 errors。
