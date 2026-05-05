---
description: Analyze recent Claude Code transcripts to find Bash commands that ran in auto / bypassPermissions mode but are not in permissions.allow, and recommend allowlist patterns grouped by readonly / write. Use when the user wants to harvest auto-mode usage into a curated allowlist, audit which commands run without prompts, or migrate from auto mode to default / acceptEdits without losing convenience.
allowed-tools: Bash, Read, Write, Glob, Grep
---

# recommend-bash-allowlist

## 概要

ユーザーの transcript JSONL を分析し、`auto` または `bypassPermissions` モード下で実行された `Bash` コマンドのうち、現在の `permissions.allow` にマッチしないものを抽出する。前方一致パターン（`Bash(<prefix>:*)` 形式）に集約し、readonly / write / unknown の 3 グループに分類して TOP 50 を提示する。ユーザーは結果から安全なものを `permissions.allow` に追加することで、緩いモードを抜けても同等の使用感を維持できる。

## 前提条件

- macOS / Linux 環境（transcript パスは `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`）
- 分析対象セッションが少なくとも 1 件存在し、そのうち最低 1 件が `auto` または `bypassPermissions` モードでの実行を含むこと
- `~/.claude/settings.json` または `<repo>/.claude/settings*.json` の少なくとも片方が読める（無くてもエラーにはせず、空 allowlist 扱いで進める）

## 手順

### 1. 分析対象セッションの決定

- **対象プロジェクト**: 現在の cwd に対応する `~/.claude/projects/<encoded-cwd>/`。`Glob` または `ls ~/.claude/projects/ | grep <repo-basename>` で実在ディレクトリを特定する
- **対象セッション**: そのディレクトリ配下の `*.jsonl` を mtime 降順で最新 5〜10 セッション
- **除外**: 実行中セッション（mtime 最新の 1 件）。ユーザーが明示指定した場合は除外しない
- **件数の調整**: ユーザーから指定があれば従う

候補セッション一覧（ファイル名 / mtime / サイズ）を簡潔に提示してから処理に進む。

### 2. JSONL の構造把握

各行が独立した JSON オブジェクト。本スキルで使う主なフィールド:

| 場所 | 内容 |
| --- | --- |
| `type == "permission-mode"` のレコード | そのターン以降の `permissionMode` を切替（`auto`, `default`, `plan`, `acceptEdits`, `bypassPermissions` 等） |
| `type == "assistant"` の `message.content[]` 内の `tool_use` ブロック（`name == "Bash"`） | Bash 呼び出し本体。`input.command` に実コマンド |
| `cwd`, `gitBranch`, `sessionId` | 文脈用 |

`permission-mode` レコードは `timestamp` を持たず、フィールドも極小（実例）:

```json
{"type": "permission-mode", "permissionMode": "auto", "sessionId": "..."}
```

同モード値でも転送のたびに繰り返し出現することがある。位置情報は **JSONL の行順** だけが頼りなので、ストリーミングで先頭から読むこと。

**permissionMode 区間の構築**:

1. ファイル先頭からシーケンシャルに走査
2. `type == "permission-mode"` を見つけたら現在モードを更新
3. それ以降の `tool_use` レコードに「現在のモード」を割り当てる
4. ファイル冒頭にモードレコードが無い場合は `default` 扱い

### 3. 対象 Bash コマンドの抽出

各 `tool_use` (Bash) について:

- 現在の permissionMode が `auto` または `bypassPermissions` のもののみ採用
- `input.command` を取得
- `cd /path && actual_cmd` のような連結は **`actual_cmd` 部分** を解析対象とする（`cd ... && `、`export X=Y && ` などの prefix は剥がす）
- `;`, `&&`, `||`, `|` で連結された複数コマンドは **左から順に各々を解析対象**にする（ただし複雑な引用や heredoc が絡む場合は最初のコマンドのみで妥協してよい）

巨大セッションは `python3 -c "..."` で集約することを推奨。1 ファイル全文 Read は避ける。

### 4. 現行 allowlist の取得

以下を順に読み、`permissions.allow` を結合:

1. `~/.claude/settings.json`
2. `<repo>/.claude/settings.json`
3. `<repo>/.claude/settings.local.json`

各エントリは `Bash(<pattern>)` または `Bash(<pattern>:*)` 形式。比較用に以下に正規化:

- `Bash(git log:*)` → prefix `git log`、suffix glob あり
- `Bash(npm install)` → prefix `npm install`、完全一致のみ
- `Bash(<other-tool>...)` → 本スキルでは Bash 以外は無視

