# bump PR のリリース経過日数の基準を 3 日に縮める

## 目的

`merge-dependabot-bump-pr` のリリース経過日数チェックを 7 日から 3 日に縮め、bump PR を早くマージできるようにする。

## 方針

- `plugins/merge-dependabot-bump-pr/skills/merge-dependabot-bump-pr/SKILL.md` の手順 5 で、「1週間以上」を「3日以上」に、判定の「7日以上 / 7日未満」を「3日以上 / 3日未満」に変える。
- `plugin.json` の version は、これまでの変更でも上げていないので据え置く。

## 完了条件

- [x] SKILL.md に 7 日・1 週間の記述が残っていない（grep で確認）
- [x] `python3 scripts/validate-skills.py` が通る
- [ ] レビューを取り込み CI が通った PR → <URL>

## 作業ログ

- 2026-11-03: 開始。SKILL.md の閾値を 3 日に変更し、grep と validate-skills.py で確認した。
