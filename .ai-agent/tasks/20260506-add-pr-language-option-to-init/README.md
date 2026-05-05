# autodev-init で create-pr インストール時に PR 言語を選べるようにする

## 目的・ゴール

`autodev-init` スキルが `autodev-create-pr` をインストールするとき、ユーザーに PR タイトル / 本文の記述言語を確認し、その選択をテンプレートに反映できるようにする。

現状の `templates/skills/autodev-create-pr/SKILL.md` は

- 注意事項に「PR タイトルは日本語で簡潔に」と日本語固定
- 本文例の見出し（`## 目的` / `## 変更概要`）が日本語固定

となっており、英語圏のリポジトリに `autodev-init` でセットアップすると、生成される PR が日本語になって不自然になる。

## 実装方針

### 1. `plugins/autodev/skills/autodev-init/SKILL.md` を更新

- Step 5 のレビュー形式確認の隣に、**PR の言語確認** ステップを追加
  - `AskUserQuestion` で「PR タイトル / 本文をどの言語で書くか」を聞く
  - 候補: `Japanese (日本語)` / `English` / `Other (free text)`
  - デフォルトは Japanese（既存ユーザーの挙動を変えないため）
- Step 5 「カスタマイズすべき項目」一覧に `autodev-create-pr` の言語反映を明記
- `autodev-create-pr` テンプレートをコピー後、選択言語に合わせて
  - 注意事項の「PR タイトルは日本語で簡潔に」 → 選択言語名に置換
  - 本文例の `## 目的` / `## 変更概要` → 選択言語の対応する見出しに置換

### 2. `templates/skills/autodev-create-pr/SKILL.md` のマーカー化

カスタマイズ箇所が分かるように、注意事項と本文例に `<!-- autodev-init: pr-language -->` のような目印コメントを置くか、テンプレートを「日本語例」と「英語例」の対比つきで提示するなど、`autodev-init` 側からカスタマイズしやすい形にする。最終的に置換すれば良いだけなので、過剰な抽象化は避ける。

### 3. 動作確認

- `python3 scripts/validate-skills.py` が通ること
- `templates/skills/autodev-create-pr/SKILL.md` のフロントマターが破損していないこと
- 英語選択時のテンプレートが自然な英語になることを README で例示

## 完了条件

- [x] `plugins/autodev/skills/autodev-init/SKILL.md` に言語選択ステップとカスタマイズ手順を追加
- [x] `plugins/autodev/skills/autodev-init/templates/skills/autodev-create-pr/SKILL.md` の言語固定箇所をカスタマイズ可能な形に整理
- [x] `python3 scripts/validate-skills.py` が通る
- [x] PR を作成（`/autodev-create-pr`） → https://github.com/mizunashi-mana/agent-skills/pull/17

## 作業ログ

### 2026-05-06: タスク開始

- 現状把握: `autodev-create-pr` テンプレートで日本語固定箇所を特定
  - `templates/skills/autodev-create-pr/SKILL.md:50` 「PR タイトルは日本語で簡潔に」
  - 同 `:27-32` 本文例 `## 目的` / `## 変更概要`
- トリアージ: そのまま `autodev-start-new-task` で進行（数時間で完了見込み）

### 2026-05-06: 実装

- `autodev-init/SKILL.md` Step 5 に「PR タイトル・本文の言語の確認」サブステップを追加（候補: 日本語 / 英語 / その他）
- 同インストール手順 2 のカスタマイズ項目に `autodev-create-pr` の言語反映手順を追記。マーカーコメント `<!-- pr-language: ja -->` 〜 `<!-- /pr-language -->` で囲んだ箇所を選択言語へ置換し、置換後はマーカーごと削除する流れ
- `templates/skills/autodev-create-pr/SKILL.md` の本文例ブロックと注意事項の「PR タイトルは日本語で簡潔に」をマーカーコメントで囲んだ
- `python3 scripts/validate-skills.py` 実行: 23 ファイル / 0 エラー

### 2026-05-06: ユーザーフィードバック反映 (マーカー削除→多言語対応)

- レビュー指摘: 「マーカーを削除するのではなく、多言語対応できますか？」
  - 例として「PR タイトルは English で簡潔に」のような形を提示された
- 方針変更: マーカーは保持し、開始マーカーの言語コード（`pr-language: ja` → `pr-language: en` 等の ISO 639-1 コード）と内側の本文を選択言語に応じて置換する形へ
- `autodev-init/SKILL.md` インストール手順 2 を更新:
  - 「マーカー削除」指示を撤回し、「マーカー保持・言語コード書き換え」に変更
  - 注意事項置換の早見表（日本語 / 英語 / 中国語）を追加
  - 本文例（英語選択時）の具体例を追加
  - SKILL 本体の地の文はプロジェクト主要言語のままにする旨を明記（本文例マーカー内だけ多言語化される）
- `templates/skills/autodev-create-pr/SKILL.md` 自体は変更不要（マーカーはすでに入っており、デフォルトの `ja` がそのまま日本語ユーザーで成立する）
- `python3 scripts/validate-skills.py` 実行: 23 ファイル / 0 エラー
