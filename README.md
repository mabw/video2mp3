# 视频管家

适老化单机工具：微信/抖音视频 → MP3（唱戏机规格）→ U 盘。设计文档见
`docs/superpowers/specs/2026-09-26-video2mp3-design.md`，实施计划见
`docs/superpowers/plans/2026-09-26-video2mp3.md`。

## 开发（macOS/Windows 通用）
    brew install ffmpeg yt-dlp   # mac；Windows 装 ffmpeg 并入 PATH
    uv sync
    uv run pytest                # 34 个测试（network/gui 默认跳过）
    uv run python -m app         # 启动界面

开发调试环境变量：`VIDEO2MP3_HOME`（数据目录）、`VIDEO2MP3_USB_DIR`
（模拟 U 盘目录）、`VIDEO2MP3_FFMPEG`/`VIDEO2MP3_YTDLP`（外部工具路径）。

真实抖音下载冒烟：把 `tests/test_douyin_network.py` 的占位链接换成真实
分享短链后 `uv run pytest -m network tests/test_douyin_network.py`。

## 打包发布（Windows 虚拟机）
1. 项目根备好 `yt-dlp.exe`（官方 Releases）与 `ffmpeg-win64-gpl.zip`
   （BtbN FFmpeg-Builds）；脚本会自动解压 ffmpeg.exe
2. `powershell scripts/build_windows.ps1`
3. `dist\视频管家\` 整目录拷到老人电脑，右键 exe 发送到桌面快捷方式
4. 首次运行如遇 Defender 提示：右键 → 属性 → 解除锁定 / "仍要运行"

## 老人使用（装机时教学一次）
- 视频：微信里另存到「收件箱」（桌面放收件箱快捷方式），或直接拖进软件窗口
- 抖音：手机复制链接 → 切到软件（自动填入）→ 点【下载】
- 听歌：插 U 盘 → 勾选 → 【发送到 U 盘】→ 看到"可以安全拔出"再拔
- 不要的歌：【整理 U 盘内容】勾选删除（电脑上的不受影响）

## 数据位置
Windows：`C:\视频管家\`（收件箱/video/mp3/library.db/logs）；
其他平台：`~/.video2mp3/`。
