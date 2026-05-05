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
5. オプションフラグ（`-`, `--` で始まるトークン）は中間に挟まっても無視せずスキップする（例: `git --no-pager log` → `git log`）。ただし `git rebase --continue` のように **動作を決定するフラグ** はそのまま含める（heuristic: 終端のフラグなら含める）

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

最終的に推薦パターンは `Bash(<prefix>:*)` 形式に整形する。

### 6. readonly / write / unknown の分類

prefix の **末尾の動詞トークン** を以下のキーワードリストで分類する。マッチしないものは `unknown` として扱う。誤分類があり得るので、レポート上で「この分類は heuristic」と明示する。

#### readonly キーワード

- 観察系: `log`, `status`, `show`, `view`, `get`, `list`, `ls`, `ll`, `head`, `tail`, `cat`, `less`, `more`, `diff`, `describe`, `inspect`, `info`, `outdated`, `audit`, `search`, `whoami`, `pwd`, `find`, `grep`, `rg`, `fd`
- 検査系: `check`, `test`, `lint`, `validate`, `dry-run`, `--dry-run`, `--help`, `-h`, `--version`, `version`
- git 系: `rev-parse`, `ls-files`, `ls-remote`, `ls-tree`, `merge-base`, `symbolic-ref`, `remote`（get-url 等）, `submodule`（status 等）, `blame`, `shortlog`, `cherry`, `name-rev`
- gh 系: `pr view`, `pr list`, `pr diff`, `pr checks`, `issue view`, `issue list`, `repo view`, `release view`, `release list`, `run view`, `run list`, `run watch`, `run download`, `cache list`, `label list`, `search`
- aws 系: `get-`, `list-`, `describe-`, `head-`（プレフィックス match）

#### write キーワード

- 変更系: `install`, `add`, `update`, `upgrade`, `remove`, `uninstall`, `delete`, `rm`, `mv`, `cp`, `chmod`, `chown`, `mkdir`, `rmdir`, `touch`
- ビルド系: `build`, `compile`, `bundle`, `pack`, `publish`, `release`
- 実行系: `exec`, `run`, `start`, `stop`, `restart`, `kill`, `apply`, `destroy`, `init`, `migrate`, `seed`
- VCS 系: `commit`, `push`, `pull`, `fetch`, `merge`, `rebase`, `checkout`, `branch`, `tag`, `reset`, `stash`, `cherry-pick`, `revert`
- 編集系: `format`, `fix`（lint --fix 等は write 寄り）

#### 判定優先順位

1. prefix 末尾トークンが write キーワードに完全一致 → write
2. prefix 末尾トークンが readonly キーワードに完全一致 → readonly
3. prefix 末尾トークンが `aws` の `get-`/`list-`/`describe-`/`head-` で始まる → readonly
4. それ以外 → unknown

「`gh pr view`」のように prefix 全体で意味を持つ場合は最後のトークン (`view`) を見れば良い。

### 7. 集約と TOP 50 選定

- 同一 prefix のコマンドを集計（出現回数 + 代表コマンド例 1〜2 件）
- 既に `permissions.allow` でマッチするものは除外
  - prefix がいずれかの allowlist エントリの prefix と完全一致 → 除外
  - prefix が allowlist エントリの prefix の **下位（より長い接頭辞）** → 除外（既に親パターンで許可済み）
  - 例: 既に `Bash(git:*)` があれば `git log` は除外。`Bash(git log:*)` があれば `git log --oneline` 由来の prefix `git log` は除外
- 出現回数の多い順に並べ、上位 50 件を選択
- 同数の場合は readonly を優先

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

- 抽出コマンド総数: <N>
- 既存 allowlist でカバー済み: <M>
- 推薦候補（未カバー）: <K>
  - readonly: <X>
  - write: <Y>
  - unknown: <Z>

## 推薦パターン TOP 50

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

## 反映方法

`~/.claude/settings.json` に追加するなら:

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

プロジェクト固有なら `<repo>/.claude/settings.json` に追加する。

## 注意事項

- 分類は heuristic。特に unknown と write はユーザー側で安全性を確認してから追加してください
- 引数で挙動が変わるコマンド（例: `npm run <script>` の中身次第）は完全一致のほうが安全な場合があります
- `Bash(<cmd>:*)` 形式は引数すべてを許可する glob です。スコープを絞りたい場合はリテラル指定（`Bash(npm install)` のように `:*` なし）を検討してください
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

def extract_prefix(cmd: str) -> str:
    # cd ... && の剥がし、; && || の最初の節
    cmd = re.sub(r"^(cd|export|env)\s+\S+\s*&&\s*", "", cmd).strip()
    head = re.split(r"\s*[;&|]\s*", cmd, maxsplit=1)[0].strip()
    tokens = [t for t in head.split() if not (t.startswith("-") and t not in ("--continue", "--abort"))]
    if not tokens:
        return ""
    base = tokens[0]
    depth = SUBCMD_DEPTH.get(base, 1)
    return " ".join(tokens[:depth])

# ... ループ内で permission-mode を追跡しつつ tool_use Bash を集約
```

完全実装は不要 — Claude が transcript を読み取り、推薦結果を生成できれば良い。

## 注意事項

- **Bash 以外のツール（Read, Write, Edit など）は対象外**。本スキルはコマンド allowlist の整備に特化する
- **連結コマンドの解析は ベストエフォート**。複雑な heredoc / シェル展開はスキップしてよい
- **分類は heuristic**。レポート上に「heuristic である旨」「ユーザー判断必須」を明記する
- **transcript には機密情報を含む可能性がある**。コマンド代表例にトークン的な値が混入していないか軽くチェックし、疑わしければマスクする
- **既存 allowlist との重複判定**は前方一致まで。`Bash(git:*)` がある状態で `git log` を提案しないこと
