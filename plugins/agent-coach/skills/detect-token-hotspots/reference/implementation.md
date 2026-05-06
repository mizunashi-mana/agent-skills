# 実装ヒント（detect-token-hotspots）

`Bash` で `python3` ヒアドキュメントを使うと一気に集計できる。本体 SKILL.md の手順 3〜5 を満たす最小実装の骨格を示す。

完全実装は不要 — Claude が transcript を読み取り上記指標を集計できれば良い。集計が複雑になりすぎたら **1〜2 セッションだけ手で読み込み**、定性的に finding を作っても十分価値がある（このスキルのゴールは「ユーザーが次の書き換えを選べる」こと）。

## 1. ターン単位の usage / tool_result 集計（v2.1.x JSONL 対応）

```python
import json, glob, os
from collections import Counter, defaultdict
from datetime import datetime

PROJ = os.path.expanduser("~/.claude/projects/<encoded-cwd>/")

def select_sessions():
    files = sorted(glob.glob(PROJ + "*.jsonl"), key=os.path.getmtime, reverse=True)
    sel = []
    for i, p in enumerate(files):
        if i == 0:
            continue  # in-progress
        if os.path.getsize(p) < 5000:
            continue  # tiny / empty
        sel.append(p)
        if len(sel) >= 10:
            break
    return sel

def tool_result_len(content):
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(len(p.get("text", "") or "") for p in content if isinstance(p, dict))
    return 0

def per_turn(path):
    """ターンごとに usage と紐づく tool_result サイズを返す。"""
    pending = {}  # tool_use_id -> (turn_idx, name, args)
    turns = []   # [{turn, usage, tools: [(name, args, result_len)], ts, deferred_count}]
    turn_idx = 0
    deferred_added = []  # accumulated deferred tool names
    for line in open(path, errors="replace"):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = rec.get("type")
        if t == "attachment":
            att = rec.get("attachment") or {}
            if att.get("type") == "deferred_tools_delta":
                deferred_added.extend(att.get("addedNames", []) or [])
        elif t == "assistant":
            turn_idx += 1
            usage = rec.get("message", {}).get("usage", {}) or {}
            cc_extra = usage.get("cache_creation") or {}
            entry = {
                "turn": turn_idx,
                "usage": {
                    k: usage.get(k, 0) or 0
                    for k in (
                        "input_tokens",
                        "output_tokens",
                        "cache_creation_input_tokens",
                        "cache_read_input_tokens",
                    )
                },
                "cc_1h": cc_extra.get("ephemeral_1h_input_tokens", 0),
                "cc_5m": cc_extra.get("ephemeral_5m_input_tokens", 0),
                "tools": [],
                "ts": rec.get("timestamp"),
            }
            turns.append(entry)
            for block in rec.get("message", {}).get("content", []) or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    pending[block.get("id")] = (
                        turn_idx,
                        block.get("name"),
                        block.get("input") or {},
                    )
        elif t == "user":
            content = rec.get("message", {}).get("content")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        tid = block.get("tool_use_id")
                        info = pending.pop(tid, None)
                        if info is None:
                            continue
                        ti, name, args = info
                        size = tool_result_len(block.get("content"))
                        for tt in turns:
                            if tt["turn"] == ti:
                                tt["tools"].append((name, args, size))
                                break
    return turns, deferred_added
```

## 2. 軸別 hot spot 抽出