### 5. prefix の抽出（readonly/write 判別可能な粒度）

各コマンドから prefix を抽出する。深さは「readonly か write かを人間が判断できる単位」を目安に決める。

#### 抽出ルール

1. コマンドを空白でトークナイズ
2. 先頭トークンを取得
3. 先頭トークンが下表の「サブコマンド体系ツール」に該当する場合、指定深さまでトークンを連結
4. それ以外は先頭トークンのみ
5. オプションフラグ（`-`, `--` で始まるトークン）の扱い:
   - **中間に挟まっているフラグはスキップ**（例: `git --no-pager log` → `git log`）
   - **末尾の動作決定フラグは prefix に含める**: depth-N の非フラグトークンを取った直後に**ちょうど 1 つだけ** `--xxx` 形式のフラグがあり、それ以降に非フラグが続かない場合は、そのフラグも prefix に取り込む。例:
     - `git rebase --continue` → `git rebase --continue`（write/readonly 判定が `--continue` で決まるため）
     - `git branch --show-current` → `git branch --show-current`（readonly）
     - `git remote get-url origin` の `get-url` のような **非フラグの動詞**は (D1 の例外則) で対処、ここではフラグのみ
   - 末尾フラグが 2 つ以上連続する場合（例: `git log --oneline --graph`）は format option とみなし、prefix には**含めない**（`git log` のまま）

#### サブコマンド体系ツールの深さ表

| ツール | 深さ | 例 |
| --- | --- | --- |
| `git` | 2 | `git log`, `git push`, `git rebase --continue` |
| `gh` | 3 | `gh pr view`, `gh issue list`, `gh run watch` |
| `npm` | 2 | `npm install`, `npm run`, `npm test` |
| `pnpm` / `yarn` | 2 | `pnpm add`, `yarn install` |
| `npx` | 2 | `npx tsc`, `npx eslint` |
| `aws` | 3 | `aws s3 ls`, `aws sts get-caller-identity` |
| `gcloud` / `az` | 3 | `gcloud compute instances list` |
| `kubectl` | 2 | `kubectl get`, `kubectl apply` |
| `docker` / `podman` | 2 | `docker ps`, `docker build` |
| `brew` / `mas` | 2 | `brew info`, `mas search` |
| `nix` | 2 | `nix flake show`, `nix search` |
| `cargo` / `go` / `dotnet` | 2 | `cargo build`, `go test` |
| `terraform` / `tofu` | 2 | `terraform plan`, `terraform apply` |
| `make` | 1 | `make` |
| `uv` / `pip` / `poetry` | 2 | `uv pip list`, `pip show` |
| その他のコマンド | 1 | `ls`, `cat`, `find`, `grep`, `jq`, `head` |

ツール固有の慣用句（`nix-prefetch-url`, `nix-prefetch-github` 等）は単一トークンとして扱う。

#### 深さ例外則: 末尾動詞で readonly/write が分かれるサブコマンド

`git remote get-url` (readonly) と `git remote add` (write) のように、depth=2 で同じ prefix にまとまるが末尾動詞で readonly/write が決まるサブコマンドがある。以下に該当する場合は **+1 段深く** prefix を取る:

- `git remote {add|set-url|rename|remove}` (write) / `git remote {get-url|show|prune}` (readonly)
- `git submodule {add|update|deinit}` (write) / `git submodule {status|summary|foreach}` (readonly)
- `git stash {push|pop|drop|apply|clear}` (write) / `git stash {list|show}` (readonly)
- `git tag` 引数に応じて write/readonly → tag 名引数があれば write、`-l` `--list` なら readonly
- `npm run <script>` (script 次第で write/readonly) → 一段深く取って `npm run <script>` 単位で集計

本表に列挙されない動詞でも、depth=2 で `unknown` 落ちした prefix の出現が多い場合は手動で +1 段拡張してよい。

最終的に推薦パターンは `Bash(<prefix>:*)` 形式に整形する。

### 6. readonly / write / unknown の分類

prefix の **末尾の動詞トークン** を以下のキーワードリストで分類する。マッチしないものは `unknown` として扱う。誤分類があり得るので、レポート上で「この分類は heuristic」と明示する。

#### readonly キーワード

