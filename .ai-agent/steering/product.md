# プロダクトビジョン

## ミッション

AI エージェント駆動のソフトウェア開発ワークフローを、再利用可能なスキルとして標準化・公開し、開発者がすぐに使える形で提供する。

## ターゲットユーザー

- AI コーディングエージェント（Claude Code 等）を使って日常的に開発しているソフトウェアエンジニア
- チームにエージェント駆動ワークフローを導入したい開発リード

### 解決する課題

- エージェントの開発ワークフロー設定が個人の dotfiles に閉じており、共有・再利用が難しい
- プロジェクトごとに AI エージェント向けのコンテキスト（steering ドキュメント等）をゼロから構築する手間
- Issue 作成、PR レビュー、タスク管理など開発プロセスの各段階でエージェントを活用するための統合的なスキルセットがない

## 提供スキル

### autodev-init
リポジトリの AI エージェント開発環境を対話的に初期化するスキル。steering ドキュメント（product/tech/market/work）の生成、開発ワークフロースキル群のインストール、structure.md/CLAUDE.md/README.md の作成を一括で行う。初期化後のリポジトリには以下のサブスキルが含まれる:

- **autodev-create-issue**: GitHub Issue の作成（Bug Report/Feature Request/Problem テンプレート）
- **autodev-create-pr**: プルリクエストの作成
- **autodev-discussion**: アイデアや考えの対話的な整理
- **autodev-import-review-suggestions**: レビュー指摘の取り込み（GitHub/ローカル両対応）
- **autodev-replan**: ロードマップの再策定
- **autodev-review-pr**: PR コードレビュー（マルチエージェント）
- **autodev-start-new-project**: 長期プロジェクトの開始
- **autodev-start-new-survey**: 技術調査の開始
- **autodev-start-new-task**: 個別タスクの開始（トリアージ付き）
- **autodev-steering**: steering ドキュメントの更新
- **autodev-switch-to-default**: デフォルトブランチへの切り替え

### merge-dependabot-bump-pr
Dependabot が作成したバージョンバンプ PR を、4段階の安全性チェック（リリース経過日数、重大バグ報告、破壊的変更、ソースコード差分）の後にレビュー・マージするスキル。

## 差別化ポイント

- **軽量かつ統合的**: BMAD-METHOD のような重厚なフレームワークではなく、必要十分な粒度で開発ライフサイクル全体をカバー
- **GitHub ネイティブ**: Issue/PR/Review の GitHub API 連携がビルトイン
- **初期化の自動化**: autodev-init による一括セットアップで、ゼロからエージェント駆動開発を始められる
- **エージェント非依存**: Claude Code 向けを主としつつ、agentskills.io 仕様準拠でクロスプラットフォーム展開を視野に
