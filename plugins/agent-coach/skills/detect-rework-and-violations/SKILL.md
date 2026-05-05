---
description: Analyze recent Claude Code transcripts to detect rework loops (direction corrections, redo cycles, post-completion rollbacks) and instruction violations against project rules (CLAUDE.md, skill definitions, memory files, system reminders), then propose concrete remediation across five categories — prompt rewrites, rule wording improvements, Hook-based deterministic enforcement, rewind workflow advice, and skill description fixes. Use when the user feels work needs frequent redoing, the model ignores established rules, you want to audit how often the model went off-track, or you need actionable rewrites for prompts and rules.
allowed-tools: Bash, Read, Write, Glob, Grep
---

# detect-rework-and-violations

## 概要

ユーザーの transcript JSONL を分析し、**手戻り**（方向修正ループ・差し戻し・「やり直し」指示）と **指示違反**（CLAUDE.md / SKILL.md / memory / system reminder で示されたルールに対する違反）を検出する特化スキル。`agent-coach` の観点 2（方向修正多発プロンプト）と観点 3（指示違反）が「サマリ提示」止まりなのに対し、本スキルは:

1. プロジェクトと session 内に存在する**ルールを構造化抽出**（"必ず X する" / "Y してはいけない" / skill description の Use when / Distinct from / SKIP 条件）
2. 手戻り事例を **3 点組（元プロンプト → Claude の解釈 → ユーザーの修正）**で抽出
3. 指示違反事例を **(ルール文, 違反した assistant 行動, 違反ターン)** で抽出
4. 主因を 5 種に分類（**曖昧プロンプト / ルール埋没 / 検証なし完了 / トリガミス / コンテキストロット起因**）
5. 改善提案を 5 カテゴリに分類して具体的な書き換え案を提示（**A. プロンプト書き換え / B. ルール明文化 / C. Hook 化 / D. 巻き戻し運用 / E. skill description 改善**）

`agent-coach` の総合健康診断で「補正ループや指示違反が主因らしい」とわかった後の**深掘り**として呼び出すのが想定ユースケース。単独でも動く。

姉妹スキルとの関係:

- `detect-context-rot`: 履歴肥大による劣化が主眼。本スキルは「rot がなくても起きる」ループ・違反に焦点を当て、改善は文面レベル（プロンプト・ルール文言）と運用レベル（Hook・巻き戻し）が中心。違反の主因が rot 起因の場合は `detect-context-rot` の結果と整合させる
- `detect-token-hotspots`: トークン消費が主眼。本スキルは消費量と独立に「やり直し」と「指示無視」を見る
- `detect-missed-skill-triggers`: スキル/サブエージェント未トリガが主眼。本スキルは「使うべきだったが使わなかった」結果が指示違反になっているケースを重複検出する。両者で同じ finding が出るのが正常で、改善カテゴリ E（description 改善）は同じ提案に揃える

## 前提条件

- macOS / Linux 環境（transcript パスは `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`）
- 分析対象セッションが少なくとも 1 件存在すること（パターン抽出には 3 件以上推奨。1〜2 件しかないときは「単発の手戻り / 違反」の報告にフォールバック）
- （任意）プロジェクトの `CLAUDE.md`・`~/.claude/CLAUDE.md`・`~/.claude/projects/<encoded-cwd>/memory/*.md`・`<repo>/.claude/skills/**/SKILL.md`・`plugins/*/skills/**/SKILL.md` が読めると、ルール抽出の精度が上がる

## 手順

### 1. 分析対象セッションの決定

- **対象プロジェクト**: 現在の cwd に対応する `~/.claude/projects/<encoded-cwd>/`。`Glob` または `ls ~/.claude/projects/ | grep <repo-basename>` で実在ディレクトリを特定
- **対象セッション**: そのディレクトリ配下の `*.jsonl` を mtime 降順で**最新 5〜10 セッション**（パターン化に複数セッション推奨）
- **除外**: 実行中セッション（mtime 最新の 1 件）。ユーザー明示指定時は除外しない
- **件数の調整**: ユーザーから指定があれば従う

候補セッション一覧（ファイル名 / mtime / サイズ / 概算ターン数）を簡潔に提示してから処理に進む。

### 2. JSONL の構造把握（手戻り・違反検出に使うフィールド）

