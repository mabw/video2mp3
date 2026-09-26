"""把多尺寸 PNG 合成 Windows ICO（Vista+ 的 PNG-in-ICO 格式）。

用法：uv run python scripts/make_ico.py
输入：assets/icon{256,64,32,16}.png（由 assets/icon.svg 经 qlmanage/sips 生成）
输出：assets/icon.ico（PyInstaller --icon 与快捷方式用）
"""
import struct
from pathlib import Path


def _png_size(data: bytes) -> tuple[int, int]:
    """从 PNG 的 IHDR 块读取宽高（字节 16-24）。"""
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def make_ico(png_paths: list[Path], out: Path) -> None:
    images = [p.read_bytes() for p in png_paths]
    count = len(images)
    header = struct.pack("<HHH", 0, 1, count)  # 保留位、类型 1（图标）、数量
    entries = b""
    offset = 6 + 16 * count  # ICONDIR + 各 ICONDIRENTRY 之后是首个图像数据
    blobs = b""
    for data in images:
        w, h = _png_size(data)
        # 宽高字节（256 记为 0）、色板 0、保留 0、平面 1、位深 32、大小、偏移
        entries += struct.pack("<BBBBHHII", w % 256, h % 256, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    out.write_bytes(header + entries + blobs)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    srcs = [root / f"assets/icon{s}.png" for s in (256, 64, 32, 16)]
    make_ico(srcs, root / "assets/icon.ico")
    print(f"OK: {root / 'assets/icon.ico'}")
