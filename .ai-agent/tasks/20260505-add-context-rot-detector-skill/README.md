# コンテキストロット検出スキルの追加

## 目的・ゴール

`plugins/agent-coach/` プラグインに、ユーザーの transcript を分析して**コンテキストロット**のシグナルを検出し、具体的な改善方法（断点・Plan 化・Subagent 委譲・MEMORY.md 移行・Compact Instructions）を提案するスキルを追加する。

既存 `agent-coach` スキルは 6 観点を横断する「総合健康診断」だが、観点 4（コンテキストロット）はサマリ提示にとどまる。本スキルは観点 4 を**深掘り専用**としてフォーカスし、以下を提供する:

- セッション別タイムラインで「いつ rot が始まったか」を特定
- /clear・/compact・Plan モード移行・Subagent 委譲の**具体的な断点候補**
- 繰り返し参照される情報の **MEMORY.md 化候補**
- 長期セッションを支える **CLAUDE.md Compact Instructions** の雛形

## 実装方針

### スキル配置

- ディレクトリ: `plugins/agent-coach/skills/detect-context-rot/`
- 本体: `SKILL.md`
- agent-coach プラグインに同居（`recommend-bash-allowlist` と並ぶ「特化型分析スキル」）
- 既存 agent-coach の観点 4 はそのまま残し、本スキルへのリンクを SKILL.md と handbook に追記して相互参照

### スキル名と description

- 名前: `detect-context-rot`
- description (英語、Use when ... トリガ含む):
  > "Analyze recent Claude Code transcripts to detect context rot signals (turn count growth, repeated reads, fading initial instructions, bloated tool results, cache miss patterns) and suggest concrete remediation: where to /clear, when to switch to Plan mode, which investigations to delegate to subagents, what to migrate into MEMORY.md, and which CLAUDE.md Compact Instructions to add. Use when sessions feel unfocused, the model forgets earlier context, you want to diagnose long sessions, or harvest repeated patterns into structured memory."

### 分析ロジック（SKILL.md に記述）

1. **対象セッション特定**: agent-coach / recommend-bash-allowlist と同じ規約（cwd → `~/.claude/projects/<encoded-cwd>/` 配下、最新 N セッション、実行中セッションは除外）。本スキルは長期/重い rot シグナルを見るので**デフォルトで最新 5〜10 セッション**を推奨

2. **シグナル抽出（セッション別）**:
   - **量的シグナル**: ターン数、累積 input/output/cache_*_tokens、ターン間の mtime gap、tool_result サイズの累積分布
   - **反復シグナル**: 同一ファイルの再 Read、同一引数の Bash 反復、同じツール（Grep/Glob/Read）の似た呼び出し
   - **指示忘却シグナル**: CLAUDE.md / 初期 system reminder / 初期ユーザー指示で示されたルールに後半で違反した箇所
   - **巨大ツール出力シグナル**: > 5000 文字の tool_result、> 50KB の Read、> 100 行の Bash 出力
   - **断点欠落シグナル**: 50 ターン以上 /clear なし、Plan モードに入らず長期実装、Subagent を呼ばずに重い調査

3. **rot 開始ターン推定**:
   - 累積 cache_creation_input_tokens の屈曲点（前半 30 ターンの平均×2 を超えたターン）
   - 同じファイル/コマンドが 2 回以上反復し始めたターン
   - 上記 2 つのうち**早い方**を「rot 始点候補」とする
   - 「ここで /clear すべきだった」候補ターンとして報告

4. **クロスセッション傾向**:
   - 平均ターン数、平均トークン、rot 始点までの平均ターン数
   - 同じファイル/トピックを複数セッションで繰り返し Read している → MEMORY.md 候補
   - 同じユーザー指示が複数セッションで欠落している → CLAUDE.md / memory ファイル化候補

5. **改善提案カテゴリ**（finding を 5 つのアクションに mapping）:
   - **A. 断点（/clear・/compact）**: 「セッション X のターン N 以降は別タスク。/clear 推奨」
   - **B. Plan モード化**: 「長期実装タスクは最初に Plan で方針確定 → 実行ターンを短く」候補ターン提示
   - **C. Subagent 委譲**: 「ターン N の重い調査は Agent(subagent_type=Explore) 候補」
   - **D. MEMORY.md 移行**: 「ファイル X / コマンド Y が n セッションで反復 → memory 化候補」
   - **E. CLAUDE.md Compact Instructions**: 「compaction 時に失われやすい項目（プロジェクト用語・命名規則）」雛形を提示

