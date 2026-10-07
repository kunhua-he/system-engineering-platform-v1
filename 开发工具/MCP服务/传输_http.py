# -*- coding: utf-8 -*-
"""MCP HTTP 传输 —— Streamable HTTP 服务端（复用既有协议派发 / 工具表 / 统一信封）。

本件**只做传输适配**：HTTP 与 MCP 的握手 / 会话 / 响应形状 + 本机安全；业务派发一律走
`协议.派发`（同一份工具表、同一份统一信封），**不复制**任何业务 / 写盘权限 / 参数解析。

支持的方法：`initialize` · `notifications/initialized`（通知，202 Accepted）· `tools/list` ·
`tools/call` · `ping`；未知方法回 JSON-RPC `-32601`，坏帧回 `-32700` / `-32600` 且给正确 HTTP 状态。

**响应类型**：请求一律 `Content-Type: application/json`（单对象）；通知 / 客户端响应回 202 空体。
GET 回 405（本服务不主动向客户端发起请求 / 通知，故不提供服务端 SSE 流 —— 规格允许）。
**无状态（2026-10-08）**：本服务**不分配、不校验** `Mcp-Session-Id`（会话在 MCP 里本就可选，
且**从未参与授权** ⇒ 去掉不回退任何安全口径）：initialize 不回会话头；请求带陈旧 / 未知会话头
一律**忽略**（不再 404）；DELETE 无可终止的会话 ⇒ 405。**为何必须去会话依赖**：ZCode 打包
SDK 的 `StreamableHTTPClientTransport` 只判 401/403/400/202、**没有 404 分支**，规范要求的
「带会话 404 ⇒ 重新 initialize」它不做 ⇒ 有会话的服务端一旦回收会话就整条客户端不可用。
每请求自带全部上下文 ⇒ 服务可重启、可多实例（同宪法「多实例安全」）。
**版本门**：无状态 ⇒ 每请求按官方 `MCP-Protocol-Version` 规则判 —— `initialize` 与新版探测
`server/discover` 豁免（`协议.初始化前方法集`），其余方法带了**不支持的**版本头回 400 JSON
（不是 HTML）；头缺省按官方口径视作 2025-03-26，不拦。
**安全**：只绑环回；`Origin` 有值则须为本机环回，否则 403；`Host` 须为环回，否则 403（防 DNS
rebinding）；请求体 / 并发连接 / 连接空闲全部有界；不设任何 CORS 头（不开放到 `*`）。

依据：MCP Streamable HTTP 规格（2025-06-18）· `项目文档/决策记录/2026-09-27_MCP适配层.md`。
"""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from . import 协议
from .服务常量 import (绑定地址, 并发连接上限, 协议版本集, 协议版本最高, 服务标识,
                  服务路径, 连接空闲秒, 默认监听端口, 请求体上限字节)

# 视为本机环回的主机名（Host / Origin 校验用）；`Origin` 缺省 ⇒ 放行（非浏览器客户端）。
环回主机集 = {"127.0.0.1", "localhost", "::1", "[::1]"}
# MCP 通知方法统一前缀（如 `notifications/initialized`）：带 id 的才是请求。
已知通知前缀 = "notifications/"


def 协商协议版本(客户端版本):
    """HTTP 面的版本协商：客户端版本在支持集内 ⇒ 用它；否则回本服务最高支持版本。"""
    return 客户端版本 if 客户端版本 in 协议版本集 else 协议版本最高


class 传输服务(ThreadingHTTPServer):
    """带并发上限的 HTTP 服务：超上限的连接直接 503，不无界起线程。"""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, 监听地址, 处理器类, 仓根, 工具表):
        self.仓根 = 仓根
        self.工具表 = 工具表
        self._名额 = threading.BoundedSemaphore(并发连接上限)
        super().__init__(监听地址, 处理器类)

    def process_request(self, 请求, 客户端地址):
        if not self._名额.acquire(blocking=False):
            try:
                请求.sendall(b"HTTP/1.1 503 Service Unavailable\r\n"
                        b"Content-Length: 0\r\nConnection: close\r\n\r\n")
            except OSError:
                pass
            请求.close()
            return
        super().process_request(请求, 客户端地址)

    def shutdown_request(self, 请求):
        try:
            super().shutdown_request(请求)
        finally:
            self._名额.release()


