# タスク: `.claude-plugin/marketplace.json` の作成

## 目的・ゴール

Claude Code のプラグインマーケットプレイス機能で `agent-skills` リポジトリを配布できるようにする。
`.claude-plugin/marketplace.json` を作成し、公開対象のスキルをプラグインとして登録する。

## 背景

- `plan.md` の Phase 1 で「進行中」とされているタスク
- `tech.md` ではバンドル候補として以下 2 つが定義されている
  - `autodev`: autodev-init スキル（サブスキルテンプレートを含む）
  - `merge-dependabot-bump-pr`: Dependabot PR マージスキル

## 検討事項: ディレクトリ構造の選択

Claude Code プラグインの公式構造は以下の通り（`anthropics/claude-plugins-official` を参照）:

```
<plugin-dir>/.claude-plugin/plugin.json     # プラグインメタデータ（必須）
<plugin-dir>/skills/<skill-name>/SKILL.md   # プラグインに含まれるスキル
<plugin-dir>/agents/, commands/, hooks/...  # その他コンポーネント（任意）
```

一方、本リポジトリの現状 / steering の `tech.md`・`structure.md` での想定:

```
skills/<skill-name>/SKILL.md   # 直接トップレベルに skill を配置
```

両者は階層が異なるため、いずれかの調整が必要。候補:

### Option A: プラグイン中心へ再構成

```
plugins/autodev/.claude-plugin/plugin.json
plugins/autodev/skills/autodev-init/SKILL.md
plugins/autodev/skills/autodev-init/templates/...
plugins/merge-dependabot-bump-pr/.claude-plugin/plugin.json
plugins/merge-dependabot-bump-pr/skills/merge-dependabot-bump-pr/SKILL.md
```

- ✅ Claude Code 公式パターンに完全準拠
- ✅ プラグインとスキルの境界が明確
- ⚠️ `skills/` トップレベルから `plugins/` 配下へ移動する大きな構造変更
- ⚠️ steering の `tech.md` / `structure.md` の更新が必要

### Option B: 既存 `skills/<name>/` をプラグイン化

```
skills/autodev-init/.claude-plugin/plugin.json
skills/autodev-init/SKILL.md           # 既存
skills/autodev-init/skills/autodev-init/SKILL.md  # 重複 or 移動
```

- ⚠️ プラグインローダーが `skills/<plugin>/skills/<skill>/SKILL.md` を期待する場合は重複が発生
- ⚠️ 「skill」「plugin」の概念が混在し可読性が下がる
- 移動量は少ないが構造が不自然

### Option C: 現状維持＋marketplace のみ

`skills/<name>/` をそのまま `marketplace.json` の `source` として参照し、`.claude-plugin/plugin.json` のみ追加。
プラグインローダーがプラグインルート直下の `SKILL.md` を発見できるかは未確認。

## 実装方針（Option A 採用予定 / 要ユーザー確認）

1. ディレクトリを `skills/` → `plugins/<plugin>/skills/<skill>/` に再構成
2. 各プラグインに `.claude-plugin/plugin.json` を追加
3. `.claude-plugin/marketplace.json` を作成し、両プラグインを登録
4. `.ai-agent/steering/tech.md` と `.ai-agent/structure.md` を新構造に合わせて更新
5. `README.md` のインストール手順を marketplace 経由の形に更新

## 完了条件

- [x] `.claude-plugin/marketplace.json` が作成され、両プラグインが登録されている
- [x] 各プラグインに `.claude-plugin/plugin.json` が存在する
- [x] `tech.md` / `structure.md` が新構造を反映している
- [x] `README.md` でマーケットプレイス経由のインストール方法が説明されている
- [ ] PR が作成されている

## 作業ログ

- 2026-04-26: タスク作成、構造選択肢を整理
- 2026-04-26: ユーザー承認のもと Option A（plugins/ 配下に再構成）+ 2 バンドル構成を採用
- 2026-04-26: `git mv` で skills/ → plugins/<plugin>/skills/<skill>/ へ再構成
- 2026-04-26: `plugins/autodev/.claude-plugin/plugin.json` と `plugins/merge-dependabot-bump-pr/.claude-plugin/plugin.json` を作成
- 2026-04-26: `.claude-plugin/marketplace.json` を作成（autodev / merge-dependabot-bump-pr の 2 プラグインを登録）
- 2026-04-26: `tech.md` / `structure.md` / `plan.md` / `README.md` を新構造に合わせて更新
- 2026-04-26: JSON ファイルの構文をバリデート済み