- 観察系: `log`, `status`, `show`, `view`, `get`, `list`, `ls`, `ll`, `head`, `tail`, `cat`, `less`, `more`, `diff`, `describe`, `inspect`, `info`, `outdated`, `audit`, `search`, `whoami`, `pwd`, `find`, `grep`, `rg`, `fd`, `readlink`, `realpath`, `stat`, `file`, `which`, `where`, `type`, `du`, `df`, `wc`, `tree`, `tac`, `sort`, `uniq`, `cut`, `awk`, `sed -n`, `xxd`, `base64 -d`
- 検査系: `check`, `test`, `lint`, `validate`, `dry-run`, `--dry-run`, `--help`, `-h`, `--version`, `version`, `verify`, `analyze`, `explain`, `plan`（`terraform plan` は readonly）
- git 系: `rev-parse`, `ls-files`, `ls-remote`, `ls-tree`, `merge-base`, `symbolic-ref`, `remote`（get-url 等）, `submodule`（status 等）, `blame`, `shortlog`, `cherry`, `name-rev`, `for-each-ref`, `reflog`, `worktree list`, `--show-current`, `--show-toplevel`, `--get-url`
- gh 系: `pr view`, `pr list`, `pr diff`, `pr checks`, `issue view`, `issue list`, `repo view`, `release view`, `release list`, `run view`, `run list`, `run watch`, `run download`, `cache list`, `label list`, `search`, `api`（GET メソッドが既定。POST/PATCH/PUT/DELETE フラグがあれば write）
- aws 系: `get-`, `list-`, `describe-`, `head-`（プレフィックス match）

#### write キーワード

- 変更系: `install`, `add`, `update`, `upgrade`, `remove`, `uninstall`, `delete`, `rm`, `mv`, `cp`, `chmod`, `chown`, `mkdir`, `rmdir`, `touch`, `ln`, `link`, `unlink`, `truncate`, `sync`, `dd`
- 作成系: `create`, `new`, `clone`, `fork`, `generate`, `gen`, `scaffold`, `make`（make ターゲットは個別判断）
- ビルド系: `build`, `compile`, `bundle`, `pack`, `publish`, `release`, `deploy`
- 実行系: `exec`, `run`, `start`, `stop`, `restart`, `kill`, `apply`, `destroy`, `init`, `migrate`, `seed`, `provision`, `bootstrap`, `setup`, `teardown`
- VCS 系: `commit`, `push`, `pull`, `fetch`, `merge`, `rebase`, `checkout`, `branch`, `tag`, `reset`, `stash`, `cherry-pick`, `revert`, `am`, `mv`
- 編集系: `format`, `fix`（lint --fix 等は write 寄り）, `edit`, `rename`, `replace`, `patch`

#### 判定優先順位

1. prefix 末尾フラグ (`--show-current`, `--list` 等) が readonly キーワードに完全一致 → readonly
2. prefix 末尾トークンが write キーワードに完全一致 → write
3. prefix 末尾トークンが readonly キーワードに完全一致 → readonly
4. prefix 末尾トークンが `aws` の `get-`/`list-`/`describe-`/`head-` で始まる → readonly
5. それ以外 → unknown

「`gh pr view`」のように prefix 全体で意味を持つ場合は最後のトークン (`view`) を見れば良い。

#### 任意コード実行系の特別扱い

`python3`, `python`, `node`, `bash`, `sh`, `zsh`, `fish`, `ruby`, `perl`, `osascript`, `deno`, `bun` のような **インタプリタ系コマンド** は、`Bash(python3:*)` のような prefix 形式で allowlist に追加すると **任意コード実行を全許可**することと等しい。これらの prefix は次のいずれかで扱う:

- 推薦結果から完全に除外する（推奨）
- もしくは推薦には残すが「⚠ allowlist 不適合（任意コード実行）」のラベルを付け、ユーザーが追加しないよう明示的に注意喚起する

heredoc (`python3 << 'EOF' ... EOF`) や `-c '...'` は本体のコードが任意である以上、prefix 単位の許可は意味を持たない。

### 7. 集約と TOP N (≤50) 選定

- 同一 prefix のコマンドを集計（出現回数 + 代表コマンド例 1〜2 件）
  - 代表コマンド例は **改行で truncate** する（heredoc 本体やリダイレクト後の続きを切る）。長すぎる場合は 120 文字で省略
- 既に `permissions.allow` でマッチするものは別バケット「カバー済み」に分離（除外ではなく集計表示する）
  - prefix がいずれかの allowlist エントリの prefix と完全一致 → カバー済み
  - prefix が allowlist エントリの prefix の **下位（より長い接頭辞）** → カバー済み（既に親パターンで許可済み）
  - 例: 既に `Bash(git:*)` があれば `git log` はカバー済み。`Bash(git log:*)` があれば `git log --oneline` 由来の prefix `git log` はカバー済み
