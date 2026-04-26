# add-agent-coach-skill

## 目的・ゴール

Claude Code の transcript（直近の対話履歴）を分析し、ユーザーのプロンプト・スキル定義・メモリ・コンテキスト管理に対する改善提案を行うスキル `agent-coach` を新規プラグインとして追加する。

### 解決したい課題

- ユーザーが書いたプロンプトに対して Claude が方向修正を何度も受けている → プロンプト自体の改善余地がある
- 既存スキル/メモリの指示が守られていない → 指示の書き方に問題がある
- コンテキストロット（履歴の肥大化・重要情報の埋没）が起きている → コンテキスト管理戦略の見直しが必要
- 本来使われるべきスキルが triggering されていない → スキル description の改善余地がある
- 直近のトークン消費が大きい箇所 → コスト hot spot の可視化

これらをユーザーが自力で transcript を読んで気付くのは大変なので、エージェント自身に分析させて改善提案させる。

## スコープ

### このタスクで作るもの

- 新規プラグイン `plugins/agent-coach/`
  - `.claude-plugin/plugin.json`
  - `skills/agent-coach/SKILL.md`
- `.claude-plugin/marketplace.json` への登録
- `README.md` への記載追加

### このタスクでやらないこと

- 自動化（hooks 等によるトリガ）— ユーザーが明示的に呼ぶスキルとして実装
- transcript からの構造化出力データベース化 — 単発の分析レポート生成にとどめる
- 過去全期間の網羅分析 — 「直近のセッション」or「ユーザー指定範囲」を対象とする

## 実装方針

### スキルの動作モデル

**runtime に Claude が transcript を読んで分析する** 設計。前処理スクリプトは持たず、SKILL.md に「どこを読み」「何を観点に分析し」「どう報告するか」を記述する。

理由:
- transcript の JSONL は Claude が直接読める
- 分析は判断を伴うので LLM 自身がやる方が柔軟
- スクリプトを増やすとメンテ対象が増える

### 分析観点（5本柱）

1. **トークン消費 hot spot**: メッセージごとのサイズ／ツール結果のサイズを集計し、上位を抽出
2. **方向修正多発プロンプト**: ユーザーの "no", "stop", "instead", "actually" 等のシグナル + 連続コレクション → 元プロンプトの曖昧さを指摘し、Claude 公式プロンプトベストプラクティスに沿った改善案を提示
3. **指示違反**: スキル/メモリで明示されたルールに対する違反パターン → 指示文の明確化提案（より具体的に、why を加える、配置場所の見直し等）
4. **コンテキストロット**: ターン数の増加に伴う初期指示の忘却、サブエージェント未活用、巨大ファイルの全文読込み等 → plan/サブエージェント/要約の活用提案
5. **スキル未活用**: ユーザー要求のキーワードと利用可能スキルの description の不一致による未起動 → スキル description の triggering 改善案

### 参照する公式ベストプラクティス

実装中に確定（要調査）:
- Anthropic 公式の Prompt engineering ガイド（docs.anthropic.com）
- Claude Code Skills のベストプラクティス（code.claude.com/docs）
- 本リポジトリ内の関連 steering（無ければ参照しない）

SKILL.md には「これらのリソースを参照して提案する」と記述し、URL 直書きは最小限にする（リンク切れリスク）。

### transcript の場所

調査が必要だが、macOS では `~/.claude/projects/{encoded-cwd}/{session-id}.jsonl` に保存されている想定。SKILL.md 内で場所と JSONL フォーマットの最低限の説明を行う。

## 完了条件

- [x] `plugins/agent-coach/.claude-plugin/plugin.json` を作成
- [x] `plugins/agent-coach/skills/agent-coach/SKILL.md` を作成（5観点の分析手順を含む）
- [x] `.claude-plugin/marketplace.json` に `agent-coach` を登録
- [x] `README.md` に説明を追加
- [x] `python3 scripts/validate-skills.py` がパスする
- [x] 実際にこのリポジトリの直近 transcript に対してスキルを動かしてみて、有用な提案が出るか軽く確認（集計ロジックの動作確認まで実施）
- [x] structure.md を更新（新プラグイン追加を反映）
- [x] PR 作成（<https://github.com/mizunashi-mana/agent-skills/pull/5>）

## 作業ログ

### 2026-04-26

- トリアージ: start-new-task のままで進行可と判断（スキル1つ追加で完結）
- 命名議論: `transcript-review` 案を提示 → ユーザー指摘により `agent-coach`（手段ではなく目的を表す）を採用
- README 作成
- ブランチ作成: `feature/add-agent-coach-skill`
- transcript JSONL フォーマット調査（`type` 種別、`assistant.message.usage` の token フィールド構成を把握）
- `plugins/agent-coach/` プラグイン雛形作成（plugin.json, SKILL.md）
- SKILL.md 本体作成（5観点の分析手順、レポート構造、注意事項）
- `.claude/skills/agent-coach/skill.md` を SKILL.md へのシンボリックリンクとして作成（自リポジトリでの利用用）
- `.claude-plugin/marketplace.json` / `README.md` / `.ai-agent/structure.md` 更新
- `scripts/validate-skills.py` パス確認（Checked 19 file(s): 0 error(s)）
- スモークテスト: 直近 3 セッションの token 集計が成功（最大 220 ターン / cache_read 約 2000 万トークンを検出）
- 自セッション特定ヒューリスティックを SKILL.md に明記（mtime 最新 = 実行中とみなして除外）
- 第1回 PR レビュー（#5）の指摘 5 件を対応: 4 件修正（543ec57）、1 件は別 issue 化方針でスキップ
- サーベイ `.ai-agent/surveys/20260426-claude-code-best-practices/` を基準に再レビュー実施
- B1 方針で SKILL.md 全面更新（f402b41）: 観点 0 シークレット検出を独立化、観点 3 にハーネス化判断基準追加、レポートテンプレに重大度・根拠フィールド必須化、Tier 表追加、サーベイへの内部リンク追加、MCP 過多シグナル / 2回補正運用提案 / 量的根拠 / cache miss why を追記
- スコープ外として 2 件の follow-up issue を起票:
  - #6: examples/ にサンプル jsonl 配置（regression test 化）
  - #7: validate-skills.py の description 長/triggering チェック追加
