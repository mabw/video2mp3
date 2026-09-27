"""抖音：链接提取、yt-dlp 参数构造、cookies 扩展链路与重试。"""
import subprocess as real_subprocess

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


# ---------- 打开抖音页（触发扩展上报） ----------

def test_open_douyin_page_prefers_edge_then_chrome(monkeypatch):
    """Windows 上 Edge 优先、Chrome 次之；都存在时只用 Edge。"""
    import webbrowser

    from app import douyin

    opened = []
    monkeypatch.setattr(douyin.sys, "platform", "win32")
    monkeypatch.setattr(douyin.os.path, "isfile", lambda p: True)
    monkeypatch.setattr(webbrowser, "register", lambda *a, **k: None)

    class FakeBrowser:
        def __init__(self, name):
            self.name = name

        def open(self, url):
            opened.append((self.name, url))
            return True

    monkeypatch.setattr(webbrowser, "get",
                        lambda name: FakeBrowser(name.replace("v2m_", "")))
    monkeypatch.setattr(webbrowser, "open", lambda u: opened.append(("default", u)))
    douyin._open_douyin_page()
    assert opened == [("edge", "https://www.douyin.com/")]


def test_open_douyin_page_falls_back_to_default(monkeypatch):
    """Edge/Chrome 都不存在（或启动失败）：退回默认浏览器，不抛异常。"""
    import webbrowser

    from app import douyin

    opened = []
    monkeypatch.setattr(douyin.sys, "platform", "win32")
    monkeypatch.setattr(douyin.os.path, "isfile", lambda p: False)
    monkeypatch.setattr(webbrowser, "open", lambda u: opened.append(u))
    douyin._open_douyin_page()
    assert opened == ["https://www.douyin.com/"]


# ---------- 等待扩展落盘 ----------

def test_wait_cookies_file_detects_refresh(monkeypatch, tmp_path):
    """扩展落盘 = cookies.txt mtime 变新；文件不动则超时 False。"""
    from app import douyin

    cf = tmp_path / "cookies.txt"
    cf.write_text("old", encoding="utf-8")
    monkeypatch.setattr(douyin.time, "sleep", lambda s: None)
    clock = {"t": 0.0}

    # monotonic 快进：模拟等满超时窗口，文件始终未刷新
    monkeypatch.setattr(douyin.time, "monotonic",
                        lambda: (clock.__setitem__("t", clock["t"] + 60)
                                 or clock["t"]))
    assert douyin._wait_cookies_file(cf) is False

    def refresh_then_sleep(_s):
        cf.write_text("new", encoding="utf-8")

    monkeypatch.setattr(douyin.time, "sleep", refresh_then_sleep)
    assert douyin._wait_cookies_file(cf) is True


# ---------- 下载主流程 ----------

def _patch_ytdlp(monkeypatch, douyin, outputs):
    """把 subprocess.run 换成按序返回 outputs（CalledProcessError 或 stdout）。"""
    state = {"n": 0}

    def fake_run(cmd, check, capture_output, text=True, timeout=None,
                 encoding=None, errors=None, env=None, creationflags=0):
        out = outputs[min(state["n"], len(outputs) - 1)]
        state["n"] += 1
        if isinstance(out, Exception):
            raise out
        return type("P", (), {"stdout": out})()

    monkeypatch.setattr(douyin.subprocess, "run", fake_run)
    monkeypatch.setattr(douyin, "find_ytdlp", lambda: "yt-dlp")
    return state


def test_download_video_parses_print_output(monkeypatch, tmp_path):
    """stdout 解析：末行=产物路径，倒数第二行=标题（NA 视为无标题）。"""
    from app import douyin

    mp4 = tmp_path / "abc123.mp4"
    mp4.write_bytes(b"x" * 16)
    _patch_ytdlp(monkeypatch, douyin, [f"好听的歌\n{mp4}\n"])
    path, title = douyin.download_video("https://v.douyin.com/iABc123/", tmp_path)
    assert path == mp4
    assert title == "好听的歌"


