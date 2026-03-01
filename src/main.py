"""
main.py
Kindle Transcriber エントリポイント。
Kindle for Mac を自動操作し、スクリーンショット→OCR→Markdown出力のパイプラインを実行する。

使い方:
    python src/main.py --pages 100 --title "書籍タイトル"
    python src/main.py --pages 200 --title "書籍タイトル" --start-page 50
    python src/main.py --help
"""

import argparse
import logging
import sys
import time
from pathlib import Path

import yaml

# src/ を Python パスに追加（直接実行時用）
sys.path.insert(0, str(Path(__file__).parent))

from kindle_controller import (
    bring_kindle_to_front,
    get_kindle_window_bounds,
    is_kindle_running,
    turn_page_forward,
)
from ocr import run_ocr
from output import MarkdownWriter
from screenshot import (
    capture_region,
    get_screenshot_path,
    load_existing_screenshot,
    preprocess_image,
)

# ---------------------------------------------------------------------------
# ロガー設定
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# デフォルト設定
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "total_pages": 100,
    "start_page": 1,
    "page_turn_delay": 1.5,
    "capture_region": "auto",
    "language": "auto",
    "vertical_text": False,
    "confidence_threshold": 0.3,
    "output_dir": "output",
    "save_screenshots": True,
    "verbose": False,
    "dry_run": False,
}


# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    config = load_config(args.config)

    # コマンドライン引数で設定を上書き
    if args.pages:
        config["total_pages"] = args.pages
    if args.start_page:
        config["start_page"] = args.start_page

    title = args.title
    total_pages = config["total_pages"]
    start_page = config["start_page"]
    delay = config["page_turn_delay"]
    language = config["language"]
    vertical = config["vertical_text"]
    threshold = config["confidence_threshold"]
    save_shots = config["save_screenshots"]
    dry_run = config["dry_run"]

    if config["verbose"]:
        logging.getLogger().setLevel(logging.DEBUG)

    output_dir = Path(config["output_dir"])

    print_banner(title, total_pages, start_page)

    # Kindle の起動確認
    if not is_kindle_running():
        logger.error(
            "Kindle for Mac が起動していません。"
            "Kindle を起動して文字起こしを開始するページを表示してから再実行してください。"
        )
        sys.exit(1)

    if not bring_kindle_to_front():
        logger.error("Kindle をフォアグラウンドに表示できませんでした。")
        sys.exit(1)

    # ウィンドウ領域を取得
    region = resolve_capture_region(config)
    if region is None:
        sys.exit(1)

    logger.info(f"キャプチャ領域: {region}")

    # Markdown ライターを初期化
    writer = MarkdownWriter(output_dir=output_dir, title=title)
    writer.initialize(total_pages=total_pages)

    # 3 秒のカウントダウン（Kindle にフォーカスを移す時間）
    logger.info("3 秒後に開始します。Kindle for Mac をアクティブにしてください...")
    for i in range(3, 0, -1):
        print(f"  {i}...")
        time.sleep(1)

    # ページごとのループ
    failed_pages: list[int] = []

    for page_num in range(start_page, total_pages + 1):
        prefix = f"[{page_num:>4}/{total_pages}]"

        # 既に処理済みならスキップ（再開時）
        if writer.is_page_processed(page_num):
            print(f"{prefix} スキップ（処理済み）")
            turn_page_forward(delay=delay)
            continue

        print(f"{prefix} キャプチャ中...", end="\r")

        # スクリーンショット撮影
        shot_path = get_screenshot_path(output_dir, page_num) if save_shots else None
        img = capture_region(region, save_path=shot_path)

        if img is None:
            logger.warning(f"{prefix} キャプチャ失敗。スキップします。")
            failed_pages.append(page_num)
            turn_page_forward(delay=delay)
            continue

        if not dry_run:
            # OCR 実行（精度向上のため 2 倍に拡大）
            processed_img = preprocess_image(img, scale=2.0)
            result = run_ocr(
                img=processed_img,
                page_number=page_num,
                language=language,
                vertical_text=vertical,
                confidence_threshold=threshold,
            )

            # Markdown に追記
            writer.write_page(result)

            conf_str = f"conf={result.confidence:.0%}" if result.text else "テキストなし"
            print(f"{prefix} 完了 ({conf_str})          ")
        else:
            print(f"{prefix} キャプチャのみ（dry-run）  ")

        # ページをめくる（最終ページ以外）
        if page_num < total_pages:
            turn_page_forward(delay=delay)

    # 完了処理
    if not dry_run:
        writer.finalize()

    print("\n" + "=" * 50)
    print(f"完了: {total_pages - start_page + 1} ページを処理しました。")
    if failed_pages:
        print(f"失敗したページ: {failed_pages}")
    if not dry_run:
        print(f"出力ファイル: {writer.md_path}")
    print("=" * 50)


