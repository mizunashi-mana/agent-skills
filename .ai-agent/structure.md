# agent-skills ディレクトリ構成

## 概要

AI エージェント向けスキル／プラグインコレクションリポジトリ。Markdown ベースのスキル定義を Claude Code プラグイン形式で管理・配布する。

## ディレクトリ構成

```
agent-skills/
├── .ai-agent/                                                  # AI エージェント向け開発管理
│   ├── steering/                                               # 戦略的ガイドドキュメント
│   │   ├── market.md                                           # 市場分析・競合調査
│   │   ├── plan.md                                             # 実装計画・ロードマップ
│   │   ├── product.md                                          # プロダクトビジョン・戦略
│   │   ├── tech.md                                             # 技術アーキテクチャ・スタック
│   │   └── work.md                                             # 開発ワークフロー・規約
│   ├── structure.md                                            # 本ファイル（ディレクトリ構成の説明）
│   ├── projects/                                               # 長期プロジェクト管理
│   ├── tasks/                                                  # 個別タスク管理
│   └── surveys/                                                # 技術調査・検討
├── .claude/                                                    # Claude Code 設定
│   ├── settings.local.json                                     # ローカル設定
│   └── skills/                                                 # 開発用スキル（autodev シリーズ）
│       ├── autodev-create-issue/                               # GitHub Issue 作成
│       ├── autodev-create-pr/                                  # PR 作成
│       ├── autodev-discussion/                                 # 対話的アイデア整理
│       ├── autodev-import-review-suggestions/                  # レビュー指摘取り込み
│       ├── autodev-replan/                                     # ロードマップ再策定
│       ├── autodev-review-pr/                                  # PR レビュー（マルチエージェント）
│       │   ├── skill.md
│       │   └── reviewer-spawn-prompt.md
│       ├── autodev-start-new-project/                          # 長期プロジェクト開始
│       ├── autodev-start-new-survey/                           # 技術調査開始
│       ├── autodev-start-new-task/                             # タスク開始（トリアージ付き）
│       ├── autodev-steering/                                   # steering ドキュメント更新
│       └── autodev-switch-to-default/                          # デフォルトブランチ切り替え
├── .claude-plugin/                                             # プラグインマーケットプレイス定義
│   └── marketplace.json
├── plugins/                                                    # 公開プラグイン本体
│   ├── autodev/                                                # autodev プラグイン
│   │   ├── .claude-plugin/plugin.json                          # プラグインメタデータ
│   │   └── skills/
│   │       └── autodev-init/                                   # リポジトリ初期化スキル
│   │           ├── SKILL.md                                    # autodev 環境のセットアップ
│   │           └── templates/                                  # 展開対象のテンプレート
│   │               ├── claude-md.md                            # CLAUDE.md ベース
│   │               ├── work.md                                 # 開発ワークフロー（GitHub Flow）
│   │               └── skills/                                 # autodev サブスキル 11 種
│   │                   ├── autodev-create-issue/
│   │                   ├── autodev-create-pr/
│   │                   ├── autodev-discussion/
│   │                   ├── autodev-import-review-suggestions/  # GitHub 版 + .local.md
│   │                   ├── autodev-replan/
│   │                   ├── autodev-review-pr/                  # GitHub 版 + .local.md + reviewer-spawn-prompt
│   │                   ├── autodev-start-new-project/
│   │                   ├── autodev-start-new-survey/
│   │                   ├── autodev-start-new-task/
│   │                   ├── autodev-steering/
│   │                   └── autodev-switch-to-default/
│   └── merge-dependabot-bump-pr/                               # merge-dependabot-bump-pr プラグイン
│       ├── .claude-plugin/plugin.json
│       └── skills/
│           └── merge-dependabot-bump-pr/
│               └── SKILL.md                                    # バージョンバンプ PR の安全性レビュー＋マージ
├── template/                                                   # スキル作成テンプレート
│   └── SKILL.md                                                # YAML フロントマター + 本文セクション雛形
├── scripts/                                                    # CI/CD 用スクリプト
│   └── validate-skills.py                                      # SKILL.md フロントマター + plugin/marketplace JSON の検証
├── .github/                                                    # GitHub 設定
│   └── workflows/
│       └── lint.yml                                            # markdownlint + validate-skills.py の CI ワークフロー
├── .markdownlint-cli2.yaml                                     # markdownlint-cli2 設定
├── CLAUDE.md                                                   # Claude Code 向けプロジェクトガイド
├── README.md                                                   # プロジェクト説明（英語）
└── LICENSE                                                     # ライセンスファイル
```

## アーキテクチャパターン

### スキルの二重構造

1. **`.claude/skills/`**: このリポジトリ自体の開発に使う autodev スキル群（開発者向け）
2. **`plugins/`**: 公開・配布するプラグイン本体（ユーザー向け）。各プラグイン配下の `skills/` に SKILL.md を持つ

### プラグインの構成

各プラグインは `plugins/{plugin-name}/` ディレクトリに配置され、以下の構成:

- `.claude-plugin/plugin.json`: プラグインメタデータ（`name`, `description`, `version`, `author`, ...）
- `skills/{skill-name}/SKILL.md`: スキル本体（YAML フロントマター + Markdown 本文）
- スキル配下の任意リソース: `templates/`, `scripts/`, `reference/` 等

### 配布形式

`.claude-plugin/marketplace.json` で各プラグインを登録し、Claude Code のマーケットプレイス経由でインストール可能にする。
