# Claude Code ベストプラクティス調査

## 調査の問い

- Claude Code を効果的に使いこなすためのベストプラクティスは何か
- 1M コンテキスト時代におけるセッション管理・スキル設計・ハーネス設計の指針
- 本リポジトリ `agent-skills`（特に `agent-coach` のようなプロンプト改善スキル）が「ユーザーの利用履歴を分析して改善提案する」とき、何を観察し、何を根拠に何を提案すべきか

## 背景

- 本リポジトリ `agent-skills` は Claude Code プラグイン（スキル群）を配布する場所
- `agent-coach` スキルは transcript を分析して 5 観点（トークン hot spot / 方向修正 / 指示違反 / コンテキストロット / スキル未活用）から提案するもの
- これらの提案を「公式ベストプラクティスに基づく」根拠付きで行うため、観点ごとに知見を整理しておく必要がある

## ファイル構成

| ファイル | テーマ | agent-coach のどの観点に対応 |
| --- | --- | --- |
| [01-context-and-session.md](01-context-and-session.md) | コンテキストウィンドウとセッション運用 | 観点 1 (トークン hot spot), 4 (コンテキストロット) |
| [02-prompt-design.md](02-prompt-design.md) | プロンプト設計とコミュニケーション | 観点 2 (方向修正多発プロンプト) |
| [03-extensions.md](03-extensions.md) | CLAUDE.md / Skill / Subagent / Hook の使い分けと設計 | 観点 3 (指示違反), 5 (スキル未活用) |
| [04-harness-engineering.md](04-harness-engineering.md) | 「仕組みで品質強制」のハーネス視点 | 横断 |
| [05-failure-patterns-and-signals.md](05-failure-patterns-and-signals.md) | アンチパターンと transcript 上の検出シグナル | 全観点 |
| [06-coach-checklist.md](06-coach-checklist.md) | プロンプト改善スキル用の統合チェックリスト | 全観点（統合） |

## 一次ソース

### 公式ドキュメント

- [Best practices for Claude Code](https://code.claude.com/docs/en/best-practices)
- [How Claude Code works](https://code.claude.com/docs/en/how-claude-code-works)
- [Extend Claude with skills](https://code.claude.com/docs/en/skills)
- [Create custom subagents](https://code.claude.com/docs/en/sub-agents)
- [Hooks reference](https://code.claude.com/docs/en/hooks)
- [Explore the .claude directory](https://code.claude.com/docs/en/claude-directory)
- [Memory (CLAUDE.md)](https://code.claude.com/docs/en/memory)
- [Permissions](https://code.claude.com/docs/en/permissions)
- [Common workflows](https://code.claude.com/docs/en/common-workflows)
- [Plugins](https://code.claude.com/docs/en/plugins)
- [Agent Skills 仕様](https://agentskills.io)

### コミュニティ・補足

- [Thariq (@trq212): Using Claude Code: Session Management & 1M Context (2026-04-16)](https://x.com/trq212/status/2044548257058328723) — セッション管理・1M コンテキスト時代の運用
- [fabymetal: Claude Code 超完全ガイド (note.com)](https://note.com/fabymetal/n/n3f0f2873b56c) — WSCE フレームワーク、モデル選択、トークン最適化の実務
- [nyosegawa: Harness Engineering Best Practices 2026](https://nyosegawa.com/posts/harness-engineering-best-practices-2026/) — 「ハーネスがモデルより重要」の論、Hook 4 パターン、リンタ自動化、Codex との比較
- [How Anthropic teams use Claude Code (PDF)](https://www-cdn.anthropic.com/58284b19e702b49db9302d5b6f135ad8871e7658.pdf)
- [The Complete Guide to Building Skills for Claude (PDF)](https://resources.anthropic.com/hubfs/The-Complete-Guide-to-Building-Skill-for-Claude.pdf)

## 結論サマリ

詳細は各ファイルにあるが、本リポジトリ／プロンプト改善スキルの観点で最重要な原則を 5 つに圧縮すると:

1. **コンテキストは最重要リソース** — `/clear` / `/compact` / `/rewind` / Subagent を能動的に使い分ける。`/context` で常時可視化し、60% 超で次セッションを検討する。
2. **「修正するより巻き戻す」** — 失敗したアプローチを履歴に残さない。2 回補正したら `/clear` の合図。
3. **プロンプトに検証手段を埋める** — テスト・スクショ・期待出力。これが単一で最も投資効率が高い。
4. **CLAUDE.md は短く保ち、長物は Skill / Subagent / Hook に逃がす** — CLAUDE.md は 50 行以下、上限 200 行が指針（IFScale 研究の primacy bias から）。
5. **「プロンプトで頼む」より「仕組みで強制する」** — Hook と決定論的ツール（リンタ・テスト・型チェック）に投資する方が複利で効く。

プロンプト改善スキル `agent-coach` の観点では、これらを transcript から検出して具体的な書き換え案・設定変更案を提示することが価値の中心となる。詳細は [06-coach-checklist.md](06-coach-checklist.md)。

## 次のアクション候補

- `agent-coach` SKILL.md の「観点別 改善提案の方向性」を、本サーベイの 06-coach-checklist.md に対応する形で同期する
- `validate-skills.py` に description 長 (1,536 字超で warn) と `disable-model-invocation` ガイドラインのチェックを追加する Issue を起票
- 本サーベイを引いて参照しやすくするため、今後の `agent-coach` 報告に「該当ファイル名 + アンカー」のリンクを含めるテンプレを SKILL に組み込む
