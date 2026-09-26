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
        url,
    ]


def download_video(url: str, dest_dir: Path) -> Path:
    """下载视频到收件箱，返回产物路径。失败抛 CalledProcessError，由 UI 转人话提示。"""
    subprocess.run([find_ytdlp(), *build_ytdlp_args(url, dest_dir)],
                   check=True, capture_output=True)
    files = sorted(dest_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime)
    if not files:
        raise RuntimeError("yt-dlp 未产出 mp4")
    return files[-1]
