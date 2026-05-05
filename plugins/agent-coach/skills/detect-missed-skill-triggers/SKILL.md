---
description: Analyze recent Claude Code transcripts to detect cases where a Skill or subagent (Agent tool with subagent_type) should have been invoked but wasn't, and propose concrete description-frontmatter rewrites (Use when ... clauses, missing keywords, disambiguation from competing skills) plus Hook / skill-creator escalation when wording alone won't fix it. Use when skills feel underutilized, the user notices the model picking generic approaches over a matching specialized skill, you want to audit which skills are dormant across sessions, or you need rewrite suggestions for skill descriptions to improve triggering.
allowed-tools: Bash, Read, Write, Glob, Grep
---

# detect-missed-skill-triggers

## 概要

ユーザーの transcript JSONL を分析し、**スキル / サブエージェント（`Agent` ツールの `subagent_type` 指定）が本来トリガされるべきだったのにトリガされていないシーン**を検出する特化スキル。`agent-coach` の観点 5 が「サマリ提示」にとどまるのに対し、本スキルは:

1. transcript の `<system-reminder>` から **利用可能スキル/サブエージェント一覧を構造化**して復元
2. 各ユーザー入力について「どのスキル/サブエージェントが妥当だったか」を意味マッチで判定し、実際の `Skill` / `Agent` 呼び出しと突合
3. 未トリガ事例を **キーワード不足 / description 競合 / 知名度不足** の 3 原因に分類
4. 各原因に対して `description` フロントマターの**書き換え案**を提示（Use when 節追加、不足キーワード追加、競合スキルとの区別明示）
5. 文面改善で改善しない・影響が大きい場合は **Hook 化**または **skill-creator** での triggering 最適化を案内

`agent-coach` の総合健康診断で「スキル未活用が頻発している」とわかった後の**深掘り**として呼び出すのが想定ユースケース。単独でも動く。

## 前提条件

- macOS / Linux 環境（transcript パスは `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`）
- 分析対象セッションが少なくとも 1 件存在すること（パターン抽出には 3 件以上推奨。1〜2 件では「単発の見逃し」報告にフォールバック）
- （任意）プロジェクトの `CLAUDE.md`・`~/.claude/CLAUDE.md`・`plugins/*/skills/*/SKILL.md` が読めると、改善案の生成元 description が transcript 抽出と一致するかをクロスチェックできる

## 手順

### 1. 分析対象セッションの決定

- **対象プロジェクト**: 現在の cwd に対応する `~/.claude/projects/<encoded-cwd>/`。`Glob` または `ls ~/.claude/projects/ | grep <repo-basename>` で実在ディレクトリを特定
- **対象セッション**: そのディレクトリ配下の `*.jsonl` を mtime 降順で**最新 5〜10 セッション**（パターン化に複数セッションが必要）
- **除外**: 実行中セッション（mtime 最新の 1 件）。ユーザー明示指定時は除外しない
- **件数の調整**: ユーザーから指定があれば従う

候補セッション一覧（ファイル名 / mtime / サイズ / 概算ターン数）を簡潔に提示してから処理に進む。

### 2. 利用可能スキル/サブエージェント一覧の復元

transcript には Claude Code 側から `<system-reminder>` で利用可能なスキル一覧が注入される。これを抽出して構造化する。

#### 2.1 スキル一覧の場所

`type == "system"` レコードまたは `type == "user"` の `tool_result` 配下に、以下のヘッダで始まる節がある:

```
The following skills are available for use with the Skill tool:
- <skill-name>: <description>
- ...
```

走査手順:

1. ファイル全体を grep するとヒット数が膨らむため、`type == "system"` または `tool_result` ブロックに絞る
2. 上記ヘッダ以降〜次の空行/見出しまでを取り出す
3. 行頭が `- ` で始まる行を `name`（`:` 前）と `description`（`:` 後）に分割

セッション中に一覧が切り替わる場合（`/plugin install` 等）は、各 user 入力時点での「直前に観測した一覧」を採用する。

#### 2.2 サブエージェント一覧の場所

サブエージェントは `Agent` ツールのツール定義（システムプロンプト中）に含まれる。transcript の `type == "system"` 配下、または `Agent` ツール初登場時のツール定義テキストに以下のような行がある:

```
- <subagent-type>: <description> (Tools: ...)
```

