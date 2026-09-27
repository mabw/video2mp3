"""适老化视觉常量与纯函数：大字号、高对比、白底黑字。"""
import re
import sys

IS_WIN = sys.platform == "win32"

# Windows 用微软雅黑，mac 开发回退苹方
FONT_FAMILY = "Microsoft YaHei UI" if IS_WIN else "PingFang SC"

FONT_BODY = (FONT_FAMILY, 18)            # 正文
FONT_BUTTON = (FONT_FAMILY, 22, "bold")  # 按钮
FONT_STATUS = (FONT_FAMILY, 16)          # 状态小字

COLOR_BG = "#ffffff"
COLOR_TEXT = "#000000"
COLOR_PRIMARY = "#1a7f37"   # 下载（绿）
COLOR_SEND = "#d97706"      # 发送 U 盘（橙）
COLOR_MANAGE = "#4a5568"    # 整理 U 盘（灰蓝）
COLOR_DISABLED = "#9aa0a6"  # 已在 U 盘
COLOR_ROW_ALT = "#f5f7fa"   # 隔行底色
COLOR_DELETE = "#c0392b"    # 删除（红），主窗口行按钮与 U 盘窗口共用

# 列表行/弹窗中标题最多显示的字符数：抖音标题常有 40+ 字，Tk 的 Label
# 不自动换行，超长会把行内按钮挤出窗口（布局位移）。完整标题仍存数据库
MAX_TITLE_CHARS = 18

# 默认窗口尺寸：18 字标题 + 时长 + 右侧三按钮（约 1030px）的安全宽度；
# 1366 老屏幕也放得下。最小尺寸防拖太小布局全乱
DEFAULT_WINDOW_SIZE = (1100, 720)
MIN_WINDOW_SIZE = (900, 600)


def shorten_title(title: str | None, max_chars: int = MAX_TITLE_CHARS) -> str:
    """超长标题截断加省略号，保住列表布局。纯函数便于单测。"""
    title = title or ""
    return title if len(title) <= max_chars else title[:max_chars] + "…"


_SIZE_RE = re.compile(r"(\d{3,5})x(\d{3,5})")


def resolve_window_size(
    saved: str | None, screen_w: int, screen_h: int
) -> tuple[int, int]:
    """由持久化的尺寸决定窗口大小：垃圾/缺失回默认，超出屏幕或过小则钳回。

    只记尺寸不记位置——位置存了可能在换显示器/改分辨率后恢复到屏幕外。
    纯函数便于单测。
    """
    m = _SIZE_RE.fullmatch((saved or "").strip())
    if m is None:
        return DEFAULT_WINDOW_SIZE
    w, h = int(m[1]), int(m[2])
    min_w, min_h = MIN_WINDOW_SIZE
    return (min(max(w, min_w), screen_w), min(max(h, min_h), screen_h))
