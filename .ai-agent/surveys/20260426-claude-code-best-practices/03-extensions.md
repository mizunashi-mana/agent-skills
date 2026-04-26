# 03. 拡張機能の使い分けと設計

> agent-coach 観点 **3（指示違反）** と **5（スキル未活用）** に対応する章。CLAUDE.md / Skill / Subagent / Hook / MCP の使い分けと、各々の設計ノウハウ。

## 3.1 5 機能の比較表

公式 [Extend Claude Code](https://code.claude.com/docs/en/features-overview) ベース + 補助記事:

| 機能 | いつ使うか | コンテキスト負荷 | 起動契機 | 強制力 |
| --- | --- | --- | --- | --- |
| **CLAUDE.md** | 毎セッション必要なプロジェクト規約 | 全セッション常駐 | 自動 | 助言（守られない可能性あり） |
| **Skill** | 反復するプレイブック・知識・チェックリスト | 説明のみ常駐、本体は呼出時のみ | 自動 or `/skill-name` | 助言（呼出後はそのセッション中常駐） |
| **Subagent** | 大量読込・特殊権限・コンテキスト隔離 | 親には結果のみ戻る | Claude の判断 or 明示指示 | 親の指示通りに振る舞う |
| **Hook** | 例外なく毎回起こすべき副作用 | なし（外部実行） | ライフサイクルイベント | 決定論（強制） |
| **MCP** | 外部サービス（Notion/DB/Figma 等） | サーバ毎にツール定義（一部 deferred） | ツール呼出 | 外部サービス依存 |

判断基準（[nyosegawa](https://nyosegawa.com/posts/harness-engineering-best-practices-2026/)）:

> 「**プロンプトで頼む**」より「**仕組みで強制する**」方が複利で効く。重要なルールは Hook へ。

## 3.2 CLAUDE.md の設計

### 配置場所と階層

| 場所 | 適用範囲 | git commit |
| --- | --- | --- |
| `~/.claude/CLAUDE.md` | 全セッション共通（個人） | × |
| `./CLAUDE.md` | プロジェクト共通 | ○（チーム共有） |
| `./CLAUDE.local.md` | プロジェクト個人設定 | × (gitignore) |
| 親ディレクトリの CLAUDE.md | モノレポで自動マージ | ○ |
| 子ディレクトリの CLAUDE.md | 該当領域編集時にオンデマンドロード | ○ |

`@path/to/file` 構文で他ファイルを import 可能。

### 書くべきもの・書かないもの（公式）

| ✅ 書く | ❌ 書かない |
| --- | --- |
| 推測不能な Bash コマンド（独自スクリプト等） | コードを読めば分かること |
| デフォルトと違うコードスタイル規則 | 標準的な言語慣習 |
| テスト方針・推奨テストランナー | 詳細 API ドキュメント（リンクで十分） |
| ブランチ命名・PR 規約 | 頻繁に変わる情報 |
| プロジェクト固有のアーキ判断 | 長い解説・チュートリアル |
| 開発環境のクセ（必須 env var 等） | ファイル単位の説明 |
| 非自明な落とし穴 | "綺麗なコードを書く" のような自明な指示 |

### サイズの指針（補強）

- **理想 50 行以下、上限 200 行**（[nyosegawa](https://nyosegawa.com/posts/harness-engineering-best-practices-2026/)）
- IFScale 研究で 150-200 指示時点で primacy bias 顕著化、性能劣化
- 各行ごとに「**これを消したら Claude がミスをするか？**」と自問する（公式）
- **長すぎる CLAUDE.md は重要ルールがノイズに埋もれて無視される**（公式・fabymetal 両方が強調）

### 「ポインタ型」設計（nyosegawa）

CLAUDE.md は説明書ではなく、**ルーティング指示**として書く:

- コマンド一覧
- ADR の所在
- アーキテクチャ検証方法へのポインタ
- 禁止事項リスト（各項目に ADR / リンタールール参照を付ける）

ポインタ先のファイルが消えれば 404 が出るので、**腐敗が機械的に検出可能**。これが説明文書（散文）と決定的に違う点。

### Compact Instructions セクション

公式機能。要約時に保持させたい項目を CLAUDE.md に書ける:

```markdown
# Compact Instructions
- Always preserve the full list of modified files
- Always preserve the test commands used
- Drop debug log dumps
```

## 3.3 Skill の設計

### 配置場所

| 場所 | 範囲 |
| --- | --- |
| `~/.claude/skills/<name>/SKILL.md` | 個人（全プロジェクト） |
| `.claude/skills/<name>/SKILL.md` | プロジェクト |
| プラグイン内 `skills/<name>/SKILL.md` | プラグイン enable 時 |
| エンタープライズ管理設定 | 組織全体 |

優先度は エンタープライズ > 個人 > プロジェクト。プラグインは namespace 化されるので衝突しない。

### フロントマターの主要フィールド（公式）

| フィールド | 役割 |
| --- | --- |
| `description` | **最重要**。Claude が呼出を判断する根拠。先頭 1,536 字でカット |
| `when_to_use` | description に追記される使用条件（同じく 1,536 字共有） |
| `argument-hint` | autocomplete に出る引数ヒント |
| `arguments` | 名前付き位置引数 |
| `disable-model-invocation` | true で手動起動限定 |
| `user-invocable` | false で `/` メニュー非表示（背景知識スキル用） |
| `allowed-tools` | このスキルアクティブ中は許可不要のツール |
| `model` | スキルアクティブ時のモデル切替 |
| `effort` | 思考レベル切替 |
| `context: fork` | サブエージェントで実行 |
| `agent` | fork 時の subagent 種類 |
| `paths` | 該当ファイル編集時のみ自動ロード |
| `hooks` | このスキルライフサイクル限定の hook |

### description 設計の鉄則

1. **トリガフレーズを front-load**: ユーザーが言いそうな自然言語キーワードを先頭に
2. **"Use when..." を含める**: 公式例の頻出パターン
3. **具体ユースケース**: 「コードを綺麗にする」より「TypeScript のリンタ警告を一括修正」
4. **副作用の有無を示す**: 「副作用あり」スキルは説明にも書いておく
5. **1,536 字制限**: description + when_to_use の合計

### Skill 本体のライフサイクル（重要）

公式の最重要仕様:

- セッション開始時、**全スキルの description のみ**がコンテキストに常駐
- スキルが呼ばれた瞬間、**SKILL.md 全文**が会話に挿入される
- **同セッション内で再読込されない**。よってタスク中ずっと従わせたい指示は「スタンディング指示」として書く（「最初の 1 回だけ X しろ」型は機能しない）
- Auto-compaction 後は最近呼出されたスキルが再アタッチされる（先頭 5,000 トークン、合計 25,000 トークン上限）
- `disable-model-invocation: true` のスキルは description もコンテキストに載らず、呼出時のみ全文挿入

### `disable-model-invocation: true` を付けるべきケース

- 副作用がある（deploy, commit, push, send-message）
- 起動タイミングを人間がコントロールしたい
- Claude が誤って起動するとコストが大きい

本リポジトリの該当例: `autodev-create-issue`, `autodev-create-pr`, `autodev-review-pr`, `merge-dependabot-bump-pr` 等。

### `user-invocable: false` を付けるべきケース

- 背景知識（"legacy-system-context" のような状況説明）
- 「ユーザーが `/foo` で叩く意味がない」スキル
- ただしこれは menu visibility のみ。Skill ツール access は `disable-model-invocation` で制御

### サブファイル分割

`SKILL.md` 本体は **500 行以下**を推奨（公式 Tip）。長文リソースは別ファイル化:

```
my-skill/
├── SKILL.md          # ナビゲーション + 標準手順
├── reference.md      # 詳細 API ドキュメント
├── examples.md       # サンプル
└── scripts/
    └── helper.py     # 実行スクリプト
```

`SKILL.md` から「いつ読むか」を明示する:

```markdown
## Additional resources
- For complete API details, see [reference.md](reference.md)
- For usage examples, see [examples.md](examples.md)
```

### 動的コンテキスト挿入

`` !`<command>` `` でシェルコマンドの出力を Claude が見る前に注入できる:

```yaml
---
name: pr-summary
description: Summarize a pull request
context: fork
agent: Explore
allowed-tools: Bash(gh *)
---

## PR context
- Diff: !`gh pr diff`
- Comments: !`gh pr view --comments`

## Your task
Summarize this PR...
```

これは Claude が実行するのではなく、**スキル展開時の前処理**。

### Skill triggering の改善（agent-coach 観点 5）

スキルが呼ばれるべきなのに呼ばれない場合の典型原因:

| 原因 | 修正 |
| --- | --- |
| description が抽象的 | "Use when..." 句を追加、具体キーワード列挙 |
| 似た description のスキルが競合 | 区別を明示（"Unlike X, this is for Y"） |
| description が 1,536 字でカットされてキーワード喪失 | 重要トリガを先頭に front-load |
| `disable-model-invocation: true` だが手動起動を促していない | README にトリガ手順を明記 |
| スキル数が多く合計 description budget を超過 | `SLASH_COMMAND_TOOL_CHAR_BUDGET` 拡張 or 整理 |

## 3.4 Subagent の設計

### いつ使うか

> 判断基準: **「このツール出力を再び使うか、結論だけでいいか？」**（[Thariq](https://x.com/trq212/status/2044548257058328723)）

- 大量のファイル読込・ログ解析（結論だけ親に欲しい）
- 特殊権限（破壊的操作を限定タスクで行う）
- 並列実行（Writer/Reviewer パターン）
- コスト削減（Haiku ワーカーへの委譲）

### 組み込みエージェント

| Agent | モデル | ツール | 用途 |
| --- | --- | --- | --- |
| **Explore** | Haiku | 読取専用 | コードベース探索 |
| **Plan** | inherit | 読取専用 | Plan モード内研究 |
| **general-purpose** | inherit | 全 | 複雑な多段階タスク |
| **statusline-setup** | Sonnet | 限定 | `/statusline` 設定 |
| **Claude Code Guide** | Haiku | WebFetch | Claude Code Q&A |

**まず組み込みで足りるか考える**こと。新規定義は再利用される見込みがあるときに限る。

### 主要フロントマター（公式）

| フィールド | 内容 |
| --- | --- |
| `name` | 必須。識別子 |
| `description` | 必須。Claude が委譲判断する根拠 |
| `tools` | allowlist |
| `disallowedTools` | denylist（先に適用） |
| `model` | sonnet / opus / haiku / `inherit` |
| `permissionMode` | default / acceptEdits / auto / dontAsk / bypassPermissions / plan |
| `maxTurns` | 上限ターン数 |
| `skills` | 起動時に preload する skills 名 |
| `mcpServers` | このサブエージェント限定の MCP |
| `hooks` | このサブエージェント限定の hook |
| `memory` | user / project / local（永続メモリ有効化） |
| `background` | 常にバックグラウンド実行 |
| `effort` | 思考レベル |
| `isolation: worktree` | 一時 git worktree で分離実行 |
| `initialPrompt` | `--agent` で main 起動時の初手プロンプト |

### 設計のキーポイント

- **必要最小権限**: `Read, Grep, Glob` で済むものに `Bash` を入れない
- **Haiku ワーカー化**: 機械的検証・カウント等は `model: haiku` でコスト削減
- **memory: project**: 推奨デフォ。`MEMORY.md` に学習を蓄積し複数セッションで活用（公式）
- **Subagent はサブエージェントを spawn できない**（無限ネスト防止）
- **プラグイン由来の Subagent は `hooks`/`mcpServers`/`permissionMode` が無視される**（セキュリティ制約）
- **クエリだけでなく目的コンテキストも渡す**（[fabymetal](https://note.com/fabymetal/n/n3f0f2873b56c)）。「何のために調べているか」「すでに分かっていること」を一緒に渡す

### Subagent 間反復取得パターン（fabymetal）

親→サブエージェント→評価→フォローアップ質問を**最大 3 サイクル**まで回す。一発で完璧な答えは期待しない。

## 3.5 Hook の設計

### 強制力としての価値

公式: **"Unlike CLAUDE.md instructions which are advisory, hooks are deterministic and guarantee the action happens."**

CLAUDE.md は助言、Hook は強制。「例外なく毎回」が必要なら Hook 一択。

### 5 種類のタイプ

| タイプ | 用途 |
| --- | --- |
| `command` | シェル script (stdin に JSON) |
| `http` | 外部 endpoint への POST |
| `mcp_tool` | 接続中 MCP のツール呼出 |
| `prompt` | LLM に Yes/No 判定させる |
| `agent` | サブエージェント起動 |

### 主要イベント

実行前:

- `SessionStart` — セッション開始/再開
- `UserPromptSubmit` — ユーザー入力受領前
- `PreToolUse` — ツール呼出前（**ブロック可能**）
- `PermissionRequest` — 権限ダイアログ表示時

実行後:

- `PostToolUse` — ツール成功後
- `PostToolUseFailure` — ツール失敗後
- `PermissionDenied` — Auto モード拒否時

ライフサイクル:

- `Stop` / `StopFailure` — Claude 応答完了時
- `SubagentStart` / `SubagentStop`
- `Notification`
- `CwdChanged` / `FileChanged`
- `PreCompact` / `PostCompact`
- `InstructionsLoaded` / `ConfigChange`

### 配置と上書き

| 場所 | 範囲 |
| --- | --- |
| `~/.claude/settings.json` | 全プロジェクト |
| `.claude/settings.json` | プロジェクト共有 |
| `.claude/settings.local.json` | 個人（gitignore） |

### Hook 4 パターン（[nyosegawa](https://nyosegawa.com/posts/harness-engineering-best-practices-2026/)）

実用的に最も整理された分類:

1. **Safety Gates (PreToolUse)**: 破壊的コマンド・機密ファイル編集を Exit 2 でブロック
2. **Quality Loops (PostToolUse)**: リント結果を `additionalContext` として注入し自己修正駆動
3. **Completion Gates (Stop)**: テスト通過まで完了許可しない
4. **Observability**: 全イベント。意図・結果・コンテキスト損失を監視パイプライン送信

### PreToolUse の決定値

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow|deny|ask|defer",
    "permissionDecisionReason": "...",
    "updatedInput": { ... }
  }
}
```

### Hook を書く 2 つの典型例

**a. 破壊的コマンドブロック**:

```bash
#!/bin/bash
COMMAND=$(jq -r '.tool_input.command')
if echo "$COMMAND" | grep -q 'rm -rf'; then
  jq -n '{ hookSpecificOutput: { hookEventName: "PreToolUse",
    permissionDecision: "deny",
    permissionDecisionReason: "Destructive command blocked" } }'
fi
```

**b. ファイル編集後の自動フォーマット**:

PostToolUse で `Write|Edit|MultiEdit` をマッチさせ、prettier / ruff format を自動実行 → 失敗時はエラー出力を `additionalContext` で Claude に戻す。

## 3.6 MCP の設計

### サーバ単位のコスト

各 MCP サーバはツール定義を持ち、有効化中は記述がコンテキストに載る（一部 deferred）。

- 「設定済み 20〜30 / 有効 10 以下 / アクティブツール 80 以下」が経験則（fabymetal）
- 不要時は `disabledMcpServers` でプロジェクト単位に無効化
- `/mcp` でサーバ毎コストを確認できる

### CLI ツールへの代替

公式の助言: **「外部サービス操作は CLI ツールが最もコンテキスト効率的」**。

| サービス | CLI |
| --- | --- |
| GitHub | `gh` |
| AWS | `aws` |
| GCP | `gcloud` |
| Sentry | `sentry-cli` |

これらが使えるなら MCP より CLI の方が軽い。Claude は `--help` から学習できる。

### Subagent 限定 MCP

`mcpServers` フィールドで「特定サブエージェントだけが使える MCP」を定義可能。**親会話のツール定義を汚さない**ので有用:

```yaml
---
name: browser-tester
mcpServers:
  - playwright:
      type: stdio
      command: npx
      args: ["-y", "@playwright/mcp@latest"]
---
```

## 3.7 機能間連携

- **Skill + Subagent**: `context: fork` でスキル内容をサブエージェントに渡して実行
- **Subagent + Skill**: `skills:` フィールドでサブエージェント起動時にスキル本体を preload
- **Skill + Hook**: フロントマターの `hooks:` でスキルライフサイクルに hook をスコープ
- **Plugin = 全部入り**: skills + agents + hooks + MCP を 1 単位で配布

本リポジトリ `agent-skills` はプラグインバンドル機構を提供しており、ユーザーが `/plugin install` 1 回でスキル群を入れられるのが価値の中心。
