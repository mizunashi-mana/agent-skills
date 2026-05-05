# detect-rework-and-violations スキルの実使用評価と改善

## 目的・ゴール

`plugins/agent-coach/skills/detect-rework-and-violations/SKILL.md` を実際の transcript に対して使用し、

1. SKILL.md の手順通りにレポートを生成できるか（手順の曖昧さ・不足の検出）
2. 生成されたレポートの**指摘が正しいか**（手戻り・違反の判定が誤検出になっていないか、ルール抽出が正確か）
3. 分析過程を知らない人が読んでも**わかりやすいか**（背景・根拠・改善案がレポート単体で理解できるか）
4. **クロスセッションで毎回されている追加指示**（cross-session repeated additional instructions）の検知を組み込む。「追加指示の最小化」がこのスキルの目的なので、繰り返される追加指示を検出して MEMORY / CLAUDE.md / skill description 等への昇格を提案できるようにする

を評価し、明らかになった問題点を SKILL.md に反映する。

## 実装方針

1. **試用**: 現在の `agent-skills` リポジトリの transcript（最新 5〜10 セッション）に対して SKILL.md の手順をそのまま追体験する。
2. **評価軸**:
   - 手順の網羅性（手戻り・違反検出のステップが詰まる箇所はないか）
   - ルール抽出の精度（CLAUDE.md / SKILL.md / memory / system reminder からの抽出に漏れ・誤検出はないか）
   - 検出された手戻り/違反の判定妥当性（誤検出が混入していないか、人手で読んで納得できるか）
   - レポートの可読性（分析過程を知らない人が読んで「なぜそう判定したか / 何をすればいいか」が分かるか）
   - **クロスセッション追加指示**の検知が今の SKILL でカバーされているか（カバーされていない場合の追加方針）
3. **改善対象**: SKILL.md のみ（必要に応じて）。実装スクリプトを残す方針ではない（スキルはあくまで「手順書」）。
4. **作業成果物**:
   - `.ai-agent/tmp/20260506-rework-violations/report.md` — 試用で生成された実レポート
   - 評価メモ（このタスクの README 作業ログ）
   - SKILL.md 修正差分

## 完了条件

- [x] SKILL.md の手順通りにレポートを生成できた
- [x] レポート内の指摘について 1 件ずつ正誤確認・誤検出の有無を評価
- [x] 「分析過程を知らない人が読んでわかるか」観点でレポート構造を評価
- [x] クロスセッション追加指示の検知ロジックを SKILL.md に追加
- [x] 評価で見つかった問題点を作業ログにリストアップ
- [x] 修正可能な問題点について SKILL.md を更新
- [x] `python3 scripts/validate-skills.py` が通る
- [x] PR を作成（`/autodev-create-pr`） → https://github.com/mizunashi-mana/agent-skills/pull/16

## 作業ログ

### 2026-05-06: タスク開始

- 関連ドキュメント確認: `plan.md`（Phase 2 = 品質改善・標準化フェーズ）、`structure.md`（agent-coach プラグインに分類）、過去の同種評価タスク `20260506-evaluate-recommend-bash-allowlist` を参照。
- transcript 候補: `~/.claude/projects/-Users-mizunashi-Workspace-MyWork-agent-skills/` に 21 セッション存在。

### 2026-05-06: 試用と評価

試用レポート: `.ai-agent/tmp/20260506-rework-violations/report.md`

データ: 最新 10 セッション（実行中 1 件除外）。違反候補 14 件 / 手戻り 0 件 / クロスセッション反復追加指示 2 種を検出。

#### 検出された SKILL.md の問題点

**[A] 違反検出の誤検出: slash command 由来の許可済み行動を違反扱い (Critical / 14 件中 10 件)**

- 14 件中 10 件が `git commit` の誤検出。すべて `/autodev-create-pr` 経由の指示済みコミット
- SKILL.md には「ユーザー明示指示時のみ」のルール文があるだけで、slash command 起動が「明示指示」に該当するかを判定するステップが書かれていない
- 結果: PR 作成スキル経由のコミットを毎回違反として報告してしまう

**[B] 手戻りシグナルの覆い不足: post-completion supplement パターン (Critical)**

- NEG_WORDS ベースでは 0 件検出。しかし実際には「PR タイトル日本語に」「task README も含めて」のような **完了宣言寸前の追加指示** が複数セッションで発生
- 否定・修正語を含まない建設的口調の追加指示は現行ルールから完全に漏れる
- 4.1 に新カテゴリ「完了宣言/PR 作成/コミット直前直後の追加指示」を加える必要がある

**[C] クロスセッション追加指示検知の欠落 (本タスクの主目的)**