# ---------------------------------------------------------------------------
# ヘルパー関数
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Kindle for Mac のページを自動文字起こしして Markdown に出力するツール",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--title", "-t",
        required=True,
        help="書籍タイトル（出力ファイル名に使用されます）",
    )
    parser.add_argument(
        "--pages", "-p",
        type=int,
        default=None,
        help="文字起こしするページ数",
    )
    parser.add_argument(
        "--start-page", "-s",
        type=int,
        default=None,
        dest="start_page",
        help="開始ページ番号（途中再開時に指定）",
    )
    parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        help="設定ファイルのパス（デフォルト: config.yaml）",
    )
    return parser.parse_args()


def load_config(config_path: str) -> dict:
    """設定ファイルを読み込み、デフォルト値とマージして返す。"""
    config = DEFAULT_CONFIG.copy()
    path = Path(config_path)

    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                user_config = yaml.safe_load(f) or {}
            config.update(user_config)
            logger.debug(f"設定ファイル読み込み: {path}")
        except Exception as e:
            logger.warning(f"設定ファイルの読み込みに失敗しました ({path}): {e}")
    else:
        logger.warning(f"設定ファイルが見つかりません ({path})。デフォルト設定を使用します。")

    return config


def resolve_capture_region(config: dict) -> dict | None:
    """
    設定から Kindle のキャプチャ領域を解決する。
    'auto' の場合は AppleScript でウィンドウ座標を取得し、
    辞書形式の場合はそのまま使用する。
    """
    raw = config.get("capture_region", "auto")

    if raw == "auto":
        bounds = get_kindle_window_bounds()
        if bounds is None:
            logger.error(
                "Kindle ウィンドウの座標を自動取得できませんでした。\n"
                "config.yaml の capture_region に手動で座標を設定してください:\n"
                "  capture_region:\n"
                "    left: 0\n"
                "    top: 0\n"
                "    width: 1200\n"
                "    height: 800"
            )
            return None

        # マージン（タイトルバー・ツールバーを除外）
        margin_top = 80
        margin_side = 10
        region = {
            "left": bounds["left"] + margin_side,
            "top": bounds["top"] + margin_top,
            "width": bounds["width"] - margin_side * 2,
            "height": bounds["height"] - margin_top - margin_side,
        }
        return region

    elif isinstance(raw, dict):
        required_keys = {"left", "top", "width", "height"}
        if not required_keys.issubset(raw.keys()):
            logger.error(f"capture_region に必要なキーが不足しています: {required_keys - raw.keys()}")
            return None
        return raw

    else:
        logger.error(f"capture_region の値が不正です: {raw!r}")
        return None


def print_banner(title: str, total_pages: int, start_page: int) -> None:
    print()
    print("=" * 50)
    print("  Kindle Transcriber")
    print("=" * 50)
    print(f"  書籍: {title}")
    print(f"  ページ: {start_page} → {total_pages}")
    print("=" * 50)
    print()


if __name__ == "__main__":
    main()
