# agent-coach reference handbook

このスキルが提案を組み立てる際の参照資料。SKILL.md は分析手順を定義し、本ファイルは具体的な書き換えテンプレ・スニペット・量的目安を提供する。

各観点の見出しは SKILL.md からアンカーリンクで参照される。

---

## 観点 0: シークレット検出パターン

### よくある接頭辞

- `sk-`, `sk_live_` (OpenAI / Stripe live)
- `sk_test_`, `pk_test_` (Stripe test — 重大度低だが警告)
- `xoxb-`, `xoxp-`, `xoxa-` (Slack)
- `ghp_`, `gho_`, `ghs_`, `ghr_` (GitHub)
- `AIza` (Google API key)
- `AKIA[A-Z0-9]{16}` (AWS Access Key ID)
- `eyJ` で始まる長文字列（JWT — context 次第）

### 認証ヘッダ・環境変数

- `Authorization: Bearer <値>`
- `Cookie: session=<値>`
- `AWS_SECRET_ACCESS_KEY`, `GITHUB_TOKEN`, `OPENAI_API_KEY` 等のキー名と右辺

### マスク方針

末尾 4 文字のみ残す: `sk-***xxxx`。原本は引用しない。

### ユーザーへの警告テンプレ

> ターン X (ファイル Y) で `sk-***xxxx` 形式の API キーが検出されました。transcript として保存されているため流出の可能性があります。該当キーのローテーションを推奨します。

---

## 観点 1: トークン消費 hot spot

### 量的目安

- 設定済み MCP サーバー: 20〜30 程度
- 有効化 MCP: 10 以下
- アクティブツール: 80 以下
- prompt cache TTL: 5 分（cache miss を避けるなら 270 秒以下、または 1200 秒以上に空けて 1 回だけ miss）

### 改善テンプレ

**巨大 Read → 部分 Read**:

> ファイル `src/big.ts` を全文 Read していますが、必要なのは `XXX` 関数だけです。次回は `Grep "XXX" src/big.ts` でヒット行を取り、`Read offset:N limit:50` でピンポイント取得すると、トークン消費を 1/10 に削減できます。

**Bash 繰り返し → 集約**:

> `ls a; ls b; ls c` を 3 回別々に呼んでいますが、`ls a b c` 1 コールにまとめれば tool_use 1 つで済みます。

**探索委譲**:

> 認証フローの理解に N 回の Read（合計 K 字）を消費しています。次回は `Agent(subagent_type=Explore, prompt: "...")` に委譲すれば、親コンテキストにはサマリのみ載ります。

**MCP 過多**:

> アクティブ MCP が N 個あり、定義だけで K トークン消費しています。本セッションで使わない MCP は `disabledMcpServers` で無効化してください。

---

## 観点 2: 方向修正の書き換え cookbook

### よくある曖昧プロンプト

| 元 | 改善 |
| --- | --- |
| "認証直して" | "`@src/auth/login.ts:42` で `if (user.email)` が falsy 値を見落としている。`if (user?.email != null)` に修正し、`tests/auth.test.ts` を実行して確認" |
| "いい感じにテスト書いて" | "`src/utils/format.ts` の `formatDate` に対する vitest を `tests/utils/format.test.ts` に追加。エッジケース: 不正な date 文字列、null、未来日付" |
| "適切にエラーハンドリング" | "`fetchUserById` で 404 → null 返却、5xx → throw、それ以外 → throw。catch では `logger.warn({source, raw, error})` をログ" |

### 補正ループの脱出

2 回連続で誤解されたら、修正を続けるより `Esc Esc`（`/rewind`）で巻き戻し → 上記の具体プロンプトで再開する方が効率的。

### 推奨運用テンプレ（レポートに含める）

> このタイプの補正が 2 回続いた時点で `Esc Esc`（または `/rewind`）で巻き戻し、改善プロンプトで再開する方が効率的です。
>
> Claude Code best practices: "After two failed corrections, `/clear` and write a better initial prompt incorporating what you learned."