代表的な type: `general-purpose`, `Explore`, `Plan`, `claude-code-guide`, `statusline-setup` 等。プロジェクト固有のカスタムサブエージェント（`.claude/agents/*.md`）も同様に列挙される。

抽出方法はスキル一覧と同様。

### 3. JSONL 構造のおさらい

| 場所 | 用途 |
| --- | --- |
| `type == "user"` の `message.content` | ユーザー入力テキスト（未トリガ判定の対象） |
| `type == "system"` 内の skill/subagent 一覧 | 利用可能スキル/サブエージェント |
| `type == "assistant"` の `message.content[]` 内の `tool_use`（`name == "Skill"`）| スキル呼び出し本体 |
| `type == "assistant"` の `message.content[]` 内の `tool_use`（`name == "Agent"`）| サブエージェント呼び出し本体（`input.subagent_type` を見る） |
| 各レコードの timestamp / 順序 | ターン番号 |

**1 ファイル全文 Read は避ける**。1MB 超は `Bash` の `python3` ヒアドキュメントで集計する（実装ヒント参照）。

### 4. 未トリガ判定（ユーザー入力単位）

各 `type == "user"` メッセージについて以下を実施:

1. **メッセージから意図を抽出**: 短文ならそのまま、長文なら冒頭 1〜2 文 + 動詞句（「○○して」「○○を作って」「○○について教えて」）を抽出
2. **候補スキル/サブエージェントのマッチング**:
   - 各スキル/サブエージェントの `description` の **Use when 節**（"Use when ..." または「次の場合に使う」相当）と意図文を意味マッチ
   - キーワードベースのマッチも併用（ユーザー意図の名詞・動詞が description に出現するか）
   - `disable-model-invocation: true` のスキルは候補から除外（明示呼び出し限定）
   - Slash コマンド形式（`/foo`）でユーザーが明示指定した場合はトリガ済みとみなす
3. **実呼び出しの確認**:
   - 同じユーザー入力以降〜次のユーザー入力までの間で、候補スキル/サブエージェントが `Skill` / `Agent` ツールで実際に呼ばれたか
   - 部分マッチ（`general-purpose` で十分なところを別の形で代替）も**呼ばれた**扱い
4. **未トリガ事例の記録**: 候補があったのに呼ばれなかったケースを 3 点組で記録
   - ユーザー入力テキスト（必要なら抜粋）
   - マッチした候補スキル/サブエージェント名
   - 実際の Claude の対応（generic 実装 / 別ツール直接利用 / 無視 等）
   - セッション ID + ターン番号

#### 判定の精度に関する注意

- **意味マッチは Claude の判断**: キーワード完全一致のみでは取り逃すので、Use when 節とユーザー意図を読み比べて妥当性を判断する
- **誤検出を避ける条件**:
  - ユーザーが「こうしてほしい」と具体的なアプローチを指定した場合は未トリガ扱いにしない
  - 候補スキルが実は別の用途を主目的としている（description 抜粋だけで判定すると外す）場合は除外
  - 1 文字程度のキーワード被りで強引にマッチさせない

### 5. パターンへの集約

未トリガ事例を以下の軸で集約する。

#### 5.1 同一スキル/サブエージェントごとに集約

- 同じスキル/サブエージェントが複数事例で未トリガ → 1 つの「未トリガパターン」にまとめる
- パターン内で代表事例 2〜3 件を保持

#### 5.2 原因の分類

各パターンを以下 3 種に分類:

| 原因 | シグナル |
| --- | --- |
| **キーワード不足** | ユーザーが繰り返し使った単語が `description` に明示されていない |
| **description 競合** | 似た description のスキルが複数あり、Claude が別のスキルを選んだ／一般実装を選んだ |
| **知名度不足** | 全セッション通じて 0〜1 回しか呼ばれていない（または「sub-」型でモデル invocation 自体が起こりにくい） |

複数原因が重なる場合は主因を 1 つ選び、補足として併記。

#### 5.3 セッション横断の傾向

- 「全セッション通算で未トリガ X 件」の上位スキル/サブエージェント
- 特定ユーザー意図カテゴリ（例: 「ファイル探索」「PR レビュー」「設定追加」）で繰り返し未トリガ

### 6. description 改善案の生成

各パターンに対して以下のいずれか（または複合）を提案する。**書き換え後の文面まで提示**すること（「もっと具体的に」だけで終わらせない）。

