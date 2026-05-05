# agent-coach umbrella スキルの削除と特化スキル間相互参照の除去

## 目的・ゴール

agent-coach プラグイン内の umbrella スキル `agent-coach` を削除し、特化された 5 スキル（`detect-context-rot` / `detect-token-hotspots` / `detect-rework-and-violations` / `detect-missed-skill-triggers` / `recommend-bash-allowlist`）が単独で完結するよう、agent-coach への言及および姉妹スキル間の関係性記述をすべて除去する。

## 背景

- 観点を分解した特化スキルにすることで分析精度が高まると判断し、5 スキルへ分解済み。
- 単一の特化スキル呼び出し時に umbrella スキルや他特化スキルの記述が context にロードされると、当該タスク遂行に無関係な情報が乗ってコンテキストロットの一因になる。
- agent-coach プラグイン本体（5 スキルの束）は維持する。削除対象は umbrella スキル定義のみ。

## 実装方針

### 削除対象

- `plugins/agent-coach/skills/agent-coach/SKILL.md`
- `plugins/agent-coach/skills/agent-coach/reference/handbook.md`
- `plugins/agent-coach/skills/agent-coach/reference/`（空になる）
- `plugins/agent-coach/skills/agent-coach/`（空になる）
- `.claude/skills/agent-coach/skill.md`（symlink、リンク切れになるため）
- `.claude/skills/agent-coach/`（空になる）

### 修正対象（agent-coach 言及・姉妹スキル相互参照の除去）

- `plugins/agent-coach/skills/detect-context-rot/SKILL.md`
- `plugins/agent-coach/skills/detect-token-hotspots/SKILL.md`
- `plugins/agent-coach/skills/detect-rework-and-violations/SKILL.md`
- `plugins/agent-coach/skills/detect-missed-skill-triggers/SKILL.md`
- `plugins/agent-coach/skills/recommend-bash-allowlist/SKILL.md`（言及なしの可能性大、念のため確認）

各スキルから以下を除去:

- 「`agent-coach` の観点 X が...」「`agent-coach` の総合健康診断で...」など umbrella を前提とした文言
- 「`detect-context-rot` との関係」「`detect-missed-skill-triggers` との関係」など姉妹スキル節
- 「（agent-coach 観点 0 と同じ方針）」のような注釈
- 分析手順中で他スキルの結果との整合を求める指示

### メタ情報の更新

- `README.md` の Key Skills セクションから umbrella としての `agent-coach` 表現を削除し、agent-coach プラグインを「分析特化スキル群」として再表現。
- `.ai-agent/structure.md` の agent-coach プラグインツリーから `agent-coach/SKILL.md` 行を削除。`.claude/skills/agent-coach` 行も削除。
- `plugins/agent-coach/.claude-plugin/plugin.json` の `description` を、umbrella スキル説明ではなく束のテーマ説明に書き換え。
- `.claude-plugin/marketplace.json` の agent-coach plugin entry の `description` も同様に更新。

### CI 検証

- `python3 scripts/validate-skills.py` を実行して frontmatter / JSON Schema が壊れていないことを確認。

## 完了条件

- [x] `plugins/agent-coach/skills/agent-coach/` が削除されている
- [x] `.claude/skills/agent-coach/` が削除されている（リンク切れ防止）
- [x] 5 つの特化スキル SKILL.md から `agent-coach` への言及が消えている（`grep -n agent-coach` で 0 件）
- [x] 特化スキル相互の関係性記述（「〜との関係」節、姉妹スキルへの送り出し指示）が消えている
- [x] README.md / structure.md / plugin.json / marketplace.json の記述が新構造と整合している
- [x] `validate-skills.py` がパスする
- [x] PR を作成

## 作業ログ

- 2026-05-05: タスク開始、トリアージ完了（このスキルで続行）
- 2026-05-05: ブランチ `delete-agent-coach-umbrella-skill` 作成
- 2026-05-05: agent-coach スキル本体（SKILL.md + handbook）と `.claude/skills/agent-coach/` symlink 削除
- 2026-05-05: 5 特化スキルから agent-coach 言及および姉妹スキル名参照を除去。`detect-rework-and-violations` のロット起因の議論はスキル名を伴わない抽象表現に書き換えて保持
- 2026-05-05: README / structure.md / plugin.json / marketplace.json を新構造に合わせて更新
- 2026-05-05: `python3 scripts/validate-skills.py` パス（23 ファイル / 0 エラー）
