"""
screenshot.py
スクリーンショット撮影モジュール。
mss を使って Kindle ウィンドウの指定領域をキャプチャし、Pillow 画像として返す。
"""

import logging
from pathlib import Path
from typing import Optional, Union

import mss
import mss.tools
from PIL import Image

logger = logging.getLogger(__name__)


def capture_region(
    region: dict,
    save_path: Optional[Path] = None,
) -> Optional[Image.Image]:
    """
    指定領域をスクリーンショット撮影して Pillow Image を返す。

    Args:
        region: {"left": int, "top": int, "width": int, "height": int}
        save_path: 指定すると PNG として保存する
    Returns:
        PIL.Image オブジェクト、または失敗時 None
    """
    monitor = {
        "left": region["left"],
        "top": region["top"],
        "width": region["width"],
        "height": region["height"],
    }

    try:
        with mss.mss() as sct:
            raw = sct.grab(monitor)
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            logger.debug(f"キャプチャ: {img.size} @ {region}")

            if save_path is not None:
                save_path.parent.mkdir(parents=True, exist_ok=True)
                img.save(save_path, format="PNG")
                logger.debug(f"スクリーンショット保存: {save_path}")

            return img
    except Exception as e:
        logger.error(f"スクリーンショット撮影に失敗: {e}")
        return None


def get_screenshot_path(output_dir: Path, page_number: int) -> Path:
    """
    ページ番号からスクリーンショットの保存パスを返す。
    例: output/screenshots/page_0042.png
    """
    return output_dir / "screenshots" / f"page_{page_number:04d}.png"


def load_existing_screenshot(path: Path) -> Optional[Image.Image]:
    """
    既存のスクリーンショット PNG を読み込んで返す（再処理用）。
    """
    if not path.exists():
        return None
    try:
        img = Image.open(path).convert("RGB")
        logger.debug(f"既存スクリーンショット読み込み: {path}")
        return img
    except Exception as e:
        logger.warning(f"スクリーンショット読み込み失敗: {path} - {e}")
        return None


def preprocess_image(img: Image.Image, scale: float = 2.0) -> Image.Image:
    """
    OCR 精度向上のための前処理。画像を拡大してシャープにする。

    Args:
        img: 元画像
        scale: 拡大倍率（デフォルト 2.0 倍）。Apple Vision は高解像度の方が精度が上がる
    Returns:
        前処理済み画像
    """
    new_size = (int(img.width * scale), int(img.height * scale))
    return img.resize(new_size, Image.LANCZOS)
