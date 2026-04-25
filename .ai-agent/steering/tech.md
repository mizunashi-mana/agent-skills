# 技術アーキテクチャ

## 技術スタック

- **スキル定義**: Markdown（YAML フロントマター付き SKILL.md）
- **配布形式**: Claude Code プラグインマーケットプレイス（`.claude-plugin/marketplace.json`）
- **仕様準拠**: Agent Skills 仕様（agentskills.io）
- **バージョン管理**: Git / GitHub

## アーキテクチャ概要

スキルコレクション型リポジトリ。各スキルは `skills/` 配下にディレクトリとして配置され、`SKILL.md` と関連リソース（テンプレート、プロンプト等）で構成される。

### リポジトリ構成

```
agent-skills/
├── .claude-plugin/
│   └── marketplace.json       # プラグインバンドル定義
├── skills/
│   ├── autodev-init/          # リポジトリ初期化スキル
│   │   ├── SKILL.md
│   │   └── templates/         # steering/スキルテンプレート
│   └── merge-dependabot-bump-pr/
│       └── SKILL.md
├── template/
│   └── SKILL.md               # スキル作成用テンプレート
├── CLAUDE.md
├── README.md
└── LICENSE
```

### スキルの構造

各スキルは anthropics/skills の規約に従う:

1. **SKILL.md**: YAML フロントマター（`name`, `description`）＋ Markdown 本文
2. **リソースディレクトリ**（任意）: `templates/`, `scripts/`, `reference/` 等
3. **LICENSE.txt**（任意）: スキル個別のライセンス

### プラグイン配布

`.claude-plugin/marketplace.json` で以下のバンドルを定義:
- **autodev**: autodev-init スキル（サブスキルテンプレートを含む）
- **merge-dependabot-bump-pr**: Dependabot PR マージスキル

## 開発環境

特別なセットアップは不要。テキストエディタと Git があれば開発可能。

## テスト戦略

- スキルの動作確認は実際のリポジトリでの手動テスト
- 将来的に `evals/evals.json` によるスキル評価の導入を検討（anthropics/skills の skill-creator パターン）

## CI/CD

現時点では未構成。将来的に以下を検討:
- Markdown lint（markdownlint）
- SKILL.md フロントマターのバリデーション
