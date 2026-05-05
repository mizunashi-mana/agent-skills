# recommend-bash-allowlist スキルの実使用評価と改善

## 目的・ゴール

`plugins/agent-coach/skills/recommend-bash-allowlist/SKILL.md` を実際の transcript に対して使用し、

1. SKILL.md に書かれた手順通りに実行できるか（手順の曖昧さ・不足の検出）
2. 出力されるレポートが「ユーザーが allowlist に追記する判断」をするのに十分か（実用性）
3. heuristic 分類（readonly / write / unknown）が妥当か（精度）

を評価し、明らかになった問題点を SKILL.md に反映する。

## 実装方針

1. **試用**: 現在の `agent-skills` リポジトリの transcript（最新 5〜10 セッション）に対して SKILL.md の手順をそのまま追体験する。
2. **評価軸**:
   - 手順の網羅性（ステップが詰まる箇所はないか）
   - prefix 抽出ルールの実例での妥当性（`cd && ` 剥がし、heredoc、`python3 -c "..."` 等のエッジケース）
   - readonly / write / unknown 分類の精度（誤分類した代表例があるか）
   - 既存 allowlist との重複判定が正しく機能するか
   - レポートの読みやすさ（TOP5 / 反映方法ブロック / 件数集計の妥当性）
3. **改善対象**: SKILL.md のみ（必要に応じて）。実装スクリプトを残す方針ではない（スキルはあくまで「手順書」）。
4. **作業成果物**:
   - `.ai-agent/tmp/20260506-bash-allowlist/report.md` — 試用で生成された実レポート
   - 評価メモ（このタスクの README 作業ログ）
   - SKILL.md 修正差分

## 完了条件

- [x] SKILL.md の手順通りにレポートを生成できた
- [x] 評価で見つかった問題点を作業ログにリストアップ
- [x] 修正可能な問題点について SKILL.md を更新
- [x] `python3 scripts/validate-skills.py` が通る
- [ ] PR を作成（`/autodev-create-pr`）

## 作業ログ

### 2026-05-06: 試用と評価

試用レポート: `.ai-agent/tmp/20260506-bash-allowlist/report.md`

データ: 9 セッション、Bash 総数 214 (default 150 + auto 64)。auto モード抽出 64 → distinct prefix 19 → 既存 allowlist でカバー済み 13 → 推薦候補 6 (readonly 0 / write 3 / unknown 3)。既存 allowlist 221 件が既に充実しているため readonly 推薦が 0 になるのは想定内。

#### 検出された SKILL.md の問題点

**[A] 分類 heuristic の取りこぼし**

- A1. `WRITE_KEYWORDS` に `create` が無く、`gh pr create` が `unknown` 落ち（明らかな write）
- A2. `READONLY_KEYWORDS` に `readlink` が無く `unknown` 落ち
- A3. `git branch --show-current` が `write` に誤分類。フラグ全削除後に末尾が `branch` (write) になるため。SKILL の「終端のフラグなら含める」ルールが `--continue/--abort` のみ拾う実装にとどまり、`--show-current`、`--list`、`--show-toplevel` 等の readonly 確定フラグを拾えていない
- A4. `python3` のような汎用ランタイムが `unknown` のまま手薄。`python3:*` 追加は**任意コード実行を許可するに等しい** → 「allowlist 不適合」として明示的に除外/警告するカテゴリが必要

**[B] permission-mode のスキーマ記述が薄い**

- B1. SKILL は `type == "permission-mode"` レコードに言及するが、フィールド名 (`permissionMode`)、timestamp が無いこと、同モード値が連続出現することを明記していない。実装ヒントに最小サンプル JSON が欲しい
- B2. `attachment.type == "auto_mode"` という補助シグナルもあるが言及なし。permission-mode と併用すべきか単独で十分かが不明

**[C] エッジケース記述不足**

- C1. ヒアドキュメント (`python3 << 'EOF' ... EOF`) の扱い。SKILL は prefix 抽出ルールしか書いていないが、heredoc の場合は本体（任意コード）を allowlist 化することの危険性に触れるべき
- C2. リダイレクト (`2>/dev/null`, `>file`, `&>file`) の扱い未明記。先頭トークン抽出には影響しないが、代表コマンド例の整形ルール (改行で truncate するか) が無い
- C3. `cd /path && cmd && cmd2` のように `cd` が深く入った連結はテーブル例と乖離している

**[D] depth 表の妥当性**

- D1. `git` 深さ 2 は `git branch`、`git remote`、`git submodule` のような「サブコマンド名 = 動詞」が write/readonly 両義のものに対して粒度が荒い。例えば `git remote get-url` (readonly) と `git remote add` (write) は同じ `git remote` prefix にまとまる
- D2. 一方で粒度を上げると prefix 数が増えて TOP 50 が薄まるトレードオフ。SKILL に「サブコマンド体系ツールでも、末尾の動詞が write/readonly 判定に効くなら 1 段深く取る」例外則を入れる余地

