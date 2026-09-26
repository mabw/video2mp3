"""平台适配层：可跨平台测试的部分。"""
import sys

import pytest

from app import platform as plat


def test_get_usb_root_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO2MP3_USB_DIR", str(tmp_path))
    assert plat.get_usb_root() == tmp_path


def test_usb_drive_dataclass():
    d = plat.UsbDrive(volume_label="金士顿", drive="E:", free_bytes=1024)
    assert d.display() == "金士顿 (E:)"


@pytest.mark.skipif(sys.platform == "win32", reason="验证 mac 分支的 open 命令构造")
def test_play_media_mac_uses_open(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(plat.subprocess, "run", lambda cmd, check: calls.append((cmd, check)))
    plat.play_media(tmp_path / "a.mp3")
    assert calls == [(["open", str(tmp_path / "a.mp3")], False)]
