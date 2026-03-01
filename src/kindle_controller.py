"""
kindle_controller.py
Kindle for Mac ウィンドウの制御モジュール。
AppleScript を通じてフォーカス・ウィンドウ情報取得・ページめくりを行う。
"""

import subprocess
import time
import logging
from typing import Optional

import pyautogui

logger = logging.getLogger(__name__)

KINDLE_APP_NAME = "Kindle"


def bring_kindle_to_front() -> bool:
    """Kindle for Mac をフォアグラウンドにフォーカスする。"""
    script = f'tell application "{KINDLE_APP_NAME}" to activate'
    result = _run_applescript(script)
    if result is None:
        logger.error("Kindle を起動できませんでした。Kindle for Mac がインストールされているか確認してください。")
        return False
    time.sleep(0.5)  # アクティベーション待ち
    return True


def is_kindle_running() -> bool:
    """Kindle for Mac が起動しているか確認する。"""
    script = 'tell application "System Events" to (name of processes) contains "Kindle"'
    result = _run_applescript(script)
    return result is not None and result.strip() == "true"


def get_kindle_window_bounds() -> Optional[dict]:
    """
    Kindle for Mac のウィンドウ座標とサイズを取得する。
    Returns:
        {"left": int, "top": int, "width": int, "height": int} または None
    """
    script = """
    tell application "System Events"
        tell process "Kindle"
            set win to front window
            set pos to position of win
            set sz to size of win
            return (item 1 of pos as string) & "," & (item 2 of pos as string) & "," & (item 1 of sz as string) & "," & (item 2 of sz as string)
        end tell
    end tell
    """
    result = _run_applescript(script)
    if result is None:
        logger.warning("Kindle ウィンドウの座標を取得できませんでした。")
        return None

    try:
        parts = [int(x.strip()) for x in result.strip().split(",")]
        bounds = {
            "left": parts[0],
            "top": parts[1],
            "width": parts[2],
            "height": parts[3],
        }
        logger.debug(f"Kindle ウィンドウ: {bounds}")
        return bounds
    except (ValueError, IndexError) as e:
        logger.error(f"ウィンドウ座標のパースに失敗: {e} (raw: {result!r})")
        return None


def turn_page_forward(delay: float = 1.5) -> None:
    """
    右矢印キーを送信してページを進める。
    `delay`: ページ遷移アニメーションの待機時間（秒）
    """
    pyautogui.press("right")
    time.sleep(delay)


def turn_page_backward(delay: float = 1.5) -> None:
    """左矢印キーを送信してページを戻る。"""
    pyautogui.press("left")
    time.sleep(delay)


def go_to_first_page() -> None:
    """
    Cmd + Home で書籍の先頭に移動する。
    ※ Kindle for Mac のバージョンによっては動作しない場合があります。
    """
    pyautogui.hotkey("command", "home")
    time.sleep(1.0)


# ---------------------------------------------------------------------------
# 内部ヘルパー
# ---------------------------------------------------------------------------

def _run_applescript(script: str) -> Optional[str]:
    """
    AppleScript を実行して標準出力を返す。
    エラー時は None を返し、ログに記録する。
    """
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            logger.error(f"AppleScript エラー: {result.stderr.strip()}")
            return None
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.error("AppleScript がタイムアウトしました。")
        return None
    except Exception as e:
        logger.error(f"AppleScript 実行例外: {e}")
        return None
