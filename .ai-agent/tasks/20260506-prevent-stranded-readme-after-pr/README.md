# PR 作成後の未 push README 変更を残さないようにする

## 目的・ゴール

`autodev-start-new-task` スキルの「完了時」フローでは、`/autodev-create-pr` で PR を作成したあとに、得られた PR URL を task README の完了条件チェックに併記する慣例がある。
この PR URL 反映分が追加コミット + push されずブランチに残ってしまうケースが発生している（直近の `4def80d タスク README に PR URL を反映` がまさに別コミットでの後追い対応だった）。

スキル定義を改善し、PR 作成後の README 反映 → 追加コミット + push までを必ず実行させ、ブランチに未 push の変更が残らない状態でタスクを完了できるようにする。

## 実装方針

`.claude/skills/autodev-start-new-task/skill.md`（dogfood 用）と `plugins/autodev/skills/autodev-init/templates/skills/autodev-start-new-task/SKILL.md`（配布テンプレート）の「完了時」セクションを次のように書き換える。

1. 完了条件のうち PR 作成項目はまだチェックしない（PR URL 未確定のため）。それ以外の完了条件と作業ログを README に記載。
2. `/autodev-create-pr` を呼び、ここまでの変更（実装 + README）をコミット + push + PR 作成。返却された PR URL を控える。
3. PR URL を README の完了条件「PR を作成」項目に併記する形で反映（例: `- [x] PR を作成（\`/autodev-create-pr\`） → <PR URL>`）。
4. **追加コミット + push を必ず行う**（このステップを省略するとブランチに未 push 変更が残ったまま完了することになる、と明記）。
5. `git status` でクリーン状態を確認。
6. ユーザーに PR URL 付きで完了報告。

両ファイル間の文面はテンプレートと dogfood 版で揃え、`scripts/validate-skills.py` を実行してフロントマター検証を通す。

## 完了条件

- [x] `.claude/skills/autodev-start-new-task/skill.md` の「完了時」セクションを更新
- [x] `plugins/autodev/skills/autodev-init/templates/skills/autodev-start-new-task/SKILL.md` の「完了時」セクションを更新（同等の文面）
- [x] `python3 scripts/validate-skills.py` が成功する
- [ ] PR を作成（`/autodev-create-pr`）

## 作業ログ

### 2026-05-06: 完了時フローの再構成

- 観測: 直近の `4def80d タスク README に PR URL を反映` が、まさに今回の問題（PR 作成後の README 反映分が別コミットになる）への後追い対応だった
- 原因の見立て: 旧「完了時」セクションが「README 更新 → PR 作成」の 2 ステップだけで、PR 作成後に PR URL を README へ反映する流れが暗黙化していた
- 改善: 完了時を 6 ステップの番号付き手順に再構成
  1. README に完了条件・作業ログを記載（PR 作成項目はまだチェックしない、PR URL 未確定のため）
  2. `/autodev-create-pr` で PR 作成（コミット + push + PR URL 取得）
  3. PR URL を README に反映（PR 作成チェック行に併記）
  4. 追加コミット + push（**省略しない**ことを強調）
  5. `git status` でブランチがクリーンか確認
  6. PR URL を含めてユーザーへ完了報告
- 反映先 2 ファイル:
  - `.claude/skills/autodev-start-new-task/skill.md`（dogfood 版）
  - `plugins/autodev/skills/autodev-init/templates/skills/autodev-start-new-task/SKILL.md`（配布テンプレート）
- 文面はテンプレートと dogfood 版で揃えた
- `python3 scripts/validate-skills.py` 実行: 23 ファイル / 0 エラー
