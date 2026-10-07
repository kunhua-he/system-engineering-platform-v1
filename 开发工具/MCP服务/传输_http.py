# -*- coding: utf-8 -*-
"""MCP HTTP 传输 —— Streamable HTTP 服务端（复用既有协议派发 / 工具表 / 统一信封）。

本件**只做传输适配**：HTTP 与 MCP 的握手 / 会话 / 响应形状 + 本机安全；业务派发一律走
`协议.派发`（同一份工具表、同一份统一信封），**不复制**任何业务 / 写盘权限 / 参数解析。

支持的方法：`initialize` · `notifications/initialized`（通知，202 Accepted）· `tools/list` ·
`tools/call` · `ping`；未知方法回 JSON-RPC `-32601`，坏帧回 `-32700` / `-32600` 且给正确 HTTP 状态。

**响应类型**：请求一律 `Content-Type: application/json`（单对象）；通知 / 客户端响应回 202 空体。
GET 回 405（本服务不主动向客户端发起请求 / 通知，故不提供服务端 SSE 流 —— 规格允许）。
**会话**：initialize 时发 `Mcp-Session-Id`；后续带未知 / 已回收会话 ⇒ 404（客户端据此重初始化）；
DELETE 终止会话；不带会话也照服务（无状态可用）。
**安全**：只绑环回；`Origin` 有值则须为本机环回，否则 403；`Host` 须为环回，否则 403（防 DNS
rebinding）；请求体 / 并发连接 / 连接空闲全部有界；不设任何 CORS 头（不开放到 `*`）。
**断连**：客户端先关连接 / RST 属预期（不是服务缺陷）—— 只把三类网络断开收成**一条有界单行**，
其余异常照旧冒泡到 `handle_error`（见 `请求处理器.handle_one_request`）。

依据：MCP Streamable HTTP 规格（2025-06-18）· `项目文档/决策记录/2026-09-27_MCP适配层.md`。
"""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from . import 协议
from .http会话 import 会话表
from .服务常量 import (绑定地址, 并发连接上限, 协议版本集, 协议版本最高, 服务标识,
                  服务路径, 连接空闲秒, 默认监听端口, 请求体上限字节)

# 视为本机环回的主机名（Host / Origin 校验用）；`Origin` 缺省 ⇒ 放行（非浏览器客户端）。
环回主机集 = {"127.0.0.1", "localhost", "::1", "[::1]"}
# MCP 通知方法统一前缀（如 `notifications/initialized`）：带 id 的才是请求。
已知通知前缀 = "notifications/"
# 预期网络断开的三类异常（客户端先关连接 / RST / 中止）：只吞这三类，其余照旧冒泡 ——
# 见 `请求处理器.handle_one_request`。这是「客户端走了」，不是服务缺陷。
断连异常类 = (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)
# 断连日志里路径字段的截断上限（有界：日志不许被一条超长路径撑爆）。
断连字段上限 = 200


def 协商协议版本(客户端版本):
    """HTTP 面的版本协商：客户端版本在支持集内 ⇒ 用它；否则回本服务最高支持版本。"""
    return 客户端版本 if 客户端版本 in 协议版本集 else 协议版本最高


