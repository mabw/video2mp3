"""平台适配层：全部 OS 差异集中于此。"""
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ENV_USB_DIR = "VIDEO2MP3_USB_DIR"


@dataclass(frozen=True)
class UsbDrive:
    """一块可移动磁盘。"""

    volume_label: str
    drive: str
    free_bytes: int

    def display(self) -> str:
        return f"{self.volume_label} ({self.drive})"


def detect_removable_drives() -> list[UsbDrive]:
    """枚举 removable 磁盘（Windows 专属；其他平台返回空）。"""
    if sys.platform != "win32":
        return []
    import psutil  # 延迟导入：仅 Windows 需要随包

    drives = []
    for part in psutil.disk_partitions(all=False):
        if part.fstype == "" or "cdrom" in part.opts:
            continue
        if not _is_removable(part.device):
            continue
        label = _volume_label(part.device)
        try:
            free = psutil.disk_usage(part.mountpoint).free
        except OSError:
            continue  # 枚举与用量查询之间盘被拔出：跳过该盘，保证枚举永不抛
        drives.append(UsbDrive(label, part.mountpoint.rstrip("\\/"), free))
    return drives


def _is_removable(device: str) -> bool:
    """Windows GetDriveTypeW 判断可移动磁盘。"""
    import ctypes

    DRIVE_REMOVABLE = 2
    # windll 为 Windows 专属（typeshed 按平台限定），本函数仅 win32 路径调用
    return ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(device)) == DRIVE_REMOVABLE  # pyright: ignore[reportAttributeAccessIssue]


def _volume_label(device: str) -> str:
    """读取卷标；失败回退"U盘"。"""
    import ctypes

    buf = ctypes.create_unicode_buffer(261)
    fs = ctypes.create_unicode_buffer(261)
    ok = ctypes.windll.kernel32.GetVolumeInformationW(  # pyright: ignore[reportAttributeAccessIssue]
        ctypes.c_wchar_p(device), buf, 261, None, None, None, fs, 261
    )
    return buf.value if ok and buf.value else "U盘"


def get_fixed_drives() -> list[str]:
    """固定硬盘盘符列表（如 ["C:", "D:"]；非 Windows 返回空）。用于数据目录选址。"""
    if sys.platform != "win32":
        return []
    import ctypes

    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    DRIVE_FIXED = 3
    drives: list[str] = []
    for i in range(26):
        if bitmask & (1 << i):
            letter = f"{chr(65 + i)}:"
            if ctypes.windll.kernel32.GetDriveTypeW(
                ctypes.c_wchar_p(letter + "\\")
            ) == DRIVE_FIXED:
                drives.append(letter)
    return drives


def get_usb_root() -> Path | None:
    """当前应使用的 U 盘根目录：env 覆盖 > 唯一 removable 根 > None（0 或多块）。"""
    env = os.environ.get(ENV_USB_DIR)
    if env:
        return Path(env)
    drives = detect_removable_drives()
    if len(drives) == 1:
        return Path(drives[0].drive + "/")
    return None


def get_usb_drives() -> list[UsbDrive]:
    """多盘时的选择列表。"""
    return detect_removable_drives()


def play_media(path: Path) -> None:
    """调用系统默认播放器。"""
    if sys.platform == "win32":
        # getattr 写法绕过 typeshed 的 win32 限定（mac 上 pyright 不报 os.startfile 不存在）
        getattr(os, "startfile")(str(path))  # noqa: B009
    else:
        subprocess.run(["open", str(path)], check=False)


def hook_drop_files(window, callback) -> bool:
    """注册拖拽回调；成功返回 True。mac 上不可用，返回 False。"""
    if sys.platform != "win32":
        return False
    import windnd

    windnd.hook_dropfiles(window, func=callback)
    return True
