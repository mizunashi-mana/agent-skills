# PR #{PR_NUMBER} のレビュー

あなたは PR #{PR_NUMBER} の reviewer です。コードを読んでレビューし、GitHub のレビューとして投稿してください。ファイルの修正やコミットはしないでください。

## 手順

### 1. 前提を読む

- `.ai-agent/steering/tech.md`: 技術スタック・規約
- `.ai-agent/steering/plan.md`: 計画（無ければ飛ばす）
- `.ai-agent/structure.md`: ディレクトリ構成
- 変更に関係するなら `.ai-agent/steering/product.md` も読む

### 2. PR を読む

- `gh pr view {PR_NUMBER} --json title,body,baseRefName,headRefName,files`
- `gh pr diff {PR_NUMBER}`
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

### 5. 投稿する

- Critical があれば `REQUEST_CHANGES`、Warning か Info だけなら `COMMENT`、指摘が無ければ `APPROVE`。
- 自分が作成者の PR には `APPROVE` と `REQUEST_CHANGES` を付けられない。`gh pr view {PR_NUMBER} --json author -q .author.login` と `gh api user -q .login` が同じなら自分の PR なので、そのときは `COMMENT` にする。
- 自分の PR かどうかに関わらず、総評の先頭に `推奨アクション: <APPROVE / REQUEST_CHANGES / COMMENT>` と `Critical N 件 / Warning N 件 / Info N 件` を書く。`/autodev-merge-and-switch` がこの 2 行でマージしてよいかを判断する。
- Critical と Warning は行コメントにし、Info は総評にまとめる。

```bash
gh api -X POST "repos/{owner}/{repo}/pulls/{PR_NUMBER}/reviews" --input - <<'JSON'
{
  "event": "COMMENT",
  "body": "推奨アクション: COMMENT\nCritical 0 件 / Warning 1 件 / Info 0 件\n\n総評",
  "comments": [
    { "path": "src/foo.ts", "line": 42, "side": "RIGHT", "body": "**Critical**: ..." }
  ]
}
JSON
```

- 行コメントの `line` は差分に含まれる行にする。範囲なら `start_line` を添える。
- 投稿に失敗したら、行コメントを総評に移して投稿し直す。

### 6. 返す

次の形で結果を返して終える。

```
## レビュー結果

推奨アクション: APPROVE / REQUEST_CHANGES / COMMENT
投稿: <レビューの URL>

### Critical (N 件)
1. `path:line` 問題と直し方

### Warning (N 件)

### Info (N 件)

### 総評
```
