---
description: Review a GitHub pull request using a reviewer subagent in a clean context and report the findings (review only, no fixes). Use when you want an unbiased code review without the current conversation's context influencing the review.
allowed-tools: Read, Glob, Grep, AskUserQuestion, Agent, "Bash(git branch --show-current)", "Bash(git status *)", "Bash(gh pr list *)", "Bash(gh pr view *)"
---

# PR レビュー

PR「$ARGUMENTS」を、クリーンなコンテキストの reviewer サブエージェントでレビューし、結果を報告します。このスキルはレビューのみを行い、指摘に基づく修正は行いません。

## 手順

### 1. 対象 PR の特定

- `$ARGUMENTS` が指定されている場合: その PR 番号または URL を使用
- `$ARGUMENTS` が空の場合:
  1. `git branch --show-current` で現在のブランチ名を取得
  2. `gh pr list --head <branch-name> --json number,url --limit 1` で該当ブランチの PR を検索
  3. PR が見つかった場合はその PR をレビュー対象とする
  4. PR が見つからない場合はユーザーに PR 番号の指定を求める

### 2. 未 push の変更がないか確認

- `git status` で未コミット・未 push の変更がないことを確認する
- 残っている場合は、レビュー対象の差分とローカルが乖離するため、先にコミット + push するかユーザーに確認する

### 3. Reviewer サブエージェントの起動

`.claude/skills/autodev-review-pr/reviewer-spawn-prompt.md` を読み込み、`{PR_NUMBER}` をレビュー対象の PR 番号に置換して prompt として使用する。

```
Agent({
  description: "Review PR #{PR番号}",
  prompt: "{reviewer-spawn-prompt.md の内容（{PR_NUMBER} を置換済み）}",
  subagent_type: "general-purpose",
  model: "opus"
})
```

reviewer は GitHub にレビューを投稿し、最終応答としてレビュー結果（指摘一覧・推奨アクション・投稿したレビューの ID）を返す。Agent ツールの返り値（バックグラウンド実行された場合は完了通知で届く最終報告）がそのままレビュー結果になるため、メッセージのやり取りやシャットダウン処理は不要。バックグラウンド実行の場合は、完了通知が届くまで結果を推測せずに待つ。

### 4. 結果報告

reviewer のレビュー結果を報告して終了する。報告には以下を含める:

- Critical / Warning / Info の各指摘（ファイル名・行番号・問題・修正案）
- 推奨アクション（自分の PR の場合、指摘が無くても COMMENT にフォールバックしている点に注意）
- 投稿したレビューの ID と URL

指摘の取り込み（修正・コミット・コメントへの返信）は呼び出し元が行う。`/autodev-start-new-task` から呼ばれた場合は、同スキルの「レビュー指摘の取り込み」手順で処理される。

## 注意事項

- reviewer は clean context で動作するため、現在の会話の文脈に影響されない公正なレビューが可能
- reviewer は steering docs（tech.md, structure.md 等）を自分で読み込んでレビューする
- 大きな PR でも reviewer が段階的にレビューする
- このスキルはファイルの修正・コミット・push を行わない