- 「推薦候補」は**未カバーのもの**から、出現回数の多い順で **最大 50 件**（候補が少なければそのまま全件）
- 同数の場合は readonly を優先
- インタプリタ系（手順 6 の特別扱い）は推薦候補ではなく**警告セクション**に分離する

### 8. レポート生成

レポートは画面に直接ダンプせず、ファイルに書き出す:

1. 出力ディレクトリは **`.ai-agent/tmp/<YYYYMMDD>-bash-allowlist/`**（cwd 基準）。存在しなければ `mkdir -p`
2. レポート本文を `.ai-agent/tmp/<YYYYMMDD>-bash-allowlist/report.md` として `Write`
3. 画面には以下のみ表示する:
   - レポートファイルのパス
   - 各グループ件数（readonly / write / unknown）
   - 上位 5 件のサマリ（推薦パターン + 出現回数）

#### レポート構造

````markdown
# Bash allowlist 推薦レポート

対象: <セッション一覧と期間>
分析モード: auto + bypassPermissions
現行 allowlist: ~/.claude/settings.json (N 件) + <repo>/.claude/settings.json (M 件) + <repo>/.claude/settings.local.json (K 件)

## サマリ

- Bash 呼び出し総数 (全モード): <N_all>
- 抽出コマンド (auto / bypassPermissions): <N_target>
- 既存 allowlist でカバー済み (distinct prefix): <M>
- 推薦候補 (未カバー、distinct prefix): <K>
  - readonly: <X>
  - write: <Y>
  - unknown: <Z>
  - ⚠ 任意コード実行系 (allowlist 不適合): <W>

> 既存 allowlist が十分大きく readonly 推薦が 0 になる場合は、それは allowlist の成熟シグナルであり問題ではありません。

## 推薦パターン TOP N (最大 50)

### 🟢 readonly (<件数>)

| 推薦パターン | 出現回数 | 代表コマンド例 |
| --- | ---: | --- |
| `Bash(git log:*)` | 42 | `git log --oneline -10` |
| `Bash(ls:*)` | 38 | `ls -la /path/to/dir` |
| ... | | |

### 🟡 write (<件数>)

| 推薦パターン | 出現回数 | 代表コマンド例 |
| --- | ---: | --- |
| `Bash(npm install)` | 12 | `npm install` |
| `Bash(git commit:*)` | 8 | `git commit -m "..."` |
| ... | | |

### ⚪ unknown (<件数>)

heuristic で分類できなかったもの。手動確認推奨。

| 推薦パターン | 出現回数 | 代表コマンド例 |
| --- | ---: | --- |

### ⚠ 任意コード実行系 (allowlist 不適合)

`Bash(<interpreter>:*)` 形式で allowlist に追加すると任意コード実行を許可することになるため、**追加しないこと**を推奨します。auto モードで都度承認するか、用途を限定する運用ルールに留めてください。

| パターン | 出現回数 | 備考 |
| --- | ---: | --- |
| `Bash(python3:*)` | 18 | heredoc / -c による任意コード実行 |

## 既存 allowlist でカバー済み (TOP 10)

参考までに、auto/bypassPermissions モードで実行されたが既に許可済みの prefix を出現回数順で:

| 出現回数 | カバー済み prefix |
| ---: | --- |
| 14 | `ls` |
| 4 | `cat` |
| ... | |

## 反映方法

readonly 系で問題なさそうなものはそのまま、write 系・unknown はユーザーが個別に安全性判断したうえで追加してください。`~/.claude/settings.json` または `<repo>/.claude/settings.json` に:

```json
{
  "permissions": {
    "allow": [
      "Bash(git log:*)",
      "Bash(ls:*)"
    ]
  }
}
```

⚠ **追加非推奨と推奨範囲限定の例**:

- `Bash(python3:*)` 等のインタプリタ系: **追加しないこと**を推奨（任意コード実行）
- `Bash(git push:*)`: force push (`--force`) も通過するためリスク許容できる場合のみ
- `Bash(git checkout:*)`: 任意ブランチへの切り替えも通過。`Bash(git checkout main)` など特定ブランチ限定の方が安全
- `Bash(git branch:*)`: `git branch -D <name>` 等の破壊的操作も通過。`Bash(git branch --show-current)` 等のサブパターンに絞ることを推奨

プロジェクト固有のものは `<repo>/.claude/settings.json` に書くと他プロジェクトに漏れない。
````

### 9. 実装ヒント

`Bash` で `python3` ヒアドキュメントを使うと一気に集計できる。例:

