# 実装計画

## 現在のフェーズ

初期構築フェーズ。dotfiles からのスキル移植とリポジトリ公開準備。

## 完了済み

- リポジトリ作成
- .ai-agent/ ディレクトリ構造の構築
- steering ドキュメント 5 種（market.md, product.md, tech.md, plan.md, work.md）の作成

## 進行中

- `template/SKILL.md` の作成（次タスク候補）

## ロードマップ

### Phase 1: スキル移植と公開準備

- [x] dotfiles から autodev-init スキル＋テンプレート群を移植（2026-04-26）
- [x] dotfiles から merge-dependabot-bump-pr スキルを移植（2026-04-26）
- [x] `.claude-plugin/marketplace.json` の作成と plugins/ 配下への再構成（2026-04-26）
- [ ] `template/SKILL.md` の作成
- [x] CLAUDE.md / README.md / LICENSE の作成
- [x] GitHub リポジトリの公開

### Phase 2: 品質改善・標準化

- [ ] agentskills.io 仕様への準拠確認・調整
- [ ] クロスプラットフォーム対応の検討（.codex, .cursor-plugin 等）
- [ ] スキル評価（evals）の導入
- [ ] CI/CD（Markdown lint、フロントマターバリデーション）の構築

### Phase 3: スキル拡充

- [ ] 既存スキルの改善（競合分析で得たパターンの取り込み）
- [ ] 新規スキルの追加（需要に応じて）
- [ ] コミュニティからのコントリビューション受け入れ体制の整備
