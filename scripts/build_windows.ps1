# scripts/build_windows.ps1 —— 在 Windows 虚拟机上运行：产出 dist\视频管家\
# 前置：项目根有 yt-dlp.exe 与 ffmpeg-win64-gpl.zip（或已解压的 ffmpeg.exe）
if (-not (Test-Path "ffmpeg.exe")) {
  Expand-Archive -Path ffmpeg-win64-gpl.zip -DestinationPath _fftmp -Force
  Copy-Item "_fftmp/ffmpeg-master-latest-win64-gpl/bin/ffmpeg.exe" "."
  Remove-Item -Recurse -Force _fftmp
}
if (-not (Test-Path "yt-dlp.exe")) { Write-Error "缺少 yt-dlp.exe"; exit 1 }
if (-not (Test-Path "assets/icon.ico")) { Write-Error "缺少 assets/icon.ico"; exit 1 }

uv sync --dev
uv pip install pyinstaller
uv run pyinstaller --noconfirm --clean --onedir --windowed `
  --name "视频管家" `
  --icon "assets/icon.ico" `
  --add-binary "ffmpeg.exe;." `
  --add-binary "yt-dlp.exe;." `
  --add-data "assets;assets" `
  --collect-all windnd `
  run_build.py
Write-Host "完成：dist\视频管家\ —— 整个目录拷给老人电脑，桌面快捷方式指向 视频管家.exe"