```python
import json, glob, os, re
from collections import Counter

SESSIONS = sorted(glob.glob(os.path.expanduser("~/.claude/projects/<encoded-cwd>/*.jsonl")), key=os.path.getmtime, reverse=True)[1:6]

TARGET_MODES = {"auto", "bypassPermissions"}
SUBCMD_DEPTH = {
    "git": 2, "gh": 3, "npm": 2, "pnpm": 2, "yarn": 2, "npx": 2,
    "aws": 3, "gcloud": 3, "az": 3, "kubectl": 2, "docker": 2,
    "brew": 2, "mas": 2, "nix": 2, "cargo": 2, "go": 2, "dotnet": 2,
    "terraform": 2, "tofu": 2, "make": 1, "uv": 2, "pip": 2, "poetry": 2,
}

INTERPRETERS = {"python3", "python", "node", "bash", "sh", "zsh", "fish",
                "ruby", "perl", "osascript", "deno", "bun"}

def extract_prefix(cmd: str) -> tuple[str, bool]:
    """returns (prefix, is_interpreter)"""
    # cd / export / env prefix を剥がす
    cmd = re.sub(r"^\s*(cd|export|env)\s+\S+\s*&&\s*", "", cmd).strip()
    # ; && || | で連結された最初の節
    head = re.split(r"\s*[;&|]+\s*", cmd, maxsplit=1)[0].strip()
    raw_tokens = head.split()
    if not raw_tokens:
        return "", False
    base = raw_tokens[0]
    is_interpreter = base in INTERPRETERS
    # 中間フラグはスキップ、非フラグだけで base prefix を取る
    nonflag = [t for t in raw_tokens if not t.startswith("-")]
    depth = SUBCMD_DEPTH.get(base, 1)
    prefix_tokens = nonflag[:depth]
    # 末尾フラグ保持: depth 個目の非フラグの直後に "ちょうど 1 つだけ" のフラグ
    # で終わっている場合のみ末尾フラグを含める
    if len(nonflag) >= depth:
        idx_in_raw = 0
        nf_seen = 0
        # 元 token 列で depth 個目の非フラグの位置を特定
        for i, t in enumerate(raw_tokens):
            if not t.startswith("-"):
                nf_seen += 1
                if nf_seen == depth:
                    idx_in_raw = i
                    break
        tail = raw_tokens[idx_in_raw + 1:]
        if len(tail) == 1 and tail[0].startswith("--"):
            prefix_tokens = prefix_tokens + tail
    return " ".join(prefix_tokens), is_interpreter

# permission-mode を追跡しつつ tool_use Bash を集約
# 例: cur_mode = "default"
#     for line in open(path):
#         rec = json.loads(line)
#         if rec.get("type") == "permission-mode":
#             cur_mode = rec.get("permissionMode", "default")
#         elif rec.get("type") == "assistant":
#             ...
```

完全実装は不要 — Claude が transcript を読み取り、推薦結果を生成できれば良い。

## 注意事項

- **Bash 以外のツール（Read, Write, Edit など）は対象外**。本スキルはコマンド allowlist の整備に特化する
- **連結コマンドの解析はベストエフォート**。複雑な heredoc / シェル展開はスキップしてよい
- **インタプリタ系（`python3`, `node`, `bash` 等）の prefix 推薦は意味を成さない**ので、推薦候補から除外するか「allowlist 不適合」として警告セクションに分離する
- **分類は heuristic**。レポート上に「heuristic である旨」「ユーザー判断必須」を明記する
- **引数で挙動が変わるコマンド**（例: `npm run <script>` の中身次第、`gh api` の HTTP メソッド次第）は完全一致 (`Bash(<cmd>)` で `:*` なし) のほうが安全な場合がある旨をレポートで触れる
- **`Bash(<cmd>:*)` 形式は引数すべてを許可する glob**。force push (`git push --force`) や任意ブランチへの checkout (`git checkout <any>`) のような破壊的バリアントも通過することを反映方法セクションで明示する
- **transcript には機密情報を含む可能性がある**。コマンド代表例にトークン的な値が混入していないか軽くチェックし、疑わしければマスクする
- **既存 allowlist との重複判定は前方一致まで**。`Bash(git:*)` がある状態で `git log` を提案しないこと
- **データが少ない場合の挙動**: auto モード実行が少ないセッション群では推薦候補が 0〜数件に留まる。これは異常ではなく allowlist が成熟しているサインの可能性が高い。報告時に「カバー済み prefix の出現件数」を併記して状況をユーザーが判断できるようにする