| 場所 | 用途 |
| --- | --- |
| `type == "user"` の `message.content` | ユーザー入力（修正指示・元指示・否定語の検出） |
| `type == "assistant"` の `message.content[]` の `text` | Claude の応答テキスト（「Wait, you mean...」「I'll commit now」等の確認/宣言パターン） |
| `type == "assistant"` の `message.content[]` の `tool_use` | 実行された行動（違反判定の対象） |
| `type == "system"` 内の skill 一覧 / CLAUDE.md / システム reminder | 当該セッションで有効だったルール |
| 各レコードの timestamp / 順序 | ターン番号、隣接性の判定 |

**1 ファイル全文 Read は避ける**。1MB 超は `Bash` で `python3` ヒアドキュメントで集計する（実装ヒント参照）。

### 3. ルールの構造化抽出

「ルール」とは `必ず X する` / `Y してはいけない` / `Z の場合は ...` のような **assistant の行動を制約する記述**。違反検出の左辺。

#### 3.1 プロジェクトファイルから

以下を `Read` で確認（存在する範囲で）:

- `<repo>/CLAUDE.md`
- `<repo>/.claude/CLAUDE.md`
- `~/.claude/CLAUDE.md`
- `~/.claude/projects/<encoded-cwd>/memory/*.md`（auto memory）
- `<repo>/.claude/skills/**/SKILL.md` の本文
- `plugins/*/skills/**/SKILL.md` の本文

抽出対象の語彙パターン（日英混在）:

- `必ず`, `しなければならない`, `MUST`, `IMPORTANT`, `Always`
- `してはいけない`, `禁止`, `NEVER`, `NEVER use`, `Never`, `Don't`, `避ける`
- `〜のとき`, `〜の場合`, `Use when`, `When ...`, `If ...`
- `〜と区別する`, `Distinct from`, `Not for`, `SKIP when`

各ルールを `(出典ファイル, 該当行 or 抜粋, 否定/肯定, 適用条件)` の組で保持。

#### 3.2 当該セッションの system reminder から

`type == "system"` の reminder（または `tool_result` 配下）には、その時点で有効な以下が含まれることがある:

- `# claudeMd` ブロック（プロジェクト CLAUDE.md の現在の内容）
- 利用可能スキル一覧（description にトリガ条件・SKIP 条件を含む）
- 個別スキルの SKILL.md 本文（Skill ツール呼び出し時に注入される）
- Auto Mode / Permission Mode の宣言

セッション中に内容が切り替わる場合は、各 user 入力時点で「直前に観測した reminder」を採用する。

#### 3.3 ユーザーが直前に与えたルール

直前のユーザー指示で「以後は X しないで」「次回からは Y を使って」と発話されたら、その時点以降に対する**新規ルール**として動的に追加する。

### 4. シグナル抽出

#### 4.1 手戻りシグナル（観点 2 系統）

ユーザーメッセージ中の以下を検出:

- **否定・修正語**: `no`, `not that`, `not what I meant`, `instead`, `actually`, `stop`, `wait`, `違う`, `そうじゃなくて`, `やめて`, `いや`, `じゃなくて`, `戻して`, `revert`, `undo`, `元に戻して`
- **短い即時返信**: 直前 assistant ターンへの即応で、ユーザーメッセージが 50 文字未満（不満の即時表明シグナル）
- **同一トピック再指示**: 直近 3 ターン以内にユーザーが同じ対象（同じファイル名・関数名・機能名）を再度言及して別の指示を出している
- **完了後の差し戻し**: assistant が「完了しました」「Done」「PR を作成しました」等の宣言をした次のユーザー入力に否定・修正語が含まれる
- **assistant の確認パターン**: assistant 応答に `Wait, you mean ...?`, `Did you mean ...?`, `Let me clarify ...`, `すみません、もう一度確認させてください` 等が現れる
- **`/rewind` / `Esc Esc`**: ユーザーが巻き戻し操作を行った痕跡（`type == "user"` で `<command-name>/rewind</command-name>` 等）

各シグナル検出時、**直前の元プロンプト**を 1 つ前の `type == "user"` から特定し、紐付けて保持する。

#### 4.2 指示違反シグナル（観点 3 系統）

3 で抽出したルール各 R について、当該セッションの assistant 行動を走査し、違反候補を検出:

- ルールが「必ず X する」型 → 該当文脈で X が行われていない `tool_use` シーケンス
- ルールが「Y してはいけない」型 → 該当文脈で Y が `tool_use` または assistant text に出現
- ルールが skill description の Use when / SKIP when → 該当ユーザー入力時に当該 skill を呼ばずに別手段で対応している（detect-missed-skill-triggers と重複可）

