"""UI 展示辅助：标题截断（防长抖音标题把列表按钮挤出窗口）。"""
from app.ui.style import MAX_TITLE_CHARS, shorten_title


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
