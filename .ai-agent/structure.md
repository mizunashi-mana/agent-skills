# agent-skills ディレクトリ構成

## 概要

AI エージェント向けスキルコレクションリポジトリ。Markdown ベースのスキル定義を管理・配布する。

## ディレクトリ構成

```
agent-skills/
├── .ai-agent/                          # AI エージェント向け開発管理
│   ├── steering/                       # 戦略的ガイドドキュメント
│   │   ├── market.md                   # 市場分析・競合調査
│   │   ├── plan.md                     # 実装計画・ロードマップ
│   │   ├── product.md                  # プロダクトビジョン・戦略
│   │   ├── tech.md                     # 技術アーキテクチャ・スタック
│   │   └── work.md                     # 開発ワークフロー・規約
│   ├── structure.md                    # 本ファイル（ディレクトリ構成の説明）
│   ├── projects/                       # 長期プロジェクト管理
│   ├── tasks/                          # 個別タスク管理
│   └── surveys/                        # 技術調査・検討
├── .claude/                            # Claude Code 設定
│   ├── settings.local.json             # ローカル設定
│   └── skills/                         # 開発用スキル（autodev シリーズ）
│       ├── autodev-create-issue/       # GitHub Issue 作成
│       ├── autodev-create-pr/          # PR 作成
│       ├── autodev-discussion/         # 対話的アイデア整理
│       ├── autodev-import-review-suggestions/  # レビュー指摘取り込み
│       ├── autodev-replan/             # ロードマップ再策定
│       ├── autodev-review-pr/          # PR レビュー（マルチエージェント）
│       │   ├── skill.md
│       │   └── reviewer-spawn-prompt.md
│       ├── autodev-start-new-project/  # 長期プロジェクト開始
│       ├── autodev-start-new-survey/   # 技術調査開始
│       ├── autodev-start-new-task/     # タスク開始（トリアージ付き）
│       ├── autodev-steering/           # steering ドキュメント更新
│       └── autodev-switch-to-default/  # デフォルトブランチ切り替え
├── skills/                             # 公開スキル本体
│   ├── autodev-init/                   # リポジトリ初期化スキル
│   │   ├── SKILL.md                    # メインスキル（autodev 環境のセットアップ）
│   │   └── templates/                  # 展開対象のテンプレート
│   │       ├── claude-md.md            # CLAUDE.md ベース
│   │       ├── work.md                 # 開発ワークフロー（GitHub Flow）
│   │       └── skills/                 # autodev サブスキル 11 種
│   │           ├── autodev-create-issue/
│   │           ├── autodev-create-pr/
│   │           ├── autodev-discussion/
│   │           ├── autodev-import-review-suggestions/  # GitHub 版 + .local.md
│   │           ├── autodev-replan/
│   │           ├── autodev-review-pr/                  # GitHub 版 + .local.md + reviewer-spawn-prompt
│   │           ├── autodev-start-new-project/
│   │           ├── autodev-start-new-survey/
│   │           ├── autodev-start-new-task/
│   │           ├── autodev-steering/
│   │           └── autodev-switch-to-default/
│   └── merge-dependabot-bump-pr/       # 【未作成】Dependabot PR マージスキル（移植予定）
├── .claude-plugin/                     # 【未作成】プラグインマーケットプレイス定義
├── template/                           # 【未作成】スキル作成テンプレート
├── CLAUDE.md                           # Claude Code 向けプロジェクトガイド
├── README.md                           # プロジェクト説明（英語）
└── LICENSE                             # ライセンスファイル
```

## アーキテクチャパターン

### スキルの二重構造

1. **`.claude/skills/`**: このリポジトリ自体の開発に使う autodev スキル群（開発者向け）
2. **`skills/`**: 公開・配布するスキル本体（ユーザー向け）

### スキルの構成

各スキルは `skills/{name}/` ディレクトリに配置され、以下の構成:
- `SKILL.md`: YAML フロントマター（name, description）＋ Markdown 本文
- リソースディレクトリ（任意）: `templates/`, `scripts/`, `reference/` 等

### 配布形式

`.claude-plugin/marketplace.json` でプラグインバンドルを定義し、Claude Code のマーケットプレイス経由でインストール可能にする。
