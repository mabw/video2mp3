"""U 盘导出逻辑：目标目录抽象，用模拟目录测试。"""
import shutil

import pytest

from app.db import init_db, insert_video
from app.usb import check_free_space, match_usb_items, usb_uuids


@pytest.fixture
def usb_root(tmp_path):
    d = tmp_path / "usb"
    d.mkdir()
    return d


def test_usb_uuids_reads_root_mp3s(usb_root):
    (usb_root / "aaa.mp3").write_bytes(b"x")
    (usb_root / "bbb.mp3").write_bytes(b"x")
    (usb_root / "notes.txt").write_bytes(b"x")
    assert usb_uuids(usb_root) == {"aaa", "bbb"}


def test_match_usb_items_joins_title_and_flags_unknown(usb_root, layout):
    init_db(layout.db_path)
    insert_video(layout.db_path, "aaa", "一襟风月", str(layout.video / "aaa.mp4"), "douyin")
    (usb_root / "aaa.mp3").write_bytes(b"x")
    (usb_root / "自拷的歌.mp3").write_bytes(b"x")

    items = match_usb_items(usb_root, layout)
    by_title = {i.title: i for i in items}
    assert by_title["一襟风月"].uuid == "aaa"
    assert by_title["一襟风月"].in_library is True
    assert by_title["自拷的歌.mp3"].in_library is False


def test_check_free_space(usb_root):
    (usb_root / "pad.bin").write_bytes(b"x" * 1024)
    total = shutil.disk_usage(usb_root).free
    assert check_free_space(usb_root, [1]) is True          # 1 字节总装得下
    assert check_free_space(usb_root, [total]) is False     # 全盘大小必装不下（1.05 倍余量）
