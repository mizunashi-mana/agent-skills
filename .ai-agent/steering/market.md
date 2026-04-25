# 市場分析

## 市場概要

AI エージェント向けスキル／プラグインの市場。LLM ベースのコーディングエージェント（Claude Code、Cursor、Codex、Gemini CLI 等）の普及に伴い、エージェントの振る舞いを定義・共有するスキルエコシステムが急速に成長している。agentskills.io によるクロスプラットフォーム仕様の標準化も進行中。

## ターゲットセグメント

- Claude Code を日常的に使う個人開発者・小規模チーム
- AI エージェント駆動の開発ワークフローを構築したいチーム
- 複数のエージェントツールにまたがってスキルを活用したいユーザー

## 競合分析

### スキルコレクション

| プロダクト | Stars | 特徴 | 強み | 弱み |
|---|---|---|---|---|
| [obra/superpowers](https://github.com/obra/superpowers) | 121k | スキルフレームワーク＋開発方法論 | 計画→実装→レビューのワークフロー、マルチエージェント連携、8プラットフォーム対応 | GitHub Issue/PR 統合が薄い、方法論が重厚 |
| [anthropics/skills](https://github.com/anthropics/skills) | 105k | Anthropic 公式スキルコレクション | 標準フォーマット策定者、ドキュメント処理系が充実 | 開発ワークフロー系がほぼない |
| [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | 15k | 公式プラグインディレクトリ | PR レビュー、Feature Dev 等あり | 個別コマンドの寄せ集め、ワークフロー統合なし |
| [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills) | 24k | Vercel 公式スキル | フロントエンド・デプロイ特化 | ドメインが限定的 |
| [trailofbits/skills](https://github.com/trailofbits/skills) | 4k | セキュリティスキル | 監査・脆弱性検出 | セキュリティドメイン限定 |

### プロジェクト初期化・仕様駆動開発（autodev-init の直接競合）

| プロダクト | Stars | 方法論 | エージェント対応 | 特徴 |
|---|---|---|---|---|
| [BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD) | 42.7k | アジャイル AI-DLC | マルチ IDE | 12+ エージェントペルソナ（PM、Architect、QA 等）、フルライフサイクル（分析→計画→設計→実装）、PRD/PRFAQ 生成。非常に包括的だが重厚 |
| [cc-sdd](https://github.com/gotalab/cc-sdd) | 3k | Kiro SDD (EARS) | 8 エージェント | Requirements → Design → Tasks の厳密なパイプライン、Mermaid 図生成、バリデーションコマンド、13言語対応。機能単位の仕様に特化 |
| [CEK/SDD](https://github.com/NeoLabHQ/context-engineering-kit) | 726 | Arc42 SDD | Claude + 他 | 9 専門エージェント、LLM-as-Judge 品質ゲート、MAKER パターン。学術的根拠が強い。GPL ライセンス |
| [planning-with-files](https://github.com/OthmanAdi/planning-with-files) | 17.5k | Manus スタイル計画 | Claude | 永続マークダウン計画。初期化よりも継続的な計画追跡に特化 |

### カタログ・キュレーション系

| プロダクト | Stars | 特徴 |
|---|---|---|
| [ComposioHQ/awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills) | 49k | キュレーション＋外部サービス連携 |
| [sickn33/antigravity-awesome-skills](https://github.com/sickn33/antigravity-awesome-skills) | 28k | 1,300+ スキルカタログ |
| [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) | 13k | クロスプラットフォーム対応リスト |

## 差別化ポイント

- **開発ライフサイクル全体のカバー**: Issue 作成 → タスク管理 → 実装 → PR 作成 → レビュー → マージの一連のフローをスキルで統合。BMAD-METHOD ほど重厚でなく、実用的な粒度
- **GitHub ネイティブ統合**: Issue/PR/Review の GitHub API 連携がビルトイン。obra/superpowers や cc-sdd はこの部分が薄い
- **軽量な初期化**: BMAD-METHOD（12+ ペルソナ）や cc-sdd（EARS 形式の厳密な仕様）と比べ、対話ベースで必要十分な steering ドキュメントを生成
- **ローカル／GitHub 二重レビューモード**: GitHub Review API を使わないローカルレビューも選択可能
- **エージェント非依存の志向**: agentskills.io 仕様に沿った設計で他エージェントへの移植を考慮

## 市場ギャップ（チャンス）

1. **GitHub Issue 作成・管理の専用スキル**: 競合にほぼない
2. **軽量かつ統合的なワークフロー**: BMAD は重すぎ、cc-sdd は機能単位に限定。プロジェクト全体を適切な粒度でカバーするスキルセットが不足
3. **レビュー→フィードバック取り込みの自動化**: レビュー結果を自動で取り込む双方向フローは独自

## 参考にすべきパターン

- **クロスプラットフォーム対応**（obra/superpowers）: `.claude-plugin`, `.codex`, `.cursor-plugin` 等の並列対応
- **agentskills.io 仕様準拠**: エージェント非依存の標準フォーマット
- **npx インストーラー**（cc-sdd, BMAD）: `npx` による簡単インストール
- **バリデーションコマンド**（cc-sdd）: ギャップ分析・設計レビュー・実装検証
- **プラグインマーケットプレイス**（anthropics/skills）: `.claude-plugin/marketplace.json` によるバンドル配布
- **サブエージェントプロンプト分離**（obra/superpowers）: レビュアー等のプロンプトを別ファイルに

## 市場動向

- Agent Skills 仕様（agentskills.io）の標準化が進行し、クロスプラットフォーム互換が重要に
- BMAD-METHOD（42.7k stars）の急成長が示すように、単体スキルより統合ワークフローへの需要が高い
- cc-sdd の Kiro スタイル仕様駆動開発が一つのデファクトに
- セキュリティ（trailofbits）、PM（phuryn/pm-skills）など、ドメイン特化コレクションも伸長
