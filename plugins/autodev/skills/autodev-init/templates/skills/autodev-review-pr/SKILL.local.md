---
description: Review the current branch's changes locally with a reviewer subagent in a clean context, then apply the findings. Use when you want an unbiased code review without the current conversation's context influencing it, and want the review feedback addressed in the same flow.
allowed-tools: Read, Write, Edit, MultiEdit, Glob, Grep, AskUserQuestion, Agent, "Bash(git branch --show-current)", "Bash(git status *)", "Bash(git add *)", "Bash(git commit *)", "Bash(git push *)", "Bash(gh pr list *)", "Bash(gh pr view *)"
---

# ローカルレビュー

現在のブランチの変更を、クリーンなコンテキストの reviewer サブエージェントでローカルレビューし、指摘事項を取り込みます。

## 手順

### 1. 対象 PR の特定

- `$ARGUMENTS` が指定されている場合: その PR 番号を使用
- `$ARGUMENTS` が空の場合:
  1. `git branch --show-current` で現在のブランチ名を取得
  2. `gh pr list --head <branch-name> --json number --limit 1` で該当ブランチの PR 番号を検索
  3. PR が見つからない場合はユーザーに PR 番号の指定を求める

### 2. 未コミットの変更がないか確認

- `git status` で未コミットの変更がないことを確認する
- 残っている場合は、レビュー対象の差分に含まれないため、先にコミットするかユーザーに確認する

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

reviewer はレビュー結果を `.ai-agent/tmp/reviews/YYYYMMDD-pr-{PR番号}/REVIEW-{連番}.md` に保存し、最終応答としてレビュー結果（指摘一覧・推奨アクション・保存先パス）を返す。Agent ツールの返り値がそのままレビュー結果になるため、メッセージのやり取りやシャットダウン処理は不要。

### 4. 結果報告

reviewer のレビュー結果サマリーをユーザーに報告する。レビューファイルの保存先パスも伝える。

**推奨アクションが APPROVE で指摘が無い場合**: ここでタスク完了。

### 5. 各指摘の分類

Critical / Warning / Info の各指摘について、修正の要否を判断し、以下の形式で提示する:

```
**1. ファイル名:行番号 - 概要**
> 指摘内容の要約

→ **修正推奨/不要/要確認**: 理由

---
```

判断基準:

- **修正推奨**: バグ修正、セキュリティ改善、アクセシビリティ改善、明らかな UX 改善、テストカバレッジの拡充、プロジェクト規約違反の是正
- **修正不要（スキップ）**: ユーザーが明示的に決定した設計、プロジェクト方針と異なる提案、過剰な抽象化・将来対応の提案
- **要確認**: トレードオフがある変更、設計判断が必要な変更

### 6. 要確認の指摘のみユーザーに確認

- 「修正推奨」は確認なしで修正対象とする
- 「修正不要」は確認なしでスキップする
- 「要確認」の指摘がある場合のみ、`AskUserQuestion` で修正するかどうかをユーザーに確認する

### 7. 修正実行

- 修正対象の指摘を反映する
- 修正対象が 0 件の場合は手順 9 へ進む

### 8. コミット・プッシュ

- 修正内容をまとめてコミット
- PR ブランチにプッシュ

### 9. レビューファイルへの対応結果の追記

レビューファイル（手順 3 で reviewer が返した保存先）の末尾に、各指摘への対応結果を追記する:

```markdown
## 対応結果

- **1. ファイル名:行番号**: 修正済み — ○○を△△に変更
- **2. ファイル名:行番号**: スキップ — ○○の理由から現状維持
```

### 10. 完了報告

以下をユーザーに報告する:

- 推奨アクション
- 修正した指摘 / スキップした指摘（理由付き）の件数と要約
- 追加したコミット
- レビューファイルの保存先パス

## 注意事項

- reviewer は clean context で動作するため、現在の会話の文脈に影響されない公正なレビューが可能
- reviewer は steering docs（tech.md, structure.md 等）を自分で読み込んでレビューする
- 大きな PR でも reviewer が段階的にレビューする
- レビュー結果は `.ai-agent/tmp/reviews/YYYYMMDD-pr-{PR番号}/REVIEW-{連番}.md` に保存される
- このスキルが取り込むのは reviewer サブエージェントの指摘のみ。人間のレビュアーによるコメントは対象外
