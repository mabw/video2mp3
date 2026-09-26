"""真实抖音下载冒烟（默认跳过，手动跑：uv run pytest -m network tests/test_douyin_network.py）。"""
import pytest

from app.douyin import download_video

pytestmark = pytest.mark.network


def test_real_download(layout):
    # 换成任意真实的抖音分享短链后手动运行
    path = download_video("https://v.douyin.com/_REPLACE_ME_/", layout.inbox)
    assert path.exists() and path.stat().st_size > 100_000
