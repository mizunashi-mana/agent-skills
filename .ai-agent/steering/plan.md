# 実装計画

## 現在のフェーズ

Phase 2（品質改善・標準化）と Phase 3（スキル拡充）の並行進行。Phase 1 のスキル移植・公開準備は完了済み。

## 進行中

- 次タスク候補は Issue ベースで管理:
  - [#19](https://github.com/mizunashi-mana/agent-skills/issues/19) autodev-init で全スキルの出力言語を選択できるようにする（enhancement / priority: medium）
  - [#8](https://github.com/mizunashi-mana/agent-skills/issues/8) autodev: モノリポ（複数パッケージ）でのメモリ・コンテキスト管理に対応（enhancement）
  - [#7](https://github.com/mizunashi-mana/agent-skills/issues/7) validate-skills.py: SKILL.md description の長さ警告と triggering ガイド系チェックを追加（enhancement / ci）

## ロードマップ

### Phase 1: スキル移植と公開準備（完了）

- [x] dotfiles から autodev-init スキル＋テンプレート群を移植（2026-04-26）
- [x] dotfiles から merge-dependabot-bump-pr スキルを移植（2026-04-26）
- [x] `.claude-plugin/marketplace.json` の作成と plugins/ 配下への再構成（2026-04-26）
- [x] `template/SKILL.md` の作成（2026-04-26）
- [x] CLAUDE.md / README.md / LICENSE の作成（2026-04-26）
- [x] GitHub リポジトリの公開（2026-04-26）

### Phase 2: 品質改善・標準化

- [x] CI/CD（フロントマター + plugin/marketplace JSON Schema バリデーション）の構築（2026-04-26）
- [ ] validate-skills.py の拡張（[#7](https://github.com/mizunashi-mana/agent-skills/issues/7): description 長さ警告と triggering ガイド系チェック）
- [ ] agentskills.io 仕様への準拠確認・調整
- [ ] クロスプラットフォーム対応の検討（.codex, .cursor-plugin 等）
- [ ] スキル評価（evals）の導入

### Phase 3: スキル拡充

#### 完了

- [x] agent-coach プラグインの追加（5 スキル）
  - [x] detect-context-rot（2026-05-05）
  - [x] recommend-bash-allowlist（2026-05-05）
  - [x] detect-missed-skill-triggers（2026-05-05）
  - [x] detect-token-hotspots（2026-05-05）
  - [x] detect-rework-and-violations（2026-05-05）
  - [x] agent-coach アンブレラスキル削除と分割スキルへの分離（2026-05-05）
  - [x] recommend-bash-allowlist の試用評価反映（分類精度・レポート構造改善, 2026-05-05）
  - [x] detect-rework-and-violations の試用評価反映（クロスセッション反復追加指示検知追加, 2026-05-05）
- [x] autodev サブスキル群の改善
  - [x] autodev-init で PR タイトル・本文の言語を選択可能に（[#17](https://github.com/mizunashi-mana/agent-skills/pull/17), 2026-05-06）
  - [x] PR 作成後に未 push の README 変更を残さない完了フローへ更新（[#18](https://github.com/mizunashi-mana/agent-skills/pull/18), 2026-05-06）
  - [x] autodev-review-pr 完了後に import-review-suggestions を自動チェーン（[#20](https://github.com/mizunashi-mana/agent-skills/pull/20), 2026-05-06）

#### 未着手

- [ ] autodev-init で全スキルの出力言語を選択可能に（[#19](https://github.com/mizunashi-mana/agent-skills/issues/19)）
- [ ] autodev のモノリポ対応（[#8](https://github.com/mizunashi-mana/agent-skills/issues/8)）
- [ ] 既存スキルの改善（競合分析で得たパターンの取り込み）
- [ ] 新規スキルの追加（需要に応じて）
- [ ] コミュニティからのコントリビューション受け入れ体制の整備
