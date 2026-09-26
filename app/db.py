"""SQLite 映射库：videos 表的建库与读写。短连接 + WAL，进程内多线程安全。"""
import sqlite3
from dataclasses import dataclass
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
  uuid       TEXT PRIMARY KEY,
  title      TEXT NOT NULL,
  video_path TEXT,
  mp3_path   TEXT,
  source     TEXT CHECK(source IN ('wechat','douyin','manual')),
  duration   INTEGER,
  status     TEXT DEFAULT 'pending',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


@dataclass(frozen=True)
class VideoRecord:
    uuid: str
    title: str
    video_path: str | None
    mp3_path: str | None
    source: str
    duration: int | None
    status: str
    created_at: str


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path) -> None:
    """建库建表并开启 WAL。应用启动时调用一次。"""
    with _connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(_SCHEMA)


def insert_video(db_path: Path, uuid: str, title: str, video_path: str, source: str) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO videos (uuid, title, video_path, source) VALUES (?, ?, ?, ?)",
            (uuid, title, video_path, source),
        )


def update_status(
    db_path: Path,
    uuid: str,
    status: str,
    mp3_path: str | None = None,
    duration: int | None = None,
) -> None:
    """更新状态；记录不存在时静默跳过（并发扫描下的容忍）。"""
    sets: list[str] = ["status = ?"]
    params: list[object] = [status]
    if mp3_path is not None:
        sets.append("mp3_path = ?")
        params.append(mp3_path)
    if duration is not None:
        sets.append("duration = ?")
        params.append(duration)
    params.append(uuid)
    with _connect(db_path) as conn:
        conn.execute(f"UPDATE videos SET {', '.join(sets)} WHERE uuid = ?", params)


def list_videos(db_path: Path) -> list[VideoRecord]:
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM videos ORDER BY created_at DESC, uuid DESC").fetchall()
    return [VideoRecord(**dict(r)) for r in rows]
