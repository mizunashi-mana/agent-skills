# dotfiles からの merge-dependabot-bump-pr スキル移植

## 目的・ゴール

`merge-dependabot-bump-pr` スキルを本リポジトリの `skills/merge-dependabot-bump-pr/` に移植する。Phase 1 ロードマップの第 2 タスク。

## 移植元

- 本体: `~/.claude/skills/merge-dependabot-bump-pr/SKILL.md`（dotfiles の home-manager 経由でシンボリックリンク済み、146 行）

## 移植先

`skills/merge-dependabot-bump-pr/SKILL.md` に同名で配置する。

## 実装方針

1. **そのままコピー**を基本とする。dotfiles 側で運用実績のあるスキルをそのまま再利用する。
2. コピー後、以下を確認・調整する:
   - YAML フロントマター（`description`, `allowed-tools`）が正しい形式か
   - dotfiles 固有のパス参照や記述があれば一般化する（autodev-init 移植時と同様）
3. `.ai-agent/structure.md` の「【未作成】skills/merge-dependabot-bump-pr/」マーカーを更新
4. `.ai-agent/steering/plan.md` のロードマップ該当項目をチェック済みに更新

## 完了条件

- [x] `skills/merge-dependabot-bump-pr/SKILL.md` が配置されている
- [x] YAML フロントマターが妥当（`description` フィールド存在）
- [x] dotfiles 固有の表現が残っていないことを確認（grep で検出ゼロ）
- [x] `.ai-agent/structure.md` の該当マーカーを更新
- [x] `.ai-agent/steering/plan.md` のロードマップ該当項目をチェック済みに更新

## トリアージ結果

- 判定: そのまま続行
- 理由: ゴール明確 / 技術的不確実性低 / 1 変更セットで完結 / 数時間規模

## 作業ログ

- 2026-04-26: タスク開始。dotfiles 側のファイル構成（146 行 1 ファイル）を確認、移植計画を作成。
- 2026-04-26: `skills/merge-dependabot-bump-pr/SKILL.md` を配置（146 行）。YAML フロントマター（`description`, `allowed-tools`）が正しい形式であることを確認。dotfiles 固有のパス（`mizunashi`, `Workspace/MyWork`, `nix/programs`, `home-manager`）が含まれていないことを `grep` で確認（検出ゼロ）。
- 2026-04-26: `.ai-agent/structure.md` の【未作成】マーカーを更新。`.ai-agent/steering/plan.md` のロードマップ該当項目を完了済みに更新、進行中項目を次タスク候補（`.claude-plugin/marketplace.json` 作成）に置き換え。
- 2026-04-26: タスク完了。本リポジトリは git リポジトリではないため、PR 作成手順はスキップ。