代表例:

| ルール | 違反シグナル |
| --- | --- |
| 「コミットは指示時のみ」 | ユーザー指示なしで `git commit` 実行 |
| 「`--no-verify` は使わない」 | `git commit --no-verify` / `--no-gpg-sign` の使用 |
| 「テスト追加・実行」 | 実装後に `pytest` / `npm test` を実行せず終了 |
| 「コメントは書かない」 | 新規コード追加で `//`, `#` コメント挿入 |
| 「README は要求時のみ」 | `*.md` の `Write` 新規作成（要求なし） |
| 「英語で書く / 日本語で書く」 | 指定言語と異なる出力 |
| skill description Use when ... | 該当ケースで Skill ツール未呼び出し（generic 実装） |

#### 4.3 3 点組の組み立て

各手戻り・違反イベントについて以下を 1 レコードにまとめる:

```
{
  "kind": "rework" | "violation",
  "session": "<id>",
  "turn": <int>,
  "rule_or_signal": "<ルール文 or 修正語パターン>",
  "user_original": "<元プロンプト抜粋>",
  "claude_action": "<assistant の応答 / tool_use 要約>",
  "user_correction": "<修正プロンプト抜粋>",  // rework のみ
  "rule_source": "<出典>"  // violation のみ
}
```

#### 4.4 検出の精度に関する注意

- **誤検出を避ける条件**:
  - 否定語があってもそれが過去の話題への言及（"yesterday I said no to ..."）なら手戻りではない
  - ルール文の「IMPORTANT」が一般的注意であって個別アクションを禁じていない場合は違反扱いにしない
  - ユーザー自身が一旦容認した行動（assistant が確認 → ユーザー OK）後の方針変更は手戻りに数えない
  - 計画的な「ステップ 2 として行います」を完了後の差し戻しと誤判定しない
- **断定を避ける**: ルール本文の解釈には幅があるため、複数シグナルが揃ったときに「違反候補」のトーンで提示する

### 5. パターン化（主因分類）

検出した 3 点組レコードを以下の主因軸で集約する。1 件が複数主因に当てはまる場合は最も影響度が高い主因を main、他は補足参照。

| 主因 | シグナル | 代表的改善カテゴリ |
| --- | --- | --- |
| **曖昧プロンプト** | 元プロンプトに具体性が乏しい（"いい感じに", "適切に", "直して" 単独） / Claude が `Wait, you mean ...?` を返した | A（プロンプト書き換え） |
| **ルール埋没** | ルール出典が CLAUDE.md の中盤以降 / system reminder の長文末尾 / 違反が複数セッションで反復 | B（ルール明文化） |
| **検証なし完了** | 「完了」宣言の直後に差し戻し / テスト / 動作確認の `tool_use` が無いまま finish | C（Hook 化）または B（ルール明文化） |
| **トリガミス** | 該当 skill の Use when にマッチしているのに Skill 未呼び出しで generic 対応 | E（description 改善） + 必要なら B |
| **コンテキストロット起因** | 違反ターンが推定 rot 始点以降 / 同セッション後半でのみ違反 / 初期指示が消失している | `detect-context-rot` への送り（D 巻き戻し / Compact Instructions） |

#### 5.1 セッション横断の傾向

- 同一ルールが **複数セッションで違反** → ルール文言改善 + Hook 化が候補
- 同一プロンプトパターンで **複数回手戻り** → プロンプト雛形化 / skill 化候補
- 完了後差し戻しが頻発 → 完了ゲート Hook（Stop）を提案

### 6. 改善提案カテゴリへのマッピング

検出した 3 点組を以下 5 カテゴリに振り分け、**書き換え後の文面まで提示**する。「もっと明確に」だけでは終わらせない。

#### A. プロンプト書き換え（曖昧プロンプト → 具体プロンプト）

雛形:

```
[元プロンプト]
"認証直して"

[改善後]
"src/auth/login.ts:42 の `if (user.email)` が falsy 値を見落としている。
 `if (user?.email != null)` に修正し、tests/auth.test.ts:120 の
 `it('rejects empty email')` をパスさせて確認。他のテストはそのまま。"
```

押さえるポイント:

- ファイルパス + 行番号 + 関数名で **対象を一意化**
- **期待挙動と検証方法**を 1 行で
- **触らない範囲**を明示（暗黙の差分を防ぐ）

