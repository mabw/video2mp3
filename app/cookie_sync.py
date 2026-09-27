"""本地 cookie 同步服务：接收浏览器扩展上报的抖音 cookies 并落盘。

扩展运行在浏览器内部，拿到的 cookie 是明文（含 httpOnly），绕开一切
读浏览器库的死结（DPAPI 应用绑定加密 / 文件锁 / 落盘延迟）。
写出的 Netscape 格式 cookies.txt 被 douyin._resolve_cookies_args 最优先使用。
"""
import http.server
import json
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

SYNC_PORT = 18642        # 扩展上报端口（仅绑定 127.0.0.1，不对外）
# 抖音风控所需的关键 cookie：上报数据至少含其一才落盘，挡掉空数据/垃圾请求
_REQUIRED_COOKIE_NAMES = ("ttwid", "msToken", "__ac_nonce", "__ac_signature")
_FAR_FUTURE = "2000000000"  # 永不过期的 expires 占位（Netscape 格式秒级时间戳）
# 落盘串行锁：扩展一个页面会分多波上报（并发请求），.part 临时名必须互斥使用
_WRITE_LOCK = threading.Lock()


def to_netscape(cookies: list[dict]) -> str:
    """把扩展上报的 cookie 列表转成 yt-dlp 认的 Netscape 格式。纯函数便于单测。"""
    lines = ["# Netscape HTTP Cookie File", "# 由视频管家浏览器扩展自动更新"]
    for c in cookies:
        domain = c.get("domain", "")
        flag = "TRUE" if domain.startswith(".") else "FALSE"
        path = c.get("path", "/")
        secure = "TRUE" if c.get("secure") else "FALSE"
        expires = str(int(c["expirationDate"])) if c.get("expirationDate") else _FAR_FUTURE
        lines.append(
            f"{domain}\t{flag}\t{path}\t{secure}\t{expires}\t{c['name']}\t{c['value']}")
    return "\n".join(lines) + "\n"


def make_sync_server(cookies_file: Path, port: int = SYNC_PORT) -> http.server.HTTPServer:
    """构造绑定本机回环的同步服务：POST /cookies 收扩展上报并原子落盘。

    port=0 时由系统随机分配（测试用，避免与正在运行的软件实例抢固定端口）。
    安全校验：只接受 Origin 为 chrome-extension:// 的请求——浏览器强制网页
    无法伪造 Origin 头，因此任意网页都写不进来，只有装了扩展的浏览器可以。
    """
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # http.server 基类接口命名
            origin = self.headers.get("Origin", "")
            if self.path != "/cookies" or not origin.startswith("chrome-extension://"):
                self.send_response(403)
                self.end_headers()
                return
            try:
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                cookies = json.loads(body)
                if not any(c.get("name") in _REQUIRED_COOKIE_NAMES for c in cookies):
                    self.send_response(422)  # 没有关键 cookie：不落盘
                    self.end_headers()
                    return
                with _WRITE_LOCK:
                    tmp = cookies_file.with_name(cookies_file.name + ".part")
                    tmp.write_text(to_netscape(cookies), encoding="utf-8")
                    tmp.replace(cookies_file)
                logger.info("[cookie_sync] 收到扩展上报 %d 条 cookie，已落盘", len(cookies))
                self.send_response(204)
            except (ValueError, OSError, KeyError) as exc:
                logger.warning("[cookie_sync] 上报处理失败: %s", exc)
                self.send_response(400)
            self.end_headers()

        def log_message(self, format: str, *args) -> None:  # 基类签名约定
            pass  # 静默常规访问日志，失败已单独落日志

    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    return server


def start_sync_server(cookies_file: Path) -> http.server.HTTPServer | None:
    """启动同步服务（daemon 线程）。端口被占（重复启动）返回 None，不影响主程序。"""
    try:
        server = make_sync_server(cookies_file)
    except OSError:
        logger.warning("[cookie_sync] 端口 %d 已被占用，跳过启动", SYNC_PORT)
        return None
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logger.info("[cookie_sync] 监听 127.0.0.1:%d，等待浏览器扩展上报", SYNC_PORT)
    return server
