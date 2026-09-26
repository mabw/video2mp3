"""U 盘导出：目标以目录路径抽象（usb_root），不关心是否真盘。"""
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from app.db import VideoRecord, list_videos
from app.paths import Layout

logger = logging.getLogger(__name__)

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


def send_one(src: Path, usb_root: Path) -> str:
    """复制一首到 U 盘根目录；已存在同名则跳过（不覆盖），复制后读回校验。"""
    dst = usb_root / src.name
    if dst.exists():
        return "skipped"
    tmp = usb_root / (src.name + ".part")
    try:
        shutil.copy2(src, tmp)
    except OSError:
        tmp.unlink(missing_ok=True)  # 中途拔盘/写保护：清残片再抛
        raise
    if tmp.stat().st_size != src.stat().st_size:  # 复制后大小比对（廉价即时校验）
        tmp.unlink(missing_ok=True)
        raise OSError(f"写入校验失败: {dst}")
    tmp.replace(dst)
    return "copied"


def delete_files(paths: list[Path]) -> int:
    """删除盘内文件，返回成功数。只动 U 盘，不动本地库。"""
    count = 0
    for p in paths:
        try:
            p.unlink()
            count += 1
        except OSError as exc:
            logger.warning("[usb] 删除失败 %s: %s", p, exc)  # 写保护等：留排查线索
            continue
    return count
