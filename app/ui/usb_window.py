"""整理 U 盘二级窗口：查看盘内歌曲、勾选删除（只动 U 盘，不动本地库）。"""
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import messagebox, ttk

from app.paths import Layout
from app.ui import style
from app.usb import delete_files, match_usb_items


def open_usb_window(
    parent: tk.Misc, layout: Layout, usb_root: Path, on_changed: Callable[[], None]
) -> None:
    win = tk.Toplevel(parent)
    win.title("U 盘里的音乐")
    win.geometry("680x560")
    win.configure(bg=style.COLOR_BG)

    tk.Label(win, text="勾选不要的歌，点删除", font=style.FONT_BODY,
             bg=style.COLOR_BG).pack(anchor="w", padx=16, pady=(16, 8))

    # 滚动列表：Canvas 承载行容器，行数多时靠竖滚动条翻页
    container = tk.Frame(win, bg=style.COLOR_BG)
    container.pack(fill="both", expand=True, padx=16)
    canvas = tk.Canvas(container, bg=style.COLOR_BG, highlightthickness=0)
    scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
    rows = tk.Frame(canvas, bg=style.COLOR_BG)
    rows.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=rows, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # 盘内 mp3 与本地库匹配：命中显示标题和时长，外来文件显示文件名并标注
    items = match_usb_items(usb_root, layout)
    vars_list: list[tk.BooleanVar] = []
    for i, item in enumerate(items):
        row_bg = style.COLOR_ROW_ALT if i % 2 else style.COLOR_BG
        row = tk.Frame(rows, bg=row_bg)
        row.pack(fill="x", pady=2)
        var = tk.BooleanVar(value=False)
        vars_list.append(var)
        tk.Checkbutton(row, variable=var, bg=row_bg).pack(side="left", padx=(8, 0))
        duration = f"{item.duration // 60}分{item.duration % 60}秒" if item.duration else ""
        title = style.shorten_title(item.title)  # 长标题截断，防行内布局位移
        text = f"{title}（{duration}）" if duration else title
        if not item.in_library:
            text += "  （不是视频管家传的）"
        tk.Label(row, text=text, font=style.FONT_BODY, bg=row_bg).pack(
            side="left", padx=8, pady=12)

    # 两个回调须在按钮创建前定义：command=on_delete 在构造时即取值
    def count_checked(*_) -> None:
        n = sum(v.get() for v in vars_list)
        del_btn.config(text=f"🗑 删除所选（{n} 首）")

    def on_delete() -> None:
        chosen = [it.path for it, v in zip(items, vars_list) if v.get()]
        if not chosen:
            messagebox.showinfo("提示", "请先勾选要删除的歌", parent=win)
            return
        if not messagebox.askyesno(
            "确认删除",
            f"确定删除 U 盘里的 {len(chosen)} 首歌吗？\n电脑上的还留着。",
            parent=win,
        ):
            return
        delete_files(chosen)
        on_changed()  # 通知主窗口刷新列表（已在U盘状态会变）
        win.destroy()

    btns = tk.Frame(win, bg=style.COLOR_BG)
    btns.pack(fill="x", padx=16, pady=16)

    del_btn = tk.Button(btns, text="🗑 删除所选（0 首）", font=style.FONT_BUTTON,
                        bg=style.COLOR_DELETE, fg="white", command=on_delete)
    del_btn.pack(side="left", ipadx=24, ipady=12, expand=True, fill="x")
    tk.Button(btns, text="完成", font=style.FONT_BUTTON, bg=style.COLOR_MANAGE,
              fg="white", command=win.destroy).pack(side="left", padx=(12, 0),
                                                    ipadx=24, ipady=12, expand=True, fill="x")

    # 勾选变化时同步删除按钮上的计数
    for v in vars_list:
        v.trace_add("write", count_checked)
