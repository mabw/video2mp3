"""数据目录约定：生产与测试共用同一 Layout，根目录可注入。"""
import os
import sys
from dataclasses import dataclass
from pathlib import Path

# 环境变量优先级最高，用于测试与开发调试
ENV_HOME = "VIDEO2MP3_HOME"


@dataclass(frozen=True)
class Layout:
    """所有数据落点的唯一来源。"""

    root: Path
    inbox: Path
    video: Path
    mp3: Path
    db_path: Path
    logs: Path

    @classmethod
    def create(cls, root: Path) -> "Layout":
        """按约定在 root 下建目录并返回布局。"""
        layout = cls(
            root=root,
            inbox=root / "收件箱",
            video=root / "video",
            mp3=root / "mp3",
            db_path=root / "library.db",
            logs=root / "logs",
        )
        for d in (layout.root, layout.inbox, layout.video, layout.mp3, layout.logs):
            d.mkdir(parents=True, exist_ok=True)
        return layout


def default_layout() -> Layout:
    """生产环境布局：Windows 用系统盘\\视频管家，其余平台用用户主目录。"""
    env = os.environ.get(ENV_HOME)
    if env:
        root = Path(env)
    elif sys.platform == "win32":
        drive = os.environ.get("SYSTEMDRIVE", "C:") + "/"
        root = Path(drive) / "视频管家"
    else:
        root = Path.home() / ".video2mp3"
    return Layout.create(root)


def asset_path(name: str) -> Path:
    """资源文件定位：开发态项目根 assets/，PyInstaller onedir 态 _MEIPASS/assets/。"""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        base = Path(meipass) / "assets"  # --add-data 落在 _internal/
    else:
        base = Path(__file__).resolve().parents[1] / "assets"
    return base / name
