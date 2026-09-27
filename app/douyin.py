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
import tempfile
import time
from pathlib import Path

from app.convert import find_ytdlp
from app.paths import asset_path

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
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ],
    "chrome": [
        r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
        r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ],
}


def _utf8_env() -> dict[str, str]:
    """yt-dlp（Python 程序）在管道输出时默认用系统码页（cp936），
    抖音标题的 emoji 会触发编码错误；强制其 stdio 走 UTF-8。"""
    return {**os.environ, "PYTHONIOENCODING": "utf-8"}


def _decode_stream(data: bytes | str) -> str:
    """yt-dlp stdout 的实际编码不可控：打包版 exe 可能无视 PYTHONIOENCODING
    仍按系统码页（Windows 中文 = GBK）输出中文路径（真机实测踩过，路径乱码
    导致产物检查失败）。按字节双解码兜底：先严格 UTF-8，失败退 GBK。"""
    if isinstance(data, str):  # 测试桩或已解码
        return data
    for enc in ("utf-8", "gbk"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def extract_douyin_url(text: str) -> str | None:
    """从任意分享文本中提取第一个抖音链接；无则返回 None。"""
    m = _DOUYIN_RE.search(text or "")
    return m.group(0) if m else None


def build_ytdlp_args(url: str, dest_dir: Path, cookies_args: list[str] | None = None) -> list[str]:
    """构造 yt-dlp 参数（不含二进制名）。产物落在收件箱。"""
    args = [
        "--no-playlist",
        # 优先 H.264：抖音源默认"最佳"常落在 HEVC 播放流，Windows 自带播放器
        # 缺 HEVC 解码会打不开原视频；转 MP3 不受影响（只取音频）。
        # 用 -S 排序偏好而非 -f 过滤：抖音的 h264 档是合成流，-f 的 bv* 选择器
        # 匹配不到（实测踩过）；-S +vcodec:h264 把编码偏好提到排序最前
        "-S", "+vcodec:h264",
        "--merge-output-format", "mp4",
        "-o", str(dest_dir / "%(id).30s.%(ext)s"),
        "--print", "title",                  # stdout 输出视频标题（供界面显示）
        "--print", "after_move:filepath",    # stdout 输出确切产物路径（不猜文件）
    ]
    if cookies_args:
        args += cookies_args
    args.append(url)
    return args


def _find_browser_exe() -> str | None:
    """定位可用的 Edge/Chrome 可执行文件（Edge 自带优先）。"""
    for candidates in _BROWSER_CANDIDATES.values():
        exe = next((os.path.expandvars(c) for c in candidates
                    if os.path.isfile(os.path.expandvars(c))), None)
        if exe is not None:
            return exe
    return None


# 临时实例的 profile 目录名：同时是"哪些进程属于临时实例"的唯一识别特征
TEMP_PROFILE_NAME = "v2m_browser_profile"


def _seed_via_temp_browser(ext_dir: Path) -> None:
    """启动临时浏览器实例（独立 profile + 内置扩展）访问抖音。

    免安装路线：不碰用户浏览器 profile，不要求装扩展——软件自带扩展目录，
    --load-extension 挂到临时实例上；cookie 由扩展上报本地服务落盘。
    用完由 _close_temp_browser() 按特征精确关闭，不影响用户开着的浏览器。
    找不到/启动失败时退回默认浏览器打开（该路径需手动装扩展兜底）。
    """
    exe = _find_browser_exe()
    if exe is None:
        logger.warning("[douyin] 未找到 Edge/Chrome，退回默认浏览器（需手动装扩展）")
        import webbrowser

        webbrowser.open("https://www.douyin.com/")
        return
    profile = Path(tempfile.gettempdir()) / TEMP_PROFILE_NAME  # 固定目录可复用
    profile.mkdir(exist_ok=True)
    try:
        subprocess.Popen(
            [exe,
             f"--user-data-dir={profile}",
             f"--load-extension={ext_dir}",
             "--no-first-run", "--no-default-browser-check",
             "https://www.douyin.com/"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=_NO_WINDOW,
        )
    except OSError:
        logger.warning("[douyin] 启动临时浏览器失败（%s），退回默认浏览器", exe,
                       exc_info=True)
        import webbrowser

        webbrowser.open("https://www.douyin.com/")


def _close_temp_browser() -> None:
    """按 profile 特征精确定向关闭临时浏览器实例的全部进程。

    不能用 Popen 句柄 terminate：Windows 上若已有 Edge 实例，新启动的
    msedge.exe 只是把 URL 转交既有进程树后自己退出，窗口不属于我们的句柄
    （真机实测：cookie 到了但窗口关不掉）。临时实例的每个进程命令行都带
    --user-data-dir=<TEMP>\\v2m_browser_profile，按此特征逐个精确终止；
    用户自己开着的浏览器不带该参数，绝无误伤。
    """
    try:
        if sys.platform == "win32":
            ps_cmd = ("Get-CimInstance Win32_Process | Where-Object "
                      "{$_.CommandLine -like '*v2m_browser_profile*'} | "
                      "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }")
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                check=False, capture_output=True, creationflags=_NO_WINDOW)
        else:
            subprocess.run(["pkill", "-f", TEMP_PROFILE_NAME],
                           check=False, capture_output=True)
        logger.info("[douyin] 已按特征关闭临时浏览器实例")
    except OSError as exc:
        logger.warning("[douyin] 关闭临时浏览器失败（不影响下载）: %s", exc)


def _wait_cookies_file(cookies_file: Path | None) -> bool:
    """等待扩展落盘的 cookie 波次收敛（ttwid 出现且内容不再变化）。

    全新临时 profile 的页面 JS 会持续多波种 cookie：先基础项，风控关键的
    __ac_signature/web_sign_token 等要跑完页面挑战才出现——固定秒数收尾
    都赌时序（端到端实测 3 秒太早）。改为检测"内容连续两轮不变"即收敛。
    超时但文件确有更新时也返回 True（尽力重试）。
    """
    if cookies_file is None:
        return False
    refreshed = False
    last_text = ""
    stable = False
    deadline = time.monotonic() + COOKIE_WAIT_S
    while time.monotonic() < deadline:
        time.sleep(5)
        try:
            text = cookies_file.read_text(encoding="utf-8") \
                if cookies_file.exists() else ""
        except OSError:  # 恰好读到 .part 替换的空档：下一轮再看
            continue
        if not text:
            continue
        refreshed = True
        if "ttwid" in text:
            if text == last_text:
                stable = True
                break
            last_text = text  # 还在变：页面仍在种新 cookie，继续等
    if stable:
        logger.info("[douyin] cookie 波次已收敛（ttwid 在且内容稳定）")
    return refreshed


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
            # 字节接收 + 双解码：见 _decode_stream（编码不可控，str 模式会踩乱码）
            proc = subprocess.run(
                [find_ytdlp(), *build_ytdlp_args(url, dest_dir, cookies_args)],
                check=True, capture_output=True, env=_utf8_env(),
                creationflags=_NO_WINDOW,
            )
            lines = [ln.strip() for ln in _decode_stream(proc.stdout).splitlines()
                     if ln.strip()]
            break  # 下载命令成功，跳出重试循环
        except subprocess.CalledProcessError as exc:
            stderr = _decode_stream(exc.stderr or b"") + _decode_stream(exc.stdout or b"")
            # stderr 落日志：真机上失败的具体原因（cookie 失效/网络/风控）全在这里
            logger.error("[douyin] yt-dlp 第 %d 次尝试失败:\n%s", attempt + 1, stderr)
            if attempt == 0 and "cookie" in stderr.lower():
                if status_cb is not None:
                    status_cb("正在自动获取抖音访问权限，可能弹出抖音页面，请稍候…")
                try:
                    _seed_via_temp_browser(asset_path("extension"))
                    _wait_cookies_file(cookies_file)
                finally:
                    # 按特征精确定向关闭：只关临时实例，用户浏览器不受影响
                    _close_temp_browser()
                continue  # 第二轮：扩展刷新了 cookies.txt 就能过
            raise
    if len(lines) < 2:
        raise RuntimeError("yt-dlp 未返回产物路径")
    path = Path(lines[-1])
    if not path.is_file():
        raise RuntimeError(f"yt-dlp 产物不存在: {path}")
    title = None if lines[-2] == "NA" else lines[-2]
    return path, title
