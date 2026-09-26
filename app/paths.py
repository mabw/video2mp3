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


def _config_file_path() -> Path:
    """数据目录.txt 的位置：程序旁（打包版 exe 同级 / 开发态项目根）。"""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parents[1]
    return base / "数据目录.txt"


def _configured_home(cfg_file: Path | None = None) -> Path | None:
    """读程序旁的 数据目录.txt（一行绝对路径）：绿色版最直观的数据位置配置。"""
    cfg_file = cfg_file or _config_file_path()
    try:
        text = cfg_file.read_text(encoding="utf-8-sig").strip()  # 容忍记事本 BOM
    except OSError:
        return None
    return Path(text) if text else None


def write_configured_home(new_home: Path, cfg_file: Path | None = None) -> Path:
    """把数据目录选择写入程序旁的 数据目录.txt（重启后生效）。返回该文件路径。"""
    cfg_file = cfg_file or _config_file_path()
    cfg_file.write_text(str(new_home) + "\n", encoding="utf-8")
    return cfg_file


def default_layout(*, cfg_file: Path | None = None) -> Layout:
    """生产环境布局（优先级）：环境变量 > 程序旁 数据目录.txt > 非系统盘固定盘 > 系统盘。

    cfg_file 仅测试注入用；生产调用不传（自动定位程序旁的 数据目录.txt）。
    """
    env = os.environ.get(ENV_HOME)
    if env:
        root = Path(env)
    elif (configured := _configured_home(cfg_file)) is not None:
        root = configured
    elif sys.platform == "win32":
        from app.platform import get_fixed_drives

        system_drive = os.environ.get("SYSTEMDRIVE", "C:")
        fixed = get_fixed_drives()
        # 数据不放系统盘：有非系统固定盘（D/E/…）就选第一个，否则退回系统盘
        non_system = [d for d in fixed if d.upper() != system_drive.upper()]
        drive = (non_system or [system_drive])[0]
        root = Path(drive + "/") / "视频管家"
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
