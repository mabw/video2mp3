"""收件箱：三个入口（拖拽/另存为/抖音下载）的统一收敛点。"""
import os
import time
import uuid as uuidlib
from pathlib import Path

from app.db import insert_video
from app.paths import Layout

VIDEO_EXTS = (".mp4", ".mov", ".mkv")


def is_file_stable(path: Path, interval: float = 1.0) -> bool:
    """两次采样大小与 mtime 均一致则认为写入完成。"""
    try:
        s1 = path.stat()
    except OSError:
        return False
    time.sleep(interval)
    try:
        s2 = path.stat()
    except OSError:
        return False
    return (s1.st_size, s1.st_mtime) == (s2.st_size, s2.st_mtime)


def intake_file(layout: Layout, src: Path, source: str, title: str | None = None) -> str:
    """生成 UUID、把原视频改名移入存档、写库（pending）。返回 uuid。"""
    uid = uuidlib.uuid4().hex
    ext = src.suffix.lower() or ".mp4"
    dest = layout.video / f"{uid}{ext}"
    os.replace(src, dest)
    try:
        insert_video(
            layout.db_path,
            uid,
            title=title or src.stem,
            video_path=str(dest),
            source=source,
        )
    except Exception:
        os.replace(dest, src)  # 回滚：文件回收件箱，避免无库记录的孤儿
        raise
    return uid


def scan_inbox(layout: Layout, interval: float = 1.0) -> list[str]:
    """扫描收件箱中已写完的视频并全部录入。返回 uuid 列表。

    阻塞调用（每个候选文件两次采样含 sleep），请在后台线程调用，勿在 UI 线程直接调。
    """
    uuids: list[str] = []
    for p in sorted(layout.inbox.iterdir()):
        if not p.is_file() or p.suffix.lower() not in VIDEO_EXTS:
            continue
        if not is_file_stable(p, interval=interval):
            continue
        uuids.append(intake_file(layout, p, source="wechat"))
    return uuids
