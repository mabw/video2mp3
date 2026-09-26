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
    # --print 两项：标题 + 确切产物路径（不靠 mtime 猜文件）
    assert "--print" in args
    assert "after_move:filepath" in args


def test_download_video_parses_print_output(monkeypatch, tmp_path):
    """stdout 解析：末行=产物路径，倒数第二行=标题（NA 视为无标题）。"""
    from app import douyin

    mp4 = tmp_path / "abc123.mp4"
    mp4.write_bytes(b"x" * 16)

    class FakeProc:
        stdout = f"好听的歌\n{mp4}\n"

    def fake_run(cmd, check, capture_output, text=True):
        return FakeProc()

    monkeypatch.setattr(douyin.subprocess, "run", fake_run)
    monkeypatch.setattr(douyin, "find_ytdlp", lambda: "yt-dlp")
    path, title = douyin.download_video("https://v.douyin.com/iABc123/", tmp_path)
    assert path == mp4
    assert title == "好听的歌"

    FakeProc.stdout = "NA\n" + str(mp4) + "\n"  # 无标题场景
    path, title = douyin.download_video("https://v.douyin.com/iABc123/", tmp_path)
    assert title is None


def test_download_video_raises_on_missing_output(monkeypatch, tmp_path):
    from app import douyin

    class FakeProc:
        stdout = "标题\n/不存在的路径/xxx.mp4\n"

    def fake_run(cmd, check, capture_output, text=True):
        return FakeProc()

    monkeypatch.setattr(douyin.subprocess, "run", fake_run)
    monkeypatch.setattr(douyin, "find_ytdlp", lambda: "yt-dlp")
    import pytest

    with pytest.raises(RuntimeError, match="产物不存在"):
        douyin.download_video("https://v.douyin.com/iABc123/", tmp_path)
