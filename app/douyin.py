"""抖音入口：链接提取 + yt-dlp 下载。cookies 完全由浏览器扩展自动供给。

扩展运行在浏览器内部（明文 cookie、无文件锁、无 DPAPI 加密问题），
打开抖音页即把 cookie 上报给本地同步服务（app.cookie_sync）落盘为
数据根 cookies.txt，yt-dlp 通过 --cookies 使用。
"""
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from app.convert import find_ytdlp

logger = logging.getLogger(__name__)

# 同 app/convert：抑制 Windows 上子进程弹控制台窗口
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

# 扩展从页面加载到上报的全程上限（页面加载完成后 5 秒即上报，此为宽松兜底）
COOKIE_WAIT_S = 120

# 覆盖 v.douyin.com 短链与 www.douyin.com 完整链接
_DOUYIN_RE = re.compile(r"https?://(?:v\.douyin\.com|www\.douyin\.com)/[A-Za-z0-9._/-]+")

# 打开抖音页用的浏览器候选（Windows）：Edge 系统自带优先，Chrome 次之。
# 只用于"让扩展抓 cookie"，cookie 读取不走浏览器库，无加密/锁问题
_BROWSER_CANDIDATES = {
    "edge": [
        r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
        r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
    ],
    "chrome": [
        r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
        r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
    ],
}


def _utf8_env() -> dict[str, str]:
    """yt-dlp（Python 程序）在管道输出时默认用系统码页（cp936），
    抖音标题的 emoji 会触发编码错误；强制其 stdio 走 UTF-8。"""
    return {**os.environ, "PYTHONIOENCODING": "utf-8"}


def extract_douyin_url(text: str) -> str | None:
    """从任意分享文本中提取第一个抖音链接；无则返回 None。"""
    m = _DOUYIN_RE.search(text or "")
    return m.group(0) if m else None


def build_ytdlp_args(url: str, dest_dir: Path, cookies_args: list[str] | None = None) -> list[str]:
    """构造 yt-dlp 参数（不含二进制名）。产物落在收件箱。"""
    args = [
        "--no-playlist",
        "-o", str(dest_dir / "%(id).30s.%(ext)s"),
        "--print", "title",                  # stdout 输出视频标题（供界面显示）
        "--print", "after_move:filepath",    # stdout 输出确切产物路径（不猜文件）
    ]
    if cookies_args:
        args += cookies_args
    args.append(url)
    return args


def _open_douyin_page() -> None:
    """打开抖音首页，触发扩展上报 cookie（Windows 用 Edge/Chrome）。"""
    import webbrowser

    if sys.platform == "win32":
        for name, candidates in _BROWSER_CANDIDATES.items():
            exe = next((os.path.expandvars(c) for c in candidates
                        if os.path.isfile(os.path.expandvars(c))), None)
            if exe is None:
                continue
            try:
                webbrowser.register(f"v2m_{name}", None,
                                    webbrowser.BackgroundBrowser(exe))
                webbrowser.get(f"v2m_{name}").open("https://www.douyin.com/")
                return
            except (OSError, webbrowser.Error):
                logger.warning("[douyin] 用 %s 打开抖音页失败（%s）", name, exe,
                               exc_info=True)
        logger.warning("[douyin] 未找到 Edge/Chrome，退回默认浏览器")
    webbrowser.open("https://www.douyin.com/")


def _wait_cookies_file(cookies_file: Path | None) -> bool:
    """等待扩展刷新 cookies.txt（mtime 变新即成功）。超时返回 False。"""
    if cookies_file is None:
        return False
    mtime0 = cookies_file.stat().st_mtime if cookies_file.exists() else 0.0
    deadline = time.monotonic() + COOKIE_WAIT_S
    while time.monotonic() < deadline:
        time.sleep(5)
        try:
            if cookies_file.exists() and cookies_file.stat().st_mtime > mtime0:
                logger.info("[douyin] 扩展已刷新 %s", cookies_file)
                return True
        except OSError:  # 恰好读到 .part 替换的空档：下一轮再看
            continue
    return False


def download_video(
    url: str,
    dest_dir: Path,
    cookies_file: Path | None = None,
    status_cb=None,
) -> tuple[Path, str | None]:
    """下载视频到收件箱，返回 (产物路径, 视频标题|None)。

    从 stdout 拿确切产物路径（收件箱是多入口共享目录，不能按 mtime 猜文件）；
    标题用于替代不可读的数字 id。失败抛 CalledProcessError，由 UI 转人话提示。
    cookies 由浏览器扩展自动落盘到 cookies_file；因失效下载失败时自动打开
    抖音页触发扩展重新上报，等文件刷新后重试一轮（status_cb 报告状态）。
    """
    lines: list[str] = []  # 循环内成功路径必赋值；此处初始化仅为静态分析
    for attempt in range(2):
        cookies_args = (["--cookies", str(cookies_file)]
                        if cookies_file is not None and cookies_file.exists() else [])
        try:
            proc = subprocess.run(
                [find_ytdlp(), *build_ytdlp_args(url, dest_dir, cookies_args)],
                check=True, capture_output=True, text=True,
                encoding="utf-8", errors="replace", env=_utf8_env(),
                creationflags=_NO_WINDOW,
            )
            lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
            break  # 下载命令成功，跳出重试循环
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "") + (exc.stdout or "")
            # stderr 落日志：真机上失败的具体原因（cookie 失效/网络/风控）全在这里
            logger.error("[douyin] yt-dlp 第 %d 次尝试失败:\n%s", attempt + 1, stderr)
            if attempt == 0 and "cookie" in stderr.lower():
                if status_cb is not None:
                    status_cb("正在自动获取抖音访问权限，可能弹出抖音页面，请稍候…")
                _open_douyin_page()
                _wait_cookies_file(cookies_file)
                continue  # 第二轮：扩展刷新了 cookies.txt 就能过
            raise
    if len(lines) < 2:
        raise RuntimeError("yt-dlp 未返回产物路径")
    path = Path(lines[-1])
    if not path.is_file():
        raise RuntimeError(f"yt-dlp 产物不存在: {path}")
    title = None if lines[-2] == "NA" else lines[-2]
    return path, title
