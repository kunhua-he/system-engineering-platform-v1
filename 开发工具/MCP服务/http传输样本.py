# -*- coding: utf-8 -*-
"""HTTP 传输自检样本 —— 起环回服务，用标准库 http.client 跑真实 MCP 握手并断言形状。

`MCP服务_http.py --自检` 调 `跑自检`；`MCP服务.py --自检`（判据 ㊽）也调它一次
（HTTP 面与 stdio 面共用同一份自检）。**只用标准库**（仓内 Python 零第三方依赖）。

覆盖：initialize 协商版本 + 会话头 · tools/list 与 stdio 合同一致 · 通知 202 · 只读 tools/call ·
坏帧 / 批量 / 未知方法 / 未知会话 / 坏 Origin / 坏 Host / GET 405 / DELETE 终止 / 错路径。
"""
import http.client
import json
import socket
import threading

from . import 传输_http
from .服务常量 import 服务路径

# 自检客户端默认头：Accept 同时列 JSON 与 SSE（规格要求），Content-Type 为 JSON。
标准头 = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def _起环回(仓根, 工具表):
    """在 127.0.0.1 的临时端口起传输 ⇒ (服务对象, 监听端口)。"""
    服务对象 = 传输_http.传输服务(("127.0.0.1", 0), 传输_http.请求处理器, 仓根, 工具表,
                            传输_http.会话表())
    监听端口 = 服务对象.server_address[1]
    运行线程 = threading.Thread(target=服务对象.serve_forever,
                          kwargs={"poll_interval": 0.01}, daemon=True)
    运行线程.start()
    return 服务对象, 监听端口


def _调用(监听端口, 请求方法, 请求正文=None, 请求头=None, 请求路径=服务路径):
    """发一条 HTTP 请求 ⇒ (状态码, 内容类型, 会话头, 应答字节)。"""
    连接 = http.client.HTTPConnection("127.0.0.1", 监听端口, timeout=5)
    连接.request(请求方法, 请求路径, body=请求正文, headers=请求头 or {})
    应答 = 连接.getresponse()
    应答数据 = 应答.read()
    状态码 = 应答.status
    内容类型 = 应答.getheader("Content-Type")
    会话头 = 应答.getheader("Mcp-Session-Id")
    连接.close()
    return 状态码, 内容类型, 会话头, 应答数据


def _报文(请求报文):
    """JSON-RPC 报文 ⇒ UTF-8 字节。"""
    return json.dumps(请求报文, ensure_ascii=False).encode("utf-8")


def _错误码(应答数据):
    """从应答字节里取 JSON-RPC 错误码；取不到 ⇒ None。"""
    try:
        return (json.loads(应答数据).get("error") or {}).get("code")
    except ValueError:
        return None


def _原始请求(监听端口, 原始字节, 读超时=2):
    """用裸 socket 发原始字节，读回全部响应 ⇒ 响应字节（验 keep-alive 帧与关连接行为）。"""
    连接 = socket.create_connection(("127.0.0.1", 监听端口), 读超时)
    try:
        连接.sendall(原始字节)
        连接.settimeout(读超时)
        响应字节 = b""
        try:
            while True:
                响应片段 = 连接.recv(65536)
                if not 响应片段:
                    break
                响应字节 += 响应片段
        except socket.timeout:
            pass
        return 响应字节
    finally:
        连接.close()


def _原始帧(路径, 请求头, 正文=b""):
    """拼一条原始 HTTP/1.1 POST 帧 ⇒ 字节（Content-Length 按正文实数）。"""
    return (b"POST " + 路径.encode("utf-8") + b" HTTP/1.1\r\n" + 请求头
            + b"Content-Length: " + str(len(正文)).encode("utf-8") + b"\r\n\r\n" + 正文)


