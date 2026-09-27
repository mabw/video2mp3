"""适老化视觉常量：大字号、高对比、白底黑字。"""
import sys

IS_WIN = sys.platform == "win32"

# Windows 用微软雅黑，mac 开发回退苹方
FONT_FAMILY = "Microsoft YaHei UI" if IS_WIN else "PingFang SC"

FONT_BODY = (FONT_FAMILY, 18)            # 正文
FONT_BUTTON = (FONT_FAMILY, 22, "bold")  # 按钮
FONT_STATUS = (FONT_FAMILY, 16)          # 状态小字

COLOR_BG = "#ffffff"
COLOR_TEXT = "#000000"
COLOR_PRIMARY = "#1a7f37"   # 下载（绿）
COLOR_SEND = "#d97706"      # 发送 U 盘（橙）
COLOR_MANAGE = "#4a5568"    # 整理 U 盘（灰蓝）
COLOR_DISABLED = "#9aa0a6"  # 已在 U 盘
COLOR_ROW_ALT = "#f5f7fa"   # 隔行底色
COLOR_DELETE = "#c0392b"    # 删除（红），主窗口行按钮与 U 盘窗口共用
