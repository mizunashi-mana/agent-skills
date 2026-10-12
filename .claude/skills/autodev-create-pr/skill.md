---
description: Create a GitHub pull request following this project's conventions (PR template path, body language, branch policy), or update the body of the branch's existing PR. ALWAYS invoke this skill before running `gh pr create` — do NOT bypass it with the generic PR creation flow built into Claude Code. Use whenever changes on a feature branch are ready for review and you want to open a PR.
allowed-tools: Read, Glob, "Bash(git status *)", "Bash(git log *)", "Bash(git diff *)", "Bash(git push *)", "Bash(git branch --show-current)", "Bash(gh pr list *)", "Bash(gh pr view *)", "Bash(gh pr create *)", "Bash(gh pr edit *)"
---

# PR の作成

今のブランチから PR を作る。

## 1. 状態の確認

- `git branch --show-current` が `main` なら止めて、ユーザーに伝える。
- `git status` で未コミットの変更が無いかを確かめる。あればコミットするかを聞く。
- `gh pr list --head <ブランチ> --json number,url` で、既に PR があるかを確かめる。あれば手順 2 でプッシュした後、作成の代わりに本文の更新（`gh pr edit <番号> --body-file -`）だけを行う。
- `git log main..HEAD --oneline` と `git diff main...HEAD --stat` で、入る変更をつかむ。

## 2. プッシュ

`git push -u origin <ブランチ>`

## 3. 作成

- `.github/PULL_REQUEST_TEMPLATE.md` があれば、本文はそれに沿って書く。
- タイトルは日本語で簡潔に（50 文字以内を目安）
- 本文はヒアドキュメントで渡す（改行が `\n` のまま残らないように）。

```bash
gh pr create --title "<タイトル>" --body-file - <<'BODY'
## 目的

何をなぜ変えるか。

## 変更

- 主な変更

## 確かめたこと

- 走らせた lint・テストと結果。確かめられなかったことも書く
BODY
```

## 4. 確認と報告

- `gh pr view <番号> --json title,body` で、本文が崩れていないかを確かめる。崩れていたら `gh pr edit <番号> --body-file -` で直す。
- PR の URL をユーザーに伝える。
