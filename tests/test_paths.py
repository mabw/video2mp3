"""Layout 目录约定测试。"""
import sys
from pathlib import Path

from app.paths import Layout, default_layout


def test_create_builds_all_dirs(tmp_path):
    layout = Layout.create(tmp_path)
    assert layout.inbox.is_dir()
    assert layout.video.is_dir()
    assert layout.mp3.is_dir()
    assert layout.logs.is_dir()
    assert layout.db_path.parent.is_dir()
    assert layout.inbox == tmp_path / "收件箱"


def test_default_layout_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO2MP3_HOME", str(tmp_path))
    layout = default_layout()
    assert layout.root == tmp_path


def test_default_layout_win32_branch(tmp_path, monkeypatch):
    # win32 分支在 mac 上会把 D:/ 视为相对路径，chdir 进 tmp 防止污染工作区
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("VIDEO2MP3_HOME", raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("SYSTEMDRIVE", "D:")
    layout = default_layout()
    assert layout.root == Path("D:/视频管家")


def test_default_layout_posix_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv("VIDEO2MP3_HOME", raising=False)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    layout = default_layout()
    assert layout.root == tmp_path / ".video2mp3"
