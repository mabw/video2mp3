# 视频管家

适老化单机工具：微信/抖音视频 → MP3（唱戏机规格）→ U 盘。设计文档见
`docs/superpowers/specs/2026-09-26-video2mp3-design.md`，实施计划见
`docs/superpowers/plans/2026-09-26-video2mp3.md`。

## 开发（macOS/Windows 通用）
    brew install ffmpeg yt-dlp   # mac；Windows 装 ffmpeg 并入 PATH
    uv sync
    uv run pytest                # 36 个测试（network/gui 默认跳过）
    uv run python -m app         # 启动界面

开发调试环境变量：`VIDEO2MP3_HOME`（数据目录）、`VIDEO2MP3_USB_DIR`
（模拟 U 盘目录）、`VIDEO2MP3_FFMPEG`/`VIDEO2MP3_YTDLP`（外部工具路径）。

真实抖音下载冒烟：把 `tests/test_douyin_network.py` 的占位链接换成真实
分享短链后 `uv run pytest -m network tests/test_douyin_network.py`。

## 打包发布

**方式一：GitHub Actions（推荐，无需本地 Windows）**
Actions → ci → Run workflow（或推一个 `v*` tag）→ 构建完成后在该 run 的
Artifacts 下载 `shipinguanjia-win64`，解压即完整发行目录。

**方式二：本地 Windows 虚拟机**
1. 项目根备好 `yt-dlp.exe`（官方 Releases）与 `ffmpeg-win64-gpl.zip`
   （BtbN FFmpeg-Builds）；脚本会自动解压 ffmpeg.exe
2. `powershell scripts/build_windows.ps1`
3. `dist\视频管家\` 整目录拷到老人电脑，右键 exe 发送到桌面快捷方式

装机：首次运行如遇 Defender 提示：右键 → 属性 → 解除锁定 / "仍要运行"。

## 抖音 cookies（自动 + 手动两档）

抖音风控要求下载方持有新鲜 cookies（**无需登录账号**）。软件自动解析来源：

1. **自动（推荐，零配置）**：数据根无 `cookies.txt` 时，自动探测本机浏览器
   （Edge → Chrome → Firefox，轻量模拟解析验证），可用者记住（数据根
   `cookies_source`），失败自动清记忆重探。前提：该浏览器访问过 douyin.com
   ——装机时用老人电脑的 Edge 打开一次抖音网页即可。
2. **手动（后备）**：插件（如 "Get cookies.txt LOCALLY"）导出 douyin.com
   cookies，改名 `cookies.txt` 放数据根（`C:\视频管家\`）——存在即优先。

两档都失败时抖音链接提示失败，走微信兜底（手机抖音 分享 → 微信发送 →
电脑另存为收件箱），功能不受影响。

## 老人使用（装机时教学一次）
- 视频：微信里另存到「收件箱」（桌面放收件箱快捷方式），或直接拖进软件窗口
- 抖音：手机复制链接 → 切到软件（自动填入）→ 点【下载】
- 听歌：插 U 盘 → 勾选 → 【发送到 U 盘】→ 看到"可以安全拔出"再拔
- 不要的歌：【整理 U 盘内容】勾选删除（电脑上的不受影响）

## 数据位置
Windows 上自动选择：**优先非系统盘的固定硬盘**（如 `D:\视频管家\`，避开
C 盘），没有其他硬盘时才用系统盘；其他平台 `~/.video2mp3/`。

更改位置（两种方式）：
- **界面设置**：主界面右下角「设置」→ 选目录 → 确认 → 重启软件生效
  （写入程序旁的 `数据目录.txt`）
- **手动**：在软件文件夹里新建 `数据目录.txt`，内容写一行目标路径
  （如 `D:\视频库`），重启生效

优先级：`VIDEO2MP3_HOME` 环境变量 > `数据目录.txt` > 自动选址。
数据目录含：收件箱/video/mp3/library.db/logs/app.log。