---

## 観点 3: 指示違反 → 文面改善 vs Hook 化

### 文面改善で足りるケース

- ルールが曖昧 → 具体例・反例を追加
- ルールが埋もれている → CLAUDE.md 冒頭 IMPORTANT に移動、または専用 memory ファイル化
- ルールに why が無い → `**Why:**` `**How to apply:**` セクション追加
- skill description に triggering ロジックが無い → "Use when ..." 追加

### Hook 化を提案すべきケース

| 状況 | 提案する Hook | 例 |
| --- | --- | --- |
| 同じルール違反 3 回以上 | PostToolUse | リント違反を `additionalContext` で注入 |
| 完了ゲート（コミット前テスト等） | Stop | テスト未実行なら finish 不可 |
| 危険コマンド (`rm -rf`, `git push --force`) | PreToolUse Safety Gate | exit 2 で実行ブロック |
| リンタ違反パターン | PostToolUse Quality Loop | フォーマッタ自動実行 |

CLAUDE.md は advisory、Hook は deterministic。文面改善で繰り返し違反されるなら Hook へ格上げを提案。

### Hook スニペット例（`.claude/settings.json`）

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "scripts/safety-gate.sh" }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "scripts/require-tests-passed.sh" }
        ]
      }
    ]
  }
}
```

---

## 観点 4: コンテキストロット

### 量的目安

- 1M モデルでも 30〜40 万トークン付近から劣化
- 200K モデル（Opus 等）では実効上限 70K 程度に縮むケース
- コンテキスト使用率 60% 超で次セッション化を検討
- `/context` で常時可視化

### 対処の優先順位

1. 区切りで `/clear`（次タスクが明確に別なら）
2. `/compact [指示]` で焦点を絞った圧縮
3. 探索は `Agent(subagent_type=Explore)` 委譲
4. 長期記憶は `MEMORY.md` (auto memory) で外出し
5. CLAUDE.md に "Compact Instructions" セクションを追加

### Compact Instructions サンプル

```markdown
# Compact Instructions
- Always preserve the full list of modified files
- Always preserve the test commands used
- Drop debug log dumps
```

---

## 観点 5: スキル description 改善

### Use when... テンプレ

```yaml
description: |
  Review and merge a Dependabot bump PR after safety checks.
  Use when the user wants to merge a Dependabot version bump PR,
  says '依存関係をアップデート' / 'Dependabot を見て' / 'bump をマージ',
  or asks to handle dependency upgrade PRs.
```

### よくある triggering 失敗

- description が抽象的（"Manage dependencies" 等）
- 日本語・口語キーワード不足
- 似た description のスキルが複数あり選択ミス

### 改善ポイント

- 「Use when」節を必ず入れる
- ユーザーが言いそうなフレーズ（日本語含む）を列挙
- 区別が必要な兄弟スキルがあれば「Not for ...」も明示

---

## 推奨アクション TOP3 の Tier

| Tier | 内容 |
| --- | --- |
| Tier 1（必ず TOP3） | シークレット流出 / 危険コマンド検出 / 同じミス 3 回以上反復 |
| Tier 2（影響大なら TOP3） | 補正ループ（2 回以上） / 検証なしの「完了」宣言 / スキル未活用 3 件以上 |
| Tier 3（運用改善） | ターン数過多 / ファイル全文 Read / cache miss |

判断基準: **ユーザーがすぐに行動でき、複数セッションにわたって効果が継続するもの** を上に置く。

---

## 一次ソース

- [Best practices for Claude Code](https://code.claude.com/docs/en/best-practices)
- [Extend Claude with skills](https://code.claude.com/docs/en/skills)
- [Hooks reference](https://code.claude.com/docs/en/hooks)
- [Memory (CLAUDE.md)](https://code.claude.com/docs/en/memory)
- [Sub-agents](https://code.claude.com/docs/en/sub-agents)
