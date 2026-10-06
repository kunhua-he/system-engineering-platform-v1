"""连接 —— 手写两件：发一条请求、收一条应答（只用标准库）。"""

import sys
import urllib.error
import urllib.parse
import urllib.request

from .常量 import 回环地址, 默认端口, 默认超时秒, 端口环境变量


def 拼请求地址(端口: int, 路径: str) -> str:
    """拼 URL。路径**百分号编码**：接口面路径是非 ASCII，而 HTTP 请求行只许 ASCII
    （`路由.rs` 文件头：浏览器与 fetch 也是这么发的，网关负责解码）。"""
    return "http://{}:{}{}".format(回环地址, 端口, urllib.parse.quote(路径, safe="/"))


def 发请求(端口: int, 方法: str, 路径: str, 体文本: str, 显示请求: bool) -> tuple:
    """发一条请求 → `(状态码, 应答体文本)`。**不解析、不校验**，只搬运。"""
    请求体字节 = 体文本.encode("utf-8") if 体文本 is not None else None
    请求 = urllib.request.Request(拼请求地址(端口, 路径), data=请求体字节, method=方法)
    请求.add_header("Accept", "application/json")
    if 请求体字节 is not None:
        请求.add_header("Content-Type", "application/json; charset=utf-8")
    if 显示请求:
        源码行 = "{} {} HTTP/1.1".format(方法, urllib.parse.quote(路径, safe="/"))
        print("> " + 源码行, file=sys.stderr)
        print("> Host: {}:{}".format(回环地址, 端口), file=sys.stderr)
        if 请求体字节 is not None:
            print("> Content-Length: {}".format(len(请求体字节)), file=sys.stderr)
            print("> {}".format(体文本), file=sys.stderr)
    try:
        with urllib.request.urlopen(请求, timeout=默认超时秒) as 造应答:
            return 造应答.status, 造应答.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as 错误:
        # 4xx 是**协议层**失败（请求本身不合法），体里仍是一份 JSON 说明。
        return 错误.code, 错误.read().decode("utf-8", "replace")


def 报连不上(端口: int, 原因) -> int:
    print("连不上 http://{}:{} —— 接口面没起？".format(回环地址, 端口))
    print("  原因：{}".format(原因))
    print("  端口来源：--端口 > 环境变量 {} > 默认 {}".format(
        " / ".join(端口环境变量), 默认端口))
    return 3
