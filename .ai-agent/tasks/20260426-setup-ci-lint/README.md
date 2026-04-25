# タスク: CI/CD（Markdown lint・フロントマターバリデーション）の構築

## 目的・ゴール

リポジトリに最低限の CI を導入し、PR・main への push で以下が自動チェックされる状態にする:

1. Markdown ファイルが lint ルールに沿っている
2. `SKILL.md` の YAML フロントマターが規約どおり（必須フィールド・型）
3. `plugin.json` / `marketplace.json` が有効な JSON である

これにより、新規スキル追加時の規約逸脱を機械的に検出できるようにする。

## 背景

- `plan.md` Phase 2 の項目「CI/CD（Markdown lint、フロントマターバリデーション）の構築」
- `tech.md` の「CI/CD」セクションで「現時点では未構成。将来的に Markdown lint / SKILL.md フロントマターのバリデーション」と明記済み
- 現在 `.github/` ディレクトリも未作成
- 公開リポジトリとして他者から PR を受ける可能性を見据えると、規約準拠を機械化しておきたい

## 実装方針

### 1. ツール選定

- **Markdown lint**: `markdownlint-cli2`（業界標準・高速・設定柔軟）
- **フロントマターバリデーション**: Python 標準ライブラリ（`yaml`/`json`）でシンプルなスクリプトを自前で書く
  - 外部依存を最小化する（PyYAML のみ追加）
  - スクリプトは `scripts/validate-skills.py` 等に配置
- **CI**: GitHub Actions（`.github/workflows/lint.yml`）

### 2. Markdown lint の設定

- `.markdownlint-cli2.yaml`（または `.markdownlint.json`）でルールセットを設定
- 既存の Markdown が大量に存在するため、まずは緩めのルールで開始
  - 行の長さ制限は無効化（日本語混在のため）
  - インラインHTML は許容（`<!-- -->` コメント等）
  - 重複見出しは許容（章レベルで似た見出しが頻出するため）
- 既存ファイルが lint を通る最小ルールセットから出発し、必要に応じて段階的に強化

### 3. フロントマターバリデーション

対象: `plugins/**/SKILL.md`、`template/SKILL.md`

検証項目:

- [ ] YAML フロントマターが存在し、パース可能
- [ ] `description` が必須・非空文字列
- [ ] `allowed-tools` がある場合は文字列
- [ ] `disable-model-invocation` がある場合はブーリアン
- [ ] 想定外のキーがあれば警告（厳格にエラーにはしない）

JSON バリデーション対象:

- `.claude-plugin/marketplace.json`
- `plugins/*/.claude-plugin/plugin.json`

### 4. GitHub Actions workflow

`.github/workflows/lint.yml`:

- トリガー: `pull_request` と `push: branches: [main]`
- ジョブ:
  - `markdownlint`: Node.js セットアップ → `markdownlint-cli2` 実行
  - `validate-skills`: Python セットアップ → 検証スクリプト実行

### 5. ドキュメント更新

- `tech.md`: CI/CD セクションを「構成済み」に更新し、構成内容を記載
- `structure.md`: `.github/`・`scripts/` ディレクトリの追記
- `plan.md`: 該当チェックボックスを完了に更新
- `README.md`: バッジ追加（任意）

## 完了条件

- [x] `.github/workflows/lint.yml` が作成され、ローカルで構文確認できる
- [x] `.markdownlint-cli2.yaml`（または `.markdownlint.json`）が作成され、既存 Markdown を通過する設定になっている
- [x] `scripts/validate-skills.py`（または同等のスクリプト）が作成され、ローカル実行で既存 SKILL.md を通過する
- [x] スクリプトが、わざと壊した frontmatter を検出できることを手動で確認
- [x] `tech.md` の CI/CD セクションが更新済み
- [x] `structure.md` に `.github/` と `scripts/` が追記済み
- [x] `plan.md` のチェックボックスが完了に更新
- [ ] PR が作成され、CI が緑になっていることを確認

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
