# スキル/サブエージェントの未トリガ検出スキルの追加

## 目的・ゴール

`plugins/agent-coach/` プラグインに、ユーザーの transcript を分析して**スキル / サブエージェントが本来トリガされるべきだったのにトリガされていないシーン**を検出し、各スキル/サブエージェントの `description` 改善案を提示するスキルを追加する。

既存 `agent-coach` スキルは観点 5 として「スキル未活用」を扱うが、サマリ提示にとどまる。本スキルは観点 5 を**深掘り専用**としてフォーカスし、以下を提供する:

- 利用可能スキル/サブエージェントの一覧を transcript の system reminder から抽出
- ユーザーリクエストごとに「本来はどのスキル/サブエージェントが適切だったか」を判定
- 実際に `Skill` / `Agent` ツールが呼ばれたかを照合し、**未トリガ事例**を抽出
- 各スキル/サブエージェントについて、`description` の triggering ロジック改善案（「Use when ...」テンプレ、不足キーワード追加、競合 description との区別明示など）を提示
- 文面で繰り返し外れる場合は **Hook での決定論的強制**または skill-creator による triggering 最適化を案内

## 実装方針

### スキル配置

- ディレクトリ: `plugins/agent-coach/skills/detect-missed-skill-triggers/`
- 本体: `SKILL.md`
- agent-coach プラグインに同居（`detect-context-rot`、`recommend-bash-allowlist` と並ぶ「特化型分析スキル」）
- 既存 agent-coach の観点 5 はそのまま残し、本スキルへの相互参照を SKILL.md と handbook に追記

### スキル名と description

- 名前: `detect-missed-skill-triggers`
- description (英語、Use when ... トリガ含む): 利用可能スキル/サブエージェント一覧を transcript から復元し、ユーザーリクエストとの突合で未トリガ事例を抽出、description 改善案を提示する旨を記述

### 分析ロジック（SKILL.md に記述）

1. **対象セッション特定**: agent-coach / detect-context-rot / recommend-bash-allowlist と同じ規約（cwd → `~/.claude/projects/<encoded-cwd>/` 配下、最新 N セッション、実行中セッションは除外）。本スキルは未トリガパターンの集約を目的とするため**デフォルトで最新 5〜10 セッション**

2. **利用可能スキル/サブエージェント一覧の抽出**:
   - `type == "system"` の reminder の中で `The following skills are available for use with the Skill tool:` で始まる節を取得
   - 各 entry の `name` と `description` を構造化
   - サブエージェント（`Task` ツールの `subagent_type` 引数）も同様に Agent ツール定義から抽出
   - セッション中に skill 一覧が更新される場合（plugin install 等）に備え、最後に観測したスナップショットを採用するか、各 user 入力時点のスナップショットを保持

3. **未トリガ判定（ユーザー入力単位）**:
   - 各 `type == "user"` メッセージから「目的キーワード」を抽出（短文の場合はそのまま、長文の場合は冒頭+目立つ動詞句）
   - 利用可能スキル一覧の `description` と意味マッチング（キーワードマッチ + Use when 節とのマッチを Claude の判断で行う）
   - 同じターン以降で `Skill` ツールが呼ばれているかを確認
   - サブエージェントについては `Agent` ツール（`subagent_type` 指定）が適切に呼ばれたかを判定。重い調査・パラレルタスクは Explore / general-purpose サブエージェントが妥当
   - 未トリガと判定したケースを「ユーザー入力テキスト」「マッチした候補スキル/サブエージェント」「実際の Claude の対応」の 3 点組で記録

4. **集約とパターン化**:
   - 同じスキル/サブエージェントが複数セッション・複数ユーザー入力で未トリガなら **未トリガパターン**としてまとめる
   - 競合（似た description が複数あって判別できなかったと推定）、キーワード不足（description に明示されていない単語をユーザーが多用）、知名度不足（一度も呼ばれていない）の 3 種に分類

