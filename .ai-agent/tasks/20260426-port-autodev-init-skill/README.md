# dotfiles からの autodev-init スキル移植

## 目的・ゴール

dotfiles リポジトリで運用中の `autodev-init` スキル本体とサブスキルテンプレート群を、本リポジトリの `skills/autodev-init/` に移植する。Phase 1 ロードマップの先頭タスク。

## 移植元

- 本体: `~/Workspace/MyWork/dotfiles/nix/programs/claude-code/skills/autodev-init/SKILL.md`（215行）
- テンプレート:
  - `templates/work.md`（80行）
  - `templates/claude-md.md`（13行）
  - `templates/skills/` 配下の autodev サブスキル群（計 10 スキル分）
    - `autodev-create-issue/`
    - `autodev-create-pr/`
    - `autodev-discussion/`
    - `autodev-import-review-suggestions/`（`SKILL.md` + `SKILL.local.md`）
    - `autodev-replan/`
    - `autodev-review-pr/`（`SKILL.md` + `SKILL.local.md` + `reviewer-spawn-prompt.md` + `reviewer-spawn-prompt.local.md`）
    - `autodev-start-new-project/`
    - `autodev-start-new-survey/`
    - `autodev-start-new-task/`
    - `autodev-steering/`
    - `autodev-switch-to-default/`

## 移植先

`skills/autodev-init/` 配下に同じ構造で配置する。

```
skills/autodev-init/
├── SKILL.md
└── templates/
    ├── work.md
    ├── claude-md.md
    └── skills/
        ├── autodev-create-issue/SKILL.md
        ├── autodev-create-pr/SKILL.md
        ├── ...（以下サブスキル群）
```

## 実装方針

1. **そのままコピー**を基本とする。dotfiles 側で運用実績のあるスキルをそのまま再利用する。
2. コピー後、以下を確認・調整する:
   - YAML フロントマター（`description`, `allowed-tools`, `disable-model-invocation` など）が正しい形式か
   - dotfiles 固有のパス参照や記述があれば一般化する
   - `SKILL.local.md` などのローカル運用ファイルを含めるかどうかを判断（含める方針: dotfiles 側で並置されているため、ユーザー固有の設定例として残す）
3. 本リポジトリの `.claude/skills/` には autodev 系スキルが既に置かれている。これらは本リポジトリ自体の開発用スキル（structure.md 参照）なので**重複を許容**する。`skills/autodev-init/templates/` にあるのは「他リポジトリで autodev-init を実行したときに展開されるテンプレート」であり、役割が違う。

## 完了条件

- [x] `skills/autodev-init/SKILL.md` が配置されている
- [x] `skills/autodev-init/templates/work.md` `claude-md.md` が配置されている
- [x] `skills/autodev-init/templates/skills/` 配下にサブスキル 11 種（GitHub 版とローカル版を含む）が配置されている
- [x] 全ての SKILL.md の YAML フロントマターが妥当（`description` フィールド存在）
- [x] dotfiles 固有の表現が残っていないことを確認（grep で検出ゼロ）
- [x] `.ai-agent/structure.md` の「【未作成】skills/autodev-init/」マーカーを更新
- [x] `.ai-agent/steering/plan.md` のロードマップ該当項目をチェック済みに更新

## トリアージ結果

- 判定: そのまま続行
- 理由: ゴール明確 / 技術的不確実性低 / 1 変更セットで完結 / 数時間規模

## 作業ログ

- 2026-04-26: タスク開始。dotfiles 側のファイル構成を確認、移植計画を作成。
- 2026-04-26: `skills/autodev-init/` を作成し、SKILL.md（215 行）、templates/work.md、templates/claude-md.md、templates/skills/ 配下のサブスキル 11 種（合計 18 ファイル）を移植。
- 2026-04-26: 全 SKILL.md の YAML フロントマターに `description` フィールドが存在することを確認。dotfiles 固有のパス（`/Users/mizunashi`、`Workspace/MyWork`、`nix/programs` など）が含まれていないことを `grep` で確認（検出ゼロ）。
- 2026-04-26: `.ai-agent/structure.md` のディレクトリツリーを更新（skills/autodev-init/ の中身を反映）。`.ai-agent/steering/plan.md` のロードマップを更新（autodev-init 移植を完了済みに、進行中を次タスク候補に置き換え）。
- 2026-04-26: タスク完了。本リポジトリは git リポジトリではないため、PR 作成手順はスキップ。
