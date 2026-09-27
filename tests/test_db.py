"""SQLite 映射库测试。"""
import sqlite3

from app.db import delete_video, init_db, insert_video, list_videos, update_status


def test_list_videos_tolerates_legacy_columns(layout):
    """旧库多出的历史列（如已废弃的 sent_to_usb）不应对启动造成崩溃。"""
    init_db(layout.db_path)
    insert_video(layout.db_path, "u1", "t", "/v.mp4", "manual")
    with sqlite3.connect(layout.db_path) as conn:
        conn.execute("ALTER TABLE videos ADD COLUMN sent_to_usb INTEGER DEFAULT 0")
    rows = list_videos(layout.db_path)
    assert rows[0].uuid == "u1"


def test_insert_and_list(layout):
    init_db(layout.db_path)
    insert_video(layout.db_path, "u1", "一襟风月", str(layout.video / "u1.mp4"), "douyin")
    rows = list_videos(layout.db_path)
    assert len(rows) == 1
    assert rows[0].uuid == "u1"
    assert rows[0].title == "一襟风月"
    assert rows[0].source == "douyin"
    assert rows[0].status == "pending"


def test_update_status_marks_done(layout):
    init_db(layout.db_path)
    insert_video(layout.db_path, "u1", "t", "/v/u1.mp4", "manual")
    update_status(layout.db_path, "u1", "done", mp3_path="/m/u1.mp3", duration=170)
    rows = list_videos(layout.db_path)
    assert rows[0].status == "done"
    assert rows[0].mp3_path == "/m/u1.mp3"
    assert rows[0].duration == 170


def test_update_status_missing_record_is_noop(layout):
    init_db(layout.db_path)
    update_status(layout.db_path, "nope", "failed")  # 不抛异常
    assert list_videos(layout.db_path) == []


def test_delete_video(layout):
    """删除条目：目标消失，其他条目不受影响。"""
    init_db(layout.db_path)
    insert_video(layout.db_path, "u1", "歌一", "/v/u1.mp4", "manual")
    insert_video(layout.db_path, "u2", "歌二", "/v/u2.mp4", "manual")
    delete_video(layout.db_path, "u1")
    assert [r.uuid for r in list_videos(layout.db_path)] == ["u2"]


def test_delete_video_missing_is_noop(layout):
    """删除不存在的条目不抛异常（与 update_status 的容忍语义一致）。"""
    init_db(layout.db_path)
    delete_video(layout.db_path, "nope")  # 不抛
    assert list_videos(layout.db_path) == []
