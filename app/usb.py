"""U 盘导出：目标以目录路径抽象（usb_root），不关心是否真盘。"""
import shutil
from dataclasses import dataclass
from pathlib import Path

from app.db import VideoRecord, list_videos
from app.paths import Layout

FREE_SPACE_MARGIN = 1.05  # 空间预检余量


@dataclass(frozen=True)
class UsbItem:
    """U 盘内一首歌的展示信息。"""

    path: Path
    title: str
    duration: int | None
    uuid: str | None
    in_library: bool


def usb_uuids(usb_root: Path) -> set[str]:
    """扫描根目录 mp3 文件名（去扩展名）集合，供主列表推导已在U盘状态。"""
    return {p.stem for p in usb_root.glob("*.mp3")}


def match_usb_items(usb_root: Path, layout: Layout) -> list[UsbItem]:
    """把盘内 mp3 与库匹配：命中显示标题，未命中显示文件名并标注外来。"""
    by_uuid = {r.uuid: r for r in list_videos(layout.db_path)}
    items: list[UsbItem] = []
    for p in sorted(usb_root.glob("*.mp3")):
        rec: VideoRecord | None = by_uuid.get(p.stem)
        items.append(
            UsbItem(
                path=p,
                title=rec.title if rec else p.name,
                duration=rec.duration if rec else None,
                uuid=p.stem if rec else None,
                in_library=rec is not None,
            )
        )
    return items


def check_free_space(usb_root: Path, byte_sizes: list[int]) -> bool:
    """按 1.05 倍余量检查目标剩余空间是否够用。"""
    need = sum(byte_sizes) * FREE_SPACE_MARGIN
    return shutil.disk_usage(usb_root).free >= need
