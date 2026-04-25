# 技術アーキテクチャ

## 技術スタック

- **スキル定義**: Markdown（YAML フロントマター付き SKILL.md）
- **配布形式**: Claude Code プラグインマーケットプレイス（`.claude-plugin/marketplace.json`）
- **仕様準拠**: Agent Skills 仕様（agentskills.io）
- **バージョン管理**: Git / GitHub

## アーキテクチャ概要

プラグインコレクション型リポジトリ。Claude Code のプラグインマーケットプレイス仕様に従い、各プラグインは `plugins/<plugin-name>/` 配下に `.claude-plugin/plugin.json` と `skills/<skill-name>/SKILL.md`（および任意のリソース）で構成される。

### リポジトリ構成

```
agent-skills/
├── .claude-plugin/
│   └── marketplace.json                                        # プラグインバンドル定義
├── plugins/
│   ├── autodev/                                                # autodev プラグイン
│   │   ├── .claude-plugin/plugin.json
│   │   └── skills/
│   │       └── autodev-init/                                   # リポジトリ初期化スキル
│   │           ├── SKILL.md
│   │           └── templates/                                  # steering / サブスキルテンプレート
│   └── merge-dependabot-bump-pr/                               # merge-dependabot-bump-pr プラグイン
│       ├── .claude-plugin/plugin.json
│       └── skills/
│           └── merge-dependabot-bump-pr/
│               └── SKILL.md
├── template/
│   └── SKILL.md                                                # スキル作成用テンプレート
├── CLAUDE.md
├── README.md
└── LICENSE
```

### プラグインの構造

各プラグインは Claude Code プラグイン規約（anthropics/claude-plugins-public 参照）に従う:

1. **`.claude-plugin/plugin.json`**: プラグインメタデータ（`name`, `description`, `version`, `author` 等）
2. **`skills/<skill-name>/SKILL.md`**: プラグインに含まれるスキル本体（YAML フロントマター + Markdown 本文）
3. **リソースディレクトリ**（任意）: 各スキル配下の `templates/`, `scripts/`, `reference/` 等

スキル定義（`SKILL.md`）は agentskills.io の Agent Skills 仕様に準拠する。

### プラグイン配布

`.claude-plugin/marketplace.json` で以下のバンドルを定義:

- **autodev**: autodev-init スキル（サブスキルテンプレートを含む）
- **merge-dependabot-bump-pr**: Dependabot PR マージスキル

利用者は次の手順でインストールできる:

```
/plugin marketplace add mizunashi-mana/agent-skills
/plugin install autodev
/plugin install merge-dependabot-bump-pr
```

## 開発環境

特別なセットアップは不要。テキストエディタと Git があれば開発可能。

## テスト戦略

- スキルの動作確認は実際のリポジトリでの手動テスト
- 将来的に `evals/evals.json` によるスキル評価の導入を検討（anthropics/skills の skill-creator パターン）

## CI/CD

GitHub Actions の `lint` ワークフロー（`.github/workflows/lint.yml`）を `pull_request` と `push: main` で実行する。以下の 2 ジョブで構成:

- **markdownlint**: `markdownlint-cli2` を `npx` 経由で実行。ルールセットは `.markdownlint-cli2.yaml` に定義。日本語混在のため行長制限・コードブロック言語必須化などは無効化し、ヘッディング/リスト周りの整合性チェックを中心とする
- **validate-skills**: `scripts/validate-skills.py`（Python + PyYAML）を実行。`plugins/**/SKILL.md` と `template/SKILL.md` のフロントマター（`description` 必須、`allowed-tools` / `disable-model-invocation` の型）と `.claude-plugin/marketplace.json` / `plugins/*/.claude-plugin/plugin.json` の JSON 妥当性を検証する

ローカルで実行する場合:

```bash
# Markdown lint（Docker 経由）
docker run --rm -v "$PWD":/workdir davidanson/markdownlint-cli2:latest

# フロントマター・JSON 検証
pip install pyyaml
python3 scripts/validate-skills.py
```
