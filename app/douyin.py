"""抖音入口：分享文本中的链接提取 + yt-dlp 下载（含 cookies 自动解析）。"""
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


def _utf8_env() -> dict[str, str]:
    """yt-dlp（Python 程序）在管道输出时默认用系统码页（cp936），
    抖音标题的 emoji 会触发编码错误；强制其 stdio 走 UTF-8。"""
    return {**os.environ, "PYTHONIOENCODING": "utf-8"}

# 覆盖 v.douyin.com 短链与 www.douyin.com 完整链接
_DOUYIN_RE = re.compile(r"https?://(?:v\.douyin\.com|www\.douyin\.com)/[A-Za-z0-9._/-]+")

# 自动探测顺序：Edge 是 Windows 自带（老人机最可能有），Chrome 加密最难放最后
_PROBE_BROWSERS = ("edge", "chrome", "firefox")
_PROBE_TIMEOUT_S = 30
# 打开抖音网页种下匿名 cookies 后，浏览器要过一阵才把 cookies 批量写入磁盘
# （mac 实测 25 秒时还没落盘、150 秒时已落盘；Windows 真机观测 90 秒仍不够，
# 加大窗口并轮询探测，一旦成功立即中止）
COOKIE_POLL_INTERVAL_S = 20
COOKIE_POLL_ROUNDS = 8  # 最多 8 轮 × 20 秒 ≈ 160 秒


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


def _probe_browser(url: str, browser: str) -> bool:
    """轻量探测该浏览器的 cookies 是否够过抖音风控：--simulate 只解析不下载。"""
    try:
        subprocess.run(
            [find_ytdlp(), "--no-playlist", "--simulate", "--print", "title",
             "--cookies-from-browser", browser, url],
            check=True, capture_output=True, text=True, encoding="utf-8",
            errors="replace", env=_utf8_env(), timeout=_PROBE_TIMEOUT_S,
            creationflags=_NO_WINDOW,
        )
        return True
    except subprocess.CalledProcessError as exc:
        # 失败原因必须落日志：锁/解密失败/cookies 未落盘三种命运的修法完全不同
        tail = "\n".join((exc.stderr or "").strip().splitlines()[-3:])
        logger.warning("[douyin] 探测 %s 失败:\n%s", browser, tail)
        return False
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("[douyin] 探测 %s 异常: %s", browser, exc)
        return False


def _resolve_cookies_args(url: str, cookies_file: Path | None, memo: Path) -> list[str]:
    """cookies 来源解析：cookies.txt 文件 > 记住的浏览器 > 探测 > 裸跑。"""
    if cookies_file is not None and cookies_file.exists():
        return ["--cookies", str(cookies_file)]
    if memo.exists():
        browser = memo.read_text(encoding="utf-8").strip()
        if browser:
            return ["--cookies-from-browser", browser]
    for browser in _PROBE_BROWSERS:
        if _probe_browser(url, browser):
            memo.write_text(browser, encoding="utf-8")  # 记住，下次免探测
            return ["--cookies-from-browser", browser]
    return []  # 裸跑：可能风控失败，UI 提示走微信兜底


def _open_douyin_page() -> None:
    """用 Edge 显式打开抖音页（Windows）：默认浏览器可能是 360/QQ 等套壳，
    种下的 cookies yt-dlp 读不到；Edge 系统自带且在探测列表首位。
    Edge 定位/启动失败时退回默认浏览器。
    """
    import webbrowser

    if sys.platform == "win32":
        # Edge 实际安装位置两种都有（64 位机常见 Program Files），先验证存在再用：
        # 路径不存在时 register 不会报错，open 才失败——那时已悄悄退回默认浏览器白种一轮
        candidates = [
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        ]
        edge_exe = next((p for p in candidates if os.path.isfile(p)), None)
        if edge_exe is not None:
            try:
                webbrowser.register("v2m_edge", None,
                                    webbrowser.BackgroundBrowser(edge_exe))
                webbrowser.get("v2m_edge").open("https://www.douyin.com/")
                return
            except (OSError, webbrowser.Error):
                logger.warning("[douyin] Edge 启动失败，退回默认浏览器", exc_info=True)
        else:
            logger.warning("[douyin] 未找到 msedge.exe（尝试过 %s），退回默认浏览器",
                           candidates)
    webbrowser.open("https://www.douyin.com/")


def download_video(
    url: str,
    dest_dir: Path,
    cookies_file: Path | None = None,
    status_cb=None,
) -> tuple[Path, str | None]:
    """下载视频到收件箱，返回 (产物路径, 视频标题|None)。

    从 stdout 拿确切产物路径（收件箱是多入口共享目录，不能按 mtime 猜文件）；
    标题用于替代不可读的数字 id。失败抛 CalledProcessError，由 UI 转人话提示。
    cookies 自动解析：数据根的 cookies.txt（插件导出）优先，否则从本机浏览器
    读取（探测成功的浏览器记在数据根的 cookies_source，失败自动清掉重探）。
    若因 cookies 缺失失败：自动打开一次抖音网页（种下匿名 cookies），轮询
    等待浏览器把 cookies 写入磁盘后重试一轮（status_cb 报告等待状态），仍失败才抛出。
    """
    memo = dest_dir.parent / "cookies_source"
    lines: list[str] = []  # 循环内成功路径必赋值；此处初始化仅为静态分析
    for attempt in range(2):
        cookies_args = _resolve_cookies_args(url, cookies_file, memo)
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
            # stderr 落日志：真机上"获取不到权限"的具体原因（锁/解密/风控）全在这里
            logger.error("[douyin] yt-dlp 第 %d 次尝试失败:\n%s", attempt + 1, stderr)
            if attempt == 0 and "cookie" in stderr.lower():
                # cookies 缺失：打开抖音网页种匿名 cookies，轮询等它落盘
                if status_cb is not None:
                    status_cb("正在打开抖音网页获取访问权限，首次约需一两分钟，请稍候…")
                _open_douyin_page()
                memo.unlink(missing_ok=True)  # 清记忆，重探含刚种 cookies 的浏览器
                for _ in range(COOKIE_POLL_ROUNDS):
                    time.sleep(COOKIE_POLL_INTERVAL_S)
                    # _resolve_cookies_args 探测成功会顺手把浏览器写回 memo
                    if _resolve_cookies_args(url, cookies_file, memo):
                        break
                continue  # 进入第二轮：无论轮询是否探到，都再试一次下载
            memo.unlink(missing_ok=True)  # 失败清浏览器记忆：下次重新探测
            raise
    if len(lines) < 2:
        raise RuntimeError("yt-dlp 未返回产物路径")
    path = Path(lines[-1])
    if not path.is_file():
        raise RuntimeError(f"yt-dlp 产物不存在: {path}")
    title = None if lines[-2] == "NA" else lines[-2]
    return path, title
