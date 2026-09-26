"""应用入口：python -m app / 双击快捷方式。"""
import os
import sys
from pathlib import Path


def _fix_tcl_for_dev_python() -> None:
    """mac 开发环境：uv 的 python-build-standalone 需显式定位 tcl/tk 数据目录。

    编译期路径（/tools/deps）在运行时失配导致 init.tcl 找不到；Windows 正式
    运行使用打包自带的 Tk，不受影响。必须在 import tkinter 之前调用。
    """
    if sys.platform == "win32":
        return
    base = Path(sys.base_prefix)
    for var, sub in (("TCL_LIBRARY", "tcl8.6"), ("TK_LIBRARY", "tk8.6")):
        if var not in os.environ:
            path = base / "lib" / sub
            if path.is_dir():
                os.environ[var] = str(path)


def _install_excepthooks() -> None:
    """未捕获异常落日志（windowed 打包无控制台，stderr 全丢，spec 承诺堆栈留底）。"""
    import logging
    import threading

    logger = logging.getLogger("crash")

    def sys_hook(tp, val, tb) -> None:
        logger.exception("未捕获异常", exc_info=(tp, val, tb))

    def thread_hook(args) -> None:
        logger.error("线程未捕获异常 @%s: %s", args.thread.name, args.exc_value)

    sys.excepthook = sys_hook
    threading.excepthook = thread_hook


def main() -> None:
    _fix_tcl_for_dev_python()
    import logging

    from app.db import init_db
    from app.paths import default_layout
    from app.ui.main_window import MainWindow

    layout = default_layout()
    init_db(layout.db_path)
    # 日志落盘：打包版无控制台，stderr 输出会全部丢失（spec 承诺 logs/app.log）
    logging.basicConfig(
        filename=layout.logs / "app.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    _install_excepthooks()
    MainWindow(layout).run()


if __name__ == "__main__":
    main()
