"""Layout 目录约定测试。"""
import sys
from pathlib import Path

from app.paths import Layout, _configured_home, default_layout


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


def test_configured_home_file(tmp_path):
    cfg = tmp_path / "数据目录.txt"
    cfg.write_text("D:\\我的视频库\n", encoding="utf-8")
    assert _configured_home(cfg) == Path("D:\\我的视频库")
    cfg.write_bytes("\ufeffD:/x\n".encode("utf-8"))  # 记事本 BOM 容忍
    assert _configured_home(cfg) == Path("D:/x")
    cfg.write_text("   \n", encoding="utf-8")  # 空白内容视为未配置
    assert _configured_home(cfg) is None
    assert _configured_home(tmp_path / "不存在.txt") is None


def test_write_configured_home_roundtrip(tmp_path):
    from app.paths import write_configured_home

    cfg = tmp_path / "数据目录.txt"
    write_configured_home(Path("E:/视频库"), cfg_file=cfg)
    assert cfg.read_text(encoding="utf-8") == "E:/视频库\n"
    assert _configured_home(cfg) == Path("E:/视频库")  # 写读一致


def test_default_layout_config_file_wins(tmp_path, monkeypatch):
    monkeypatch.delenv("VIDEO2MP3_HOME", raising=False)
    cfg = tmp_path / "数据目录.txt"
    cfg.write_text(str(tmp_path / "数据区"), encoding="utf-8")
    layout = default_layout(cfg_file=cfg)
    assert layout.root == tmp_path / "数据区"


def _win32_env(monkeypatch, tmp_path, fixed_drives, system_drive):
    monkeypatch.chdir(tmp_path)  # 防止相对盘符路径污染工作区
    monkeypatch.delenv("VIDEO2MP3_HOME", raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("SYSTEMDRIVE", system_drive)
    from app import platform as plat

    monkeypatch.setattr(plat, "get_fixed_drives", lambda: fixed_drives)


def test_default_layout_win32_prefers_non_system_drive(tmp_path, monkeypatch):
    _win32_env(monkeypatch, tmp_path, ["C:", "D:", "E:"], "C:")
    assert default_layout().root == Path("D:/视频管家")  # 第一个非系统固定盘


def test_default_layout_win32_falls_back_to_system_drive(tmp_path, monkeypatch):
    _win32_env(monkeypatch, tmp_path, ["C:"], "C:")
    assert default_layout().root == Path("C:/视频管家")  # 无非系统盘才退回


def test_default_layout_posix_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv("VIDEO2MP3_HOME", raising=False)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    layout = default_layout()
    assert layout.root == tmp_path / ".video2mp3"