**[E] レポート構造の問題**

- E1. SKILL の `## 注意事項` が 2 か所に重複定義されている (現 SKILL の line 218 と line 259) → 1 箇所に統合すべき
- E2. レポート構造の "TOP 50" は固定数値だが、実データでは候補が少ないこともある (今回は 6)。「TOP N (≤50)」と表記するなど柔軟化を
- E3. レポートに「**既存 allowlist でカバー済み prefix のサマリ**」を出すと、ユーザーが「自分の allowlist が機能しているか」を確認できて有益。SKILL のレポート雛形に項を追加
- E4. 反映方法の例で `Bash(<prefix>:*)` を機械的に並べると危険なものまで全部入る。「危険そうなものを別行で指摘」「`python3:*` は推奨しない」のような注釈テンプレが欲しい

**[F] 軽微**

- F1. SKILL の prefix 抽出疑似コードが「`flag` = `t.startswith("-") and t not in ("--continue", "--abort")` なら除外」という限定列挙。実装としては fragile (上記 A3 の原因)。「末尾位置のフラグは保持」という語彙的なルールに置き換えるべき
- F2. README/レポート一致性: SKILL の `### サマリ` と `### 推薦パターン TOP 50` の見出し階層がレポート内では `## サマリ` / `## 推薦パターン TOP 50` (一段下) になっており、SKILL 上の説明と齟齬がある。レポート例の Markdown ブロックは `##` で始めるべき

#### 改善対象 (SKILL.md 修正で対応)

優先度 1:
- A1, A2: WRITE/READONLY キーワードリストに `create` / `readlink` ほかを追加
- A3, F1: 末尾フラグ保持ルールを「末尾のフラグはトークンとして残す」に一般化（疑似コードも合わせて修正）
- A4: 「allowlist 不適合カテゴリ」を新設（python/sh/bash 等の任意コード実行系）
- E1: 重複 `## 注意事項` を統合

優先度 2:
- B1: `permission-mode` の最小サンプル JSON を実装ヒントに追加
- C1: heredoc/任意コード実行の警告を「注意事項」に明記
- D1: 「末尾動詞判定で粒度を上げる例外則」を depth 表の注記として追加
- E3: 「既存 allowlist でカバー済み」セクションをレポート雛形に追加
- E2: TOP 50 を TOP N (≤50) に書き換え
- E4: 反映方法に「危険そうな推薦への注釈」テンプレを追加

優先度 3 (今回見送り検討):
- B2: auto_mode attachment との併用は実害が無さそうなのでスキップ
- C2, C3: 代表コマンド例の整形ルールは現状で実害が小さい
- F2: レポート見出し階層は実害が小さい

### 2026-05-06: 適用した修正サマリ

`plugins/agent-coach/skills/recommend-bash-allowlist/SKILL.md` への変更:

1. **手順 2 (JSONL 構造)** — `permission-mode` レコードの最小サンプル JSON とフィールド構造（timestamp なし、同モード反復出現）を明記
2. **手順 5 (prefix 抽出)** — フラグ扱いを「中間スキップ / 末尾 1 つだけのフラグは保持」へ一般化。`git branch --show-current` 等が readonly 判定可能に
3. **手順 5 (深さ例外)** — `git remote {add|get-url}` 等、末尾動詞で readonly/write が分かれるサブコマンドへの「+1 段深く取る」例外則を追加
4. **手順 6 (分類キーワード)** — readonly に `readlink`/`realpath`/`stat`/`worktree list` 等、write に `create`/`new`/`clone`/`generate`/`deploy`/`patch` 等を追加。判定優先順位に末尾フラグを最上位に移動
5. **手順 6 (任意コード実行系)** — `python3`, `node`, `bash`, `sh` 等のインタプリタを「allowlist 不適合」カテゴリとして新設
6. **手順 7 (集約)** — 「TOP 50」を「TOP N (≤50)」に書き換え。インタプリタ系は警告セクションへ分離。代表コマンド例の改行トランケート/120 文字省略を明記
7. **レポート雛形** — 「⚠ 任意コード実行系」セクション、「既存 allowlist でカバー済み」セクションを追加。サマリに「全モード Bash 総数」を追加
8. **反映方法** — 危険な glob (`git push:*`, `git checkout:*`, `git branch:*`) への注釈テンプレを追加
9. **実装ヒント** — `extract_prefix` の擬似コードを末尾フラグ保持ロジック対応へ書き換え。`INTERPRETERS` セット導入。`permission-mode` 走査の擬似コードを追加
10. **注意事項** — 重複していた `## 注意事項` をレポート雛形側で削除。SKILL 末尾の `## 注意事項` にインタプリタ警告/データ不足時の解釈などを追記

