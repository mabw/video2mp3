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
    assert "--cookies" not in args  # 未提供 cookies 文件时不附加


def test_build_ytdlp_args_with_cookies(tmp_path):
    cookies = tmp_path / "cookies.txt"
    args = build_ytdlp_args("https://v.douyin.com/iABc123/", tmp_path,
                            cookies_args=["--cookies", str(cookies)])
    i = args.index("--cookies")
    assert args[i + 1] == str(cookies)


def test_resolve_cookies_prefers_file(tmp_path, monkeypatch):
    """cookies.txt 存在时优先用文件，不做浏览器探测。"""
    from app import douyin

    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# netscape\n")
    monkeypatch.setattr(douyin, "_probe_browser", lambda u, b: (_ for _ in ()).throw(
        AssertionError("不应探测浏览器")))
    memo = tmp_path / "cookies_source"
    assert douyin._resolve_cookies_args("https://v.douyin.com/x/", cookies, memo) == \
        ["--cookies", str(cookies)]
    assert not memo.exists()


def test_resolve_cookies_probes_and_memoizes(tmp_path, monkeypatch):
    """无文件无记忆时按序探测，成功者写入记忆。"""
    from app import douyin

    memo = tmp_path / "cookies_source"
    probed = []
    monkeypatch.setattr(douyin, "_probe_browser",
                        lambda u, b: probed.append(b) or b == "chrome")
    result = douyin._resolve_cookies_args("https://v.douyin.com/x/", None, memo)
    assert result == ["--cookies-from-browser", "chrome"]
    assert probed == ["edge", "chrome"]  # firefox 未被尝试
    assert memo.read_text(encoding="utf-8") == "chrome"
    # 第二次：直接用记忆，不再探测
    assert douyin._resolve_cookies_args("https://v.douyin.com/x/", None, memo) == \
        ["--cookies-from-browser", "chrome"]


def test_resolve_cookies_all_fail_returns_empty(tmp_path, monkeypatch):
    """全部浏览器探测失败：裸跑（UI 走微信兜底）。"""
    from app import douyin

    monkeypatch.setattr(douyin, "_probe_browser", lambda u, b: False)
    memo = tmp_path / "cookies_source"
    assert douyin._resolve_cookies_args("https://v.douyin.com/x/", None, memo) == []
    assert not memo.exists()


def test_download_video_parses_print_output(monkeypatch, tmp_path):
    """stdout 解析：末行=产物路径，倒数第二行=标题（NA 视为无标题）。"""
    from app import douyin

    mp4 = tmp_path / "abc123.mp4"
    mp4.write_bytes(b"x" * 16)

    class FakeProc:
        stdout = f"好听的歌\n{mp4}\n"

    def fake_run(cmd, check, capture_output, text=True, timeout=None,
                 encoding=None, errors=None, env=None, creationflags=0):
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

    def fake_run(cmd, check, capture_output, text=True, timeout=None,
                 encoding=None, errors=None, env=None, creationflags=0):
        return FakeProc()

    monkeypatch.setattr(douyin.subprocess, "run", fake_run)
    monkeypatch.setattr(douyin, "find_ytdlp", lambda: "yt-dlp")
    import pytest

    with pytest.raises(RuntimeError, match="产物不存在"):
        douyin.download_video("https://v.douyin.com/iABc123/", tmp_path)