#### 6.1 Use when 節の追加・補強

不足キーワード・シナリオを Use when 節に追加する。

雛形:

```yaml
description: <既存の説明>. Use when <user-keyword-1>, <user-keyword-2>, or <pattern> — for example "<代表ユーザー入力>".
```

#### 6.2 不足キーワードの埋め込み

ユーザーが多用する単語を description 本文に明示する。同義語をカンマで列挙すると意味マッチの取りこぼしを減らせる。

#### 6.3 競合スキルとの区別明示

似た description が複数ある場合は **Distinct from** 節を加える。

雛形:

```yaml
description: <既存の説明>. Distinct from <other-skill>: this handles <specific-aspect>; <other-skill> handles <other-aspect>.
```

#### 6.4 SKIP 条件の明示

逆に「使うべきでない場面」が誤検出を生んでいる場合（過剰トリガではないが Claude が判断に迷う場合）は SKIP 条件を加える。

雛形:

```yaml
description: <既存の説明>. SKIP when <not-applicable-context>.
```

#### 6.5 ハーネス化（文面改善で改善しない場合）

description の書き換えだけで繰り返し外れる場合は以下を案内:

- **UserPromptSubmit Hook で `<system-reminder>` を注入**してスキル使用を強制（決定論的）
  - 例: 「ユーザー入力に `commit` が含まれていたら、まず `git status` で状態確認を促す reminder を注入」
- **skill-creator** の triggering 最適化機能を回す（description のリフレーズ + evals）
- 競合する skill 同士を 1 つに統合する（過剰な分割が原因の場合）

### 7. レポート生成

レポートは画面に直接ダンプせず、ファイルに書き出す。

1. 出力ディレクトリ: **`.ai-agent/tmp/<YYYYMMDD>-skill-triggers/`**（cwd 基準）。存在しなければ `mkdir -p`
2. レポート本文: `<出力ディレクトリ>/report.md` を `Write` で書き出す
3. 画面には以下のみ表示:
   - レポートファイルパス
   - 未トリガパターン件数（skills: N / subagents: M）
   - 推奨アクション TOP3

#### レポート構造（ファイル本文）

````markdown
# 未トリガ検出レポート

対象: <セッション一覧 / 期間>
分析範囲: 最新 N セッション（<earliest> 〜 <latest>）
利用可能スキル: <K> 件 / サブエージェント: <L> 件
ユーザー入力総数: <X>

## TL;DR

- 未トリガパターン: skills <A> / subagents <B>
- 主因の内訳: キーワード不足 <a> / description 競合 <b> / 知名度不足 <c>
- → 推奨アクション TOP3 は末尾

---

## 未トリガパターン

### パターン 1: `<skill-or-subagent-name>` (<未トリガ件数>件 / 主因: <キーワード不足|競合|知名度不足>)

**起きていること**:
- セッション `<id1>` ターン N1: ユーザーが「<入力抜粋>」と依頼 → Claude は <generic 実装 / 別ツール直接利用 / 無視> で対応
- セッション `<id2>` ターン N2: ...

**現状の description**:
> <抜粋>

**改善案**:

```yaml
description: <既存>. Use when <追加トリガ>, e.g. "<代表ユーザー入力>". Distinct from <other-skill>: <区別>.
```

（または）Hook 提案:

```json
{
  "hooks": {
    "UserPromptSubmit": [{
      "matcher": "<regex>",
      "command": "<command>"
    }]
  }
}
```

(パターンごとに繰り返し。最大 5 パターン。それ以上は「その他のパターン」に圧縮)

---

## サブエージェント未トリガ（特に重い調査・並列調査の取り逃し）

| サブエージェント | 未トリガ件数 | 代表ユーザー入力 | 改善案 |
| --- | ---: | --- | --- |
| `Explore` | 6 | 「○○の実装を調べて」 | description に "broad codebase exploration" を強調、competing tool との優先関係明示 |
| `general-purpose` | 3 | ... | ... |

---

## クロスセッション傾向

- 全セッション通算で 0 回呼ばれたスキル: <list>（知名度不足候補）
- カテゴリ別未トリガ件数（PR レビュー / コミット / 探索 / 設定変更 / etc）

## 統計サマリ

- セッション数: <N>
- ユーザー入力総数: <X>
- 候補マッチ件数: <Y>
- 未トリガ件数: <Z>
- スキル別呼び出し回数 TOP10 と未トリガ件数

