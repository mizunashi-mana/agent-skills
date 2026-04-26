# 06. プロンプト改善スキル用 統合チェックリスト

> agent-coach（および類似のプロンプト改善スキル）が transcript を分析するとき、観点ごとに「何を見て、何を根拠に、何を提案するか」を一覧化したリファレンス。本サーベイの全文をベースに、コーチ視点で再構成したもの。

## 観点 1: トークン消費 hot spot

### 検出シグナル

| シグナル | 観察方法 |
| --- | --- |
| 巨大 Read（> N 千行 / > 50KB） | `assistant.message.content[].tool_use` の `Read` 引数で `offset/limit` 不在、続く `tool_result` の文字数 |
| 同一引数 Bash 繰り返し | `tool_use.name == "Bash"` で `command` 文字列が同一 |
| 探索フェーズで親が 5+ ファイル直接 Read | `Subagent` Agent ツール呼出が無い |
| ターン間隔 5 分超 | 連続 assistant ターンの timestamp 差 |
| 巨大 tool_result（> 5,000 字） | tool_result.content 文字数 |
| MCP ツール定義過多 | システム reminder の MCP 一覧文字数 |

### 根拠（公式・補助記事）

- 公式: "MCP tool definitions are deferred by default and loaded on demand"
- fabymetal: 「設定済み MCP 20〜30 / 有効 10 以下 / アクティブツール 80 以下」
- 自プロジェクトの ScheduleWakeup ガイドライン: prompt cache TTL は 5 分

### 提案テンプレ

| 検出 | 提案 |
| --- | --- |
| 巨大 Read | "ファイル X の全文 Read（YK 字）が観測されました。Grep '<シンボル>' → Read with offset で K 字に削減できます" |
| Bash 繰り返し | "`ls A; ls B; ls C` を `ls A B C` 1 コールにまとめると tool_use 1 つで済みます" |
| 探索委譲漏れ | "auth フローの理解に N 回の Read（合計 K 字）。Explore agent に委譲すると親コンテキストにはサマリのみ" |
| cache miss | "ターン X-Y 間で 7 分空いており cache miss。`ScheduleWakeup` の delaySeconds を 270 秒以下にするか、まとめて作業する設計に" |
| MCP 過多 | "アクティブ MCP が N 個。`disabledMcpServers` で本セッション不要なものを切ることで定義分のトークンを節約できます" |

### 詳細リファレンス