- 今のスキルには「複数セッションで繰り返される追加指示」を集約する機能が無い
- 追加指示の最小化＝このスキルの目的、なのに「単発の手戻り / 違反」しか拾えない構造
- 「PR タイトルを日本語に」「task README を PR に含めて」が 2 セッションずつで反復されている実例を検出できなかった

**[D] guarded read (`cat ... 2>/dev/null`) の誤検出 (3 件中 2 件)**

- `cat .file 2>/dev/null` は「ファイルが存在しないかもしれない」状況での妥当な代替手段（Read ツールは存在しないファイルでエラーになる）
- 違反検出ルールの除外条件として 4.4 に明記すべき

**[E] レポート可読性: 分析過程を知らない人向けの説明が薄い**

- 違反/手戻りの一覧は出るが、**「なぜそれを違反/手戻りと判定したか」「反証材料はあるか」** が読み手に伝わらない
- TL;DR の主因内訳「rot 起因」「ルール埋没」等は専門用語で初見では意味不明
- 各事例に「判定根拠」「反証可能性」を 1〜2 行添える必要

**[F] ルール抽出元の優先順位が曖昧**

- 3.1 で `<repo>/CLAUDE.md`, `~/.claude/CLAUDE.md`, memory, SKILL.md 本文をフラットに列挙
- どれを最優先で読むかの順序が無く、`~/.claude/CLAUDE.md` の system prompt 由来ルール（コミット / `--no-verify` 等）の抽出漏れリスクがある

**[G] 軽微 (今回スコープ外)**

- G1. 主因分類「ルール埋没」の定量化（「CLAUDE.md 中盤以降」の「中盤」とは何行目か）
- G2. tmp スクリプトの破棄/保管ポリシー（手順 7 の `.ai-agent/tmp/` 配下に分析用スクリプトも置くか）

#### 改善対象 (SKILL.md 修正で対応)

優先度 1:

- A: 違反検出の前段に「直前数ターンの slash command 起動と引数・テンプレートを確認」を追加（4.2 / 4.4）
- B: 4.1 の手戻りシグナルに「post-completion supplement」を追加
- C: 新ステップ 5.x「クロスセッション反復追加指示の集約」を追加。改善カテゴリ B / E に memory ファイル化雛形と slash command テンプレ修正雛形を追加
- D: 4.4 (誤検出を避ける条件) に guarded read の例外を追加
- E: レポート雛形に「判定根拠」「反証可能性」の行を追加。TL;DR の主因内訳に簡潔な日本語説明を併記

優先度 2:

- F: 3.1 にルール抽出元の優先順位を明記

優先度 3 (今回見送り):

- G1, G2: 軽微なので実害が小さい

### 2026-05-06: 適用した修正サマリ

`plugins/agent-coach/skills/detect-rework-and-violations/SKILL.md` への変更:

1. **概要 / description フロントマター** — 検出対象を 3 種（手戻り / 違反 / **クロスセッション反復追加指示**）に拡張。改善カテゴリを 5 → 6（**F. 反復指示の昇格**）に拡張。スキルの目的を「**追加指示の最小化**」と明記
2. **手順 3.1（ルール抽出元）** — 抽出元の優先順位を表化。session reminder（system prompt 由来）を最優先に。"Bash tool 説明由来の cd 禁止のような重要ルールを取り逃す" 警告を追加
3. **手順 4.1（手戻りシグナル）** — 否定語ベース (a) だけでは穏やかな日本語ユーザーの追加指示を取り逃す警告。**(e) post-completion supplement** カテゴリを新設（完了寸前の otherwise 追加指示）
4. **手順 4.2.1（slash command コンテキストガード）** — 違反検出の前段に「直前数ターンの slash command 起動を確認、template 内で許可されているなら違反扱いしない」必須ステップを新設。代表的な許可表（`/autodev-create-pr` で commit/push、etc.）と、これを省くと 14 件中 10 件誤報告するという実測根拠を併記
5. **手順 4.4（誤検出条件）** — guarded read (`cat ... 2>/dev/null`)、read-only 情報収集 Bash、`.ai-agent/tasks/` 配下の `Write` 等を違反扱いしない例外を追加
6. **手順 4.5（クロスセッション反復追加指示の集約）** — **本タスクの主目的**。命令キー語彙、n-gram + キーフレーズの 2 段クラスタリング、≥2 セッション要件、トピック要約までの集約手順を新設
7. **手順 5（主因分類）** — 6 番目「**反復指示**」を追加。クロスセッション傾向に「F カテゴリを最優先で提案」を追記
8. **手順 6F（反復指示の昇格）** — 4 つの昇格先（F-1 memory / F-2 プロジェクト CLAUDE.md / F-3 skill template / F-4 グローバル CLAUDE.md）の選択基準と注意点を新設。詳細雛形は `reference/promotion-templates.md` に切り出し
9. **手順 7（レポート生成）** — 「分析過程を知らない人が読んで判断できる」ための (a) 判定根拠 / (b) 反証可能性 / (c) 専門用語の 1 行注釈 / (d) 推奨アクションは具体的対象パスまで を必須化。レポート雛形に「クロスセッション反復追加指示」セクションを最重要として最初に配置。各 finding に「判定根拠」「反証可能性」行を追加
10. **TOP3 優先度** — Tier 1 に「クロスセッション反復追加指示が 2 セッション以上」を最優先で追加
11. **手順 8（実装ヒント）** — Python 骨格コードの完全版を `reference/implementation.md` に切り出し、本体は短いポインタにまとめた（slash command フレーム抽出 + クロスセッションクラスタリングの最小実装を含む）
12. **本体サイズの圧縮** — best practices の「SKILL.md は 500 行以下推奨」に従い、746 → 475 行に削減。詳細サンプル・実装ヒントを `reference/` 配下に切り出し

