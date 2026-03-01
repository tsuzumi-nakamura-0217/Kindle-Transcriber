# Kindle Transcriber

Kindle for Mac のページを自動でスクリーンショット撮影し、Apple Vision Framework（OCR）でテキストを認識して Markdown ファイルに書き出すツールです。段落内の行折り返しをスマートに結合し、自然に読めるテキストを生成します。

> **免責事項**: 本ツールは個人的な学習・ノート作成を目的としています。著作権法第30条に定める私的複製の範囲内でのみご使用ください。著作権者の許可なく第三者への配布・販売は行わないでください。

---

## 動作環境

- macOS 13 Ventura 以降（Apple Vision Framework 使用のため）
- Python 3.10 以降
- Kindle for Mac App Store 版（最新版推奨）

---

## セットアップ

```bash
# 1. リポジトリをクローン
git clone https://github.com/yourname/kindle-transcriber.git
cd Kindle-Transcriber

# 2. 仮想環境を作成・有効化
python3 -m venv .venv
source .venv/bin/activate

# 3. 依存パッケージをインストール
pip install -r requirements.txt
```

> **追加設定**: macOS の「システム設定 → プライバシーとセキュリティ → 画面収録」と「アクセシビリティ」で、ターミナルの権限を許可してください。

---

## 使い方

### 1. 設定ファイルを確認する

`config.yaml` を開き、ページ遷移速度・言語・ウィンドウ領域などを必要に応じて変更します。

### 2. Kindle for Mac を開き、文字起こしを開始するページを表示する

### 3. スクリプトを実行する

```bash
# 基本的な使い方（スクリプト実行後 3 秒以内に Kindle をアクティブにしてください）
python src/main.py --pages 100 --title "書籍タイトル"

# オプション一覧
python src/main.py --help

# 設定ファイルを指定
python src/main.py --pages 200 --title "書籍タイトル" --config config.yaml

# 途中から再開（ページ番号を指定）
python src/main.py --pages 200 --title "書籍タイトル" --start-page 50
```

### 4. 出力ファイルを確認する

`output/書籍タイトル.md` に Markdown 形式で保存されます。

---

## 保存済みスクリーンショットの再処理

`save_screenshots: true`（デフォルト）の場合、撮影した画像が `output/screenshots/` に保存されます。OCR ロジックを変更した後などに、Kindle を再操作せずテキストを作り直せます。

```bash
# 全ページを再処理（output/書籍タイトル_reflow.md が生成される）
python src/postprocess.py --title "書籍タイトル" --pages 100

# 特定ページ範囲のみ再処理
python src/postprocess.py --title "書籍タイトル" --pages 100 --start-page 10 --end-page 30

# 縦書き書籍の再処理
python src/postprocess.py --title "書籍タイトル" --pages 100 --vertical

# 問題がなければ元ファイルと置き換え
mv "output/書籍タイトル_reflow.md" "output/書籍タイトル.md"
```

---

## プロジェクト構成

```
Kindle-Transcriber/
├── src/
│   ├── main.py               # エントリポイント（撮影 → OCR → 出力）
│   ├── kindle_controller.py  # Kindle ウィンドウ制御（AppleScript）
│   ├── screenshot.py         # スクリーンショット撮影・前処理
│   ├── ocr.py                # Apple Vision OCR・段落検出
│   └── output.py             # Markdown 出力・中断再開管理
├── output/
│   └── screenshots/          # 撮影したスクリーンショット（再処理用）
├── config.yaml               # 設定ファイル
├── requirements.txt
└── README.md
```

---

## 設定ファイル (`config.yaml`) の説明

| キー | 説明 | デフォルト |
|---|---|---|
| `total_pages` | 書籍のページ総数（`--pages` で上書き可） | `100` |
| `page_turn_delay` | ページめくり後の待機時間（秒）。遅延が出る場合は増やす | `1.5` |
| `language` | OCR 言語（`ja` / `en` / `auto`） | `auto` |
| `vertical_text` | 縦書き書籍の場合 `true` に設定 | `false` |
| `capture_region` | キャプチャ領域（`auto` で Kindle ウィンドウを自動検出） | `auto` |
| `output_dir` | 出力ディレクトリ | `output` |
| `save_screenshots` | スクリーンショットを保存するか（再処理のために `true` 推奨） | `true` |
| `confidence_threshold` | OCR 信頼度の閾値（0.0〜1.0） | `0.3` |
| `verbose` | 詳細ログを表示するか | `false` |
| `dry_run` | `true` にするとスクリーンショットのみ撮影して OCR をスキップ | `false` |

---

## トラブルシューティング

- **「画面収録の権限がありません」**: 「システム設定 → プライバシーとセキュリティ → 画面収録」でターミナルを許可してください
- **ページめくりが機能しない / Kindle が反応しない**: `config.yaml` の `page_turn_delay` を `2.0` 以上に増やしてください
- **OCR 精度が低い**: Kindle の表示フォントサイズを大きくすると改善します
- **段落の区切りがおかしい**: `config.yaml` の `page_turn_delay` を増やして撮影後、`postprocess.py` で再処理してください
- **縦書き書籍でテキスト順序がおかしい**: `config.yaml` の `vertical_text: true` を設定して `postprocess.py` で再処理してください
- **途中で止まった**: `--start-page` に止まったページ番号を指定して再実行すると続きから処理できます