## 誤検出の可能性

- ユーザーが具体的アプローチを指定したケースは未トリガではない
- description 抜粋のみで判定したケース（手動で本文確認推奨）
- 同義 skill が既に呼ばれていて、Claude の選択は妥当だったケース

## 推奨アクション TOP3

1. **<アクション>** — <1 行の why と how>
2. **<アクション>** — <1 行の why と how>
3. **<アクション>** — <1 行の why と how>
````

#### TOP3 の優先度

| Tier | 内容 |
| --- | --- |
| Tier 1（必ず TOP3） | 未トリガ件数 5 件以上の単一スキル / 全セッション 0 呼び出しの「死蔵スキル」 / 重要度の高いサブエージェント（Explore など）の繰り返し未トリガ |
| Tier 2（影響大なら TOP3） | 単一セッション 3 件以上の未トリガ / description 競合で複数スキルが共倒れ |
| Tier 3（運用改善） | 単発の未トリガ / SKIP 条件追加で済む軽微なもの |

判断基準: **書き換え + 1 アクションで複数の未トリガが解消できるもの**を上に置く。

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

SKILL_HEADER = "The following skills are available for use with the Skill tool:"

def extract_skill_list(text: str):
    """system reminder からスキル一覧を抽出。name, description のリストを返す。"""
    if SKILL_HEADER not in text:
        return []
    body = text.split(SKILL_HEADER, 1)[1]
    items = []
    for line in body.splitlines():
        m = re.match(r"\s*-\s+([A-Za-z0-9:_-]+):\s*(.+)", line)
        if not m:
            if items and not line.strip():
                break  # 空行で終了
            continue
        items.append({"name": m.group(1), "description": m.group(2)})
    return items

def iter_records(path):
    for line in open(path):
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue

per_session = defaultdict(lambda: {"skills": [], "user_inputs": [], "skill_calls": [], "agent_calls": []})

for path in SESSIONS:
    sid = os.path.basename(path).removesuffix(".jsonl")
    current_skills = []
    for rec in iter_records(path):
        t = rec.get("type")
        if t == "system":
            text = rec.get("content") or rec.get("message", {}).get("content", "")
            if isinstance(text, list):
                text = "\n".join(b.get("text", "") for b in text if isinstance(b, dict))
            extracted = extract_skill_list(text)
            if extracted:
                current_skills = extracted
        elif t == "user":
            content = rec.get("message", {}).get("content")
            if isinstance(content, str):
                per_session[sid]["user_inputs"].append({"text": content, "skills_at_time": current_skills})
        elif t == "assistant":
            for block in rec.get("message", {}).get("content", []):
                if block.get("type") != "tool_use":
                    continue
                name = block.get("name")
                if name == "Skill":
                    per_session[sid]["skill_calls"].append(block.get("input", {}).get("skill"))
                elif name == "Agent":
                    per_session[sid]["agent_calls"].append(block.get("input", {}).get("subagent_type"))
    per_session[sid]["skills"] = current_skills
```

完全実装は不要 — Claude が transcript を読み取り、未トリガ事例の判定とパターン化を行えれば良い。集計が複雑になりすぎたら**1〜2 セッションだけ手で読み込み**、定性的に finding を作っても十分価値がある。

## 注意事項

- **transcript には機密情報が含まれる可能性がある**。ユーザー入力抜粋にトークン的な値が混入していないか軽くチェックし、疑わしければマスクする（agent-coach の観点 0 と同じ方針）
- **自分自身のセッションを分析しないこと**（ユーザー明示対象時を除く）。mtime 最新の jsonl を実行中セッションとみなして除外
- **巨大 JSONL の全文 Read を避ける**。1 ファイル 1MB を超える場合は `python3` での集計を併用
- **意味マッチは断定を避ける**。「未トリガ確定」ではなく「未トリガ候補」のトーンを基本に、誤検出条件を必ず併記
- **agent-coach との関係**: 観点 5 の TL;DR と矛盾しないこと（同じセッションを見ているはずなので、検出傾向は一致する想定）
- **改善提案は具体的に**。「description をもっと明確に」ではなく**書き換え後の文面まで提示**する
- **レポートはファイルに書き出し**、画面には TL;DR + TOP3 + パスのみ表示する
