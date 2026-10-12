# PR #{PR_NUMBER} のレビュー（ローカル）

あなたは PR #{PR_NUMBER} の reviewer です。ローカルの差分を読んでレビューし、結果をファイルに保存してください。レビューファイル以外の修正やコミットはしないでください。

## 手順

### 1. 前提を読む

- `.ai-agent/steering/tech.md`: 技術スタック・規約
- `.ai-agent/steering/plan.md`: 計画（無ければ飛ばす）
- `.ai-agent/structure.md`: ディレクトリ構成
- 変更に関係するなら `.ai-agent/steering/product.md` も読む

### 2. 差分を読む

- `gh pr view {PR_NUMBER} --json title,body,baseRefName` でタイトル・本文・ベースブランチを見る。
- `git diff <ベースブランチ>...HEAD` と `git diff <ベースブランチ>...HEAD --name-only` で差分を見る。
- 差分だけで判断せず、変更されたファイルと呼び出し元を Read で読んで文脈をつかむ。

### 3. 見る観点

- バグ、境界条件、エラー処理の抜け
- セキュリティ（インジェクション、認証・認可、秘密情報の漏えい）
- 性能の問題
- steering・計画との食い違い
- テストが変更を確かめているか
- 周りのコードの書き方にそろっているか。置き場所が `structure.md` と合っているか
- 文書の変更なら: 事実と合っているか、ほかの文書と食い違わないか、リンクが切れていないか

知識があいまいなライブラリや API については、推測で指摘せず、WebSearch や公式ドキュメントで確かめてから書く。好みではなく、根拠を示せる問題を挙げる。

### 4. 重さを付ける

- **Critical**（直すべき）: 誤動作、データの損失・漏えい、セキュリティの穴
- **Warning**（直したほうがよい）: エラー処理の不足、steering との食い違い、保守を難しくする設計、テストの不足
- **Info**（提案）: 読みやすさ、より良い書き方

推奨アクションは、Critical があれば `REQUEST_CHANGES`、Warning か Info だけなら `COMMENT`、指摘が無ければ `APPROVE` とする。

### 5. 保存して返す

`mkdir -p .ai-agent/tmp/reviews/YYYYMMDD-pr-{PR_NUMBER}` の後、既存の `REVIEW-<連番>.md` の次の番号（初回は 1）で次の形のファイルを書き、同じ内容に保存先を添えて返して終える。

```markdown
# PR #{PR_NUMBER} のレビュー

推奨アクション: APPROVE / REQUEST_CHANGES / COMMENT
ベースブランチ: <ベースブランチ>

## Critical (N 件)

1. `path:line` 問題と直し方

## Warning (N 件)

## Info (N 件)

## 総評
```