#### B. ルール明文化（埋没 → 上位配置・専用 memory ファイル）

雛形 1: CLAUDE.md 冒頭への昇格

```markdown
# プロジェクト名

## IMPORTANT — must follow

- コミットは明示的指示時のみ。`git commit` を勝手に呼ばない。
  - **Why:** 過去にレビュー前のコミットで CI を汚した経緯があるため
  - **How to apply:** ユーザーが「コミットして」と言うまで `git status` 提示で止まる
```

雛形 2: 専用 memory ファイル化（auto memory 仕様）

```markdown
---
name: no-auto-commit
description: コミットはユーザー明示指示時のみ
type: feedback
---

`git commit` をユーザー指示なしで実行しない。

**Why:** 過去にレビュー前コミットで CI を汚し、revert 対応が発生した。
**How to apply:** ユーザーが「コミットして」と言うまで、`git status` の提示で止まる。
```

#### C. Hook 化（決定論的強制）

ルール違反が **3 回以上反復** している、または影響が大きいときに昇格提案する。CLAUDE.md は advisory、Hook は deterministic。

代表的 Hook 種別:

| 状況 | Hook 種別 | 例 |
| --- | --- | --- |
| 完了前のテスト未実行 | Stop | `scripts/require-tests-passed.sh` で exit 2 |
| 危険コマンド実行 | PreToolUse Safety Gate | `Bash` matcher + `git push --force` 等のブロック |
| `--no-verify` 使用 | PreToolUse | matcher で `Bash`、`--no-verify` を含む command を exit 2 |
| リント違反 | PostToolUse Quality Loop | フォーマッタ自動実行 + 違反箇所を additionalContext に注入 |
| 同一ルール違反 N 回 | PostToolUse | 違反検出ごとに reminder 注入 |

Hook 設定スニペット例:

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

#### D. 巻き戻し運用（補正ループの脱出）

補正が **2 回続いた**時点で、続けて修正するより `Esc Esc`（または `/rewind`）で巻き戻し → A の改善プロンプトで再開するほうが効率的。

レポートに含めるテンプレ:

> セッション `<id>` ターン N〜N+2 で同一トピックの補正が 3 回続いています。次回類似ケースは 2 回目で `Esc Esc` → 改善プロンプトで再開してください。
> 改善プロンプト雛形: 「<A で生成した具体プロンプト>」

#### E. skill description 改善（トリガミス）

トリガミス起因で違反が起きている場合は、該当 skill の description フロントマターを書き換える。雛形:

```yaml
description: <既存の説明>. Use when <user-keyword-1>, <user-keyword-2>, or <pattern> — for example "<代表ユーザー入力>". Distinct from <other-skill>: this handles <specific-aspect>.
```

詳細パターンは `detect-missed-skill-triggers` の手順 6 を参照。本スキルでは「違反として顕在化したケース」のみ E に分類し、description 抜粋 + 1 行の修正案にとどめ、深掘りは姉妹スキルへ案内する。

### 7. レポート生成

レポートは画面に直接ダンプせず、ファイルに書き出す。

1. 出力ディレクトリ: **`.ai-agent/tmp/<YYYYMMDD>-rework-violations/`**（cwd 基準）。存在しなければ `mkdir -p`
2. レポート本文: `<出力ディレクトリ>/report.md` を `Write` で書き出す
3. 画面には以下のみ表示:
   - レポートファイルパス
   - 検出件数（rework: N / violation: M）と主因 TOP2
   - 推奨アクション TOP3

#### レポート構造（ファイル本文）

````markdown
# Rework & Violation 検出レポート

対象: <セッション一覧 / 期間>
分析範囲: 最新 N セッション (<earliest> 〜 <latest>)
抽出ルール: <K> 件（CLAUDE.md / SKILL.md / memory / system reminder）

## TL;DR

- 手戻り: <N> 件 / 指示違反: <M> 件
- 主因内訳: 曖昧プロンプト <a> / ルール埋没 <b> / 検証なし完了 <c> / トリガミス <d> / rot 起因 <e>
- 反復違反ルール TOP3: <ルール 1> / <ルール 2> / <ルール 3>
- → 推奨アクション TOP3 は末尾

---

## 手戻りパターン

### パターン 1: <名前 — 例: 完了後の方向修正> (<件数>件 / 主因: <曖昧プロンプト | ...>)

**起きていること**:
- セッション `<id1>` ターン N1: 元 "<元プロンプト抜粋>" → Claude は <要約> → ユーザー "<修正抜粋>"
- セッション `<id2>` ターン N2: ...

