# -*- coding: utf-8 -*-
"""HTTP 传输断连自检样本 —— 真实 socket 造客户端断连三例，验日志收敛与资源回收。

`http传输样本.样本列表` 调 `断连日志样本`（判据 ㊽ 经 `MCP服务.py --自检` 间接跑到）。

**为何单开一件**（判据 ⑲ 单源文件 ≤400 行）：断连样本带一批裸 socket 小工具，
塞回 `http传输样本.py` 会把它顶过 400 行硬数；一个关注点一个文件。

**口径**：预期网络断开（客户端先走 / RST）⇒ 恰好 N 条**单行有界**断连日志 · **无 traceback**；
非网络异常 ⇒ 仍**必须有 traceback**（不许被吞）。两者必须分得开 —— 那是本修的要害。
"""
import io
import json
import socket
import struct
import time
from contextlib import redirect_stderr

from . import 传输_http
from .服务常量 import 服务路径, 并发连接上限
from .http传输样本 import _原始帧, _起环回, _调用, _报文, 标准头

# 裸 socket 样本用的请求头字节（`_原始帧` 走字节，不给 dict）。
裸请求头 = b"Host: 127.0.0.1\r\nContent-Type: application/json\r\n"


def _读全响应(监听端口, 请求正文, 读超时=2):
    """发全帧并读到正文读全再关（keep-alive 帧读写都走完）⇒ 应答正文字节。"""
    连接 = socket.create_connection(("127.0.0.1", 监听端口), 读超时)
    try:
        连接.sendall(_原始帧(服务路径, 裸请求头, 请求正文))
        连接.settimeout(读超时)
        读回字节 = b""
        while b"\r\n\r\n" not in 读回字节:
            片段 = 连接.recv(65536)
            if not 片段:
                break
            读回字节 += 片段
        头块, _, 正文 = 读回字节.partition(b"\r\n\r\n")
        应读长 = 0
        for 头行 in 头块.split(b"\r\n"):
            if 头行.lower().startswith(b"content-length:"):
                应读长 = int(头行.split(b":")[1])
        while len(正文) < 应读长:
            片段 = 连接.recv(65536)
            if not 片段:
                break
            正文 += 片段
        return 正文
    finally:
        连接.close()


def _RST关(套接字):
    """带 SO_LINGER 立即关 ⇒ 对端读到 RST（不是 FIN）—— 断连的确定性写法。"""
    套接字.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
    套接字.close()


def _RST写撞(监听端口, 请求正文, 触发轮数=3):
    """每轮：发全帧后立刻 RST（不等响应）⇒ 服务端写响应撞断连。"""
    for _轮 in range(触发轮数):
        连接 = socket.create_connection(("127.0.0.1", 监听端口), 2)
        连接.sendall(_原始帧(服务路径, 裸请求头, 请求正文))
        _RST关(连接)
        time.sleep(0.02)


def _RST读撞(监听端口, 触发轮数=3):
    """每轮：连上发半行（无 CRLF）后 RST ⇒ 服务端读请求行撞断连。"""
    for _轮 in range(触发轮数):
        连接 = socket.create_connection(("127.0.0.1", 监听端口), 2)
        连接.sendall(b"POST " + 服务路径.encode("utf-8") + b" HTTP/1.1\r\nHost: 127.0.0.1")
        time.sleep(0.02)
        _RST关(连接)
        time.sleep(0.02)


def _发不等回(监听端口, 请求正文, 读超时=1):
    """发全帧后读一小会儿（不要求回帧）⇒ 见证服务端收到并处理。"""
    连接 = socket.create_connection(("127.0.0.1", 监听端口), 2)
    try:
        连接.sendall(_原始帧(服务路径, 裸请求头, 请求正文))
        连接.settimeout(读超时)
        try:
            连接.recv(65536)
        except OSError:
            pass
    finally:
        连接.close()


def _抓取stderr(样本例, 尾随条件=None, 尾随上限秒=1.0):
    """stderr 重定向下跑 `样本例()`，**轮询等到 `尾随条件` 成立**（或超上限）⇒ 抓到的文本。

    **为何轮询而不是定量睡眠**：服务线程何时写完 stderr 取决于负载（本机并发高时换出慢），
    定量睡眠在高负载下会假红；轮询在满足条件时立刻返回 ⇒ 既快又稳。`尾随条件` 为空 ⇒ 不等。
    """
    缓冲 = io.StringIO()
    with redirect_stderr(缓冲):
        样本例()
        截止时刻 = time.monotonic() + 尾随上限秒
        while 尾随条件 is not None and time.monotonic() < 截止时刻:
            if 尾随条件(缓冲.getvalue()):
                break
            time.sleep(0.01)
    return 缓冲.getvalue()


def _皆单行有界(已抓文本, 单行上限=None):
    """断连日志每条都单行且长度有界 ⇒ (皆单行, 最长行长)。空文本 ⇒ 假。"""
    上限值 = 单行上限 or (传输_http.断连字段上限 + 80)
    文本行表 = [单行文本 for 单行文本 in 已抓文本.splitlines() if 单行文本.strip()]
    return (bool(文本行表)
            and all("Traceback" not in 单行文本 and len(单行文本) <= 上限值 for 单行文本 in 文本行表),
            max((len(单行文本) for 单行文本 in 文本行表), default=0))


