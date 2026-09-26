"""主窗口：链接下载区、视频清单、U 盘状态栏、发送/整理按钮。"""
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from app import platform as plat
from app.convert import convert_video
from app.db import list_videos
from app.douyin import download_video, extract_douyin_url
from app.inbox import intake_file, scan_inbox
from app.paths import Layout, asset_path
from app.ui import style
from app.ui.usb_window import open_usb_window
from app.usb import check_free_space, send_one, usb_uuids

CLIPBOARD_POLL_MS = 2000  # 剪贴板轮询间隔
USB_POLL_MS = 3000        # U 盘轮询间隔
INBOX_POLL_MS = 5000      # 收件箱轮询间隔（软件常开时新存入的视频也要被发现）
QUEUE_POLL_MS = 200       # 后台事件出队间隔


class MainWindow:
    def __init__(self, layout: Layout) -> None:
        self.layout = layout
        self.events: queue.Queue = queue.Queue()
        self.usb_root: Path | None = None
        self.check_vars: dict[str, tk.BooleanVar] = {}
        self._inbox_scanning = False  # 防止收件箱扫描线程重叠

        self.root = tk.Tk()
        self.root.title("视频管家")
        self.root.geometry("980x720")
        self.root.configure(bg=style.COLOR_BG)
        try:
            self._icon = tk.PhotoImage(file=str(asset_path("icon.png")))
            self.root.iconphoto(True, self._icon)
        except tk.TclError:
            pass  # 资源缺失不阻断启动

        self._build_link_area()
        self._build_list_area()
        self._build_usb_area()

        plat.hook_drop_files(self.root, self._on_drop_files)

        self.root.after(QUEUE_POLL_MS, self._drain_events)
        self.root.after(CLIPBOARD_POLL_MS, self._poll_clipboard)
        self.root.after(USB_POLL_MS, self._poll_usb)
        self.root.after(0, self._poll_inbox)  # 首轮立即扫（含启动时已在收件箱的文件）

    # ---------- 界面构建 ----------

    def _build_link_area(self) -> None:
        frame = tk.Frame(self.root, bg=style.COLOR_BG)
        frame.pack(fill="x", padx=16, pady=(16, 8))
        self.link_var = tk.StringVar()
        entry = tk.Entry(frame, textvariable=self.link_var, font=style.FONT_BODY, width=42)
        entry.pack(side="left", fill="x", expand=True, ipady=10)
        btn = tk.Button(frame, text="下载", font=style.FONT_BUTTON,
                        bg=style.COLOR_PRIMARY, fg="white", command=self._on_download)
        btn.pack(side="left", padx=(12, 0), ipadx=24, ipady=10)

    def _build_list_area(self) -> None:
        header = tk.Frame(self.root, bg=style.COLOR_BG)
        header.pack(fill="x", padx=16)
        tk.Label(header, text="我的视频", font=style.FONT_BODY,
                 bg=style.COLOR_BG).pack(side="left")
        self.pending_label = tk.Label(header, text="", font=style.FONT_STATUS,
                                      bg=style.COLOR_BG, fg="#555555")
        self.pending_label.pack(side="right")

        container = tk.Frame(self.root, bg=style.COLOR_BG)
        container.pack(fill="both", expand=True, padx=16, pady=8)
        self.canvas = tk.Canvas(container, bg=style.COLOR_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.rows_frame = tk.Frame(self.canvas, bg=style.COLOR_BG)
        self.rows_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.create_window((0, 0), window=self.rows_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _build_usb_area(self) -> None:
        frame = tk.Frame(self.root, bg=style.COLOR_BG)
        frame.pack(fill="x", padx=16, pady=(8, 16))
        self.usb_var = tk.StringVar(value="请把 U 盘插上")
        tk.Label(frame, textvariable=self.usb_var, font=style.FONT_BODY,
                 bg=style.COLOR_BG).pack(anchor="w")
        btns = tk.Frame(frame, bg=style.COLOR_BG)
        btns.pack(fill="x", pady=(10, 0))
        self.send_btn = tk.Button(btns, text="发送到 U 盘", font=style.FONT_BUTTON,
                                  bg=style.COLOR_SEND, fg="white", command=self._on_send)
        self.send_btn.pack(side="left", ipadx=28, ipady=12, expand=True, fill="x")
        tk.Button(btns, text="整理 U 盘内容", font=style.FONT_BUTTON,
                  bg=style.COLOR_MANAGE, fg="white",
                  command=self._on_manage).pack(side="left", padx=(12, 0),
                                                ipadx=28, ipady=12, expand=True, fill="x")

    # ---------- 清单渲染 ----------

    def _refresh_list(self) -> None:
        for w in self.rows_frame.winfo_children():
            w.destroy()
        records = list_videos(self.layout.db_path)
        on_usb = usb_uuids(self.usb_root) if self.usb_root else set()
        pending = [r for r in records if r.status == "done" and r.uuid not in on_usb]
        self.pending_label.config(text=f"待传 U 盘：{len(pending)} 个")
        self.send_btn.config(text=f"发送到 U 盘（{len(pending)} 个）")
        self.check_vars = {}
        for i, rec in enumerate(records):
            self._build_row(i, rec, rec.uuid in on_usb)

    def _build_row(self, i: int, rec, on_usb: bool) -> None:
        row = tk.Frame(self.rows_frame, bg=style.COLOR_ROW_ALT if i % 2 else style.COLOR_BG)
        row.pack(fill="x", pady=2)
        var = tk.BooleanVar(value=bool(rec.status == "done" and not on_usb))
        self.check_vars[rec.uuid] = var
        tk.Checkbutton(row, variable=var, bg=row["bg"]).pack(side="left", padx=(8, 0))
        duration = f"{rec.duration // 60}分{rec.duration % 60}秒" if rec.duration else ""
        status = "✓已在U盘" if on_usb else {"pending": "等待中…", "converting": "转换中…",
                                             "failed": "❌转换失败", "done": ""}.get(rec.status, "")
        text = f"{rec.title}（{duration}）" if duration else rec.title
        color = style.COLOR_DISABLED if on_usb else style.COLOR_TEXT
        tk.Label(row, text=f"{text}  {status}", font=style.FONT_BODY, bg=row["bg"],
                 fg=color).pack(side="left", padx=8, pady=12)
        if rec.status == "done":
            tk.Button(row, text="▶看视频", font=style.FONT_STATUS,
                      command=lambda p=rec.video_path or "": plat.play_media(Path(p))
                      ).pack(side="right", padx=4, ipady=8)
            tk.Button(row, text="♪听音乐", font=style.FONT_STATUS,
                      command=lambda p=rec.mp3_path or "": plat.play_media(Path(p))
                      ).pack(side="right", padx=4, ipady=8)
        if rec.status == "failed":
            tk.Button(row, text="重试", font=style.FONT_STATUS,
                      command=lambda u=rec.uuid: self._start_conversion(u)
                      ).pack(side="right", padx=4, ipady=8)

    # ---------- 后台管线 ----------

    def _poll_inbox(self) -> None:
        """周期扫描收件箱（后台线程，防重叠）：软件常开时新另存为的视频也能被发现。"""
        if not self._inbox_scanning:
            self._inbox_scanning = True

            def work():
                try:
                    uuids = scan_inbox(self.layout)
                    for uid in uuids:
                        self.events.put(("convert", uid))
                    if uuids:
                        self.events.put(("refresh", None))
                finally:
                    self._inbox_scanning = False
            threading.Thread(target=work, daemon=True).start()
        self.root.after(INBOX_POLL_MS, self._poll_inbox)

    def _start_conversion(self, uid: str) -> None:
        def work():
            convert_video(self.layout, uid)
            self.events.put(("refresh", None))
        threading.Thread(target=work, daemon=True).start()

    def _drain_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "convert":
                    self._start_conversion(payload)
                elif kind == "refresh":
                    self._refresh_list()
                elif kind == "sent":
                    self.send_btn.config(state="normal")
                    self._refresh_list()
                    messagebox.showinfo("发送", payload, parent=self.root)
                elif kind == "error":
                    # 失败路径没有 "sent" 事件，这里同样要在 UI 线程恢复按钮
                    self.send_btn.config(state="normal")
                    messagebox.showerror("出错了", payload, parent=self.root)
        except queue.Empty:
            pass
        self.root.after(QUEUE_POLL_MS, self._drain_events)

    # ---------- 交互 ----------

    def _on_drop_files(self, files) -> None:
        for f in files:
            p = Path(f.decode("gbk") if isinstance(f, bytes) else f)
            if p.suffix.lower() in (".mp4", ".mov", ".mkv"):
                uid = intake_file(self.layout, p, source="manual")
                self.events.put(("convert", uid))
        self._refresh_list()

    def _poll_clipboard(self) -> None:
        try:
            text = self.root.clipboard_get()
        except tk.TclError:
            text = ""
        url = extract_douyin_url(text)
        if url and self.link_var.get().strip() != url:
            self.link_var.set(url)
            self.pending_label.config(text="已检测到抖音链接，点【下载】")
        self.root.after(CLIPBOARD_POLL_MS, self._poll_clipboard)

    def _on_download(self) -> None:
        url = extract_douyin_url(self.link_var.get())
        if not url:
            messagebox.showinfo("提示", "请先复制抖音链接，再点【下载】", parent=self.root)
            return
        self.link_var.set("")
        self.pending_label.config(text="正在下载，请稍候…")

        def work():
            try:
                path, title = download_video(url, self.layout.inbox,
                                             cookies_file=self.layout.root / "cookies.txt")
                uid = intake_file(self.layout, path, source="douyin", title=title)
                self.events.put(("convert", uid))
            except Exception:  # noqa: BLE001 -- UI 边界兜底：任何失败都转成人话提示
                self.events.put(
                    ("error", "这个链接下载失败了。\n请在手机上把视频保存后，用微信发到电脑上"))
            finally:
                self.events.put(("refresh", None))
        threading.Thread(target=work, daemon=True).start()

    def _poll_usb(self) -> None:
        root = plat.get_usb_root()
        if root != self.usb_root:
            self.usb_root = root
            drives = plat.get_usb_drives()
            if root is None and len(drives) > 1:
                names = "\n".join(f"{i + 1}. {d.display()}" for i, d in enumerate(drives))
                messagebox.showinfo("插了多个 U 盘", f"检测到多个 U 盘，请只保留一个：\n{names}",
                                    parent=self.root)
            self._refresh_list()
        if self.usb_root:
            import shutil
            try:
                free_gb = shutil.disk_usage(self.usb_root).free / 1024**3
            except OSError:  # env 调试目录被删等：视为已拔出，下轮轮询自愈
                self.usb_var.set("U 盘已拔出，请重新插上")
            else:
                drives = plat.get_usb_drives()
                label = drives[0].display() if drives else str(self.usb_root)
                self.usb_var.set(f"💾 U盘：{label}  剩余 {free_gb:.0f} GB")
        else:
            self.usb_var.set("请把 U 盘插上")
        self.root.after(USB_POLL_MS, self._poll_usb)

    def _on_send(self) -> None:
        if self.usb_root is None:
            messagebox.showinfo("提示", "请把 U 盘插上", parent=self.root)
            return
        usb_root = self.usb_root  # 固化窄化结果：嵌套函数内不能依赖外层的属性窄化
        chosen = [r for r in list_videos(self.layout.db_path)
                  if r.status == "done" and r.uuid in self.check_vars
                  and self.check_vars[r.uuid].get()]
        if not chosen:
            messagebox.showinfo("提示", "请先勾选要发送的视频", parent=self.root)
            return
        size_mb = sum(Path(r.mp3_path or "").stat().st_size for r in chosen) / 1024**2
        if not messagebox.askyesno(
            "确认发送", f"即将发送 {len(chosen)} 个，大约 {size_mb:.0f} MB。\n确定吗？",
            parent=self.root,
        ):
            return
        if not check_free_space(self.usb_root, [Path(r.mp3_path or "").stat().st_size
                                                for r in chosen]):
            messagebox.showwarning("空间不足", "U 盘装不下了，请先删掉一些再发",
                                   parent=self.root)
            return
        self.send_btn.config(state="disabled", text="正在发送…")

        def work():
            copied = skipped = 0
            try:
                for r in chosen:
                    result = send_one(Path(r.mp3_path or ""), usb_root)
                    copied += result == "copied"
                    skipped += result == "skipped"
            except Exception as exc:  # noqa: BLE001 -- UI 边界兜底：任何失败都转成人话提示
                self.events.put(("error", f"发送中断了：{exc}\n请重新插好 U 盘再试"))
            else:
                msg = f"✅ 发送成功，共 {copied} 个"
                if skipped:
                    msg += f"（{skipped} 个已在 U 盘，未重复发送）"
                msg += "\n现在可以安全拔出 U 盘了"
                self.events.put(("sent", msg))
            finally:
                self.events.put(("refresh", None))
        threading.Thread(target=work, daemon=True).start()

    def _on_manage(self) -> None:
        if self.usb_root is None:
            messagebox.showinfo("提示", "请把 U 盘插上", parent=self.root)
            return
        open_usb_window(self.root, self.layout, self.usb_root, on_changed=self._refresh_list)

    def run(self) -> None:
        self._refresh_list()
        self.root.mainloop()
