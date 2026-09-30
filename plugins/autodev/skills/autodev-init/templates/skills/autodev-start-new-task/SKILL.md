---
description: Start a new implementation task with branch, README, and structured workflow. Use when beginning a feature, bug fix, or improvement that takes a day to a few days.
allowed-tools: Read, Write, Edit, MultiEdit, Update, WebSearch, WebFetch, "Bash(git checkout -b *)", "Bash(git status *)", "Bash(git add *)", "Bash(git commit *)", "Bash(git push *)", "Bash(gh pr checks *)", "Bash(gh run view *)", Skill(autodev-create-pr), Skill(autodev-review-pr), Skill(autodev-discussion), Skill(autodev-start-new-survey), Skill(autodev-start-new-project)
---

# 新規タスク開始

新しいタスク「$ARGUMENTS」を開始します。

## 手順

### 1. トリアージ

`$ARGUMENTS` の内容を分析し、このスキル（start-new-task）で扱うべきタスクかを判断する。

**判断基準:**

| 条件                                         | ルーティング先               | 例                                                        |
| -------------------------------------------- | ---------------------------- | --------------------------------------------------------- |
| 要件が曖昧・方向性の整理が必要               | `/autodev-discussion`        | 「開発フローを改善したい」「〇〇をどうにかしたい」        |
| 技術的な不確実性が高い・調査が先に必要       | `/autodev-start-new-survey`  | 「CI を高速化する方法を検討」「○○ライブラリの比較」       |
| 複数タスクへの分解が必要（数週間以上の規模） | `/autodev-start-new-project` | 「認証システムを全面リニューアル」「新機能Xの設計〜実装」 |
| 数時間〜半日で完了する具体的な実装タスク     | **そのまま続行**             | 「バリデーション追加」「設定ファイルの修正」              |

**そのまま続行する場合の目安:**

- ゴールが明確で、完了条件を具体的に書ける
- 技術的なアプローチが概ね見えている（大きな調査が不要）
- 1ブランチ・1PR で完結する規模
- 数時間〜半日で完了する見込み

**ルーティングする場合:**

- ユーザーに判断理由と推奨スキルを提示し、確認を取る
- タスクディレクトリ（手順 2〜3）が既に作成されている場合は、README の作業ログにトリアージ結果を記録する（例: 「トリアージの結果、`/autodev-discussion` にルーティング。理由: 要件が曖昧で方向性の整理が必要」）
- ユーザーが承認したら、推奨スキルに切り替える

### 2. タスク名の決定

- `$ARGUMENTS` の内容から適切なタスク名（英語、kebab-case）を考える
- 簡潔で内容が分かるタスク名にする

### 3. タスクディレクトリ作成

`.ai-agent/tasks/YYYYMMDD-{タスク名}/README.md` を作成（YYYYMMDD は今日の日付）

### 4. README.md に以下を記載

- 目的・ゴール
- 実装方針
- 完了条件（「PR を作成」「レビュー・指摘取り込み」「CI が全て成功」の項目を必ず含める）
- 作業ログ（空欄で開始）

### 5. 関連ドキュメント確認

- `.ai-agent/steering/plan.md` で該当フェーズを確認
- `.ai-agent/steering/tech.md` で技術スタックを確認
- `.ai-agent/structure.md` でディレクトリ構成を確認

### 6. ユーザーに方針を提示して確認を取る

### 7. ブランチ作成（ユーザー確認後）

- `git checkout -b {タスク名}` でブランチを作成
- そのままブランチ作成することで、タスク内容を引き継ぐ。main の pull は後で良い

### 8. TodoWrite でタスクを細分化

### 9. 実装開始

## 実装中の注意

- 各ステップで動作確認を行う
- 必要に応じてユーザーにフィードバックをもらう

## 完了時

タスクのゴールは **「PR を作成し、レビュー指摘を取り込み、CI が全て成功したうえで、ブランチに未コミット・未 push の変更が残っていない状態」** とする。PR 作成で止めず、次の順序でレビュー取り込みと CI 確認まで進める。

1. **README に完了条件・作業ログを記載してコミット**:
   - 完了条件のうち、PR 作成・レビュー・CI の項目はこの時点ではまだチェックしない（PR URL・レビュー結果・CI 結果が未確定のため）
   - それ以外の完了条件をチェックし、作業ログに結果を記載
   - 実装変更とまとめて `git add` + `git commit` する（`/autodev-create-pr` は未コミット変更があると先にコミットを促す挙動なので、ここで commit を済ませておく）
2. **PR を作成**:
   - `/autodev-create-pr` を使用する（push + PR 作成を行い、PR URL を返す）
3. **PR URL を README に反映してコミット + push**:
   - 完了条件の「PR を作成」項目をチェックし、PR URL を併記する
     - 例: `- [x] PR を作成（\`/autodev-create-pr\`） → https://github.com/<owner>/<repo>/pull/<番号>`
   - `git add` + `git commit` + `git push` で PR ブランチに反映する（レビュー対象の差分とローカルを一致させるため、レビュー前に必ず push する）
4. **レビューと指摘の取り込み**:
   - `/autodev-review-pr {PR番号}` を使用する
   - reviewer サブエージェントによるレビュー → 指摘の分類 → 修正 → コミット + push まで、このスキル内で行われる
   - 判断が必要な「要確認」の指摘のみユーザーに質問される
5. **レビュー結果を README に反映してコミット + push**:
   - 完了条件の「レビュー・指摘取り込み」項目をチェックする
   - 作業ログにレビュー結果（推奨アクション、修正件数・スキップ件数とスキップ理由の要約）を記載する
   - `git add` + `git commit` + `git push` で PR ブランチに反映する。**このステップは省略しない**（省略するとブランチ上に未 push の変更が残る）
6. **CI が全て成功したか確認**:
   - 最後の push に対する CI の完了を `gh pr checks <PR番号> --watch` で待ち、全チェックが成功していることを確認する
   - 失敗したチェックがある場合:
     1. `gh pr checks <PR番号>` で失敗したチェックを特定し、`gh run view <run-id> --log-failed` でログを確認する
     2. 原因を修正してコミット + push し、再度 CI の完了を待つ（全て成功するまで繰り返す）
     3. 自力で解決できない失敗（CI 基盤側の障害、権限不足など）はユーザーに報告して判断を仰ぐ
   - CI が全て成功したら、完了条件の「CI が全て成功」項目をチェックし、作業ログに CI 修正の有無を記載してコミット + push する
     - この README のみのコミットで CI が再実行される場合も、完了を待って成功を確認する
   - CI が設定されていないリポジトリ（`gh pr checks` でチェックが 0 件）の場合は、その旨を作業ログに記載してこの手順をスキップする（push 直後はチェックが未登録のことがあるため、0 件のときは少し間を置いて再確認してから判断する）
7. **ブランチがクリーンか確認**:
   - `git status` で未コミット・未 push の変更がないことを確認
8. **ユーザーに完了報告**:
   - PR URL、レビューの推奨アクション、取り込んだ指摘・スキップした指摘の要約、CI の結果を含めて報告する