→ [01-context-and-session.md §1.5](01-context-and-session.md#15-トークン-hot-spot-の典型パターンと対策)

---

## 観点 2: 方向修正多発プロンプト

### 検出シグナル

| シグナル | 観察方法 |
| --- | --- |
| 否定・修正語 | ユーザーメッセージ内の `no`, `not that`, `instead`, `actually`, `stop`, `wait`, `違う`, `そうじゃなくて`, `やめて`, `いや` |
| 短いユーザー応答（< 50 字）の即時返信 | 直前 assistant ターンへの 1 文返信 |
| 同テーマで 3 ターン以内の再指示 | ユーザー発話のクラスタリング |
| Claude 側の確認 ("Wait, you mean...?") | assistant 応答のパターン |

### 根拠

- 公式: "After two failed corrections, `/clear` and write a better initial prompt incorporating what you learned."
- Thariq: 「修正するより巻き戻す」が最重要習慣
- 公式: "The more precise your instructions, the fewer corrections you'll need."

### 提案テンプレ

```markdown
### 元プロンプト（ターン X）
> "認証直して"

### Claude の解釈（同ターン応答冒頭）
> "新しい OAuth プロバイダを追加するために..."

### ユーザーの修正（ターン X+1）
> "違う、ログインのバグを直して"

### 改善案
"`@src/auth/login.ts:42` で `if (user.email)` が falsy 値を見落としている。
`if (user?.email != null)` に修正し、`tests/auth.test.ts` の該当テストを実行して確認"

### 推奨運用
このタイプの補正が 2 回以上続いたら、`Esc Esc` で巻き戻して具体プロンプトで再開する方が効率的。
```

### 詳細リファレンス

→ [02-prompt-design.md §2.6](02-prompt-design.md#26-共通アンチパターンと書き換え案)

---

## 観点 3: 指示違反（CLAUDE.md / Skill / Memory）

### 検出シグナル

| シグナル | 観察方法 |
| --- | --- |
| プロジェクト CLAUDE.md ルール違反 | CLAUDE.md 読み出し → ルール抽出 → Claude 行動と突合 |
| ユーザー `~/.claude/CLAUDE.md` 違反 | 同上、ホームの CLAUDE.md |
| 配布スキルの指示違反 | system-reminder で配布された SKILL.md 内容と Claude 行動 |
| 同じルールについてユーザーが繰り返し指示 | CLAUDE.md だけでは強制力不足のシグナル |

### 根拠

- 公式: "CLAUDE.md instructions which are advisory" / "hooks are deterministic"
- 公式: "If your CLAUDE.md is too long, Claude ignores half of it because important rules get lost in the noise."
- fabymetal: 「容赦ない削除、削除してもミスしなければ不要」
- nyosegawa: 「重要ルールは Hook へ格上げ」

### 提案テンプレ（4 種類）

#### a. ルールが曖昧

```markdown
### 違反したルール (CLAUDE.md L42)
> "適切にエラーハンドリングする"

### 違反箇所（ターン X）
- `try/catch` 無しで `JSON.parse` 直接呼出

### 改善案: ルールを具体化
"外部入力 (HTTP body, file content) を JSON.parse する箇所では必ず
try/catch で囲み、catch で `logger.warn({ source, raw, error })` を残す"
```

#### b. ルールが埋もれている

```markdown
### 違反したルール (CLAUDE.md L156)
> "コミット前に npm test を実行"

### 違反箇所（ターン Y）
- テスト未実行で `git commit` 直接実行

### 改善案: 配置場所変更 + 強制化
- CLAUDE.md L156 → CLAUDE.md 冒頭 IMPORTANT セクションへ移動
- さらに、PreToolUse hook で `Bash(git commit*)` をフックして、
  直前 5 ターン以内に `npm test` 成功が無ければブロックする
```

#### c. ルールに why が無い

```markdown
### 違反したルール (memory/feedback.md)
> "テストでは DB をモックしないこと"

### 改善案: Why と How to apply を明示
"統合テストでは DB をモックせず実 DB を使う。

**Why:** 前四半期にモックテストが pass したまま prod migration が
壊れた事故があり、モック/prod の乖離を防ぐため。

**How to apply:** `tests/integration/**` 配下のテストすべて。
ユニットテスト (`tests/unit/**`) はモック OK。"
```

#### d. skill description のトリガロジック不足

```markdown
### 違反: skill が triggering されなかった
- ユーザー: "PR 作って"
- スキル `autodev-create-pr` は呼ばれず、Claude が `gh pr create` を直接実行

### スキル description (現在)
> "Create a GitHub pull request from the current branch's changes."

### 改善案
"Create a GitHub pull request from the current branch's changes.
Use when the user says 'PR を作る', 'pull request を出す', 'PR 投げて',
'open a PR', or asks to push changes for review. Includes draft PR template
selection and reviewer assignment."
```

### 詳細リファレンス

→ [03-extensions.md §3.2](03-extensions.md#32-claudemd-の設計) §3.3

---

## 観点 4: コンテキストロット

### 検出シグナル

| シグナル | 観察方法 | 注意 |
| --- | --- | --- |
| ターン数 > 50 | jsonl 行数 | 設計議論等は正常もある |
| 後半で初期指示参照消失 | 同じファイル Read 繰返、CLAUDE.md ルール違反増 | ファイル更新による再読込は正常 |
| 同一 Bash / Read 繰返 | tool_use 引数の重複 | 状態変化を見るためなら正常 |
| 巨大 tool_result（> 5,000 字）が複数 | tool_result 文字数 | 重要な探索なら正常 |

### 根拠

- 公式: "LLM performance degrades as context fills"
- 公式: "Run `/clear` between unrelated tasks"
- Thariq: 「30〜40 万トークン付近から劣化」「悪いコンパクト」
- fabymetal: 「60% 超えたら新セッション」「自動コンパクト無効化推奨」

### 提案テンプレ

```markdown
### コンテキストロットの可能性 (信頼度: medium)

**シグナル**
- ターン数 62 / `src/auth/login.ts` を 5 回 Read / 後半で CLAUDE.md ルール違反増

**改善案 (優先度順)**
1. 区切りで `/clear` を挟む（次タスクが「ドキュメント書き」程度なら新セッション）
2. 長期記憶は CLAUDE.md でなく `MEMORY.md` (auto memory) で保持
3. 探索は `Agent(subagent_type=Explore)` 委譲
4. CLAUDE.md に "Compact Instructions" セクションを追加して保持項目を制御

**誤検出の可能性**
- ファイル更新による再 Read は正常
- 長い設計議論なら高ターン数も正常
```

### 詳細リファレンス

→ [01-context-and-session.md §1.6](01-context-and-session.md#16-コンテキストロットの典型シグナル)

---

## 観点 5: スキル未活用

### 検出シグナル

| シグナル | 観察方法 |
| --- | --- |
| ユーザーリクエストに合うスキルがあるのに呼ばれていない | system-reminder のスキル一覧 vs 実際の Skill ツール呼出 |
| 似た description のスキルで誤起動 | ユーザー意図と起動スキルの不一致 |
| description が抽象的なスキル | "Use when..." が無い、キーワード不足 |

### 取得方法

```text
1. type == "system" エントリから "The following skills are available for use with the Skill tool:" を抽出
2. ユーザーリクエストごとに、本来トリガすべきスキル候補を判定
3. 実際に Skill ツールが呼ばれたかを確認
4. 未起動だったケースを抽出
```

注意: `type` を絞らず全行 grep するとヒット数が膨らみトークンを浪費する。

### 根拠

- 公式: "Make the description more specific"
- 公式: "Description front-load the key use case: capped at 1,536 characters"
- skill-creator パターン

### 提案テンプレ

```markdown
### スキル未起動の事例

**ユーザーリクエスト** (ターン X)
> "依存関係をアップデートしてマージしたい"

**起動すべきだったスキル**
- `merge-dependabot-bump-pr`

**現在の description**
> "Review and merge a Dependabot bump PR after safety checks."

**起動されなかった原因（推定）**
- description 中に「依存関係」「アップデート」「依存ライブラリ更新」等の
  日本語キーワードが無い
- "Use when..." が省略されており、自然言語からの triggering 精度が低い

**改善案**
"Review and merge a Dependabot bump PR after safety checks.
Use when the user wants to merge a Dependabot version bump PR, says
'依存関係をアップデート', '依存ライブラリ更新', 'Dependabot を見て',
'bump をマージ', or asks to handle dependency upgrade PRs. Performs
4-stage safety check (release age, critical bug reports, breaking
changes, source diff)."
```

### 詳細リファレンス

→ [03-extensions.md §3.3](03-extensions.md#33-skill-の設計)

---

## 観点横断: 提案優先順位の決定

agent-coach が複数の検出を出すとき、どれを「推奨アクション TOP3」に上げるかの基準:

### Tier 1（必ず TOP3 に入れる）

- シークレット流出可能性（即マスク + ユーザー警告）
- 危険コマンド検出（Hook safety gate 提案）
- 同じミスが 3 回以上反復（仕組み化提案）

### Tier 2（影響大なら TOP3）

- 補正ループ（2 回以上、書き換え案セット付き）
- 検証なしの「完了」宣言（Stop Hook 提案）
- スキル未活用が 3 件以上（description 改善提案）

### Tier 3（運用改善として）

- ターン数過多
- ファイル全文 Read
- cache miss

優先順位は「**ユーザーがすぐに行動でき、複数セッションに渡って効果が継続するもの**」を上に。

---

## 観点横断: 提案の書き方ルール

[agent-coach SKILL.md](../../../plugins/agent-coach/skills/agent-coach/SKILL.md) の運用ルール + 本サーベイで強調された原則:

1. **断定を避ける** — 「この可能性があります」「次回は試してみる価値があります」
2. **具体例まで提示** — 「もう少し明確に」ではなく書き換え後のプロンプトまで
3. **誤検出の可能性を脚注**
4. **公式 / 一次ソースへのリンクを根拠として併記**
5. **重大度の高い 3〜5 項目に絞る**（冗長を避ける）
6. **シークレット候補をマスク** (`sk-...`, `Bearer ...`, `password=...`)
7. **長い transcript の引用は避け、ターン番号 / 行番号で参照**
8. **本サーベイへのアンカーリンクを挿入**して、ユーザーが詳細根拠を辿れるようにする

---

## 観点横断: agent-coach 自身の改善余地

このサーベイをまとめた結果、現行 [agent-coach SKILL.md](../../../plugins/agent-coach/skills/agent-coach/SKILL.md) に対して提案できそうな改善:

| 提案 | 理由 |
| --- | --- |
| 「観点 0: シークレット検出」を追加 | 重大度 High だが現行は注意事項に書かれているだけ |
| 「ハーネス化提案」セクションを観点 3 に統合 | nyosegawa の Hook 4 パターンを根拠に、ルール違反 → Hook 化の判断基準を明文化 |
| description の Use when... を強化 | 「context rot を疑っている」「skill が triggering しない」等のトリガ語を追加 |
| 報告の各 finding に「重大度」と「公式根拠リンク」を必須化 | 提案の信頼性向上 |
| 検出シグナルを `examples/` ディレクトリにサンプル jsonl で残す | re-evaluation / regression test 化に向け |
