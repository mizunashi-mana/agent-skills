# タスク: `template/SKILL.md` の作成

## 目的・ゴール

新しいスキルを作成する際の出発点となる `template/SKILL.md` を整備する。Agent Skills 仕様（agentskills.io）と本リポジトリの慣習（既存の autodev-init / merge-dependabot-bump-pr スキル）の双方に沿った形にする。

## 背景

- `plan.md` の Phase 1 で「次タスク候補」とされていた残作業
- `structure.md` / `tech.md` で `template/` ディレクトリの存在は前提化されているが、本体は未作成
- スキル開発フロー（`work.md` の「新規スキルの追加」）の出発点となる雛形が欠けている

## 実装方針

1. `template/` ディレクトリを作成し、`SKILL.md` を配置する
2. テンプレートには以下を含める:
   - YAML フロントマター（`description` は必須、`allowed-tools` と `disable-model-invocation` は任意）
   - フロントマター各フィールドの解説（プレースホルダ・選択肢・記述指針）
   - 標準的な本文セクション構成（概要 / 前提条件 / 手順 / 注意事項）の雛形
3. テンプレートは「コピーして埋めて使う」前提とし、各セクションに記入ガイダンスをコメント風に明示する
4. 補助的な使い方ガイドはテンプレート内に簡潔にまとめ、別ファイルは作らない
5. 関連ドキュメントを更新:
   - `.ai-agent/structure.md`: 「【未作成】」を解除し、テンプレートの内容説明を追記
   - `.ai-agent/steering/plan.md`: チェックボックスを完了状態に更新

## 完了条件

- [x] `template/SKILL.md` が作成され、YAML フロントマターと本文構成のテンプレートが揃っている
- [x] テンプレート内に、スキル作成時の注意事項（description の書き方、tool 列挙の形式など）が記載されている
- [x] `.ai-agent/structure.md` から「【未作成】」表記が削除され、`template/SKILL.md` への言及が追加されている
- [x] `.ai-agent/steering/plan.md` の該当タスクがチェック済みに更新されている
- [x] PR が作成されている

## 作業ログ

- 2026-04-26: タスク作成、方針整理
- 2026-04-26: ユーザー承認のもと「最小限の雛形」方針を採用（解説は YAML コメント・HTML コメントで最小限に）
- 2026-04-26: `feature/create-skill-template` ブランチを作成
- 2026-04-26: `template/SKILL.md` を作成（YAML フロントマター 3 フィールド + 本文 4 セクション）
- 2026-04-26: `.ai-agent/structure.md` から「【未作成】」表記を削除し、`template/SKILL.md` の説明を追記
- 2026-04-26: `.ai-agent/steering/plan.md` の該当チェックを完了に更新
- 2026-04-26: PR #3 を作成（https://github.com/mizunashi-mana/agent-skills/pull/3）