```python
def cache_miss_ratio(turn):
    u = turn["usage"]
    cc = u["cache_creation_input_tokens"]
    cr = u["cache_read_input_tokens"]
    return cc / (cc + cr + 1)

def hotspots(turns, k=10):
    by_cc       = sorted(turns, key=lambda t: -t["usage"]["cache_creation_input_tokens"])[:k]
    by_tool_sz  = sorted(turns, key=lambda t: -sum(s for _, _, s in t["tools"]))[:k]
    by_output   = sorted(turns, key=lambda t: -t["usage"]["output_tokens"])[:k]
    return by_cc, by_tool_sz, by_output

def cc_plateaus(turns, min_n=2, tol=0.01):
    """A.2 plateau 検出: 連続 N ターンで cc 値が一致 (差分 1% 以内)。"""
    plateaus = []
    i = 0
    while i < len(turns):
        cc_i = turns[i]["usage"]["cache_creation_input_tokens"]
        if cc_i < 5000:
            i += 1
            continue
        j = i + 1
        while j < len(turns):
            cc_j = turns[j]["usage"]["cache_creation_input_tokens"]
            if abs(cc_j - cc_i) > tol * max(cc_i, 1):
                break
            j += 1
        if j - i >= min_n:
            seg = turns[i:j]
            tools = Counter()
            for t in seg:
                for n, _, _ in t["tools"]:
                    tools[n] += 1
            plateaus.append({
                "start": seg[0]["turn"],
                "end": seg[-1]["turn"],
                "n": j - i,
                "cc_each": cc_i,
                "cc_total": cc_i * (j - i),
                "tools": dict(tools),
            })
        i = max(j, i + 1)
    return plateaus

def heavy_segments(turns, min_n=5, factor=1.5):
    """Axis E: 連続 N ターン以上 cc > avg*factor。TaskCreate 主体は除外。"""
    if len(turns) < min_n:
        return []
    avg = sum(t["usage"]["cache_creation_input_tokens"] for t in turns) / len(turns)
    threshold = avg * factor
    runs, run = [], []
    for t in turns:
        if t["usage"]["cache_creation_input_tokens"] > threshold:
            run.append(t)
        else:
            if len(run) >= min_n:
                runs.append(run)
            run = []
    if len(run) >= min_n:
        runs.append(run)
    out = []
    for r in runs:
        tools = Counter()
        for t in r:
            for n, _, _ in t["tools"]:
                tools[n] += 1
        total_calls = sum(tools.values())
        task_setup = sum(tools.get(n, 0) for n in ("TaskCreate", "TaskUpdate", "TaskList"))
        write_only = sum(tools.get(n, 0) for n in ("Write", "Edit"))
        is_research = total_calls > 0 and task_setup / total_calls < 0.5 and write_only / total_calls < 0.5
        out.append({
            "start": r[0]["turn"],
            "end": r[-1]["turn"],
            "n": len(r),
            "cc_total": sum(t["usage"]["cache_creation_input_tokens"] for t in r),
            "tools": dict(tools),
            "agent_calls": tools.get("Agent", 0) + tools.get("Skill", 0),
            "research_candidate": is_research,
        })
    return out
```

## 3. クロスセッション集約

```python
def cross_session_aggregates(sessions):
    file_reads = Counter()
    file_chars = Counter()
    file_offset_count = Counter()
    bash_pfx = Counter()
    bash_chars = Counter()
    mcp_servers = Counter()  # mcp__<server>__... -> count of sessions where it appears
    mcp_calls = Counter()    # actual mcp__* invocations across sessions

    for path in sessions:
        turns, deferred = per_turn(path)
        for n in deferred:
            if n.startswith("mcp__"):
                # extract server segment
                parts = n.split("__")
                server = parts[1] if len(parts) > 1 else n
                # count once per session even if same server is added multiple times
                pass
        # MCP server set per session
        servers_in_session = set()
        for n in deferred:
            if n.startswith("mcp__"):
                parts = n.split("__")
                if len(parts) > 1:
                    servers_in_session.add(parts[1])
        for s in servers_in_session:
            mcp_servers[s] += 1

        for t in turns:
            for name, args, size in t["tools"]:
                if name == "Read":
                    fp = (args or {}).get("file_path", "")
                    file_reads[fp] += 1
                    file_chars[fp] += size
                    if (args or {}).get("offset") is not None or (args or {}).get("limit") is not None:
                        file_offset_count[fp] += 1
                elif name == "Bash":
                    cmd = ((args or {}).get("command") or "").strip()
                    head = " ".join(cmd.split()[:2]) if cmd else ""
                    bash_pfx[head] += 1
                    bash_chars[head] += size
                elif name.startswith("mcp__"):
                    mcp_calls[name] += 1
    return {
        "file_reads": file_reads,
        "file_chars": file_chars,
        "file_offset_count": file_offset_count,
        "bash_pfx": bash_pfx,
        "bash_chars": bash_chars,
        "mcp_servers": mcp_servers,
        "mcp_calls": mcp_calls,
    }
```

## 4. ターン間ギャップ検出（5.5）

```python
def parse_ts(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None

def gap_events(turns, threshold_min=5):
    out = []
    prev = None
    for t in turns:
        ts = parse_ts(t["ts"])
        if prev is not None and ts is not None:
            gap = (ts - prev).total_seconds() / 60
            if gap >= threshold_min:
                out.append({
                    "turn": t["turn"],
                    "gap_min": gap,
                    "next_miss": cache_miss_ratio(t),
                    "next_cc1h": t["cc_1h"],
                    # 1h cache 増分が大きいときのみ TTL 切れシグナル
                })
        prev = ts
    return out
```

## 5. 軽量フォールバック（ヒアドキュメント不要）

集計が複雑になりすぎたとき、または対象セッションが 1〜2 件の場合:

1. `wc -l <session>.jsonl` でターン規模を見る
2. `Bash` で `grep -c '"type":"assistant"'` でアシスタントターン数を概算
3. `Bash` で `python3 -c 'import json,sys; ...'` をワンライナーで実行し、cc / cr の総計だけ得る
4. **質的な finding** として「特定 SKILL.md を頻繁に読んでいる」「TaskCreate を多用している」等を 1〜2 セッション目視 (`Read` の最初 200 行) で抽出

このスキルのゴールは「ユーザーが次の書き換えを選べる」こと。**精度 100% は不要**。
