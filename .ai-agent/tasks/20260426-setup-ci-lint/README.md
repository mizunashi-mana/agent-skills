# タスク: CI/CD（フロントマター・JSON Schema バリデーション）の構築

## 目的・ゴール

リポジトリに最低限の CI を導入し、PR・main への push で以下が自動チェックされる状態にする:

1. `SKILL.md` の YAML フロントマターが規約どおり（`description` 必須、型チェック、未知フィールド検出）
2. `plugin.json` が JSON Schema（公式プラグイン仕様準拠）を満たす
3. `marketplace.json` が JSON Schema（公式マーケットプレイス仕様準拠）を満たす

これにより、新規スキル追加時の規約逸脱を機械的に検出できるようにする。

> **方針メモ**: 当初は markdownlint も含めていたが、ユーザーフィードバックにより削除。フロントマター抽出は `python-frontmatter`、JSON 検証は `jsonschema` ライブラリを採用し、自前パーサや手書き型チェックを廃止した。

## 背景

- `plan.md` Phase 2 の項目「CI/CD（Markdown lint、フロントマターバリデーション）の構築」
- `tech.md` の「CI/CD」セクションで「現時点では未構成。将来的に Markdown lint / SKILL.md フロントマターのバリデーション」と明記済み
- 現在 `.github/` ディレクトリも未作成
- 公開リポジトリとして他者から PR を受ける可能性を見据えると、規約準拠を機械化しておきたい

## 実装方針

### 1. ツール選定

- **フロントマター抽出**: `python-frontmatter`（YAML フロントマター + Markdown 本文をパースする標準ライブラリ）
- **JSON Schema 検証**: `jsonschema`（Python の標準的な JSON Schema バリデータ）
- **CI**: GitHub Actions（`.github/workflows/lint.yml`）
- 依存は `scripts/requirements.txt` で管理

### 2. JSON Schema の作成

公式スキーマ（`https://anthropic.com/claude-code/*.schema.json`）は未公開のため、ドキュメント仕様（`code.claude.com/docs/en/plugins-reference` / `plugin-marketplaces`）から起こして `schemas/` 配下で管理する:

- `schemas/plugin.schema.json`: `name`（必須・kebab-case）、`version`/`description`/`author`/`homepage`/`repository`/`license`/`keywords` その他のメタデータと、`skills`/`commands`/`agents`/`hooks`/`mcpServers` 等のコンポーネントパスフィールド
- `schemas/marketplace.schema.json`: `name`（必須・kebab-case）、`owner`（必須・`name` 必須）、`plugins[]`（必須）。各 plugin entry は `name` + `source` 必須、`source` は relative path / github / url / git-subdir / npm の 5 種類

JSON Schema Draft 2020-12 を採用。`additionalProperties: true` でフォワードコンパチビリティを保つ。

### 3. フロントマター検証

対象: `plugins/**/SKILL.md`、`template/SKILL.md`（`*.local.md` は除外）

スクリプト内蔵の JSON Schema で検証:

- `description`: 必須、非空文字列
- `allowed-tools`: 任意、文字列
- `disable-model-invocation`: 任意、ブーリアン
- 未知フィールドはエラー（`additionalProperties: false`）

### 4. GitHub Actions workflow

`.github/workflows/lint.yml`:

- トリガー: `pull_request` と `push: branches: [main]`
- 単一ジョブ `validate-skills`: Python セットアップ → `pip install -r scripts/requirements.txt` → `python3 scripts/validate-skills.py`

### 5. ドキュメント更新

- `tech.md`: CI/CD セクションを「構成済み」に更新し、構成内容を記載
- `structure.md`: `.github/`・`scripts/`・`schemas/` ディレクトリの追記
- `plan.md`: 該当チェックボックスを完了に更新

## 完了条件

- [x] `.github/workflows/lint.yml` が作成され、`validate-skills` ジョブが定義されている
- [x] `schemas/plugin.schema.json` と `schemas/marketplace.schema.json` が公式仕様に沿って作成されている
- [x] `scripts/validate-skills.py` が `python-frontmatter` + `jsonschema` を使って書かれており、ローカル実行で既存ファイルが通過する
- [x] スクリプトが、わざと壊した frontmatter / plugin.json / marketplace.json を検出できることを手動で確認
- [x] `tech.md` の CI/CD セクションが更新済み
- [x] `structure.md` に `.github/` と `scripts/` と `schemas/` が追記済み
- [x] `plan.md` のチェックボックスが完了に更新
- [x] PR が作成され、CI が緑になっていることを確認

## 作業ログ

- 2026-04-26: タスク作成、方針整理
- 2026-04-26: `support/setup-ci-lint` ブランチを作成
- 2026-04-26: `.markdownlint-cli2.yaml` を作成（MD013/MD040/MD041/MD060 を無効化、MD024/MD026/MD033 を調整）
- 2026-04-26: `scripts/validate-skills.py` を作成（PyYAML 依存、SKILL.md frontmatter + plugin/marketplace JSON を検証）
- 2026-04-26: `.github/workflows/lint.yml` を作成（markdownlint + validate-skills の 2 ジョブ）
- 2026-04-26: 検証スクリプトが既存ファイルの実バグを検出（autodev-switch-to-default の `allowed-tools` が無効な YAML）→ 順序入れ替えで修正
- 2026-04-26: markdownlint で検出された軽微な MD022/MD032/MD033/MD034 違反を既存ファイル側で修正
- 2026-04-26: ローカルで markdownlint-cli2（Docker 経由）と validate-skills.py を実行し、全 42 ファイル / 17 SKILL.md が通過することを確認
- 2026-04-26: わざと壊したフロントマター（description 欠落、型違反、未知フィールド）を検出することを `--root` オプションで確認、exit 1 となることを検証
- 2026-04-26: `tech.md` CI/CD セクションを更新、`structure.md` に scripts/.github/.markdownlint-cli2.yaml を追記、`plan.md` のチェックを完了に更新
- 2026-04-26: PR #4 を作成（<https://github.com/mizunashi-mana/agent-skills/pull/4>）、CI 2 ジョブとも success を確認
- 2026-04-26: ユーザーフィードバックに基づき方針転換。markdownlint を撤去し、frontmatter 抽出は `python-frontmatter`、JSON 検証は `jsonschema` ライブラリに切り替え
- 2026-04-26: `schemas/plugin.schema.json` / `schemas/marketplace.schema.json` を公式ドキュメントから起こして作成
- 2026-04-26: `scripts/validate-skills.py` をライブラリベースに書き直し、`scripts/requirements.txt` を追加
- 2026-04-26: `.markdownlint-cli2.yaml` を削除、workflow から markdownlint ジョブを削除
- 2026-04-26: ローカルで再検証（17 ファイル / 0 エラー）、わざと壊したフィクスチャでエラー検出を確認
