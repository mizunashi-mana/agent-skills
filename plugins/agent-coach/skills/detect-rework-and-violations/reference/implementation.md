# 実装ヒント（Python ヒアドキュメント例）

`Bash` で `python3` ヒアドキュメントを使うと一気に集計できる。完全実装は不要 — Claude が transcript を読み取り、3 点組の組み立てとパターン化、クロスセッションクラスタリングができれば良い。集計が複雑になりすぎたら**1〜2 セッションだけ手で読み込み**、定性的に finding を作っても十分価値がある。

## 骨格

```python
import json, glob, os, re
from collections import defaultdict

SESSIONS = sorted(
    glob.glob(os.path.expanduser("~/.claude/projects/<encoded-cwd>/*.jsonl")),
    key=os.path.getmtime, reverse=True
)[1:11]  # 実行中除外して 10 件

NEG_WORDS = re.compile(
    r"\b(no|not that|not what I meant|instead|actually|stop|wait|revert|undo)\b"
    r"|違う|そうじゃ(ない|なくて)|やめて|いや|じゃなくて|戻して|元に戻して|やり直し",
    re.IGNORECASE,
)
DONE_DECLARATIONS = re.compile(
    r"\b(done|completed|finished|all set|created the PR)\b|完了しました|終わりました|作成しました",
    re.IGNORECASE,
)
INSTR_KEYS = re.compile(
    r"(してください|して下さい|お願い|しないで|避けて|しましょう|ましょう|"
    r"にして|に変えて|に直して|に変更|追加して|含めて|含めましょう|"
    r"\bplease\b|\bdon't\b|\bmust\b|\balways\b|\bnever\b|\binstead\b|\balso\b)",
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

def is_user_actual_input(rec):
    """tool_result やローカルコマンド出力ではなく、実ユーザー発話か判定。"""
    msg = rec.get("message", {})
    c = msg.get("content")
    if isinstance(c, list):
        for b in c:
            if isinstance(b, dict) and b.get("type") == "tool_result":
                return False
    if isinstance(c, str) and ("<local-command-stdout>" in c or "<local-command-stderr>" in c):
        return False
    return True

def assistant_text_and_tools(rec):
    msg = rec.get("message", {})
    text_parts = []
    tools = []
    for b in msg.get("content", []):
        if not isinstance(b, dict):
            continue
        if b.get("type") == "text":
            text_parts.append(b.get("text", ""))
        elif b.get("type") == "tool_use":
            tools.append((b.get("name"), b.get("input", {})))
    return "\n".join(text_parts), tools

def find_rework_events(path):
    """否定即時返信 + post-completion supplement を抽出。"""
    last_assistant = None
    last_user = None
    turn_idx = 0
    events = []
    for rec in iter_records(path):
        t = rec.get("type")
        if t == "assistant":
            turn_idx += 1
            text, tools = assistant_text_and_tools(rec)
            last_assistant = (turn_idx, text, tools)
        elif t == "user" and is_user_actual_input(rec):
            ut = user_text(rec)
            if not ut.strip(): continue
            if last_assistant:
                # (a) 否定語ベース
                if NEG_WORDS.search(ut):
                    events.append({
                        "kind": "negation",
                        "turn": last_assistant[0],
                        "user_correction": ut[:200],
                        "post_done": bool(DONE_DECLARATIONS.search(last_assistant[1])),
                    })
                # (e) post-completion supplement (否定語なしの追加指示)
                elif INSTR_KEYS.search(ut) and DONE_DECLARATIONS.search(last_assistant[1]):
                    events.append({
                        "kind": "post_completion_supplement",
                        "turn": last_assistant[0],
                        "user_supplement": ut[:200],
                    })
            last_user = (turn_idx, ut)
    return events

def find_violations(path, rules, slash_command_frames):
    """rules: [{'text', 'matcher': callable(name, args, text) -> bool, 'allowed_in_commands': [...] }]
    slash_command_frames: [(turn, command_name, template_text)]
    """
    turn_idx = 0
    violations = []
    for rec in iter_records(path):
        if rec.get("type") != "assistant":
            continue
        turn_idx += 1
        text, tools = assistant_text_and_tools(rec)
        for r in rules:
            for name, args in tools:
                if not r["matcher"](name, args, text):
                    continue
                # slash command コンテキストガード
                cur_frame = next(
                    (f for f in reversed(slash_command_frames) if f[0] <= turn_idx),
                    None,
                )
                if cur_frame and cur_frame[1] in r.get("allowed_in_commands", []):
                    continue  # 許可済み
                violations.append({"turn": turn_idx, "rule": r["text"], "evidence": str(args)[:200]})
    return violations

# 例: 「コミットは指示時のみ」 + /autodev-create-pr で許可
rules = [
    {
        "text": "コミットはユーザー明示指示時のみ",
        "matcher": lambda name, args, text: name == "Bash" and "git commit" in (args.get("command","")),
        "allowed_in_commands": ["/autodev-create-pr", "/autodev-import-review-suggestions"],
    },
    {
        "text": "git commit --no-verify を使わない",
        "matcher": lambda name, args, text: name == "Bash" and "--no-verify" in (args.get("command","")),
        "allowed_in_commands": [],  # 常に違反
    },
]

# slash command frame の抽出（2 系統: <command-name> と Base directory for this skill:）
SKILL_BASEDIR_RE = re.compile(r"Base directory for this skill:\s*\S+/skills/([\w\-]+)")

def collect_slash_command_frames(path):
    """returns [(turn, command_name, full_user_text), ...]
    <command-name>/<name></command-name> の正規形と、
    `Base directory for this skill: .../skills/<name>` 形式の自由貼付け版の両方を拾う。
    """
    frames = []
    turn_idx = 0
    for rec in iter_records(path):
        t = rec.get("type")
        if t == "assistant":
            turn_idx += 1
            continue
        if t != "user" or not is_user_actual_input(rec):
            continue
        ut = user_text(rec)
        m_cmd = re.search(r"<command-name>([^<]+)</command-name>", ut)
        if m_cmd:
            frames.append((turn_idx, m_cmd.group(1).strip().lstrip("/"), ut))
            continue
        m_base = SKILL_BASEDIR_RE.search(ut)
        if m_base:
            frames.append((turn_idx, m_base.group(1).strip(), ut))
    return frames

# 直前ユーザー発話の明示指示チェック（4.2.1 step 4）
USER_EXPLICIT_INSTR_RE = re.compile(
    r"(コミット|commit|プッシュ|push|PR|プルリク|task\s*README|README).*(して|しましょう|してください|お願い|please|do)"
    r"|(して|しましょう|してください|お願い).*(コミット|commit|push|PR)",
    re.IGNORECASE | re.DOTALL,
)

def has_user_explicit_instruction(violation_turn, user_messages):
    """違反ターンの直前 1 ユーザー発話に明示指示が含まれるかチェック。
    user_messages: [(turn, text), ...] (ユーザー実発話のみ、ターン昇順)
    """
    prev = [u for u in user_messages if u[0] <= violation_turn]
    if not prev: return False
    return bool(USER_EXPLICIT_INSTR_RE.search(prev[-1][1]))
```

