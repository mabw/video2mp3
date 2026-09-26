"""收件箱：稳定校验、录入、扫描。"""
from pathlib import Path

from app.db import init_db, list_videos
from app.inbox import intake_file, is_file_stable, scan_inbox


def _make_video(dest: Path, size: int = 1024) -> Path:
    dest.write_bytes(b"\x00" * size)
    return dest


def test_is_file_stable_true_for_quiet_file(tmp_path):
    f = _make_video(tmp_path / "a.mp4")
    assert is_file_stable(f, interval=0.05) is True


def test_is_file_stable_false_for_growing_file(tmp_path):
    f = tmp_path / "growing.mp4"
    f.write_bytes(b"\x00" * 100)

    import threading

    def grow():
        for _ in range(20):
            with open(f, "ab") as fh:
                fh.write(b"\x00" * 100)

    threading.Thread(target=grow).start()
    assert is_file_stable(f, interval=0.05) is False


def test_intake_file_moves_and_records(layout):
    init_db(layout.db_path)
    src = _make_video(layout.inbox / "我的视频.mp4")
    uuid = intake_file(layout, src, source="wechat")
    assert not src.exists()  # 收件箱中已移走
    stored = layout.video / f"{uuid}.mp4"
    assert stored.exists()
    rows = list_videos(layout.db_path)
    assert rows[0].uuid == uuid
    assert rows[0].title == "我的视频"
    assert rows[0].source == "wechat"
    assert rows[0].status == "pending"


def test_intake_file_generates_unique_uuid(layout):
    init_db(layout.db_path)
    src = _make_video(layout.inbox / "v.mp4")
    u1 = intake_file(layout, src, source="manual")
    src2 = _make_video(layout.inbox / "v.mp4")
    u2 = intake_file(layout, src2, source="manual")
    assert u2 != u1


def test_scan_inbox_intakes_videos_only(layout):
    init_db(layout.db_path)
    _make_video(layout.inbox / "a.mp4")
    _make_video(layout.inbox / "b.MOV")
    _make_video(layout.inbox / "ignore.txt")
    uuids = scan_inbox(layout, interval=0.05)
    assert len(uuids) == 2
    assert all(not (layout.inbox / n).exists() for n in ("a.mp4", "b.MOV"))
