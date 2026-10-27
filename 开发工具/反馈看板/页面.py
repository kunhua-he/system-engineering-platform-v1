# -*- coding: utf-8 -*-
"""反馈看板 · 页面 —— 只读页面端口：`/` 出前端页，`/api/数据` 出结构化读数。

**只读**：只两档路由，参数**白名单**（页码 / 每页 / 判词 / 任务 / 来源 / 组），**不接任意文件路径、
不接 SQL**；取数一律走 `取数.取数`（`mode=ro` 只读事务）。**不写库、不落盘**。
**复用**：起服务的写法照 `开发工具/信息核心/只读查看服务.py`（同一套 `ThreadingHTTPServer` 只读端口）。
"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import 取数

页面件名 = "看板.html"
接口路径 = "/api/数据"
整数参数 = ("页码", "每页")
文本参数 = ("判词", "任务", "来源", "组")


def 页面文件() -> Path:
    return Path(__file__).resolve().parent / 页面件名


def 读参数(查询表: dict) -> dict:
    """查询串 ⇒ 取数认的参数表（白名单；整数列解析失败即丢）。"""
    取值 = {参数名: 值表[0] for 参数名, 值表 in 查询表.items() if 值表}
    参数表 = {}
    for 参数名 in 文本参数:
        if 取值.get(参数名):
            参数表[参数名] = 取值[参数名]
    for 参数名 in 整数参数:
        if str(取值.get(参数名, "")).isdigit():
            参数表[参数名] = int(取值[参数名])
    return 参数表


class 看板处理器(BaseHTTPRequestHandler):
    """只读路由：`/` 与 `/api/数据`；其余 404。不读任意文件、不跑 SQL。"""

    def do_GET(self):
        # 请求行按 latin-1 解出 ⇒ 原始 UTF-8 字节要先还原，再 `unquote` 解百分号（两种客户端都收）。
        原始路径 = self.path
        try:
            原始路径 = 原始路径.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
        请求地址 = urlparse(unquote(原始路径))
        if 请求地址.path == 接口路径:
            载荷 = 取数.取数(self.server.仓根, 读参数(parse_qs(请求地址.query)))
            self._回JSON(载荷)
        elif 请求地址.path in ("/", "/index.html"):
            self._回页面()
        else:
            self.send_error(404, "no route")

    def _回页面(self):
        页面路径 = 页面文件()
        if not 页面路径.is_file():
            self._回文本("看板.html 不在：%s" % 页面路径, 500)
            return
        self._回字节(页面路径.read_bytes(), "text/html; charset=utf-8")

    def _回JSON(self, 载荷: dict):
        self._回字节(json.dumps(载荷, ensure_ascii=False).encode("utf-8"),
                  "application/json; charset=utf-8")

    def _回文本(self, 提示文本: str, 状态码: int):
        self._回字节(提示文本.encode("utf-8"), "text/plain; charset=utf-8", 状态码)

    def _回字节(self, 应答体: bytes, 内容型: str, 状态码: int = 200):
        self.send_response(状态码)
        self.send_header("Content-Type", 内容型)
        self.send_header("Content-Length", str(len(应答体)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(应答体)

    def log_message(self, *日志字段):
        pass


class 看板服务(ThreadingHTTPServer):
    """带仓根的 HTTP 服务（仓根给取数读唯一台账）。"""

    def __init__(self, 请求地址, 处理器, 仓根目录):
        super().__init__(请求地址, 处理器)
        self.仓根 = 仓根目录


def 起服务(监听端口: int, 仓根目录=None) -> None:
    """起只读看板端口（**永不返回**）。仓根默认取当前工作目录（唯一台账相对它定位）。"""
    仓根 = Path(仓根目录) if 仓根目录 else Path.cwd()
    服务 = 看板服务(("127.0.0.1", 监听端口), 看板处理器, 仓根)
    print("反馈看板：http://127.0.0.1:%d/　（只读 · Ctrl-C 退）" % 监听端口)
    服务.serve_forever()