def test_download_video_retries_after_browser_open(monkeypatch, tmp_path):
    """cookies 缺失失败 → 自动开浏览器种 cookies → 等待 → 重试成功。"""
    import subprocess as real_subprocess

    from app import douyin

    mp4 = tmp_path / "abc.mp4"
    mp4.write_bytes(b"x" * 8)
    calls = {"n": 0}
    actions = []
    monkeypatch.setattr(douyin.time, "sleep", lambda s: actions.append(f"sleep{s}"))
    # monkeypatch 打开动作本身（平台分支由 _open_douyin_page 的专属测试覆盖），
    # 不可 mock webbrowser.open：Windows 走 Edge 分支根本不经过它，会造成双平台断言分叉
    monkeypatch.setattr(douyin, "_open_douyin_page",
                        lambda: actions.append("https://www.douyin.com/"))
    monkeypatch.setattr(douyin, "_resolve_cookies_args", lambda *a: [])

    class FakeProc:
        stdout = f"标题\n{mp4}\n"

    def fake_run(cmd, check, capture_output, text=True, timeout=None,
                 encoding=None, errors=None, env=None, creationflags=0):
        calls["n"] += 1
        if calls["n"] == 1:
            exc = real_subprocess.CalledProcessError(1, cmd)
            exc.stderr = "ERROR: [Douyin] Fresh cookies (not necessarily logged in)"
            raise exc
        return FakeProc()

    monkeypatch.setattr(douyin.subprocess, "run", fake_run)
    monkeypatch.setattr(douyin, "find_ytdlp", lambda: "yt-dlp")
    hints = []
    _path, title = douyin.download_video("https://v.douyin.com/x/", tmp_path,
                                         status_cb=hints.append)
    assert calls["n"] == 2                       # 重试了一轮
    assert any("douyin.com" in a for a in actions)  # 打开了抖音网页
    assert any(a.startswith("sleep") for a in actions)
    assert hints                                 # UI 收到等待提示
    assert title == "标题"


def test_download_video_polling_stops_early(monkeypatch, tmp_path):
    """cookies 落盘后轮询提前中止：第 3 轮探测成功即停，不空等满 6 轮。"""
    import subprocess as real_subprocess
    import webbrowser

    from app import douyin

    mp4 = tmp_path / "abc.mp4"
    mp4.write_bytes(b"x" * 8)
    monkeypatch.setattr(douyin.time, "sleep", lambda s: None)
    monkeypatch.setattr(webbrowser, "open", lambda u: True)
    calls = {"resolve": 0, "run": 0}

    def fake_resolve(*a):
        calls["resolve"] += 1
        # 下载前 1 次 + 轮询 3 次都未落盘，第 4 次（轮询第 3 轮）成功
        return [] if calls["resolve"] < 4 else ["--cookies-from-browser", "edge"]

    monkeypatch.setattr(douyin, "_resolve_cookies_args", fake_resolve)

    class FakeProc:
        stdout = f"标题\n{mp4}\n"

    def fake_run(cmd, check, capture_output, text=True, timeout=None,
                 encoding=None, errors=None, env=None, creationflags=0):
        calls["run"] += 1
        if calls["run"] == 1:
            exc = real_subprocess.CalledProcessError(1, cmd)
            exc.stderr = "ERROR: Fresh cookies are needed"
            raise exc
        return FakeProc()

    monkeypatch.setattr(douyin.subprocess, "run", fake_run)
    monkeypatch.setattr(douyin, "find_ytdlp", lambda: "yt-dlp")
    path, title = douyin.download_video("https://v.douyin.com/x/", tmp_path)
    assert (path, title) == (mp4, "标题")
    # 首轮解析 1 + 轮询 3 + 第二轮下载前解析 1 = 5 次（跑满会是 8 次）
    assert calls["resolve"] == 5


def test_open_douyin_page_uses_edge_on_windows(monkeypatch):
    """Windows 上显式用 Edge 打开（360 等默认浏览器种的 cookies yt-dlp 读不到）。"""
    import webbrowser

    from app import douyin

    opened = []
    monkeypatch.setattr(douyin.sys, "platform", "win32")
    monkeypatch.setattr(webbrowser, "register", lambda *a, **k: None)

    class FakeBrowser:
        def open(self, url):
            opened.append(("edge", url))
            return True

    monkeypatch.setattr(webbrowser, "get", lambda name: FakeBrowser())
    monkeypatch.setattr(webbrowser, "open", lambda u: opened.append(("default", u)))
    douyin._open_douyin_page()
    assert opened == [("edge", "https://www.douyin.com/")]


def test_open_douyin_page_falls_back_on_edge_failure(monkeypatch):
    """Edge 定位失败时退回默认浏览器，不抛异常。"""
    import webbrowser

    from app import douyin

    opened = []
    monkeypatch.setattr(douyin.sys, "platform", "win32")
    monkeypatch.setattr(webbrowser, "register", lambda *a, **k: None)

    def fake_get(name):
        raise webbrowser.Error("no edge")

    monkeypatch.setattr(webbrowser, "get", fake_get)
    monkeypatch.setattr(webbrowser, "open", lambda u: opened.append(u))
    douyin._open_douyin_page()
    assert opened == ["https://www.douyin.com/"]