**改善案 (A. プロンプト書き換え)**:

```
[元] <元プロンプト>
[改善後] <具体プロンプト雛形>
```

**運用案 (D. 巻き戻し)**:
> 2 回目の補正で `Esc Esc` → 上記改善プロンプトで再開推奨

(パターンごとに繰り返し。最大 3 パターン)

---

## 指示違反パターン

### 違反 1: 「<ルール文の要約>」 (<件数>件 / 出典: <CLAUDE.md / SKILL.md / memory>)

**事例**:
- セッション `<id1>` ターン N1: <違反した tool_use 要約 / assistant 応答抜粋>
- セッション `<id2>` ターン N2: ...

**現状のルール文**:
> <抜粋>

**主因**: <ルール埋没 | 検証なし完了 | rot 起因 | トリガミス>

**改善案 (B. ルール明文化)**:

```markdown
<書き換え後の CLAUDE.md / memory ファイル雛形>
```

**Hook 化案 (C, 反復が 3 回以上の場合)**:

```json
{
  "hooks": { ... }
}
```

(違反ごとに繰り返し。最大 3 違反。それ以上は「その他の違反」に圧縮)

---

## クロスセッション傾向

- 反復違反ルール: <ルール> が <n> セッションで違反 → B + C 推奨
- 反復手戻りパターン: <パターン> が <n> セッションで再現 → A の雛形プロンプトを CLAUDE.md に追加候補
- 完了宣言後差し戻し率: <X>%（rework 中の割合）→ Stop Hook 候補

## 統計サマリ

- セッション数: <N>
- ターン総数: <合計>
- 手戻り件数: <rework_total>
- 指示違反件数: <violation_total>
- ルール抽出元: CLAUDE.md <a> / SKILL.md <b> / memory <c> / system reminder <d>

## 誤検出の可能性

- 否定語含むユーザー入力でも、過去の話題引用なら手戻りではない
- ルール文が一般的注意であって個別アクションを禁じていない場合は違反ではない
- 段階的計画の「次ステップ」を完了後差し戻しと誤判定する可能性
- rot 起因の違反は本スキルの改善案より先に `detect-context-rot` の対処を優先

## 推奨アクション TOP3

1. **<アクション>** — <1 行の why と how>
2. **<アクション>** — <1 行の why と how>
3. **<アクション>** — <1 行の why と how>
````

#### TOP3 の優先度

| Tier | 内容 |
| --- | --- |
| Tier 1（必ず TOP3） | 同一ルール違反が 3 回以上反復 / 危険コマンド系違反（`--no-verify`, `git push --force`, `rm -rf`） / 完了後差し戻しが 3 回以上 |
| Tier 2（影響大なら TOP3） | 補正ループ 2 回以上の単一パターン / 単一セッション違反 5 件以上 / トリガミス起因違反が複数セッションで反復 |
| Tier 3（運用改善） | 単発の手戻り / 軽微な文面違反 / SKIP 条件追加で済むもの |

判断基準: **書き換え + 1 アクションで複数の手戻り/違反が解消できるもの**を上に。Hook 化（C）は決定論的に効くため反復違反では Tier 1 に上がりやすい。

#### finding が少ないとき

検出が 1〜2 件しかないときは、パターン化せず **「気づいたこと」セクション 1 つ + TOP3** に圧縮する。空でも構造を埋めるために finding を水増ししないこと。

### 8. 実装ヒント

`Bash` で `python3` ヒアドキュメントを使うと一気に集計できる。骨格例:

