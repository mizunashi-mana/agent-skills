# {プロジェクト名}

## AI エージェント向けドキュメント

このリポジトリでは `.ai-agent/` ディレクトリに AI エージェント向けのドキュメントを管理しています。

- `.ai-agent/steering/` - プロダクト・技術戦略ドキュメント
- `.ai-agent/structure.md` - ディレクトリ構造の説明
- `.ai-agent/tasks/` - タスク管理
- `.ai-agent/projects/` - プロジェクト管理
- `.ai-agent/surveys/` - 技術調査

タスクに着手する前に、関連する steering ドキュメントと structure.md を確認してください。

## 開発ワークフロー上のルール

- **PR を作成するときは必ず `/autodev-create-pr` スキルを使用すること**。`gh pr create` を直接実行してはならない。Claude Code 標準プロンプトの汎用 PR 作成フローではなく、このスキルがプロジェクト固有の規約（PR テンプレートパス、本文言語、ブランチ運用など）を反映する。