## クロスセッション反復指示の集約（手順 4.5）の最小実装

```python
# 候補抽出: 各セッションから 10〜300 文字、命令キー含む user 実発話を集める
def collect_short_instructions(path):
    out = []
    turn_idx = 0
    for rec in iter_records(path):
        t = rec.get("type")
        if t == "assistant":
            turn_idx += 1
            continue
        if t != "user" or not is_user_actual_input(rec):
            continue
        ut = user_text(rec).strip()
        if not (10 <= len(ut) <= 300): continue
        if ut.startswith("<command-") or "<bash-input>" in ut: continue
        if not INSTR_KEYS.search(ut): continue
        out.append({"turn": turn_idx + 1, "text": ut})
    return out

# 簡易クラスタリング: 文字 4-gram Jaccard >= 0.30 OR 共通キーフレーズ >= 2
def char_ngrams(s, n=4):
    s = re.sub(r"\s+", "", s)
    return {s[i:i+n] for i in range(len(s)-n+1)} if len(s) >= n else set()

def keyphrases(s):
    # 英数 3 文字以上 / 漢字カナ 3 文字以上を抜く
    return set(re.findall(r"[A-Za-z][A-Za-z0-9]{2,}|[一-龥ァ-ヶー]{3,}", s))

def cluster_cross_session(all_instr_with_session):
    """[(session, turn, text), ...] -> [[member, ...], ...]
    2 セッション以上で出現したクラスタのみ採用。
    """
    # 各候補に ngram + keyphrase を計算
    enriched = [
        {**x, "ng": char_ngrams(x["text"]), "kp": keyphrases(x["text"])}
        for x in all_instr_with_session
    ]
    clusters = []
    visited = set()
    for i, a in enumerate(enriched):
        if i in visited: continue
        cluster = [a]; visited.add(i)
        for j in range(i+1, len(enriched)):
            if j in visited: continue
            b = enriched[j]
            if a["session"] == b["session"]: continue
            ng_jaccard = len(a["ng"] & b["ng"]) / max(1, len(a["ng"] | b["ng"]))
            kp_overlap = len(a["kp"] & b["kp"])
            if ng_jaccard >= 0.30 or kp_overlap >= 2:
                cluster.append(b); visited.add(j)
        if len({x["session"] for x in cluster}) >= 2:
            clusters.append(cluster)
    clusters.sort(key=lambda c: -len({x["session"] for x in c}))
    return clusters
```

