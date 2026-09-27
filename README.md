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

## 抖音 cookies（浏览器扩展自动同步）

抖音风控要求下载方持有新鲜 cookies（**无需登录账号**）。软件不读浏览器的
cookie 数据库（Edge/Chrome 新版加密后第三方读不出），而是由**配套浏览器
扩展**直接在浏览器内部拿到明文 cookie 同步给软件——无加密、无文件锁问题。

**装机时装一次扩展（子女操作，约一分钟）：**
1. Release 页下载 `douyin-cookie-extension.zip` 并解压（得到一个文件夹）
2. Edge 打开 `edge://extensions`（Chrome 则 `chrome://extensions`）
3. 右上角打开「开发人员模式」→ 点「加载解压缩的扩展」→ 选刚才的文件夹
4. 装好后用浏览器打开一次 douyin.com，看到扩展工作即成功

装好后全自动：cookie 由扩展落盘到数据根 `cookies.txt`；失效时软件自动
弹出抖音页面触发扩展刷新后重试，无需任何人工操作。

未装扩展时抖音链接下载会失败并提示，走微信兜底（手机抖音 分享 → 微信
发送 → 电脑另存为收件箱），其余功能不受影响。

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
