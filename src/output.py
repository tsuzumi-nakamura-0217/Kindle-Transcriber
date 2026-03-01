"""
output.py
Markdown ファイル出力モジュール。
OCR 結果をページ番号付きで Markdown ファイルに追記する。
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from ocr import OcrResult

logger = logging.getLogger(__name__)


class MarkdownWriter:
    """
    Markdown ファイルへの書き込みを管理するクラス。
    途中再開に対応するため、処理済みページを state ファイルで追跡する。
    """

    def __init__(
        self,
        output_dir: Path,
        title: str,
    ) -> None:
        self.output_dir = output_dir
        self.title = title
        # ファイル名に使えない文字を置換
        safe_title = _sanitize_filename(title)
        self.md_path = output_dir / f"{safe_title}.md"
        self.state_path = output_dir / f".{safe_title}_state.json"
        self._processed_pages: set[int] = set()

        output_dir.mkdir(parents=True, exist_ok=True)

    def initialize(self, total_pages: int) -> None:
        """
        Markdown ファイルのヘッダーを書き込む。
        既存ファイルがある場合は state を読み込んで再開する。
        """
        state = self._load_state()
        if state and self.md_path.exists():
            self._processed_pages = set(state.get("processed_pages", []))
            logger.info(
                f"途中再開: {len(self._processed_pages)} ページ処理済み "
                f"({self.md_path})"
            )
        else:
            # 新規ファイル作成
            self._write_header(total_pages)
            self._processed_pages = set()
            logger.info(f"新規 Markdown ファイル作成: {self.md_path}")

    def write_page(self, result: OcrResult) -> None:
        """
        1 ページ分の OCR 結果を Markdown ファイルに追記する。
        """
        if result.page_number in self._processed_pages:
            logger.debug(f"[Page {result.page_number}] 処理済みのためスキップ")
            return

        page_block = _format_page_block(result)

        with open(self.md_path, "a", encoding="utf-8") as f:
            f.write(page_block)

        self._processed_pages.add(result.page_number)
        self._save_state()

    def is_page_processed(self, page_number: int) -> bool:
        """指定ページが処理済みか確認する。"""
        return page_number in self._processed_pages

    def finalize(self) -> None:
        """
        完了フッターを追記して state ファイルを削除する。
        """
        with open(self.md_path, "a", encoding="utf-8") as f:
            f.write(
                f"\n---\n\n*文字起こし完了: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"
            )
        if self.state_path.exists():
            self.state_path.unlink()
        logger.info(f"完了: {self.md_path}")

    # -----------------------------------------------------------------------
    # 内部メソッド
    # -----------------------------------------------------------------------

    def _write_header(self, total_pages: int) -> None:
        header = (
            f"# {self.title}\n\n"
            f"- **文字起こし日時**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"- **総ページ数**: {total_pages}\n"
            f"- **OCR エンジン**: Apple Vision Framework\n\n"
            "---\n\n"
        )
        with open(self.md_path, "w", encoding="utf-8") as f:
            f.write(header)

    def _load_state(self) -> Optional[dict]:
        if not self.state_path.exists():
            return None
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"State ファイル読み込み失敗: {e}")
            return None

    def _save_state(self) -> None:
        state = {
            "title": self.title,
            "processed_pages": sorted(self._processed_pages),
            "last_updated": datetime.now().isoformat(),
        }
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# フォーマットヘルパー
# ---------------------------------------------------------------------------

def _format_page_block(result: OcrResult) -> str:
    """OcrResult を Markdown の1ページブロックに整形する。"""
    conf_note = (
        f" *(信頼度: {result.confidence:.0%})*"
        if result.confidence < 0.5
        else ""
    )
    lines = [
        f"## ページ {result.page_number}{conf_note}\n\n",
    ]

    if result.text.strip():
        lines.append(result.text.strip())
        lines.append("\n")
    else:
        lines.append("*（テキストなし / 画像ページ）*\n")

    lines.append("\n---\n\n")
    return "".join(lines)


def _sanitize_filename(name: str) -> str:
    """ファイル名に使えない文字を置換する。"""
    invalid_chars = r'\/:*?"<>|'
    for ch in invalid_chars:
        name = name.replace(ch, "_")
    return name.strip()
