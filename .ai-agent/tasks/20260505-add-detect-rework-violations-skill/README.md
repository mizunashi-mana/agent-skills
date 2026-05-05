# 手戻り・指示違反検知スキルの追加

## 目的・ゴール

`agent-coach` プラグインに、transcript から **手戻り（方向修正ループ）** と **指示違反（CLAUDE.md / SKILL.md / memory のルール違反）** を検知し、その分析と改善提案を行う深掘りスキル `detect-rework-and-violations` を追加する。

`agent-coach` 観点 2（方向修正多発プロンプト）と観点 3（指示違反）はサマリ提示にとどまっているが、本スキルは深掘り版として:

- 手戻りパターン（補正ループ・差し戻し・「やり直し」指示）を 3 点組（元プロンプト → 誤解 → 修正）で抽出
- 指示違反を「ルール抽出 → 違反検出 → 主因分類」で構造化
- 改善案を 5 カテゴリ（プロンプト書き換え / ルール明文化 / Hook 化 / 巻き戻し運用 / skill description 改善）に分類して具体的な書き換え案を提示

## 実装方針

### 配置

- 本体: `plugins/agent-coach/skills/detect-rework-and-violations/SKILL.md`
- リポジトリ自身での試用用 symlink: `.claude/skills/detect-rework-and-violations` → 上記 SKILL.md

### SKILL.md 構成（既存 detect-* スキルに揃える）

1. 概要（agent-coach 観点 2/3 との関係、姉妹スキルとの違い）
2. 前提条件
3. 手順
   1. 分析対象セッションの決定（最新 5〜10 セッション、実行中除外）
   2. JSONL 構造把握（手戻り・違反検出に使うフィールド）
   3. ルール抽出（CLAUDE.md / SKILL.md / memory / system reminder からの「必ず X」「Y してはいけない」抽出）
   4. シグナル抽出
      - 手戻りシグナル（否定語・短い即時返信・繰り返し再指示・"Wait..." 確認パターン・タスク完了後の差し戻し）
      - 違反シグナル（抽出ルールと assistant 行動の突合）
   5. 3 点組（元プロンプト → Claude 解釈 → ユーザー修正）の抽出
   6. パターン化（主因分類: 曖昧プロンプト / ルール埋没 / 検証なし完了 / トリガミス / コンテキストロット起因）
   7. 改善提案カテゴリへのマッピング（A〜E）
   8. レポート生成（`.ai-agent/tmp/<YYYYMMDD>-rework-violations/report.md` に書き出し、画面は TL;DR + TOP3 + パスのみ）
   9. 実装ヒント（python3 ヒアドキュメントの骨格）
4. 注意事項

### 連携・整合

- `agent-coach` の SKILL.md 観点 2 / 観点 3 セクションに「深掘りツール」案内を追加
- `agent-coach` の handbook.md 観点 2 / 観点 3 セクションに「深掘りツール」節を追加
- `.ai-agent/structure.md` のディレクトリツリーに新スキルを追記
- description トーンと TL;DR 構造を既存 detect-* と統一

## 完了条件

- [x] `plugins/agent-coach/skills/detect-rework-and-violations/SKILL.md` を作成
- [x] `.claude/skills/detect-rework-and-violations` symlink を作成
- [x] `agent-coach` SKILL.md に深掘りツール案内を追加（観点 2 / 観点 3）
- [x] `agent-coach` handbook.md に深掘りツール節を追加（観点 2 / 観点 3）
- [x] `.ai-agent/structure.md` を更新
- [x] `scripts/validate-skills.py` を通過（YAML フロントマター検証）
- [ ] PR を作成

## 作業ログ

- 2026-05-05: タスク開始。トリアージ → 単独 PR で完結する実装タスクと判断。
- 2026-05-05: SKILL.md（522 行）作成。既存 detect-* スキルの構造（概要 → 前提条件 → 手順 1〜8 → 注意事項）に揃え、姉妹スキル（detect-context-rot / detect-token-hotspots / detect-missed-skill-triggers）との関係を概要に明記。
- 2026-05-05: `.claude/skills/detect-rework-and-violations/skill.md` を `../../../plugins/agent-coach/skills/detect-rework-and-violations/SKILL.md` への symlink で作成（既存 detect-* と同パターン）。
- 2026-05-05: `agent-coach` SKILL.md の観点 2 / 観点 3 セクション末尾に「深掘りツール」案内を追加。本スキルが両観点を統合している旨を明記。
- 2026-05-05: handbook.md の観点 2 / 観点 3 セクションに「深掘りツール」節を追加（観点 1/4/5 と同形式）。
- 2026-05-05: `.ai-agent/structure.md` のディレクトリツリー 2 箇所（`.claude/skills/` symlink 一覧と `plugins/agent-coach/skills/` 一覧）に新スキルを追記。
- 2026-05-05: `python3 scripts/validate-skills.py` 通過（24 ファイル / 0 エラー）。frontmatter の `description` は 631 文字、`allowed-tools` は `Bash, Read, Write, Glob, Grep`。
