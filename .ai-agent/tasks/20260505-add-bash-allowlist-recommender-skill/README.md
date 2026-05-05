# Bash 許可リスト推薦スキルの追加

## 目的・ゴール

`plugins/agent-coach/` プラグインに、ユーザーの transcript を分析して `permissions.allow` に未登録の Bash コマンドパターンを抽出・推薦するスキルを追加する。

ユーザーが auto mode で運用していると、`permissions.allow` に含まれていない Bash コマンドもプロンプトなしで実行される。「実際に走った」コマンドのうち allowlist 化していないパターンを一覧化することで、他のモード（default / acceptEdits）に切り替えても同等の体験を得るための allowlist 整備を支援する。

## 実装方針

### スキル配置

- ディレクトリ: `plugins/agent-coach/skills/recommend-bash-allowlist/`
- 本体: `SKILL.md`
- agent-coach プラグインに同居（同プラグインは「Claude Code 利用ログを分析して改善提案する」軸）

### 分析ロジック（SKILL.md に記述）

1. **対象セッション特定**: agent-coach と同じ規約（cwd → `~/.claude/projects/<encoded-cwd>/` 配下、最新 N セッション、実行中セッションは除外）
2. **permission-mode 区間の構築**: `type == "permission-mode"` のレコードを順に走査し、各セッションで「あるターン時点の permissionMode」を判定
3. **Bash tool_use 抽出**: 各 `tool_use` (name=Bash) について、その時点の permissionMode を割り当てる
4. **対象モードの絞り込**: `auto` および `bypassPermissions` 下で実行されたコマンドのみ
5. **allowlist 突合**: 現在の `permissions.allow` を以下から取得して結合
   - `~/.claude/settings.json`
   - `<repo>/.claude/settings.json`
   - `<repo>/.claude/settings.local.json`
   - 各エントリは `Bash(<prefix>:*)` 形式 — 同形式で前方一致判定
6. **prefix 粒度**: readonly/write の判別が可能な深さで抽出
   - 単純コマンド（`ls`, `cat`, `find`, `grep` 等）→ 1 トークン
   - サブコマンド体系のツール（`git`, `gh`, `npm`, `aws`, `kubectl`, `docker`, `brew`, `mas`, `nix`, `npx`, `pnpm`, `yarn`, `cargo`, `gcloud`, `az`, `terraform` 等）→ 2〜3 トークン
   - 既存 allowlist 慣例に合わせる（`Bash(git log:*)`, `Bash(aws s3 ls:*)`, `Bash(gh pr view:*)` など）
7. **readonly/write 分類**: prefix を curated キーワードで分類（log/status/show/view/get/list/diff/describe/check/test/lint → readonly、install/add/push/commit/merge/rm/mv/cp/delete/remove/update/create/build/exec → write、その他 → unknown）

### 出力形式

agent-coach 同様、レポートを `.ai-agent/tmp/<YYYYMMDD>-bash-allowlist/report.md` に書き出す。画面には:

- レポートパス
- 推薦パターン TOP 50（readonly / write / unknown の 3 グループに分けて、頻度 + 代表例 1 行）

### スキル description

“Use when …” トリガを含めた 1〜2 文。agent-coach の description トーンに揃える。

## 完了条件

- [x] `plugins/agent-coach/skills/recommend-bash-allowlist/SKILL.md` が存在する
- [x] YAML フロントマターが `scripts/validate-skills.py` を pass する（`Checked 20 file(s): 0 error(s)`）
- [x] `description` に "Use when ..." 形式のトリガ条件が含まれる
- [x] `.ai-agent/structure.md` に新スキルディレクトリが反映されている
- [ ] PR が作成されている

## 作業ログ

- 2026-05-05: トリアージ実施。要件明確・1 ブランチ・1 PR 規模のため `/autodev-start-new-task` のまま続行と判断
- 2026-05-05: transcript の `type: permission-mode` レコードでモード区間を判定できることを確認
- 2026-05-05: ユーザー方針確認（TOP 50 / readonly-write 判別可能な prefix 粒度 / bypassPermissions も対象）
- 2026-05-05: ブランチ `feature/add-bash-allowlist-recommender-skill` 作成
- 2026-05-05: `plugins/agent-coach/skills/recommend-bash-allowlist/SKILL.md` 作成。サブコマンド体系ツールの深さ表と readonly/write キーワード分類を内包
- 2026-05-05: `.ai-agent/structure.md` 更新
- 2026-05-05: `scripts/validate-skills.py` 実行 → 0 errors
- 2026-05-05: `.claude/skills/recommend-bash-allowlist/skill.md` を `plugins/agent-coach/skills/recommend-bash-allowlist/SKILL.md` への相対 symlink として作成（本リポジトリ自体でも利用可能に）。structure.md も追記
