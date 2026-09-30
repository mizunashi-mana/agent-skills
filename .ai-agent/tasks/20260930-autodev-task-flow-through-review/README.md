# autodev-start-new-task をレビュー取り込みまで完結させる

## 目的・ゴール

- `autodev-start-new-task` のゴールを「PR 作成」から「PR 作成 → レビュー → 指摘取り込み」までに拡張し、1 タスクをレビュー済みの状態まで一気通貫で進められるようにする
- `autodev-review-pr` を TeamCreate / SendMessage ベースのチーム運用から、Agent ツール（サブエージェント）ベースに書き換えて簡素化する
- レビュー指摘の取り込みを `autodev-review-pr` に統合し、`autodev-import-review-suggestions` スキルを削除する

## 実装方針

### autodev-review-pr（Agent ツールベース化 + 取り込み統合）

- TeamCreate / TaskCreate / SendMessage / shutdown_request / TeamDelete の手順を廃止
- `Agent({ subagent_type: "general-purpose", model: "opus", ... })` で reviewer を起動し、reviewer の最終応答（レビュー結果サマリー）を返り値として受け取る
- reviewer-spawn-prompt から「lead へのメッセージ送信」「シャットダウン待ち」を削除し、「最終応答として報告フォーマットで返す」に変更
- 取り込みの手順を review-pr 本体に統合:
  - 各指摘を 修正推奨 / 不要 / 要確認 に分類して提示
  - ユーザー承認を得て修正 → コミット → push
  - GitHub 版: reviewer が投稿した行コメントに対応結果を返信
  - ローカル版: レビューファイル（`.ai-agent/tmp/reviews/...`）に対応結果を追記
- 対象: `.claude/skills/autodev-review-pr/` と `plugins/autodev/skills/autodev-init/templates/skills/autodev-review-pr/`（GitHub 版 + ローカル版）

### autodev-import-review-suggestions の削除

- `.claude/skills/` とテンプレート（GitHub 版 + ローカル版）の両方から削除
- 参照箇所（autodev-init SKILL.md のテーブル・説明、templates/work.md、steering の product.md / structure.md）を更新
- agent-coach の detect-rework-and-violations 内の参照は過去 transcript 解析用のコマンド名リストのため残す

### autodev-start-new-task（完了フロー拡張）

- 完了フローに「PR 作成 → PR URL 反映 push → `/autodev-review-pr` でレビュー + 取り込み → 作業ログ更新 push → CI 全成功の確認（失敗時は修正して再 push）→ クリーン確認 → 報告」を追加
- allowed-tools に `Skill(autodev-review-pr)`、`Bash(gh pr checks *)`、`Bash(gh run view *)` を追加
- 対象: `.claude/skills/` とテンプレートの両方

## 完了条件

- [x] autodev-review-pr（本リポジトリ用 + テンプレート GitHub 版 / ローカル版）が Agent ツールベースで、取り込みまで行う内容になっている
- [x] autodev-import-review-suggestions が本リポジトリ用・テンプレート双方から削除され、参照が残っていない（agent-coach の過去コマンド名リストを除く）
- [x] autodev-start-new-task（本リポジトリ用 + テンプレート）の完了フローがレビュー取り込みと CI 全成功の確認までを含む
- [x] steering ドキュメント・structure.md・autodev-init SKILL.md・templates/work.md が更新されている
- [x] `scripts/validate-skills.py` が通る
- [x] PR を作成（`/autodev-create-pr`） → https://github.com/mizunashi-mana/agent-skills/pull/23
- [x] `/autodev-review-pr` でレビューし、指摘を取り込む
- [ ] CI が全て成功

## 作業ログ

- 2026-09-30: トリアージ → 1 PR 規模の具体的タスクと判断し、そのまま続行
- 2026-09-30: 取り込み時のユーザー確認は「要確認」の指摘のみとする方針でユーザー合意
- 2026-09-30: ユーザー要望により、PR 作成後に CI が全て成功したかを確認する手順を start-new-task の完了フローに追加
- 2026-09-30: 実装完了
  - review-pr（本リポジトリ用 / テンプレート GitHub 版 / ローカル版）を Agent ツールベースに書き換え、reviewer の最終応答を返り値として受け取る形に変更。指摘の分類 → 要確認のみユーザー確認 → 修正・コミット・push → 返信（GitHub）/ 対応結果追記（ローカル）までを統合
  - reviewer-spawn-prompt から lead へのメッセージ送信・シャットダウン待ちを削除し、最終応答での報告に変更（GitHub 版はレビュー ID も返す）
  - import-review-suggestions を削除し、autodev-init SKILL.md・templates/work.md・product.md・structure.md・plan.md を更新
  - start-new-task の完了フローに review-pr 呼び出しと CI 全成功確認を追加
  - `scripts/validate-skills.py`: 22 ファイル、エラー 0
  - 未追跡の `.ai-agent/projects/20260506-autodev-workspace-support/` にも import-review-suggestions への言及があるが、本タスクの管理外のため未変更
- 2026-09-30: PR 作成 → https://github.com/mizunashi-mana/agent-skills/pull/23
- 2026-09-30: `/autodev-review-pr 23` でレビュー（新フローの初回実運用）→ 推奨アクション COMMENT（Critical 0 / Warning 2 / Info 5）
  - 修正 4 件: 自分の PR で APPROVE にならず早期終了しない問題（指摘件数で判定するよう変更）、`gh pr checks --watch` の Bash タイムアウト対策、旧 import スキルの移行案内、work.md の push 記述漏れ
  - スキップ 2 件: テーブル列幅（表示に影響なし）、`gh api *` 権限の広さ（返信投稿に必要）
  - 追加対応: Agent ツールはバックグラウンド実行されうるため、完了通知を待つ旨を review-pr に追記（実運用で判明）
