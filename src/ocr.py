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
from ocrmac.ocrmac import text_from_image as _ocrmac_recognize

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
    # ocrmac は PIL Image を直接受け取れないため一時 PNG に保存
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        img.save(tmp_path, format="PNG")

    try:
        # 言語指定
        lang_codes = _resolve_language_codes(language)
        # text_from_image は (text, confidence, bbox_tuple) のリストを返す
        annotations = _ocrmac_recognize(
            str(tmp_path),
            language_preference=lang_codes,
            recognition_level="accurate",
            confidence_threshold=0.0,
            detail=True,
        )
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

    confidences: list[float] = []
    low_conf_blocks: list = []

    for block in sorted_blocks:
        text, conf, bbox = block[0], block[1], block[2]
        confidences.append(conf)
        if conf < confidence_threshold:
            low_conf_blocks.append(block)
            logger.debug(
                f"[Page {page_number}] 低信頼度ブロック (conf={conf:.2f}): {text!r}"
            )

    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    # bbox の垂直間隔で段落を判定しながらテキストを結合
    full_text = _merge_blocks_to_text(sorted_blocks, vertical=vertical_text)

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


def _merge_blocks_to_text(blocks: list, vertical: bool = False) -> str:
    """
    ソート済み OCR ブロックを段落を考慮してテキストに結合する。

    bbox (x, y, width, height) の垂直間隔を測定して:
    - 同一行 (y がほぼ同じ)          → スペースなしで連結
    - 次の行 (間隔 ≒ 行高さ)         → 同一段落として直接連結（日本語はスペース不要）
    - 段落区切り (間隔 > 行高さ×閾値) → \\n\\n で分割

    Apple Vision の座標系: 左下原点、y は上に向かって増加。
    bbox の y は BOX の下端、y+height が上端。
    """
    if not blocks:
        return ""

    parts: list[str] = []

    for i, block in enumerate(blocks):
        text = block[0].strip()
        if not text:
            continue

        if not parts:
            parts.append(text)
            continue

        prev_block = blocks[i - 1]
        prev_bbox = prev_block[2]  # (x, y, w, h)
        curr_bbox = block[2]

        # 行高さの基準（前後ブロックの平均高さ）
        avg_line_height = (prev_bbox[3] + curr_bbox[3]) / 2

        # 垂直方向の間隔
        # Apple Vision: y の値が大きい = 画面上側 (y=1.0 が上端)
        # prev_block の下端 = prev_bbox[1]
        # curr_block の上端 = curr_bbox[1] + curr_bbox[3]
        prev_bottom = prev_bbox[1]
        curr_top = curr_bbox[1] + curr_bbox[3]

        # gap > 0 のとき 2 ブロック間に空白あり
        gap = prev_bottom - curr_top

        # 同一行判定（垂直方向にほぼ重なる → x 方向に並ぶ複数ブロック）
        if gap < -avg_line_height * 0.3:
            parts.append(" " + text)
        # 段落区切り判定（行間の 1.2 倍以上の間隔）
        elif gap > avg_line_height * 1.2:
            parts.append("\n\n" + text)
        # 通常の行継続（同一段落内の折り返し）→ そのまま結合（日本語はスペース不要）
        else:
            parts.append(text)

    return "".join(parts)


def _sort_blocks(blocks: list, vertical: bool = False) -> list:
    """
    テキストブロックを読み順にソートする。

    横書き: Y 座標（上→下）→ X 座標（左→右）
    縦書き: X 座標（右→左）→ Y 座標（上→下）

    bounding_box は ocrmac では (x, y, width, height) の正規化座標タプル。
    Apple Vision の座標系: 左下が原点 (0, 0)、右上が (1, 1)。
    よって Y 値が大きいほど画面上部にある。
    """
    def _sort_key(block):
        bbox = block[2]  # (x, y, width, height)
        x, y = bbox[0], bbox[1]
        # y は左下基準なので、上にあるほど y が大きい
        if vertical:
            # 縦書き: X 降順（右→左）→ Y 降順（上→下）
            return (-x, -y)
        else:
            # 横書き: Y 降順（上→下）→ X 昇順（左→右）
            return (-y, x)

    try:
        return sorted(blocks, key=_sort_key)
    except (IndexError, TypeError) as e:
        logger.warning(f"ブロックのソートに失敗、元の順序を使用します: {e}")
        return blocks