def 样本列表(仓根, 工具表):
    """跑一组真实 HTTP 帧样本 ⇒ `[(说明, 通过)]`（起临时服务，跑完即关，不改仓）。"""
    服务对象, 监听端口 = _起环回(仓根, 工具表)
    样本表 = []
    try:
        状态码, 内容类型, 会话头, 应答数据 = _调用(监听端口, "POST", _报文(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                        "clientInfo": {"name": "自检", "version": "0"}}}), 标准头)
        初始化读数 = json.loads(应答数据).get("result") or {}
        样本表.append(("initialize：HTTP %s · JSON %s · 版本 %s · 会话头 %s"
                 % (状态码, 内容类型, 初始化读数.get("protocolVersion"), bool(会话头)),
                状态码 == 200 and (内容类型 or "").startswith("application/json")
                and 初始化读数.get("protocolVersion") == "2025-06-18" and bool(会话头)
                and (初始化读数.get("serverInfo") or {}).get("name") == "v1-devkit"))
        带会话 = dict(标准头)
        带会话["Mcp-Session-Id"] = 会话头
        状态码, _, _, 应答数据 = _调用(监听端口, "POST", _报文(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}), 带会话)
        名单 = sorted(工具项.get("name")
                 for 工具项 in (json.loads(应答数据).get("result") or {}).get("tools", []))
        样本表.append(("tools/list：HTTP %s · 与 stdio 工具表同一份名单 %s"
                 % (状态码, 名单 == sorted(工具表)), 状态码 == 200 and 名单 == sorted(工具表)))
        状态码, _, _, 应答数据 = _调用(监听端口, "POST", _报文(
            {"jsonrpc": "2.0", "method": "notifications/initialized"}), 带会话)
        样本表.append(("通知 notifications/initialized ⇒ HTTP %s（期望 202）· 空体 %s"
                 % (状态码, 应答数据 == b""), 状态码 == 202 and 应答数据 == b""))
        状态码, _, _, 应答数据 = _调用(监听端口, "POST", _报文(
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "v1_context", "arguments": {}}}), 带会话)
        结果值 = json.loads(应答数据).get("result") or {}
        应答文本 = (结果值.get("content") or [{}])[0].get("text") or ""
        样本表.append(("tools/call v1_context 只读：HTTP %s · isError=%s · 信封含「操作目录」%s"
                 % (状态码, 结果值.get("isError"), "操作目录" in 应答文本),
                状态码 == 200 and not 结果值.get("isError") and "操作目录" in 应答文本))
        状态码, _, _, 应答数据 = _调用(监听端口, "POST", "{不是JSON".encode("utf-8"), 带会话)
        样本表.append(("坏帧（非法 JSON）⇒ HTTP %s（期望 400）· -32700 %s"
                 % (状态码, _错误码(应答数据)), 状态码 == 400 and _错误码(应答数据) == -32700))
        状态码, _, _, 应答数据 = _调用(监听端口, "POST", b"[{}]", 带会话)
        样本表.append(("批量请求 ⇒ HTTP %s（期望 400）· -32600 %s"
                 % (状态码, _错误码(应答数据)), 状态码 == 400 and _错误码(应答数据) == -32600))
        状态码, _, _, 应答数据 = _调用(监听端口, "POST", _报文(
            {"jsonrpc": "2.0", "id": 4, "method": "没有这个方法", "params": {}}), 带会话)
        样本表.append(("未知方法 ⇒ HTTP %s（期望 200）· -32601 %s"
                 % (状态码, _错误码(应答数据)), 状态码 == 200 and _错误码(应答数据) == -32601))
        坏会话 = dict(标准头)
        坏会话["Mcp-Session-Id"] = "no-such-session-id"
        状态码, _, _, _ = _调用(监听端口, "POST", _报文(
            {"jsonrpc": "2.0", "id": 5, "method": "tools/list", "params": {}}), 坏会话)
        样本表.append(("未知会话 ⇒ HTTP %s（期望 404）" % 状态码, 状态码 == 404))
        坏来源 = dict(标准头)
        坏来源["Origin"] = "http://evil.example.com"
        状态码, _, _, _ = _调用(监听端口, "POST", _报文(
            {"jsonrpc": "2.0", "id": 6, "method": "tools/list", "params": {}}), 坏来源)
        样本表.append(("非法 Origin ⇒ HTTP %s（期望 403）" % 状态码, 状态码 == 403))
        好来源 = dict(标准头)
        好来源["Origin"] = "http://127.0.0.1:%d" % 监听端口
        状态码, _, _, _ = _调用(监听端口, "POST", _报文(
            {"jsonrpc": "2.0", "id": 7, "method": "tools/list", "params": {}}), 好来源)
        样本表.append(("本机 Origin ⇒ HTTP %s（期望 200）" % 状态码, 状态码 == 200))
        坏主机 = dict(标准头)
        坏主机["Host"] = "evil.example.com"
        状态码, _, _, _ = _调用(监听端口, "POST", _报文(
            {"jsonrpc": "2.0", "id": 8, "method": "tools/list", "params": {}}), 坏主机)
        样本表.append(("非法 Host ⇒ HTTP %s（期望 403）" % 状态码, 状态码 == 403))
        状态码, _, _, _ = _调用(监听端口, "GET", None, 标准头)
        样本表.append(("GET（不提供服务端 SSE 流）⇒ HTTP %s（期望 405）" % 状态码, 状态码 == 405))
        状态码, _, _, _ = _调用(监听端口, "DELETE", None, 带会话)
        样本表.append(("DELETE 终止会话 ⇒ HTTP %s（期望 204）" % 状态码, 状态码 == 204))
        状态码, _, _, _ = _调用(监听端口, "POST", _报文(
            {"jsonrpc": "2.0", "id": 9, "method": "tools/list", "params": {}}), 带会话)
        样本表.append(("终止后再用该会话 ⇒ HTTP %s（期望 404）" % 状态码, 状态码 == 404))
        状态码, _, _, _ = _调用(监听端口, "POST", _报文(
            {"jsonrpc": "2.0", "id": 10, "method": "tools/list", "params": {}}), 标准头, "/wrong-path")
        样本表.append(("错误路径 ⇒ HTTP %s（期望 404）" % 状态码, 状态码 == 404))
        # —— keep-alive 帧错位回归：真实 ZCode 形态（新版探测头 + 同连接续请求）——
        连接 = http.client.HTTPConnection("127.0.0.1", 监听端口, timeout=5)
        try:
            探测头 = dict(标准头)
            探测头["MCP-Protocol-Version"] = "2026-07-28"
            连接.request("POST", 服务路径, body=_报文(
                {"jsonrpc": "2.0", "id": "server-discover-probe-1", "method": "server/discover",
                 "params": {"_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28",
                                      "io.modelcontextprotocol/clientInfo": {"name": "zcode",
                                                                             "version": "0.16.9"}}}}),
                headers=探测头)
            应答 = 连接.getresponse()
            状态码, 应答数据 = 应答.status, 应答.read()
            样本表.append(("同连接·初始化前无会话新版探测头 ⇒ HTTP %s · 错误码 %s（期望 200 / -32601，不回 400）"
                     % (状态码, _错误码(应答数据)), 状态码 == 200 and _错误码(应答数据) == -32601))
            连接.request("POST", 服务路径, body=_报文(
                {"jsonrpc": "2.0", "id": 101, "method": "initialize",
                 "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                            "clientInfo": {"name": "zcode", "version": "0.16.9"}}}), headers=标准头)
            应答 = 连接.getresponse()
            状态码, 会话头, 应答数据 = 应答.status, 应答.getheader("Mcp-Session-Id"), 应答.read()
            样本表.append(("同连接续 initialize ⇒ HTTP %s · 版本 %s · 会话头 %s（探测未污染下一帧）"
                     % (状态码, (json.loads(应答数据).get("result") or {}).get("protocolVersion"),
                        bool(会话头)),
                    状态码 == 200 and bool(会话头)
                    and (json.loads(应答数据).get("result") or {}).get("protocolVersion") == "2025-06-18"))
        finally:
            连接.close()

        # —— 早退必须排空：坏 Host 403 后同连接续请求不得错位（客户端只认 JSON，绝不许 HTML）——
        探测正文 = _报文({"jsonrpc": "2.0", "id": 102, "method": "ping", "params": {}})
        坏主机头 = b"Host: evil.example.com\r\nContent-Type: application/json\r\n"
        好主机头 = b"Host: 127.0.0.1\r\nContent-Type: application/json\r\nConnection: close\r\n"
        原始字节 = _原始请求(监听端口,
            _原始帧(服务路径, 坏主机头, 探测正文) + _原始帧(服务路径, 好主机头, 探测正文))
        样本表.append(("坏 Host 403 后同连接续请求 ⇒ 响应段数 %d · 无 HTML %s · 含 403 %s · 含 200 %s"
                 % (原始字节.count(b"HTTP/1.1 "), b"<!DOCTYPE" not in 原始字节,
                    b"HTTP/1.1 403" in 原始字节, b"HTTP/1.1 200" in 原始字节),
                b"<!DOCTYPE" not in 原始字节 and 原始字节.count(b"HTTP/1.1 ") == 2
                and b"HTTP/1.1 403" in 原始字节 and b"HTTP/1.1 200" in 原始字节))

        # —— 坏 / 重复 Content-Length、chunked、超限：明确拒 + 关连接 + JSON（不 HTML 污染）——
        拒绝项 = (
            ("请求体超上限", b"Content-Length: 99999999\r\n"),
            ("重复 Content-Length", b"Content-Length: 2\r\nContent-Length: 2\r\n"),
            ("不支持 chunked", b"Transfer-Encoding: chunked\r\n"),
        )
        for 说明, 头块 in 拒绝项:
            原始字节 = _原始请求(监听端口,
                b"POST " + 服务路径.encode("utf-8") + b" HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                b"Content-Type: application/json\r\n" + 头块 + b"\r\n{}")
            样本表.append(("%s ⇒ 关连接 %s · JSON %s · 非 HTML %s"
                     % (说明, b"Connection: close" in 原始字节,
                        b"application/json" in 原始字节, b"<!DOCTYPE" not in 原始字节),
                    b"Connection: close" in 原始字节 and b"application/json" in 原始字节
                    and b"<!DOCTYPE" not in 原始字节))

    finally:
        服务对象.shutdown()
        服务对象.server_close()
    return 样本表


def 跑自检(仓根, 工具表):
    """HTTP 传输自检 ⇒ 退出码（0 全过 · 1 有样本没过）—— 打印逐条读数。"""
    样本表 = 样本列表(仓根, 工具表)
    for 说明, 通过 in 样本表:
        print("  %s %s" % ("✓" if 通过 else "✗", 说明))
    return 0 if all(通过 for _说明, 通过 in 样本表) else 1
