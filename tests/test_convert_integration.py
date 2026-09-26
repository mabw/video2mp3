"""转换集成测试：真 ffmpeg 产线，守护唱戏机规格。"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.convert import convert_video, probe_duration
from app.db import init_db, list_videos
from app.inbox import intake_file

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
pytestmark = pytest.mark.skipif(
    FFMPEG is None or FFPROBE is None, reason="本机无 ffmpeg（brew install ffmpeg）"
)
if FFMPEG is None or FFPROBE is None:
    pytest.skip("本机无 ffmpeg", allow_module_level=True)
assert FFMPEG is not None and FFPROBE is not None  # 类型窄化（skip 路径到此为止）


def _make_test_video(dest: Path, seconds: int = 3) -> Path:
    """用 lavfi 现场生成带音轨的测试视频。"""
    subprocess.run(
        [
            FFMPEG, "-y",
            "-f", "lavfi", "-i", f"testsrc=duration={seconds}:size=320x240:rate=15",
            "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(dest),
        ],
        check=True, capture_output=True,
    )
    return dest


def test_probe_duration_returns_seconds(tmp_path):
    v = _make_test_video(tmp_path / "t.mp4")
    assert abs(probe_duration(v) - 3.0) < 0.5


def test_convert_video_produces_spec_compliant_mp3(layout):
    init_db(layout.db_path)
    src = _make_test_video(layout.inbox / "t.mp4")
    uid = intake_file(layout, src, source="manual")

    ok = convert_video(layout, uid)
    assert ok is True

    mp3 = layout.mp3 / f"{uid}.mp3"
    assert mp3.exists()

    # 规格守护：对照实测样本（44.1kHz / stereo / ~128kbps / 无 ID3 头）
    assert mp3.read_bytes()[:3] != b"ID3", "不应写 ID3v2 标签"
    info = json.loads(
        subprocess.run(
            [FFPROBE, "-v", "quiet", "-show_streams", "-show_format",
             "-of", "json", str(mp3)],
            check=True, capture_output=True, text=True,
        ).stdout
    )
    stream = info["streams"][0]
    assert stream["codec_name"] == "mp3"
    assert stream["sample_rate"] == "44100"
    assert stream["channels"] == 2
    assert abs(int(stream["bit_rate"]) - 128000) < 8000

    rows = list_videos(layout.db_path)
    assert rows[0].status == "done"
    assert rows[0].mp3_path == str(mp3)
    assert rows[0].duration is not None and rows[0].duration > 0


def test_convert_video_marks_failed_on_bad_input(layout):
    init_db(layout.db_path)
    bad = layout.inbox / "bad.mp4"
    bad.write_bytes(b"not a video")
    uid = intake_file(layout, bad, source="manual")

    ok = convert_video(layout, uid)
    assert ok is False
    assert list_videos(layout.db_path)[0].status == "failed"
    assert not (layout.mp3 / f"{uid}.mp3").exists()
