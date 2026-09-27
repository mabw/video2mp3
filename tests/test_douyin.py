"""抖音：链接提取、yt-dlp 参数构造、cookies 扩展链路与重试。"""
import subprocess as real_subprocess
from pathlib import Path

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


# ---------- 临时浏览器实例种 cookie ----------

def test_find_browser_exe_prefers_edge(monkeypatch):
    """Edge 自带优先，Chrome 次之；平台路径候选按存在性筛选。"""
    from app import douyin

    monkeypatch.setattr(douyin.os.path, "isfile",
                        lambda p: "msedge" in p)  # 只有 Edge 存在
    assert douyin._find_browser_exe() is not None
    assert "msedge" in douyin._find_browser_exe()
    monkeypatch.setattr(douyin.os.path, "isfile", lambda p: False)
    assert douyin._find_browser_exe() is None


def test_seed_via_temp_browser_launches_with_extension(monkeypatch, tmp_path):
    """临时实例：独立 profile + 内置扩展 + 抖音页，返回可终止的进程。"""
    import webbrowser

    from app import douyin

    launched = []
    monkeypatch.setattr(douyin, "_find_browser_exe", lambda: "/fake/msedge")
    monkeypatch.setattr(douyin.tempfile, "gettempdir", lambda: str(tmp_path))

    class FakeProc:
        def terminate(self):
            launched.append("terminated")

    monkeypatch.setattr(douyin.subprocess, "Popen",
                        lambda args, **k: launched.append(args)
                        or FakeProc())
    monkeypatch.setattr(webbrowser, "open",
                        lambda u: (_ for _ in ()).throw(
                            AssertionError("找到浏览器不应退默认")))
    proc = douyin._seed_via_temp_browser(tmp_path / "extension")
    assert proc is not None
    args = launched[0]
    assert "--user-data-dir" in " ".join(args)
    assert "--load-extension" in " ".join(args)
    assert "https://www.douyin.com/" in args


def test_seed_via_temp_browser_falls_back(monkeypatch):
    """找不到浏览器：退回默认浏览器打开（提示装扩展的路径），返回 None。"""
    import webbrowser

    from app import douyin

    opened = []
    monkeypatch.setattr(douyin, "_find_browser_exe", lambda: None)
    monkeypatch.setattr(webbrowser, "open", lambda u: opened.append(u))
    assert douyin._seed_via_temp_browser(Path("/no/such/ext")) is None
    assert opened == ["https://www.douyin.com/"]


# ---------- 等待扩展落盘 ----------

def test_wait_cookies_file_detects_refresh(monkeypatch, tmp_path):
    """就绪标准 = ttwid 出现且内容连续两轮不变（页面多波种 cookie 收敛）。"""
    from app import douyin

    cf = tmp_path / "cookies.txt"
    monkeypatch.setattr(douyin.time, "sleep", lambda s: None)
    clock = {"t": 0.0}

    # monotonic 快进：等满超时窗口，文件始终不出现 → False
    monkeypatch.setattr(douyin.time, "monotonic",
                        lambda: (clock.__setitem__("t", clock["t"] + 60)
                                 or clock["t"]))
    assert douyin._wait_cookies_file(cf) is False

    # 波次模拟：基础 → +ttwid → 再加签名（内容还在变）→ 稳定（重复同内容）
    waves = iter([
        lambda: cf.write_text("basic", encoding="utf-8"),
        lambda: cf.write_text("ttwid 1", encoding="utf-8"),
        lambda: cf.write_text("ttwid 1; __ac_signature 2", encoding="utf-8"),
        lambda: None,  # 第四轮不再写入：与上轮相同 → 收敛
    ])
    monkeypatch.setattr(douyin.time, "sleep",
                        lambda s: next(waves, lambda: None)())
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
    """cookie 失效失败 → 临时浏览器种 cookie → 文件刷新 → 重试且关掉临时实例。"""
    from app import douyin

    mp4 = tmp_path / "abc.mp4"
    mp4.write_bytes(b"x" * 8)
    exc = real_subprocess.CalledProcessError(1, ["yt-dlp"])
    exc.stderr = "ERROR: [Douyin] Fresh cookies (not necessarily logged in) are needed"
    state = _patch_ytdlp(monkeypatch, douyin,
                         [exc, f"标题\n{mp4}\n"])
    actions = []

    class FakeProc:
        def terminate(self):
            actions.append("terminated")

    monkeypatch.setattr(douyin, "_seed_via_temp_browser",
                        lambda ext: actions.append("launched") or FakeProc())
    monkeypatch.setattr(douyin, "_wait_cookies_file",
                        lambda cf: actions.append("waited") or True)
    hints = []
    _path, title = douyin.download_video("https://v.douyin.com/x/", tmp_path,
                                         status_cb=hints.append)
    assert state["n"] == 2                     # 重试了一轮
    # 时序完整：启动实例 → 等到落盘 → 只关临时实例
    assert actions == ["launched", "waited", "terminated"]
    assert hints                               # UI 收到状态提示
    assert title == "标题"


def test_download_video_raises_when_retry_also_fails(monkeypatch, tmp_path):
    """第二轮仍失败：异常向上抛（UI 转微信兜底提示），不再无限重试。"""
    import pytest

    from app import douyin

    exc = real_subprocess.CalledProcessError(1, ["yt-dlp"])
    exc.stderr = "ERROR: Fresh cookies are needed"
    _patch_ytdlp(monkeypatch, douyin, [exc, exc])

    class FakeProc:
        def terminate(self):
            pass

    monkeypatch.setattr(douyin, "_seed_via_temp_browser", lambda ext: FakeProc())
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
    monkeypatch.setattr(douyin, "_seed_via_temp_browser",
                        lambda ext: (_ for _ in ()).throw(
                            AssertionError("非 cookie 错误不应打开浏览器")))
    with pytest.raises(real_subprocess.CalledProcessError):
        douyin.download_video("https://v.douyin.com/x/", tmp_path)
    assert state["n"] == 1
