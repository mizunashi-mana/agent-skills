# bump PR のリリース経過日数の基準を 3 日に縮める

## 目的

`merge-dependabot-bump-pr` のリリース経過日数チェックを 7 日から 3 日に縮め、bump PR を早くマージできるようにする。

## 方針

- `plugins/merge-dependabot-bump-pr/skills/merge-dependabot-bump-pr/SKILL.md` の手順 5 で、「1週間以上」を「3日以上」に、判定の「7日以上 / 7日未満」を「3日以上 / 3日未満」に変える。
- `plugin.json` の version は、これまでの変更でも上げていないので据え置く。

## 完了条件

- [x] SKILL.md に 7 日・1 週間の記述が残っていない（grep で確認）
- [x] `python3 scripts/validate-skills.py` が通る
- [x] レビューを取り込み CI が通った PR → https://github.com/mizunashi-mana/agent-skills/pull/26

## 作業ログ

- 2026-11-03: 開始。SKILL.md の閾値を 3 日に変更し、grep と validate-skills.py で確認した。
- 2026-11-03: PR #26 を作成し、`/autodev-review-pr` でレビューした（Critical 0 / Warning 0 / Info 2）。
  - 取り込んだ指摘: Info 1。経過日数の数え方があいまいだったので、「24 時間単位で切り捨てた日数」と SKILL.md に明記した。
  - 取り込まなかった指摘: Info 2（3 日で十分とする根拠を残す）。依頼の意図は「bump PR を早くマージしたい」で、目的にすでに書いてある。それ以上の根拠は依頼に無く、推測で書くことになるため見送った。