class 传输服务(ThreadingHTTPServer):
    """带并发上限的 HTTP 服务：超上限的连接直接 503，不无界起线程。"""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, 监听地址, 处理器类, 仓根, 工具表, 会话登记):
        self.仓根 = 仓根
        self.工具表 = 工具表
        self.会话登记 = 会话登记
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

    def handle_one_request(self):
        """按帧处理一条请求；**只吞预期网络断开**（客户端先走 / RST）。

        读请求行撞 `ConnectionResetError`、写响应撞 `BrokenPipeError` / `ConnectionAbortedError`
        都是客户端已离开，不是服务缺陷 —— 默认 `handle_error` 会把整段 traceback 打到 stderr
        （服务日志件），一次断连刷十几行且无定位。这里**收成一条有界单行**并关连接；
        **其余异常照旧冒泡**到 `handle_error`（编程错 / 别的 IO 错必须可见，绝不吞）。
        """
        try:
            super().handle_one_request()
        except 断连异常类 as 断开原因:
            self._记断连(断开原因)
            self.close_connection = True

    def _记断连(self, 断开原因):
        """一条有界可定位单行（HTTP 方法 / 路径 / MCP 方法 / 报文号 / 原因），不打 traceback。"""
        路径文本 = (getattr(self, "path", "") or "-")[:断连字段上限]
        sys.stderr.write("断连：%s %s · MCP方法=%s · 报文号=%s · 原因=%s\n" % (
            getattr(self, "command", "") or "-", 路径文本,
            getattr(self, "_当前方法名", None), getattr(self, "_当前报文号", None),
            type(断开原因).__name__))

    def do_POST(self):
        self._本请求体已读 = False
        self._当前报文号 = None
        self._当前方法名 = None
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
        会话编号 = self.headers.get("Mcp-Session-Id")
        if 会话编号 and self.server.会话登记.删除(会话编号):
            self._写响应(204, 是否空体=True)
        else:
            self._写响应(404, 是否空体=True)

    def do_OPTIONS(self):
        # 不提供 CORS：任何预检一律 403（不开放到 `*`）。
        self._本请求体已读 = False
        self._写响应(403, 是否空体=True)

    def _校验入口(self):
        """路径 / 主机 / 来源 / 协议版本头四关；任一不过 ⇒ 已回错误，回假。"""
        if urlsplit(self.path).path.rstrip("/") != 服务路径:
            self._写响应(404, 是否空体=True)
            return False
        if not self._校验主机():
            return False
        if not self._校验来源():
            return False
        # 协议版本门：只对**已初始化（带会话）**的请求按规范拦不支持的新版头（安全 400 JSON）；
        # 初始化前的探测（无会话，如新版客户端的 `server/discover`）不在此拦 —— 放它走方法
        # 派发（未知方法回 -32601），否则会把整条新客户端的连接判死。本服务的协议版本集
        # **不声明**未实现的新版兼容，故这里只放行「探测」，不假装支持新版。
        版本头 = self.headers.get("MCP-Protocol-Version")
        if 版本头 and 版本头 not in 协议版本集 and self.headers.get("Mcp-Session-Id"):
            self._写错误(400, None, -32000, "不支持的 MCP-Protocol-Version：%s" % 版本头)
            return False
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
        # 定位给断连日志用：响应写出撞断连时，这一条请求是谁才说得清。
        self._当前报文号 = 报文号
        self._当前方法名 = 方法名
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
        # 会话先核后派发：未知 / 已终止会话 ⇒ 404，**绝不**在死会话上跑写工具（防重复执行）。
        会话编号 = self.headers.get("Mcp-Session-Id")
        if 会话编号 and not self.server.会话登记.触碰(会话编号):
            self._写错误(404, 报文号, -32000, "会话不存在或已终止")
            return
        实参 = 请求报文.get("params")
        if 实参 is None:
            实参 = {}
        if not isinstance(实参, dict):
            self._写错误(200, 报文号, -32602, "params 须是对象")
            return
        try:
            读数, 错误 = 协议.派发(方法名, 实参, self.server.仓根, self.server.工具表)
        except Exception:
            self._写错误(200, 报文号, -32603, "内部错误：%s" % (sys.exc_info()[1],))
            return
        额外头 = {}
        if 方法名 == "initialize" and 错误 is None and isinstance(读数, dict):
            读数["protocolVersion"] = 协商协议版本(实参.get("protocolVersion"))
            额外头 = {"Mcp-Session-Id": self.server.会话登记.新建()}
        self._写报文(报文号, 读数, 错误, 额外头)

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
    会话登记 = 会话表()
    服务对象 = 传输服务((绑定, 监听端口), 请求处理器, 仓根, 工具表, 会话登记)
    try:
        服务对象.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        服务对象.server_close()
