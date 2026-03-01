"""
ocr.py
Apple Vision Framework を使った OCR モジュール。
ocrmac ライブラリ経由で日本語・英語テキストを認識する。
"""

import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class OcrResult:
    """1 ページ分の OCR 結果。"""
    page_number: int
    text: str
    confidence: float          # 全ブロックの平均信頼度
    low_confidence_blocks: list = field(default_factory=list)  # 閾値以下のブロック
    raw_blocks: list = field(default_factory=list)             # ocrmac の生データ


def run_ocr(
    img: Image.Image,
    page_number: int,
    language: str = "auto",
    vertical_text: bool = False,
    confidence_threshold: float = 0.3,
) -> OcrResult:
    """
    画像に対して OCR を実行して OcrResult を返す。

    Args:
        img: PIL Image オブジェクト
        page_number: ページ番号（ログ・結果用）
        language: "ja" / "en" / "auto"
        vertical_text: True の場合、縦書き用にブロックの並び替えを行う
        confidence_threshold: 信頼度の閾値。これ以下のブロックは警告ログに記録
    """
    try:
        import ocrmac
    except ImportError:
        raise ImportError(
            "ocrmac がインストールされていません。`pip install ocrmac` を実行してください。"
        )

    # ocrmac は PIL Image を直接受け取れないため一時 PNG に保存
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        img.save(tmp_path, format="PNG")

    try:
        # 言語指定
        lang_codes = _resolve_language_codes(language)
        annotations = ocrmac.OCR(
            str(tmp_path),
            language_preference=lang_codes,
            framework="vision",
        ).recognize()
    except Exception as e:
        logger.error(f"[Page {page_number}] OCR 実行エラー: {e}")
        return OcrResult(page_number=page_number, text="", confidence=0.0)
    finally:
        tmp_path.unlink(missing_ok=True)

    if not annotations:
        logger.warning(f"[Page {page_number}] OCR 結果が空でした。")
        return OcrResult(page_number=page_number, text="", confidence=0.0)

    # 結果を座標順に並び替えて読み順を保持
    sorted_blocks = _sort_blocks(annotations, vertical=vertical_text)

    texts: list[str] = []
    confidences: list[float] = []
    low_conf_blocks: list = []

    for block in sorted_blocks:
        # ocrmac のブロック形式: (text, confidence, bounding_box)
        text, conf, bbox = block[0], block[1], block[2]
        confidences.append(conf)
        if conf < confidence_threshold:
            low_conf_blocks.append(block)
            logger.debug(
                f"[Page {page_number}] 低信頼度ブロック (conf={conf:.2f}): {text!r}"
            )
        texts.append(text)

    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    full_text = "\n".join(texts)

    if low_conf_blocks:
        logger.warning(
            f"[Page {page_number}] {len(low_conf_blocks)} ブロックが信頼度閾値 ({confidence_threshold}) 以下です。"
        )

    return OcrResult(
        page_number=page_number,
        text=full_text,
        confidence=avg_confidence,
        low_confidence_blocks=low_conf_blocks,
        raw_blocks=sorted_blocks,
    )


# ---------------------------------------------------------------------------
# 内部ヘルパー
# ---------------------------------------------------------------------------

def _resolve_language_codes(language: str) -> list[str]:
    """
    言語設定を ocrmac の言語コードリストに変換する。
    Apple Vision の識別子を使用。
    """
    mapping = {
        "ja": ["ja-JP"],
        "en": ["en-US"],
        "auto": ["ja-JP", "en-US"],
    }
    return mapping.get(language, ["ja-JP", "en-US"])


def _sort_blocks(blocks: list, vertical: bool = False) -> list:
    """
    テキストブロックを読み順にソートする。

    横書き: Y 座標（上→下）→ X 座標（左→右）
    縦書き: X 座標（右→左）→ Y 座標（上→下）

    bounding_box は ocrmac では [(x1,y1),(x2,y2),(x3,y3),(x4,y4)] の形式で
    正規化座標（0〜1）として提供される。
    """
    def _top_left(block):
        bbox = block[2]  # [(x1,y1), ...]
        # 正規化座標の左上を取得（Y は上が 1.0）
        xs = [p[0] for p in bbox]
        ys = [p[1] for p in bbox]
        x_min = min(xs)
        y_max = max(ys)  # Vision の Y は下が 0、上が 1
        return (x_min, y_max)

    try:
        if vertical:
            # 縦書き: X 降順（右→左）→ Y 降順（上→下）
            return sorted(blocks, key=lambda b: (-_top_left(b)[0], -_top_left(b)[1]))
        else:
            # 横書き: Y 降順（上→下）→ X 昇順（左→右）
            return sorted(blocks, key=lambda b: (-_top_left(b)[1], _top_left(b)[0]))
    except (IndexError, TypeError) as e:
        logger.warning(f"ブロックのソートに失敗、元の順序を使用します: {e}")
        return blocks