### 出力形式

レポートは画面に直接ダンプせず、ファイルに書き出す:

1. 出力ディレクトリ: `.ai-agent/tmp/<YYYYMMDD>-context-rot/`（cwd 基準）
2. レポート本文: `<出力ディレクトリ>/report.md`
3. 画面には以下のみ表示:
   - レポートファイルパス
   - セッション別 rot 始点候補（最大 5 件）
   - 推奨アクション TOP3（A〜E から効果の高い順）

#### レポート構造

```markdown
# Context Rot 検出レポート

対象: <セッション一覧と期間>

## TL;DR
- <セッション数> セッション中 <K> セッションで rot 始点候補を検出
- 主因: <反復 Read / 巨大 tool 出力 / 断点欠落 など>
- 推奨アクション TOP3 は末尾

## セッション別タイムライン
### <session-id> (<turns> turns, <tokens> tokens)
- ターン 1〜N: 健全（<指標>）
- ターン N+1: rot 始点候補（<シグナル>）
- ターン N+1〜M: <反復した行動>
- 推奨断点: ターン X / Plan 移行: ターン Y / Subagent: ターン Z

## クロスセッション傾向
- <ファイル/コマンド/トピック> を <n> セッションで反復参照 → memory 化候補

## 改善提案

### A. 断点（/clear・/compact）
| セッション | 推奨ターン | 根拠 |
| --- | --- | --- |

### B. Plan モード化
...

### C. Subagent 委譲
...

### D. MEMORY.md 移行候補
- <ファイル X>: <理由>。雛形 →
  ```markdown
  ---
  name: <name>
  description: <one-line>
  type: reference
  ---
  ```

### E. CLAUDE.md Compact Instructions
suggested addition:
```markdown
## Compact Instructions
- 保持: <項目>
- 削除: <項目>
```

## 統計サマリ
- セッション数 / ターン総数 / トークン総計 / 検出件数

## 誤検出の可能性
- 長い設計議論セッションは rot ではない場合あり（指標を併せて確認）

## 推奨アクション TOP3
1. ...
```

## 完了条件

- [x] `plugins/agent-coach/skills/detect-context-rot/SKILL.md` が存在する
- [x] YAML フロントマターが `scripts/validate-skills.py` を pass する（`Checked 21 file(s): 0 error(s)`）
- [x] `description` に "Use when ..." 形式のトリガ条件が含まれる
- [x] 既存 agent-coach の観点 4 セクションに本スキルへの相互参照を追記（SKILL.md 本体 + reference/handbook.md）
- [x] `.ai-agent/structure.md` に新スキルディレクトリが反映されている
- [x] `.claude/skills/detect-context-rot/skill.md` を本体への symlink として作成
- [ ] PR が作成されている

## 作業ログ

- 2026-05-05: トリアージ実施。要件明確・1 PR 規模のため `/autodev-start-new-task` のまま続行と判断
- 2026-05-05: ユーザー方針確認（agent-coach 観点 4 をフォーカスした独立スキルとして並存 / 同ブランチで継続）
- 2026-05-05: bash-allowlist 作業を別コミット (`84fbf7b`) として整理し、context-rot タスクを開始
- 2026-05-05: `plugins/agent-coach/skills/detect-context-rot/SKILL.md` 作成。rot 始点推定アルゴリズム（トークン屈曲点 / 反復出現点 / 巨大出力連発点の最早採用）と A〜E（断点 / Plan / Subagent / MEMORY.md / Compact Instructions）の改善カテゴリを内包
- 2026-05-05: 既存 agent-coach `SKILL.md` 観点 4 と `reference/handbook.md` 観点 4 に detect-context-rot への案内を追記
- 2026-05-05: `.ai-agent/structure.md` 更新（plugins ツリー + .claude/skills 両方）
- 2026-05-05: `.claude/skills/detect-context-rot/skill.md` を `plugins/agent-coach/skills/detect-context-rot/SKILL.md` への相対 symlink として作成
- 2026-05-05: `scripts/validate-skills.py` 実行 → 0 errors（21 ファイル検査）