class 请求处理器(BaseHTTPRequestHandler):
    """一个 MCP 端点：POST / GET / DELETE / OPTIONS 都落 `服务路径`。"""

    protocol_version = "HTTP/1.1"
    server_version = 服务标识
    timeout = 连接空闲秒

    def log_message(self, 日志格式, *实参):
        """静音：默认把每请求写 stderr —— 服务日志由 `服务管理` 落盘，不污染。"""

    def do_POST(self):
        self._本请求体已读 = False
        # 先有界读全请求体，再做入口校验：任何早退（路径 / 主机 / 来源 / 版本）都已在
        # keep-alive 上排空，绝不把未读 body 留给下一条请求（否则请求行错位 ⇒ 回 HTML 报错）。
        正文 = self._读请求体()
        if 正文 is None:
            return
        if not self._校验入口():
            return
        self._处理请求(正文)

    def do_GET(self):
        self._本请求体已读 = False
        if not self._校验入口():
            return
        self._写响应(405, 是否空体=True)

    def do_DELETE(self):
        self._本请求体已读 = False
        if not self._校验入口():
            return
        # 无状态：本服务不分配会话 ⇒ 没有可终止的会话。按规格回 405（不假装删过什么）。
        self._写响应(405, 是否空体=True)

    def do_OPTIONS(self):
        # 不提供 CORS：任何预检一律 403（不开放到 `*`）。
        self._本请求体已读 = False
        self._写响应(403, 是否空体=True)

    def _校验入口(self):
        """路径 / 主机 / 来源三关；任一不过 ⇒ 已回错误，回假。"""
        if urlsplit(self.path).path.rstrip("/") != 服务路径:
            self._写响应(404, 是否空体=True)
            return False
        if not self._校验主机():
            return False
        if not self._校验来源():
            return False
        # 协议版本门不在这里 —— 无状态下它按**方法名**分流（initialize / server/discover 豁免），
        # 而方法名要解析过请求体才知道 ⇒ 落在 `_处理请求` 里（见那里的版本门）。
        return True

    def _校验主机(self):
        """Host 须为环回（防 DNS rebinding）：`主机:端口` 只取主机名比。"""
        主机头 = self.headers.get("Host") or ""
        主机名 = 主机头.rsplit(":", 1)[0] if 主机头 else ""
        if 主机名 not in 环回主机集:
            self._写错误(403, None, -32000, "Host 不是本机环回：%r" % 主机头)
            return False
        return True

    def _校验来源(self):
        """Origin 缺省 ⇒ 放行（非浏览器客户端）；有值则须是本机环回，否则 403。"""
        来源头 = self.headers.get("Origin")
        if not 来源头:
            return True
        主机名 = urlsplit(来源头).hostname or ""
        if 主机名 not in 环回主机集:
            self._写错误(403, None, -32000, "Origin 不是本机环回：%r" % 来源头)
            return False
        return True

    def _读请求体(self):
        """有界读全请求体。**任何无法安全排空的情形都明确拒并关连接** —— 绝不把未读 body

        留在 keep-alive 上（否则下一条请求行错位，客户端只收到 HTML 报错）。超限**不读**，
        免得为排空把 > 上限的体读进来。
        """
        if self.headers.get("Transfer-Encoding"):
            self._写错误(400, None, -32700, "不支持 Transfer-Encoding（本服务只认 Content-Length）")
            return None
        if len(self.headers.get_all("Content-Length") or []) != 1:
            self._写错误(400, None, -32700, "Content-Length 缺失或重复")
            return None
        try:
            正文长度 = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            self._写错误(400, None, -32700, "Content-Length 不是整数")
            return None
        if 正文长度 < 0:
            self._写错误(400, None, -32700, "Content-Length 为负")
            return None
        if 正文长度 > 请求体上限字节:
            self._写错误(413, None, -32600, "请求体超过上限 %d 字节" % 请求体上限字节)
            return None
        self._本请求体已读 = True
        return self.rfile.read(正文长度) if 正文长度 else b""

    def _处理请求(self, 原始字节):
        try:
            请求报文 = json.loads(原始字节.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._写错误(400, None, -32700, "Parse error：报文不是合法 JSON")
            return
        if isinstance(请求报文, list):
            self._写错误(400, None, -32600, "不支持 JSON-RPC 批量请求（本协议版本已移除）")
            return
        if not isinstance(请求报文, dict):
            self._写错误(400, None, -32600, "报文须是 JSON 对象")
            return
        报文号 = 请求报文.get("id")
        方法名 = 请求报文.get("method")
        # 版本门（无状态 · 每请求按官方 `MCP-Protocol-Version` 规则）：`initialize` 与新版探测
        # `server/discover` 豁免（初始化前客户端还不知道服务端版本，拦它会把整条新客户端连接
        # 判死）；其余方法带了**不支持的**版本头 ⇒ 400 JSON（不是 HTML）。头缺省按官方口径
        # 视作 2025-03-26，不拦。**会话头一律忽略**（无状态：不分配、不校验）。
        if isinstance(方法名, str) and 方法名 not in 协议.初始化前方法集:
            版本头 = self.headers.get("MCP-Protocol-Version")
            if 版本头 and 版本头 not in 协议版本集:
                self._写错误(400, 报文号, -32000, "不支持的 MCP-Protocol-Version：%s" % 版本头)
                return
        if 报文号 is None and isinstance(方法名, str):
            if 方法名.startswith(已知通知前缀):
                self._写响应(202, 是否空体=True)
            else:
                self._写错误(400, None, -32601, "未知通知方法：%r" % 方法名)
            return
        if 报文号 is None:
            # 客户端响应（对服务端请求的回执）：本服务从不发起服务端请求 ⇒ 拒。
            self._写错误(400, None, -32600, "不接受客户端响应：本服务不发起服务端请求")
            return
        if not isinstance(方法名, str):
            self._写错误(400, 报文号, -32600, "缺少 method")
            return
        实参 = 请求报文.get("params")
        if 实参 is None:
            实参 = {}
        if not isinstance(实参, dict):
            self._写错误(200, 报文号, -32602, "params 须是对象")
            return
        try:
            读数, 错误 = 协议.派发(方法名, 实参, self.server.仓根, self.server.工具表, "http")
        except Exception:
            self._写错误(200, 报文号, -32603, "内部错误：%s" % (sys.exc_info()[1],))
            return
        if 方法名 == "initialize" and 错误 is None and isinstance(读数, dict):
            # 无状态：initialize **不**回 `Mcp-Session-Id`（不分配会话 ⇒ 后续请求也不带、不校验）。
            读数["protocolVersion"] = 协商协议版本(实参.get("protocolVersion"))
        self._写报文(报文号, 读数, 错误, {})

    def _写报文(self, 报文号, 读数, 错误, 额外头, 状态码=200):
        应答 = {"jsonrpc": "2.0", "id": 报文号}
        if 错误 is not None:
            应答["error"] = 错误
        else:
            应答["result"] = 读数
        self._写正文(状态码, json.dumps(应答, ensure_ascii=False).encode("utf-8"), 额外头)

    def _写错误(self, 状态码, 报文号, 错误码, 说明):
        self._写报文(报文号, None, {"code": 错误码, "message": 说明}, {}, 状态码)

    def _写响应(self, 状态码, 是否空体=False):
        if 是否空体:
            self.send_response(状态码)
            self.send_header("Content-Length", "0")
            self._补连接收尾头()
            self.end_headers()
        else:
            self._写正文(状态码, b"", {})

    def _写正文(self, 状态码, 正文, 额外头):
        self.send_response(状态码)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(正文)))
        for 头名, 头值 in 额外头.items():
            self.send_header(头名, 头值)
        self._补连接收尾头()
        self.end_headers()
        if 正文:
            self.wfile.write(正文)

    def _补连接收尾头(self):
        """本请求若仍留着未读 body（超限未读 / 非 POST 带体 / 坏 Content-Length / chunked）

        ⇒ 显式关连接。HTTP/1.1 keep-alive 下把未读 body 留着，下一条请求行会被拼进 body 尾部，
        服务端只能回 HTML 400/501 —— 而 MCP 客户端只认 JSON，就判「连不上」。
        """
        if self._有未读请求体():
            self.send_header("Connection", "close")
            self.close_connection = True

    def _有未读请求体(self):
        """本请求是否还留着未读 body（已成功读全 ⇒ 假）。"""
        if getattr(self, "_本请求体已读", False):
            return False
        if self.headers.get("Transfer-Encoding"):
            return True
        try:
            return int(self.headers.get("Content-Length") or "0") > 0
        except ValueError:
            return True


def 起传输(仓根, 工具表, 监听端口=默认监听端口, 绑定=绑定地址):
    """起 HTTP 传输（**永不返回**）：监听 `绑定:监听端口`，一个 `服务路径` 端点。"""
    服务对象 = 传输服务((绑定, 监听端口), 请求处理器, 仓根, 工具表)
    try:
        服务对象.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        服务对象.server_close()
