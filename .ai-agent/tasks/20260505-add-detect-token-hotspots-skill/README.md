# Add detect-token-hotspots skill

## 目的・ゴール

`agent-coach` プラグインに、transcript JSONL からトークン消費を分析し、**消費の激しいターン・パターン**を検出して具体的な改善提案を出す深掘りスキル `detect-token-hotspots` を追加する。

`agent-coach` の観点 1（トークン消費 hot spot）が「サマリ提示」止まりなのに対し、本スキルは:

1. ターン単位のトークン内訳（input / output / cache_creation / cache_read / tool_result サイズ）を集計
2. hot spot ターン TOP N を抽出（cache miss 多発 / 巨大 tool_result / output 過多 など複数軸）
3. クロスセッションで反復する高消費パターン（同一ファイル再 Read、巨大 Bash 出力、MCP ツール定義肥大、サブエージェント未活用）を集約
4. 改善提案を 5 カテゴリで具体化:
   - (a) ツール呼び出し方法（offset/limit、Grep 置換、Bash 出力絞り）
   - (b) サブエージェント委譲（Explore / general-purpose）
   - (c) cache 戦略（cache miss 削減、長期セッションの分割）
   - (d) MCP 切り離し（不要 MCP の disabledMcpServers 化）
   - (e) 断点（/clear, /compact）

## 実装方針

### スキルの位置づけ

- パス: `plugins/agent-coach/skills/detect-token-hotspots/SKILL.md`
- 開発用 symlink: `.claude/skills/detect-token-hotspots/skill.md` → `../../../plugins/agent-coach/skills/detect-token-hotspots/SKILL.md`
- frontmatter 構造は既存の `detect-context-rot` / `detect-missed-skill-triggers` と揃える

### スキル本文の構成（手順）

1. 分析対象セッションの決定（mtime 降順最新 5〜10、実行中除外）
2. JSONL 構造把握（`assistant.message.usage`, `tool_use`, `tool_result` の対応関係）
3. ターン単位の指標抽出
   - usage 4 種（input / output / cache_creation / cache_read）
   - tool_result サイズ（直前 tool_use と紐付け）
   - tool 種別（Read / Bash / Grep / Glob / Agent / Skill / MCP）
4. hot spot 抽出（複数軸、それぞれ TOP N）
   - 軸 A: cache_creation_input_tokens TOP 10 ターン
   - 軸 B: tool_result サイズ TOP 10 ターン
   - 軸 C: output_tokens TOP 10 ターン
   - 軸 D: cache miss 比率（cache_creation / (cache_creation + cache_read)）が高いターン
5. クロスセッション集約
   - 同一ファイル再 Read（ファイル別総 Read 回数 / 累積文字数）
   - 巨大 Bash 出力の発生コマンドパターン
   - MCP ツール定義の system reminder 文字数
   - 連続実装ターンで Agent 未呼び出しのケース
6. 改善カテゴリへのマッピング（A〜E、`detect-context-rot` の改善提案 5 分類と整合）
7. レポート生成（`.ai-agent/tmp/<YYYYMMDD>-token-hotspots/report.md`、画面には TL;DR + TOP3 + パスのみ）
8. 実装ヒント（python3 ヒアドキュメント骨格）

### 関連スキルとの差異

| スキル | 主目的 | 本スキルとの関係 |
| --- | --- | --- |
| `agent-coach` 観点 1 | トークン消費の総括的サマリ | 本スキルが深掘り版 |
| `detect-context-rot` | 履歴肥大による劣化検出 | rot ≒ 累積トークン増だが、本スキルは「単一ターンの hot spot」「カテゴリ別改善」が主軸。両者は補完関係 |
| `recommend-bash-allowlist` | Bash 実績から allowlist 抽出 | 直接の関係なし |

`detect-context-rot` と独立スキルとする根拠: rot はセッション後半の劣化現象（時系列）に焦点、本スキルはターン単位の単発・反復消費（点 + 集約）に焦点。両方が同じ巨大 tool_result を別観点で扱うことはあるが、改善提案の主眼が異なる（rot は断点/MEMORY 移行、本スキルはツール置換/委譲）。

## 完了条件

- [x] `plugins/agent-coach/skills/detect-token-hotspots/SKILL.md` が作成され、frontmatter が validate-skills.py を通る
- [x] `.claude/skills/detect-token-hotspots/skill.md` symlink が張られている
- [x] `.ai-agent/structure.md` の `plugins/agent-coach/skills/` ツリーと `.claude/skills/` ツリーに本スキルが追記されている
- [x] `agent-coach` SKILL.md の観点 1 末尾に `detect-token-hotspots` への深掘り誘導が追加されている
- [x] `python3 scripts/validate-skills.py` がエラーなく通る
- [ ] PR が作成され、CI（lint workflow）が通る

## 作業ログ

- 2026-05-05: タスク開始。トリアージで「具体的な実装タスク」と判定、そのまま続行。既存 `detect-*` 3 スキルの構造を踏襲して実装する方針。
- 2026-05-05: SKILL.md を作成（軸 A〜E の hot spot 抽出、クロスセッション集約、改善提案 5 カテゴリ）。symlink・structure.md・agent-coach SKILL.md を更新。validate-skills.py 通過確認。