def test_download_video_raises_on_missing_output(monkeypatch, tmp_path):
    from app import douyin

    _patch_ytdlp(monkeypatch, douyin, ["标题\n/不存在的路径/xxx.mp4\n"])
    import pytest

    with pytest.raises(RuntimeError, match="产物不存在"):
        douyin.download_video("https://v.douyin.com/iABc123/", tmp_path)


def test_download_video_uses_cookies_file_when_present(monkeypatch, tmp_path):
    """cookies.txt 存在时命令必须带 --cookies（扩展落盘的文件直接生效）。"""
    from app import douyin

    mp4 = tmp_path / "abc.mp4"
    mp4.write_bytes(b"x" * 8)
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# netscape\n", encoding="utf-8")
    cmds = []

    def fake_run(cmd, **k):
        cmds.append(cmd)
        return type("P", (), {"stdout": f"标题\n{mp4}\n"})()

    monkeypatch.setattr(douyin.subprocess, "run", fake_run)
    monkeypatch.setattr(douyin, "find_ytdlp", lambda: "yt-dlp")
    douyin.download_video("https://v.douyin.com/x/", tmp_path, cookies_file=cookies)
    assert "--cookies" in cmds[0]
    assert str(cookies) in cmds[0]


def test_download_video_retries_after_cookie_refresh(monkeypatch, tmp_path):
    """cookie 失效失败 → 自动开抖音页 → 扩展刷新 → 重试成功。"""
    from app import douyin

    mp4 = tmp_path / "abc.mp4"
    mp4.write_bytes(b"x" * 8)
    exc = real_subprocess.CalledProcessError(1, ["yt-dlp"])
    exc.stderr = "ERROR: [Douyin] Fresh cookies (not necessarily logged in) are needed"
    state = _patch_ytdlp(monkeypatch, douyin,
                         [exc, f"标题\n{mp4}\n"])
    actions = []
    monkeypatch.setattr(douyin, "_open_douyin_page",
                        lambda: actions.append("opened"))
    monkeypatch.setattr(douyin, "_wait_cookies_file",
                        lambda cf: actions.append("waited") or True)
    hints = []
    _path, title = douyin.download_video("https://v.douyin.com/x/", tmp_path,
                                         status_cb=hints.append)
    assert state["n"] == 2                     # 重试了一轮
    assert actions == ["opened", "waited"]     # 开页面且等到扩展刷新
    assert hints                               # UI 收到状态提示
    assert title == "标题"


def test_download_video_raises_when_retry_also_fails(monkeypatch, tmp_path):
    """第二轮仍失败：异常向上抛（UI 转微信兜底提示），不再无限重试。"""
    import pytest

    from app import douyin

    exc = real_subprocess.CalledProcessError(1, ["yt-dlp"])
    exc.stderr = "ERROR: Fresh cookies are needed"
    _patch_ytdlp(monkeypatch, douyin, [exc, exc])
    monkeypatch.setattr(douyin, "_open_douyin_page", lambda: None)
    monkeypatch.setattr(douyin, "_wait_cookies_file", lambda cf: False)
    with pytest.raises(real_subprocess.CalledProcessError):
        douyin.download_video("https://v.douyin.com/x/", tmp_path)


def test_download_video_no_retry_on_other_errors(monkeypatch, tmp_path):
    """非 cookie 原因的失败（如网络）不触发开浏览器，直接抛出。"""
    import pytest

    from app import douyin

    exc = real_subprocess.CalledProcessError(1, ["yt-dlp"])
    exc.stderr = "ERROR: Unable to download webpage"
    state = _patch_ytdlp(monkeypatch, douyin, [exc])
    monkeypatch.setattr(douyin, "_open_douyin_page",
                        lambda: (_ for _ in ()).throw(
                            AssertionError("非 cookie 错误不应打开浏览器")))
    with pytest.raises(real_subprocess.CalledProcessError):
        douyin.download_video("https://v.douyin.com/x/", tmp_path)
    assert state["n"] == 1
