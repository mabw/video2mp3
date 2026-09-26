"""抖音入口：分享文本中的链接提取 + yt-dlp 下载。"""
import re
import subprocess
from pathlib import Path

from app.convert import find_ytdlp

# 覆盖 v.douyin.com 短链与 www.douyin.com 完整链接
_DOUYIN_RE = re.compile(r"https?://(?:v\.douyin\.com|www\.douyin\.com)/[A-Za-z0-9._/-]+")


def extract_douyin_url(text: str) -> str | None:
    """从任意分享文本中提取第一个抖音链接；无则返回 None。"""
    m = _DOUYIN_RE.search(text or "")
    return m.group(0) if m else None


def build_ytdlp_args(url: str, dest_dir: Path) -> list[str]:
    """构造 yt-dlp 参数（不含二进制名）。产物落在收件箱。"""
    return [
        "--no-playlist",
        "-o", str(dest_dir / "%(id).30s.%(ext)s"),
        "--print", "title",                  # stdout 输出视频标题（供界面显示）
        "--print", "after_move:filepath",    # stdout 输出确切产物路径（不猜文件）
        url,
    ]


def download_video(url: str, dest_dir: Path) -> tuple[Path, str | None]:
    """下载视频到收件箱，返回 (产物路径, 视频标题|None)。

    从 stdout 拿确切产物路径（收件箱是多入口共享目录，不能按 mtime 猜文件）；
    标题用于替代不可读的数字 id。失败抛 CalledProcessError，由 UI 转人话提示。
    """
    proc = subprocess.run([find_ytdlp(), *build_ytdlp_args(url, dest_dir)],
                          check=True, capture_output=True, text=True)
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    if len(lines) < 2:
        raise RuntimeError("yt-dlp 未返回产物路径")
    path = Path(lines[-1])
    if not path.is_file():
        raise RuntimeError(f"yt-dlp 产物不存在: {path}")
    title = None if lines[-2] == "NA" else lines[-2]
    return path, title
