# Kindle Transcriber

Kindle for Mac のページを自動でスクリーンショット撮影し、Apple Vision Framework（OCR）でテキストを認識して Markdown ファイルに書き出すツールです。

> **免責事項**: 本ツールは個人的な学習・ノート作成を目的としています。著作権法第30条に定める私的複製の範囲内でのみご使用ください。著作権者の許可なく第三者への配布・販売は行わないでください。

---

## 動作環境

- macOS 13 Ventura 以降（Apple Vision Framework 使用のため）
- Python 3.10 以降
- Kindle for Mac（最新版推奨）

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

> **追加設定**: macOS の「システム設定 → プライバシーとセキュリティ → 画面収録」で、ターミナル（または使用するアプリ）の画面収録権限を許可してください。

---

## 使い方

### 1. 設定ファイルを編集する

`config.yaml` を開き、書籍のページ数・言語・ウィンドウ領域などを設定します。

### 2. Kindle for Mac を開き、文字起こしを開始するページを表示する

### 3. スクリプトを実行する

```bash
# 基本的な使い方
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

## プロジェクト構成

```
Kindle-Transcriber/
├── src/
│   ├── main.py               # エントリポイント
│   ├── kindle_controller.py  # Kindle ウィンドウ制御
│   ├── screenshot.py         # スクリーンショット撮影
│   ├── ocr.py                # Apple Vision OCR
│   └── output.py             # Markdown 出力
├── output/
│   └── screenshots/          # 一時スクリーンショット（再処理用）
├── config.yaml               # 設定ファイル
├── requirements.txt
└── README.md
```

---

## 設定ファイル (`config.yaml`) の説明

| キー | 説明 | デフォルト |
|---|---|---|
| `total_pages` | 書籍のページ総数（--pages で上書き可） | `100` |
| `page_turn_delay` | ページめくり後の待機時間（秒） | `1.5` |
| `language` | OCR 言語 (`ja` / `en` / `auto`) | `auto` |
| `capture_region` | キャプチャ領域（`auto` で自動検出） | `auto` |
| `output_dir` | 出力ディレクトリ | `output` |
| `save_screenshots` | スクリーンショットを保存するか | `true` |
| `confidence_threshold` | OCR 信頼度の閾値（0.0〜1.0） | `0.3` |

---

## トラブルシューティング

- **「画面収録の権限がありません」**: システム設定で権限を付与してください
- **ページめくりが機能しない**: `config.yaml` の `page_turn_delay` を増やしてください
- **OCR 精度が低い**: Kindle の表示フォントサイズを大きくすると改善します
- **縦書き書籍でテキスト順序がおかしい**: `config.yaml` の `vertical_text: true` を設定してください
Kindleの書籍をスクリーンショットし文字起こしします。
