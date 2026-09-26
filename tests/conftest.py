"""共享 fixture：可注入的数据目录布局。"""
from pathlib import Path

import pytest

from app.paths import Layout


@pytest.fixture
def layout(tmp_path: Path) -> Layout:
    """临时目录布局，隔离测试与真实数据。"""
    return Layout.create(tmp_path)
