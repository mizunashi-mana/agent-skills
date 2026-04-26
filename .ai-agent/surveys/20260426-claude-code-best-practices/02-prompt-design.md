# 02. プロンプト設計とコミュニケーション

> agent-coach 観点 **2（方向修正多発プロンプト）** に対応する章。「悪いプロンプト」を transcript から検出し、書き換え案を提示するための知識をまとめる。

## 2.1 プロンプト設計の核心: 具体性 + 検証手段 + 参照

公式 [Best practices](https://code.claude.com/docs/en/best-practices) が一貫して主張する 3 本柱:

1. **検証手段を渡す（最高の投資効率）** — テスト・スクショ・期待出力
2. **特定性 (specificity)** — ファイル・制約・例パターンを明示
3. **リッチコンテンツの活用** — `@` でファイル参照、画像、URL、パイプ

### 検証手段を渡す（最重要）

> "Include tests, screenshots, or expected outputs so Claude can check itself. **This is the single highest-leverage thing you can do.**" — 公式

| 戦略 | Before | After |
| --- | --- | --- |
| 検証基準を提示 | "validateEmail を実装して" | "validateEmail を実装。テストケース: `user@example.com`→true, `invalid`→false, `user@.com`→false。実装後にテストを実行" |
| UI を画像比較 | "ダッシュボードを綺麗にして" | "[元画像] このデザインを実装。結果のスクリーンショットを撮って差分を列挙し、修正" |
| 根本原因に対処 | "ビルドが落ちる" | "ビルドが [error] で落ちる。直して成功を確認。エラー抑制でなく根本原因を直す" |

検証手段の例:

- 単体テスト（Jest, Vitest, pytest）
- 型チェック（TypeScript）
- リンタ（ESLint, Prettier, Ruff）
- E2E（Playwright）
- ビルド検証
- 視覚比較（Claude in Chrome 拡張）

### 特定性 (Specificity)

公式の対比表を再掲（プロンプト改善の出発点）:

| 戦略 | Before | After |
| --- | --- | --- |
| スコープを切る | "add tests for foo.py" | "write a test for foo.py covering the edge case where the user is logged out. avoid mocks." |
| ソースを指す | "why does ExecutionFactory have such a weird api?" | "look through ExecutionFactory's git history and summarize how its api came to be" |
| 既存パターン参照 | "add a calendar widget" | "look at how existing widgets are implemented on the home page. HotDogWidget.php is a good example. follow the pattern..." |
| 症状を述べる | "fix the login bug" | "users report that login fails after session timeout. check the auth flow in src/auth/, especially token refresh. write a failing test that reproduces the issue, then fix it" |

> 例外: 探索フェーズの曖昧プロンプトは有用。"What would you improve in this file?" は思いつかなかった指摘を引き出す。

### リッチコンテンツの活用

- **`@` でファイル参照** — Claude は応答前にファイルを読む
- **画像のペースト** — Copy/paste またはドラッグ＆ドロップ
- **URL** — ドキュメントや API リファレンス。`/permissions` で頻用ドメインを許可
- **パイプ** — `cat error.log | claude`
- **Claude に取りに行かせる** — "Bash でこれを fetch して読んで"

## 2.2 「修正するより巻き戻す」 (Thariq)

最重要習慣だが、これは **プロンプト書き直しの判断基準**でもある。

| 状況 | 推奨アクション |
| --- | --- |
| Claude が誤解して 1 回失敗 | 即 `Esc Esc` で巻き戻し、誤解の元を排除した再プロンプト |
| 同じ件で 2 回補正 | `/clear` + より具体的な初期プロンプトでやり直し |
| 5 ファイル読んで方向違い | ファイル読み込み直後に巻き戻して "アプローチ A は使うな、B" と再指示 |
| 試行錯誤の末にうまくいった | "summarize from here" でハンドオフメッセージ化 → 新セッションへ |

agent-coach が transcript で見る「方向修正シグナル」:

- 否定・修正語: `no`, `not that`, `instead`, `actually`, `stop`, `wait`, `違う`, `そうじゃなくて`, `やめて`, `いや`
- 同一アシスタントターンへの即時返信で短いユーザーメッセージ（< 50 文字）
- 同じトピックで 3 ターン以内に再指示

これらが集中したら、**元プロンプト** + **Claude の解釈** + **ユーザーの修正** + **書き換え案**のセットで報告するのが基本（[agent-coach SKILL.md](../../../plugins/agent-coach/skills/agent-coach/SKILL.md)）。

## 2.3 大きい機能は逆インタビュー

公式推奨パターン:

```text
I want to build [brief description]. Interview me in detail using the
AskUserQuestion tool.

Ask about technical implementation, UI/UX, edge cases, concerns, and
tradeoffs. Don't ask obvious questions, dig into the hard parts I might
not have considered.

Keep interviewing until we've covered everything, then write a complete
spec to SPEC.md.
```

仕様が固まったら**新セッション**で実装。新セッションはクリーンコンテキストで実装に集中でき、SPEC.md は書面で残る。

## 2.4 Explore → Plan → Code → Commit

公式の推奨 4 段階:

1. **Explore (Plan Mode)**: 関連コード読込、書込禁止
2. **Plan (Plan Mode)**: 実装プラン作成。`Ctrl+G` でエディタに開いて手で直せる
3. **Implement (Normal Mode)**: プランに沿って実装。検証コマンド必須
4. **Commit**: コミットメッセージと PR を任せる

### Plan を **省く** べきとき

- diff が一文で説明できる程度（タイポ、ログ追加、変数名変更）
- スコープが明確で副作用が小さい
- 探索的な「何ができるか試したい」（vague プロンプトの方がよい）

### Plan が **必要** なとき

- アプローチが不確か
- 複数ファイルにまたがる変更
- 未知のコード領域

## 2.5 シニアエンジニアと話す感覚

公式の助言: **"Ask Claude questions you'd ask a senior engineer."**

オンボーディングや調査では、特別なプロンプト技術は不要:

- "How does logging work?"
- "How do I make a new API endpoint?"
- "What does `async move { ... }` do on line 134 of `foo.rs`?"
- "What edge cases does `CustomerOnboardingFlowImpl` handle?"
- "Why does this code call `foo()` instead of `bar()` on line 333?"

## 2.6 共通アンチパターンと書き換え案

agent-coach が transcript から検出すべきプロンプトのアンチパターンと、書き換え案のテンプレ:

### a. 曖昧な指示語

| Before | After |
| --- | --- |
| 「いい感じに直して」 | 「`@src/auth/login.ts:42` の `if (user.email)` を `if (user?.email != null)` に書き換え。意図: null ガードを明示する」 |
| 「適切に処理して」 | 「失敗時は `ErrorWithCode('AUTH_TIMEOUT')` を throw、ログを `logger.warn` で `{ userId, sessionId }` 付きで残す」 |

### b. 検証手段の欠落

| Before | After |
| --- | --- |
| 「validateEmail を実装」 | 「validateEmail を実装。テストケース: `a@b.com`→true, `invalid`→false。実装後 `npm test src/email.test.ts` 実行」 |

### c. 参照不足

| Before | After |
| --- | --- |
| 「カレンダーウィジェットを追加」 | 「`@src/widgets/HotDogWidget.tsx` のパターンに従って `CalendarWidget` を新規作成。月選択 + 前後年ページネーション。既存以外のライブラリ追加禁止」 |

### d. 症状だけ伝える

| Before | After |
| --- | --- |
| 「ログインバグ直して」 | 「セッションタイムアウト後にログインが失敗する。`@src/auth/` のトークンリフレッシュを調査。再現する failing test を `src/auth/auth.test.ts` に書いてから直す」 |

### e. 場当たり的指示の連発

シグナル: ユーザーが 1〜2 文の短い指示を連続で出している（cache hit を狙う使い方の場合は除く）

書き換え方針: 「最初に SPEC を書かせる」（2.3 の逆インタビューパターン）に誘導する。

## 2.7 「曖昧でよい」ケースを見落とさない

agent-coach が誤検知しないために重要:

- **探索フェーズ**で "what would you improve in this file?" のような曖昧プロンプトは正しい使い方
- **対話的設計**では、ユーザーが意図的に Claude の解釈を見て調整している場合がある
- ユーザー指示が短くても、コンテキストが豊富（`@` で大量のファイル参照、明確な制約）なら適切

判断は「同じテーマで 3 ターン以内に再指示」「明示的な否定語」「Claude の応答が `Wait, you mean...?` 系の確認」が揃ったときに限定する。

## 2.8 プロンプトキャッシュの実利

`claude-api` skill 等の知見と公式の組み合わせ:

- Anthropic prompt cache の TTL は **5 分**
- ターン間隔が 5 分超えるとキャッシュミス → 入力トークンが膨らむ
- agent-coach は連続ターン間隔も観察対象に。`ScheduleWakeup` の `delaySeconds` 設計に反映できる
- `~5 分` は最悪のスリープ長（300 秒で cache miss を踏みつつ短い）。270s で踏みとどまるか、1200s+ にしてミス分を償却するのがセオリー（自プロジェクトの ScheduleWakeup ガイドラインより）

## 2.9 「delegate, don't dictate」

公式の重要原則:

> "Think of delegating to a capable colleague. Give context and direction, then trust Claude to figure out the details."

| Don't（過剰指示） | Do（委譲） |
| --- | --- |
| 「`grep -rn 'foo' src/` してから `cat src/auth/login.ts` を読んで...」 | 「checkout flow が期限切れカードユーザーで壊れている。関連コードは `src/payments/`。調査して直して」 |

エンジニアによっては「ファイル指定までしないと間違うのでは」と思いがちだが、公式は明確に逆を推奨している。