5. **description 改善案の生成**:
   - 各未トリガパターンに対して、Use when 節の追加・キーワード追加・他スキルとの区別明示などの**書き換え案**を提示
   - 雛形例:
     - `Use when X, Y, or Z (not just A or B).`
     - `Use this for <user-keyword-1>, <user-keyword-2>, or anything matching <pattern>.`
     - `Distinct from <other-skill>: this handles <specific-aspect>.`
   - 文面改善で繰り返し外れる場合は Hook 化（UserPromptSubmit hook で `<system-reminder>` を注入する等）を案内

### 出力形式

レポートは画面に直接ダンプせず、ファイルに書き出す:

1. 出力ディレクトリ: `.ai-agent/tmp/<YYYYMMDD>-skill-triggers/`（cwd 基準）
2. レポート本文: `<出力ディレクトリ>/report.md`
3. 画面には以下のみ表示:
   - レポートファイルパス
   - 未トリガパターン数 (skills: N / subagents: M)
   - 推奨アクション TOP3（description 改善案 / Hook 化 / skill-creator 利用などから優先）

#### レポート構造

```markdown
# 未トリガ検出レポート

対象: <セッション一覧と期間>
利用可能スキル: N 件 / サブエージェント: M 件
ユーザー入力総数: <X>

## TL;DR
- 未トリガ: <skills: A / subagents: B>
- 主因: <キーワード不足 / description 競合 / 知名度不足>
- 推奨アクション TOP3 は末尾

## 未トリガパターン

### パターン 1: <スキル/サブエージェント名> (<未トリガ件数>)
**起きていること**: <2-3 行の概要 + 代表ユーザー入力 1-2 件>

**推定原因**: <キーワード不足 / 競合 / 知名度不足>

**現状の description**:
> <抜粋>

**改善案**:
```yaml
description: <改善後の description>
```

(または Hook 化提案)

(以下、パターンごとに繰り返し)

## その他の気づき
- <1 行ずつ、最大 5 件>

## 統計サマリ
- セッション数 / ユーザー入力数 / 未トリガ件数

## 誤検出の可能性
- <ユーザーが skill を意図的に使わなかったケース、ユーザー指定で別のアプローチを取ったケースなど>

## 推奨アクション TOP3
1. ...
```

## 完了条件

- [x] `plugins/agent-coach/skills/detect-missed-skill-triggers/SKILL.md` が存在する
- [x] YAML フロントマターが `scripts/validate-skills.py` を pass する（`Checked 22 file(s): 0 error(s)`）
- [x] `description` に "Use when ..." 形式のトリガ条件が含まれる
- [x] 既存 agent-coach の観点 5 セクションに本スキルへの相互参照を追記（SKILL.md 本体 + reference/handbook.md）
- [x] `.ai-agent/structure.md` に新スキルディレクトリが反映されている
- [x] `.claude/skills/detect-missed-skill-triggers/skill.md` を本体への相対 symlink として作成
- [x] PR が作成されている (#11)

## 作業ログ

- 2026-05-05: トリアージ実施。要件明確・1 PR 規模のため `/autodev-start-new-task` のまま続行と判断
- 2026-05-05: タスク README 作成、ブランチ `add-skill-trigger-detector-skill` を切る
- 2026-05-05: `plugins/agent-coach/skills/detect-missed-skill-triggers/SKILL.md` 作成。利用可能スキル/サブエージェント一覧の transcript からの復元、ユーザー入力との意味マッチによる未トリガ判定、3 原因分類（キーワード不足 / description 競合 / 知名度不足）、description 書き換え案生成、Hook / skill-creator 化案内まで内包
- 2026-05-05: 既存 agent-coach `SKILL.md` 観点 5 と `reference/handbook.md` 観点 5 に detect-missed-skill-triggers への案内を追記
- 2026-05-05: `.ai-agent/structure.md` 更新（plugins ツリー + .claude/skills 両方）
- 2026-05-05: `.claude/skills/detect-missed-skill-triggers/skill.md` を `plugins/agent-coach/skills/detect-missed-skill-triggers/SKILL.md` への相対 symlink として作成
- 2026-05-05: `scripts/validate-skills.py` 実行 → 0 errors（22 ファイル検査）
