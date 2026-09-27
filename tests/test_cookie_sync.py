"""本地 cookie 同步服务：Netscape 转换与上报安全校验。"""
import json
import urllib.error
import urllib.request

from app.cookie_sync import make_sync_server, to_netscape


def test_to_netscape_format():
    """Netscape 七列制表符分隔；过期时间缺省用远期占位。"""
    cookies = [
        {"domain": ".douyin.com", "path": "/", "secure": True,
         "name": "ttwid", "value": "abc"},
        {"domain": "douyin.com", "path": "/", "secure": False,
         "expirationDate": 1800000000, "name": "msToken", "value": "x y"},
    ]
    text = to_netscape(cookies)
    lines = text.strip().splitlines()
    assert lines[0].startswith("# Netscape")
    row = lines[2].split("\t")
    assert row == [".douyin.com", "TRUE", "/", "TRUE", "2000000000", "ttwid", "abc"]
    assert lines[3].split("\t")[4] == "1800000000"


def _post(server, body: bytes, origin: str) -> int:
    """向同步服务发一次 POST，返回状态码。"""
    from app.cookie_sync import SYNC_PORT
    req = urllib.request.Request(
        f"http://127.0.0.1:{SYNC_PORT}/cookies", data=body, method="POST",
        headers={"Origin": origin, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code


def _serve(tmp_path):
    server = make_sync_server(tmp_path / "cookies.txt")
    import threading
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def test_sync_accepts_extension_report(tmp_path):
    """扩展上报（Origin=chrome-extension://）且含关键 cookie：204 并落盘。"""
    server = _serve(tmp_path)
    try:
        body = json.dumps([{"domain": ".douyin.com", "path": "/",
                            "secure": True, "name": "ttwid", "value": "v"}]).encode()
        assert _post(server, body, "chrome-extension://abcdef") == 204
        text = (tmp_path / "cookies.txt").read_text(encoding="utf-8")
        assert "ttwid" in text and ".douyin.com" in text
    finally:
        server.shutdown()


def test_sync_rejects_web_page_origin(tmp_path):
    """普通网页 Origin：403 拒绝（浏览器不允许网页伪造 Origin，防伪造写入）。"""
    server = _serve(tmp_path)
    try:
        body = json.dumps([{"domain": ".douyin.com", "name": "ttwid",
                            "value": "evil"}]).encode()
        assert _post(server, body, "https://evil.example.com") == 403
        assert not (tmp_path / "cookies.txt").exists()
    finally:
        server.shutdown()


def test_sync_rejects_report_without_key_cookies(tmp_path):
    """没有关键 cookie 的上报：422 不落盘（挡空数据/垃圾请求）。"""
    server = _serve(tmp_path)
    try:
        body = json.dumps([{"domain": ".douyin.com", "name": "unrelated",
                            "value": "x"}]).encode()
        assert _post(server, body, "chrome-extension://abcdef") == 422
        assert not (tmp_path / "cookies.txt").exists()
    finally:
        server.shutdown()