```python
import json, glob, os, re
from collections import defaultdict

SESSIONS = sorted(
    glob.glob(os.path.expanduser("~/.claude/projects/<encoded-cwd>/*.jsonl")),
    key=os.path.getmtime, reverse=True
)[1:11]  # 実行中除外して 10 件

NEG_WORDS = re.compile(
    r"\b(no|not that|not what I meant|instead|actually|stop|wait|revert|undo)\b"
    r"|違う|そうじゃ(ない|なくて)|やめて|いや|じゃなくて|戻して|元に戻して",
    re.IGNORECASE,
)
DONE_DECLARATIONS = re.compile(
    r"\b(done|completed|finished|all set|created the PR)\b|完了しました|終わりました|作成しました",
    re.IGNORECASE,
)

def iter_records(path):
    for line in open(path):
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue

def user_text(rec):
    msg = rec.get("message", {})
    c = msg.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "\n".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
    return ""

def assistant_text_and_tools(rec):
    msg = rec.get("message", {})
    text_parts = []
    tools = []
    for b in msg.get("content", []):
        if b.get("type") == "text":
            text_parts.append(b.get("text", ""))
        elif b.get("type") == "tool_use":
            tools.append((b.get("name"), b.get("input", {})))
    return "\n".join(text_parts), tools

def find_rework_events(path):
    """直近 assistant ターンに対する否定即時返信を抽出。"""
    last_assistant = None  # (turn_idx, text, tools)
    last_user = None  # (turn_idx, text)
    turn_idx = 0
    events = []
    for rec in iter_records(path):
        t = rec.get("type")
        if t == "assistant":
            turn_idx += 1
            text, tools = assistant_text_and_tools(rec)
            last_assistant = (turn_idx, text, tools)
        elif t == "user":
            ut = user_text(rec)
            if last_assistant and NEG_WORDS.search(ut):
                events.append({
                    "turn": last_assistant[0],
                    "user_original": last_user[1] if last_user else "",
                    "claude_action": last_assistant[1][:200],
                    "user_correction": ut[:200],
                    "post_done": bool(DONE_DECLARATIONS.search(last_assistant[1])),
                })
            last_user = (turn_idx, ut)
    return events

def find_violations(path, rules):
    """rules: [{'text': ..., 'kind': 'positive'|'negative', 'matcher': callable(tools, asst_text) -> bool}]"""
    turn_idx = 0
    violations = []
    for rec in iter_records(path):
        if rec.get("type") != "assistant":
            continue
        turn_idx += 1
        text, tools = assistant_text_and_tools(rec)
        for r in rules:
            if r["matcher"](tools, text):
                violations.append({"turn": turn_idx, "rule": r["text"]})
    return violations

# ルール例: 「--no-verify を使わない」
rules = [
    {
        "text": "git commit --no-verify を使わない",
        "kind": "negative",
        "matcher": lambda tools, text: any(
            name == "Bash" and "--no-verify" in (args.get("command") or "")
            for name, args in tools
        ),
    },
]
```

完全実装は不要 — Claude が transcript を読み取り、3 点組の組み立てとパターン化ができれば良い。集計が複雑になりすぎたら**1〜2 セッションだけ手で読み込み**、定性的に finding を作っても十分価値がある（このスキルのゴールは「ユーザーが次の書き換え／運用変更を選べる」こと）。

## 注意事項

- **transcript には機密情報が含まれる可能性がある**。レポートに引用する元プロンプトや tool_use 引数にトークン的な値が混入していないか軽くチェックし、疑わしければマスクする（`agent-coach` 観点 0 と同じ方針）
- **自分自身のセッションを分析しないこと**（ユーザー明示対象時を除く）。mtime 最新の jsonl を実行中セッションとみなして除外する
- **巨大 JSONL の全文 Read を避ける**。1 ファイル 1MB を超える場合は `python3` ヒアドキュメントでの集計を併用する
- **ルール抽出は完全ではない**。自然言語の抜粋なので解釈には幅がある。違反判定は複数シグナル（語彙 + tool_use 不在/存在）が揃ったときに「違反候補」のトーンで提示する
- **誤検出条件を必ず併記**。「補正ループ確定」ではなく「補正ループ候補」、「指示違反確定」ではなく「指示違反候補」を基本トーンに
- **`detect-context-rot` との関係**: rot 始点以降に集中する違反は、本スキルの B/C 改善より先に `detect-context-rot` の D（MEMORY 移行）/ E（Compact Instructions）で対処したほうが根治することがある。レポートに「rot 起因の可能性」として案内する
- **`detect-missed-skill-triggers` との関係**: トリガミス起因の違反は両スキルで重複検出される。改善カテゴリ E（description 改善）は同じ提案に揃え、書き換え案の生成は姉妹スキルに委ねるか、本スキルでは要約 + 案内にとどめる
- **改善提案は具体的に**。「もっと明確に書いてください」「気をつけてください」ではなく**書き換え後の文面 / Hook スニペット / 巻き戻し操作**まで提示する
- **Hook 化の提案は慎重に**。CLAUDE.md の文面改善で十分なケースで Hook を提案すると運用が重くなる。**3 回以上反復**または**影響が大きい**ケースに限定する
- **レポートはファイルに書き出し**、画面には TL;DR + TOP3 + パスのみ表示する
