"""UI 展示辅助：标题截断与窗口尺寸解析（纯函数）。"""
from app.ui.style import (
    DEFAULT_WINDOW_SIZE,
    MAX_TITLE_CHARS,
    MIN_WINDOW_SIZE,
    resolve_window_size,
    shorten_title,
)


def test_shorten_title_truncates_long_titles():
    """超长标题截到上限并加省略号，保留前缀可辨认。"""
    long_title = "这是一首特别特别长的抖音视频标题" * 3
    out = shorten_title(long_title)
    assert len(out) == MAX_TITLE_CHARS + 1        # 截断 + 省略号
    assert out.startswith(long_title[:MAX_TITLE_CHARS])
    assert out.endswith("…")


def test_shorten_title_keeps_short_titles_untouched():
    assert shorten_title("豫剧选段") == "豫剧选段"
    assert shorten_title("好" * MAX_TITLE_CHARS) == "好" * MAX_TITLE_CHARS  # 恰好等于不截


def test_shorten_title_handles_empty_and_none():
    """空标题/None（下载时未拿到标题）显示为空串，不抛错。"""
    assert shorten_title("") == ""
    assert shorten_title(None) == ""


# ---------- 窗口尺寸（记住上次大小） ----------

def test_resolve_window_size_uses_saved_value():
    assert resolve_window_size("1280x800", 1920, 1080) == (1280, 800)


def test_resolve_window_size_falls_back_on_garbage():
    """文件缺失/内容损坏（手动改坏、截断）都回默认，不抛错。"""
    for bad in (None, "", "abc", "12x34", "1280", "1280x", "99999x99999x"):
        assert resolve_window_size(bad, 1920, 1080) == DEFAULT_WINDOW_SIZE


def test_resolve_window_size_clamps_to_screen_and_minimum():
    """存得比屏幕大（换小显示器）钳到屏内；存得过小钳到最小尺寸。"""
    assert resolve_window_size("3000x2000", 1366, 768) == (1366, 768)
    assert resolve_window_size("200x200", 1920, 1080) == MIN_WINDOW_SIZE