## セッショントピックの抽出（手順 1.1）

セッション ID 単独では読み手に意味が伝わらないため、各セッションに 1 行の topic を付ける:

```python
TOPIC_COMMANDS = {
    "/autodev-start-new-task", "/autodev-start-new-project", "/autodev-start-new-survey",
    "/autodev-discussion", "/autodev-create-issue",
    "/autodev-replan", "/autodev-steering", "/init",
}
PR_COMMANDS = {"/autodev-create-pr", "/autodev-import-review-suggestions", "/autodev-review-pr"}
NOISE_COMMANDS = {"/clear", "/compact", "/help", "/rewind", "/fast"}

def extract_topic(path):
    """セッショントピック (string, branch) を返す。
    優先順位: topic-defining コマンドの args > PR 系コマンド + branch名 > その他コマンド > 自由入力先頭。
    """
    first_topic = first_pr = first_other = first_freeform = None
    branch = None
    for rec in iter_records(path):
        if rec.get("gitBranch") and not branch:
            branch = rec.get("gitBranch")
        if rec.get("type") != "user" or not is_user_actual_input(rec):
            continue
        ut = user_text(rec)
        if not ut: continue
        m_cmd = re.search(r"<command-name>([^<]+)</command-name>", ut)
        if m_cmd:
            cmd = m_cmd.group(1).strip()
            if cmd in NOISE_COMMANDS: continue
            m_args = re.search(r"<command-args>([^<]*)</command-args>", ut, re.DOTALL)
            args = m_args.group(1).strip() if m_args else None
            if cmd in TOPIC_COMMANDS and not first_topic:
                first_topic = (cmd, args)
                break
            if cmd in PR_COMMANDS and not first_pr:
                first_pr = (cmd, args)
            if cmd not in TOPIC_COMMANDS and cmd not in PR_COMMANDS and not first_other:
                first_other = (cmd, args)
        else:
            if (not first_freeform
                and not re.match(r"^<(local-command|bash-input|bash-stdout|bash-stderr)", ut)
                and not ut.startswith("Base directory for this skill:")):
                first_freeform = ut.strip()

    def fmt(ca):
        cmd, args = ca
        return f"{cmd} 「{args[:80]}」" if args else cmd

    if first_topic:
        return fmt(first_topic), branch
    if first_pr:
        b_short = (branch or "").split("/")[-1] if branch and branch != "main" else branch
        return f"{fmt(first_pr)} (branch: {b_short or '-'})", branch
    if first_other:
        return fmt(first_other), branch
    if first_freeform:
        return first_freeform[:80], branch
    return "(no topic found)", branch
```

## さらに簡易な代替（手で十分）

実装が複雑になるなら、**手で目視 + Grep** で十分:

```bash
grep -h '<bash-input>\|<command-' -v <session-files> \
  | grep -E '(してください|しましょう|please|don'\''t)' \
  | sort -u
```

10 セッション 50〜100 候補なら 5 分で読める。
