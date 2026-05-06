# autodev-review-pr 完了後に import-review-suggestions を自動起動する

## 目的・ゴール

`/autodev-review-pr` のレビュー結果報告後、findings があった場合（推奨アクションが REQUEST_CHANGES または COMMENT のとき）に `/autodev-import-review-suggestions` を自動的に起動し、レビュー指摘の取り込みフローまでを 1 連の体験にする。

ただし、**指摘の自動修正はユーザー確認を経てから行う**。`autodev-import-review-suggestions` は既に手順 3 で「ユーザーの承認を得る」作りになっているため、その確認ステップを必ず通す形でチェーンする（autoamtic-apply にはしない）。

## 背景

現状の `autodev-review-pr` 手順 6 では:

> 推奨アクションが REQUEST_CHANGES または COMMENT の場合: reviewer をシャットダウンし、結果報告後にユーザーの判断を待つ。

となっており、ユーザーが手動で次のアクション（`/autodev-import-review-suggestions <PR番号>` 実行）を指示する必要がある。これを自動チェーンに置き換えることで、レビュー → 修正取り込みのフローをスムーズにする。

一方、自動修正は危険なので、`autodev-import-review-suggestions` 自身が持つ「修正前のユーザー確認」ステップを残す。チェーンは「次のスキルを起動する」までを自動化し、修正適用は対話的に行う。

## 実装方針

### 変更対象ファイル

1. `.claude/skills/autodev-review-pr/skill.md` — このリポジトリ自体で使う GitHub PR レビュー版
2. `plugins/autodev/skills/autodev-init/templates/skills/autodev-review-pr/SKILL.md` — テンプレート（GitHub PR 版）
3. `plugins/autodev/skills/autodev-init/templates/skills/autodev-review-pr/SKILL.local.md` — テンプレート（ローカルレビュー版）

`autodev-import-review-suggestions` 側は、既にユーザー承認ステップが存在するため変更不要の見込み。必要なら念のため「自動チェーン経由でも必ず承認を取る」旨を明記する。

### 変更内容

#### autodev-review-pr 側

- 手順 6 のフロー分岐を以下に変更:
  - **APPROVE の場合**: 現行通り、結果報告で完了。
  - **REQUEST_CHANGES / COMMENT の場合**: 結果報告 → 続けて `Skill(autodev-import-review-suggestions)` を起動する。引数として PR 番号を渡す。チェーン起動前に「指摘事項を取り込みますか？」と一言添える程度にし、import 側でユーザー承認を取る前提でそのまま起動する。
- 手順 7（結果報告）の後に新たな手順「8. 指摘事項の取り込み（findings がある場合）」を追加するか、手順 6/7 内に統合する。
- frontmatter `allowed-tools` に `Skill(autodev-import-review-suggestions)` を追記。

#### autodev-import-review-suggestions 側

- 既に手順 3 で「修正する項目をまとめて提示／ユーザーの承認を得る」とあるため、基本変更不要。
- 念のため、冒頭または注意事項に「`/autodev-review-pr` から自動起動された場合も、修正適用前に必ずユーザー確認を取る」旨を明記する（重複だが安全側に倒す）。

### ローカルレビュー版（SKILL.local.md）の扱い

ローカルレビューはレビュー結果をファイル（`.ai-agent/tmp/reviews/...`）に保存するだけで、PR コメントは投稿しない。
`autodev-import-review-suggestions/SKILL.local.md` は両ソース（ローカルファイル + PR コメント）を扱える設計のため、`autodev-review-pr/SKILL.local.md` 側からも同様に自動チェーンする。

## 完了条件

- [x] `.claude/skills/autodev-review-pr/skill.md` を更新
- [x] `plugins/.../autodev-review-pr/SKILL.md` を更新
- [x] `plugins/.../autodev-review-pr/SKILL.local.md` を更新
- [x] `import-review-suggestions` 側に「自動起動でも必ずユーザー確認」旨を明記（必要なら）
- [x] 各 frontmatter `allowed-tools` の整合性を確認（`Skill(autodev-import-review-suggestions)` の追加）
- [x] `scripts/validate-skills.py` を実行して frontmatter 検証を通す
- [x] `.ai-agent/structure.md` の更新が必要かチェック → 不要
- [ ] PR を作成（`/autodev-create-pr`）

## 作業ログ

- 2026-05-06: タスク開始。トリアージ結果「具体的な実装タスク」としてそのまま続行。
- 2026-05-06: 対象 6 ファイル（review-pr 系 3 ファイル + import-review-suggestions 系 3 ファイル）を更新。
  - review-pr: 手順 6/7 に findings がある場合の自動チェーンを追加し、`allowed-tools` に `Skill(autodev-import-review-suggestions)` を追記。
  - import-review-suggestions: 「自動起動経由でも必ずユーザー確認を取る」旨を冒頭注意書きとして追記。
- 2026-05-06: `scripts/validate-skills.py` 実行 → 全 23 ファイル OK。
- 2026-05-06: ブランチ `feature/chain-import-suggestions-after-review` でコミット作成。
