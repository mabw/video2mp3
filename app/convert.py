"""转换：ffmpeg 命令构造、二进制定位、时长探测、转换执行。"""
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

from app.db import list_videos, update_status
from app.paths import Layout

logger = logging.getLogger(__name__)

# Windows GUI 程序调控制台子进程（ffmpeg 等）默认各弹一个新控制台窗口；加标志抑制
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

# 唱戏机适配参数：与已验证可播样本（VLC 默认档）规格一致
# 44.1kHz / 立体声 / CBR 128k / 不写 ID3 标签
# ID3 抑制双保险：ffmpeg 9 起移除 -write_id3v2 语义（静默失效，仍写 ID3 头），
# 实际由 -id3v2_version 0 生效；旧版 ffmpeg 则由 -write_id3v2 0 生效。
AUDIO_ARGS = [
    "-vn", "-ar", "44100", "-ac", "2",
    "-write_id3v2", "0", "-id3v2_version", "0",
    "-b:a", "128k",
]


def build_ffmpeg_args(src: str, dst: str) -> list[str]:
    """构造 ffmpeg 参数（不含二进制名），纯函数便于单测。

    -y 前置，保证码率参数紧邻输出文件（唱戏机档位核心参数可读性）。
    """
    return ["-i", src, "-y", *AUDIO_ARGS, dst]


def find_tool(name: str, env_var: str) -> str:
    """外部工具定位：环境变量 > 应用目录 > PATH。找不到抛 FileNotFoundError。"""
    env_val = os.environ.get(env_var)
    if env_val and Path(env_val).exists():
        return env_val
    exe = f"{name}.exe" if sys.platform == "win32" else name
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        beside = Path(meipass) / exe  # PyInstaller onedir 的 _internal/
    else:
        beside = Path(__file__).resolve().parent / exe
    if beside.exists():
        return str(beside)
    which = shutil.which(name)
    if which:
        return which
    raise FileNotFoundError(f"找不到 {name}，请设置 {env_var} 或将其加入 PATH")


def find_ffmpeg() -> str:
    return find_tool("ffmpeg", "VIDEO2MP3_FFMPEG")


def find_ytdlp() -> str:
    return find_tool("yt-dlp", "VIDEO2MP3_YTDLP")


def find_ffprobe() -> str:
    """ffprobe 与 ffmpeg 同目录定位。"""
    p = Path(find_ffmpeg()).with_name("ffprobe")
    if sys.platform == "win32":
        p = p.with_name("ffprobe.exe")
    if p.exists():
        return str(p)
    which = shutil.which("ffprobe")
    if which:
        return which
    raise FileNotFoundError("找不到 ffprobe，请将其与 ffmpeg 放在同一目录")


def probe_duration(path: Path) -> float:
    """ffprobe 读取媒体时长（秒）。"""
    out = subprocess.run(
        [find_ffprobe(), "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
        creationflags=_NO_WINDOW,
    ).stdout.strip()
    return float(out)


def convert_video(layout: Layout, uuid: str) -> bool:
    """执行一条转换：converting→done/failed，校验产出时长偏差 <2 秒。"""
    rec = next((r for r in list_videos(layout.db_path) if r.uuid == uuid), None)
    if rec is None or rec.video_path is None:
        update_status(layout.db_path, uuid, "failed")
        return False
    video_path = Path(rec.video_path)
    if not video_path.exists():
        update_status(layout.db_path, uuid, "failed")
        return False
    update_status(layout.db_path, uuid, "converting")
    dst = layout.mp3 / f"{uuid}.mp3"
    try:
        subprocess.run(
            [find_ffmpeg(), *build_ffmpeg_args(str(video_path), str(dst))],
            check=True, capture_output=True, creationflags=_NO_WINDOW,
        )
        src_duration = probe_duration(video_path)
        dst_duration = probe_duration(dst)
        if abs(dst_duration - src_duration) >= 2.0:
            raise RuntimeError("产出时长与原视频偏差超过 2 秒")
    except (subprocess.CalledProcessError, ValueError, RuntimeError, OSError) as exc:
        dst.unlink(missing_ok=True)
        update_status(layout.db_path, uuid, "failed")
        logger.error("[convert] %s 转换失败: %s", uuid, exc)
        return False
    update_status(layout.db_path, uuid, "done", mp3_path=str(dst),
                  duration=int(dst_duration))
    return True
