"""转换：命令构造与外部二进制定位。"""
import pytest

from app.convert import build_ffmpeg_args, find_tool


def test_build_ffmpeg_args_matches_spec(tmp_path):
    src = tmp_path / "u1.mp4"
    dst = tmp_path / "u1.mp3"
    args = build_ffmpeg_args(str(src), str(dst))
    assert args[0] == "-i"
    assert args[1] == str(src)  # 源文件紧跟 -i
    assert args[args.index(str(dst)) - 2:] == ["-b:a", "128k", str(dst)]


def test_build_ffmpeg_args_locks_codec_params(tmp_path):
    args = build_ffmpeg_args("a.mp4", "a.mp3")
    joined = " ".join(args)
    assert "-ar 44100" in joined
    assert "-ac 2" in joined
    assert "-write_id3v2 0" in joined
    assert "-vn" in joined


def test_find_tool_prefers_env(monkeypatch, tmp_path):
    fake = tmp_path / "ffmpeg.exe"
    fake.write_bytes(b"")
    monkeypatch.setenv("VIDEO2MP3_FFMPEG", str(fake))
    assert find_tool("FFMPEG", env_var="VIDEO2MP3_FFMPEG") == str(fake)


def test_find_tool_raises_when_missing(monkeypatch):
    monkeypatch.delenv("VIDEO2MP3_FFMPEG", raising=False)
    with pytest.raises(FileNotFoundError, match="VIDEO2MP3_FFMPEG"):
        find_tool("__no_such_tool__", env_var="VIDEO2MP3_FFMPEG")