新規ファイル:

- `plugins/agent-coach/skills/detect-rework-and-violations/reference/promotion-templates.md` — F カテゴリ（反復指示の昇格）の memory ファイル / CLAUDE.md / slash command template 修正の雛形・実例集
- `plugins/agent-coach/skills/detect-rework-and-violations/reference/implementation.md` — Python ヒアドキュメント実装の骨格（rework 検出 / 違反検出 + slash command ガード / クロスセッションクラスタリング）と「手で目視 + Grep」の代替手段

検証結果: `python3 scripts/validate-skills.py` → 23 ファイル 0 error。

### 2026-05-06: 第 2 ラウンド評価（fresh エージェントによる独立試用）

- 修正後の SKILL.md を、本会話のコンテキストを持たない team member agent (general-purpose) に spawn し、同一の 10 セッションに対して独立試用させた
- レポート: `.ai-agent/tmp/20260506-rework-violations/report-fresh.md`（288 行）

#### 改善が確認できた点

| 観点 | 旧版 | fresh 版 |
| --- | --- | --- |
| 手戻り検出 | 0 件（NEG_WORDS のみ） | **2 件**（post-completion supplement パターンで検出） |
| 違反候補誤検出率 | 14 件中 13 件誤検出 (93%) | 12 件中 5 件 を slash command ガードで除外 (42%)、残り 7 件は真の違反候補 |
| クロスセッション反復追加指示 | 検出機能なし | **2 種**を誤検出ゼロで検出（task README / PR 言語） |
| セッション識別性 | UUID のみで読めない | topic 列で `/autodev-start-new-task「<args>」` 等が一目で識別可能 |
| 各 finding の判定根拠・反証 | 無し | 全 finding に併記（読み手単独で判断可能） |
| 新カテゴリの発見 | なし | **トリガミス型違反**（`/autodev-start-new-task` template が `/autodev-create-pr` 起動を指示しているのに 6 セッション中 5 で generic 実装で代替）を独自に発見 |

#### fresh エージェントの自己評価で挙がった残改善点

3 つすべて反映:

- **(e1) `Base directory for this skill: .../skills/<name>` を slash command frame として認識する**ロジックが reference 側にない → SKILL.md 4.2.1 step 1 と reference/implementation.md `collect_slash_command_frames` を 2 系統対応に強化
- **(e2) 直前ユーザー発話の明示指示チェックの自動化**（手動補正していた `task README も含めて` のようなケース）→ SKILL.md 4.2.1 に step 4 を追加、reference/implementation.md に `has_user_explicit_instruction` を追加
- **(e3) template が呼べと指示している skill を呼ばずに generic 実装するトリガミス型を 4.2 代表例に追加** → 4.2 表に 1 行追加

#### fresh ラウンドが検出した最重要 finding（PR ボディに反映）

このリポジトリ自体が以下の問題を抱えていることが判明した:

1. `/autodev-create-pr` を毎回呼ぶべきところで Claude が直接 `git commit + push + gh pr create` で代替している（5 セッション横断のトリガミス）
2. `/autodev-create-pr` 完了後にユーザーが「task README も含めて」「PR を日本語に」と毎回追加指示している（追加指示の最小化目的に直結する反復）

→ **これらは本タスクのスコープ外**。本タスクは detect-rework-and-violations スキルの改善であり、autodev-create-pr / autodev-start-new-task テンプレートの修正は別タスクで扱うべき。本 PR の説明にこれを finding として記載し、別タスクへの種にする。
