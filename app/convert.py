"""转换：ffmpeg 命令构造、二进制定位、时长探测、转换执行。"""
import os
import shutil
import sys
from pathlib import Path

# 唱戏机适配参数：与已验证可播样本（VLC 默认档）规格一致
# 44.1kHz / 立体声 / CBR 128k / 不写 ID3 标签
AUDIO_ARGS = ["-vn", "-ar", "44100", "-ac", "2", "-write_id3v2", "0", "-b:a", "128k"]


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