def 断连日志样本(仓根, 工具表):
    """客户端断连三例 · 其他异常仍可见 · 断连后仍通 · 连接名额回收 ⇒ 样本表。

    **为何必看 stderr**：断连日志是**服务日志件**的内容（落盘 stderr）⇒ 只能抓它。
    """
    样本表 = []
    正常正文 = _报文({"jsonrpc": "2.0", "id": 9001, "method": "initialize",
                  "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                             "clientInfo": {"name": "自检", "version": "0"}}})

    class 抛错处理器(传输_http.请求处理器):
        def _处理请求(self, 原始字节):
            raise ValueError("自检：故意编程错（必须可见，不许被吞）")

    # ① 正常完成（真读全响应再关）⇒ 无断连日志、无 traceback
    服务对象, 监听端口 = _起环回(仓根, 工具表)
    try:
        已抓文本 = _抓取stderr(lambda: _读全响应(监听端口, 正常正文))
    finally:
        服务对象.shutdown()
        服务对象.server_close()
    样本表.append(("断连样本·正常完成 ⇒ 无 traceback %s · 无断连日志 %s"
             % ("是" if "Traceback" not in 已抓文本 else "否",
                "是" if "断连：" not in 已抓文本 else "否"),
            "Traceback" not in 已抓文本 and "断连：" not in 已抓文本))

    # ② 提前关（RST 写撞）⇒ 恰好 3 条单行有界断连、无 traceback、字段可定位
    服务对象, 监听端口 = _起环回(仓根, 工具表)
    try:
        已抓文本 = _抓取stderr(lambda: _RST写撞(监听端口, 正常正文),
                          尾随条件=lambda 已抓文本: 已抓文本.count("断连：") >= 3)
        有界, 最长 = _皆单行有界(已抓文本)
    finally:
        服务对象.shutdown()
        服务对象.server_close()
    断连行 = [单行文本 for 单行文本 in 已抓文本.splitlines() if 单行文本.startswith("断连：")]
    样本表.append(("断连样本·提前关（RST 写撞）⇒ 断连行 %d（期望 3）· 无 traceback %s · 单行有界 %s（最长 %d）"
             % (len(断连行), "是" if "Traceback" not in 已抓文本 else "否",
                "是" if 有界 else "否", 最长),
            len(断连行) == 3 and "Traceback" not in 已抓文本 and 有界
            and all("MCP方法=" in 单行文本 and "报文号=" in 单行文本 and "原因=" in 单行文本
                    for 单行文本 in 断连行)))

    # ③ RST 读撞 + 名额回收 + 断连后仍通
    服务对象, 监听端口 = _起环回(仓根, 工具表)
    try:
        名额初值 = 服务对象._名额._value
        已抓文本 = _抓取stderr(lambda: _RST读撞(监听端口),
                          尾随条件=lambda 已抓文本: 已抓文本.count("断连：") >= 3)
        归位名额 = 服务对象._名额._value
        状态码, _, 会话头, 应答数据 = _调用(监听端口, "POST", 正常正文, 标准头)
        带会话 = dict(标准头)
        带会话["Mcp-Session-Id"] = 会话头
        列码, _, _, 列数据 = _调用(监听端口, "POST", _报文(
            {"jsonrpc": "2.0", "id": 9102, "method": "tools/list", "params": {}}), 带会话)
        调码, _, _, 调数据 = _调用(监听端口, "POST", _报文(
            {"jsonrpc": "2.0", "id": 9103, "method": "tools/call",
             "params": {"name": "v1_context", "arguments": {}}}), 带会话)
    finally:
        服务对象.shutdown()
        服务对象.server_close()
    断连行 = [单行文本 for 单行文本 in 已抓文本.splitlines() if 单行文本.startswith("断连：")]
    列名单 = sorted(工具项.get("name")
                for 工具项 in (json.loads(列数据).get("result") or {}).get("tools", []))
    调结果 = json.loads(调数据).get("result") or {}
    样本表.append(("断连样本·RST 读撞 ⇒ 断连行 %d（期望 3）· 原因 ConnectionResetError %s · 名额归位 %d（初值 %d · 上限 %d）"
             % (len(断连行), "是" if all("ConnectionResetError" in 单行文本 for 单行文本 in 断连行) else "否",
                归位名额, 名额初值, 并发连接上限),
            len(断连行) == 3 and all("ConnectionResetError" in 单行文本 for 单行文本 in 断连行)
            and 名额初值 == 并发连接上限 and 归位名额 == 并发连接上限))
    样本表.append(("断连样本·断连后仍通 ⇒ initialize %d · tools/list %d（名单同 %s）· tools/call %d（isError=%s）"
             % (状态码, 列码, "是" if 列名单 == sorted(工具表) else "否",
                调码, 调结果.get("isError")),
            状态码 == 200 and 列码 == 200 and 列名单 == sorted(工具表)
            and 调码 == 200 and not 调结果.get("isError")))

    # ④ 非网络异常仍可见（抛错处理器 ⇒ 必须有 traceback，不许被吞）
    服务对象, 监听端口 = _起环回(仓根, 工具表, 处理器类=抛错处理器)
    try:
        已抓文本 = _抓取stderr(lambda: _发不等回(监听端口, 正常正文),
                          尾随条件=lambda 已抓文本: "Traceback" in 已抓文本)
    finally:
        服务对象.shutdown()
        服务对象.server_close()
    样本表.append(("断连样本·其他编程错仍可见 ⇒ traceback %s · ValueError %s（不许被吞）"
             % ("是" if "Traceback" in 已抓文本 else "否",
                "是" if "ValueError" in 已抓文本 else "否"),
            "Traceback" in 已抓文本 and "ValueError" in 已抓文本))
    return 样本表
