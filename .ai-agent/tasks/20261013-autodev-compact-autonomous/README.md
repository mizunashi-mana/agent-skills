# autodev スキルをより自律的・コンパクトにする

## 目的

別リポジトリで autodev スキルを改良して運用してきた知見を取り込み、autodev のワークフロースキルを、ユーザーへの確認を減らして最後まで自走でき、かつ短く読みやすい内容にする。

## 方針

- `autodev-start-new-task`: 仕分け → 下調べ → 方針確認 → 実装 → PR → レビュー → 指摘の取り込み → CI 待ちまでを 1 本の流れにまとめる
  - ブランチは `origin/main` から切る（前タスクの未マージのコミットを持ち込まない）
  - 指摘は Critical / Warning は直し、Info は妥当なものを直す。ユーザーに聞くのは方針に関わる指摘だけ
  - GitHub レビューでは、行コメントのスレッドに返信して解決する。Critical を直したらレビューをやり直す
  - CI は `gh pr checks --watch` で待ち、落ちたら直してプッシュし直す。終わらないときの調べ方を添える
- `autodev-review-pr`: レビューのみ。reviewer プロンプトを短くし、結果をレビューの URL（ローカルでは保存先）つきで返す
- `autodev-switch-to-default` を `autodev-merge-and-switch` に改名し、マージ条件（プッシュ済み・レビュー済み・Critical なし・スレッド解決済み・CI 成功）を確かめてマージし、デフォルトブランチに戻ってブランチを消すまでを行う。ユーザーが呼んだことをマージの指示とみなすため、`disable-model-invocation: true` にする
- `autodev-create-pr` / `autodev-start-new-project` / `autodev-start-new-survey`: 手順を短くする。create-pr は既存 PR の本文更新にも使えるようにする
- `autodev-start-new-task` / `-project` / `-survey` を `autodev-start-task` / `-project` / `-survey` に改名する
- `autodev-discussion` を廃止する。はっきりしない要件は start-task が AskUserQuestion で固める
- `autodev-import-review-suggestions` は既に廃止済み。autodev-init の移行案内は残す
- 対象は `.claude/skills/`（本リポジトリ用）と `plugins/autodev/skills/autodev-init/templates/skills/`（配布用）の両方。autodev-init・work.md・steering も追随させる

## 完了条件

- [x] 上記スキルを本リポジトリ用・テンプレートの両方で書き換えた
- [x] `autodev-switch-to-default`・`autodev-start-new-*` への参照が（過去のタスク記録・agent-coach の過去コマンド名・autodev-init の移行案内を除き）残っていない
- [x] autodev-init SKILL.md・templates/work.md・steering・structure.md が更新されている
- [x] `scripts/validate-skills.py` が通る
- [x] レビューを取り込み CI が通った PR → https://github.com/mizunashi-mana/agent-skills/pull/24

## 作業ログ

- 2026-10-13: 開始
- 2026-10-13: 実装
  - start-new-task: 完了フローを「PR とレビュー」「対応結果を残す（GitHub / ローカル）」「CI を待つ」に整理。ブランチを `origin/main` から切る形に変更。指摘は Critical / Warning を直し、方針に関わるものだけ聞く。GitHub ではスレッドに返信して解決し、Critical を直したらレビューをやり直す
  - review-pr（GitHub / ローカル）と reviewer プロンプトを短くし、結果をレビューの URL（ローカルは保存先）つきで返す形に統一
  - switch-to-default を merge-and-switch に改名。マージ条件の確認 → CI 待ち → `gh pr merge --merge` → main に戻って `git branch -d` まで行う。`disable-model-invocation: true`
  - create-pr / start-new-project / start-new-survey を短くした。create-pr は既存 PR の本文更新にも対応
  - start-new-task と merge-and-switch のテンプレートは両レビュー形式の節を持ち、autodev-init で使わない方を削る
  - agent-coach の detect-rework-and-violations の「slash command が許可している行動」表に merge-and-switch と新しい start-new-task の行動を追記（過去 transcript 用に旧コマンドの行は残す）
  - `scripts/validate-skills.py`: 22 ファイル、エラー 0
- 2026-10-13: PR 作成 → https://github.com/mizunashi-mana/agent-skills/pull/24
- 2026-10-13: `/autodev-review-pr 24` → 推奨アクション COMMENT（Critical 0 / Warning 3 / Info 5）。全件取り込み（fd34699）
  - W1〜3: merge-and-switch が「最新のレビュー」を見ると、スレッド返信の空レビューを拾う → `推奨アクション:` を含む最新のレビューで判定し、reviewer に総評の先頭へ推奨アクションと件数を必ず書かせる
  - Info: リモートブランチが残ったときの案内、ローカルレビューの最新ファイルの定義、ローカル時に削る allowed-tools、create-pr の既存 PR 時のプッシュ、CI 待ち前にチェックする理由
  - 行コメントのスレッドはすべて返信・解決。Info は PR コメントで報告
- 2026-10-13: ユーザー要望により `autodev-start-new-*` を `autodev-start-*` に改名（本リポジトリ用・テンプレート・autodev-init・work.md・steering・structure.md）。autodev-init に旧名の移行案内を追加し、agent-coach では過去 transcript 用に旧名も残して新名を追記
- 2026-10-13: ユーザー要望により `autodev-discussion` を廃止。start-task の仕分けでは AskUserQuestion で要件を固める形に変更し、autodev-init に移行案内を追加（agent-coach の過去コマンド名は残す）
