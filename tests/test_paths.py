"""Layout 目录约定测试。"""
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
