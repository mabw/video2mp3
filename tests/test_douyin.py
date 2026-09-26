"""抖音：链接提取与 yt-dlp 参数构造。"""
from app.douyin import build_ytdlp_args, extract_douyin_url


def test_extract_from_plain_share_text():
    text = "8.84 nQk:/ 复制打开抖音 https://v.douyin.com/iABc123/ 好听"
    assert extract_douyin_url(text) == "https://v.douyin.com/iABc123/"


def test_extract_full_url():
    assert extract_douyin_url("看这个 https://www.douyin.com/video/7301234567890") == \
        "https://www.douyin.com/video/7301234567890"


def test_extract_returns_none_for_non_douyin():
    assert extract_douyin_url("https://www.baidu.com") is None
    assert extract_douyin_url("今天天气不错") is None


def test_build_ytdlp_args(tmp_path):
    args = build_ytdlp_args("https://v.douyin.com/iABc123/", tmp_path)
    assert "--no-playlist" in args
    assert "https://v.douyin.com/iABc123/" in args
    assert str(tmp_path) in " ".join(args)
