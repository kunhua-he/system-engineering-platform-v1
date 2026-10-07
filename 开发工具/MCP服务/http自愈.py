# -*- coding: utf-8 -*-
"""HTTP 请求间隙重载：连接排空后预检真入口，监听描述符跨 exec 保留。"""
import json
import os
import socket
import sys

from . import 自愈预检, 服务指纹
from .协议 import _重启参数

监听环境键 = "V1_MCP_HTTP_LISTENER"


def 接续监听(监听地址):
    """只接收匹配环回地址的 TCP 监听描述符；坏描述符启动失败。"""
    监听记录 = os.environ.pop(监听环境键, None)
    if 监听记录 is None:
        return None, None
    监听记录 = json.loads(监听记录)
    监听描述符 = 监听记录["描述符"]
    if type(监听描述符) is not int or 监听描述符 < 3:
        raise ValueError("监听描述符非法")
    监听套接字 = socket.socket(fileno=监听描述符)
    if (监听套接字.family != socket.AF_INET
            or 监听套接字.type != socket.SOCK_STREAM
            or tuple(监听套接字.getsockname()) != tuple(监听记录["地址"])
            or tuple(监听套接字.getsockname()) != tuple(监听地址)
            or 监听地址[0] != "127.0.0.1"):
        raise ValueError("继承描述符不是指定环回 TCP 监听器")
    监听套接字.setblocking(False)
    try:
        待接请求 = 监听套接字.accept()
        待接请求[0].setblocking(True)
    except BlockingIOError:
        待接请求 = None
    finally:
        监听套接字.setblocking(True)
    监听套接字.set_inheritable(False)
    return 监听套接字, 待接请求


def 拒绝重载(服务对象, 当前指纹, 说明):
    """同一失败版本不反复执行预检或 exec，旧服务继续接请求。"""
    服务对象._拒绝指纹 = 当前指纹
    服务对象._重载提示 = "HTTP 新版重载未通过，继续旧服务：%s" % 说明
    print(json.dumps({"event": "mcp.http.selfheal.rejected", "指纹": 当前指纹,
                      "原因": 说明}, ensure_ascii=False), file=sys.stderr, flush=True)


def 尝试重载(服务对象):
    """由唯一 accept 循环调用；预检期间排队连接仍留在原监听器。"""
    if not 服务对象._允许重载:
        return
    with 服务对象._连接锁:
        if 服务对象._在途连接:
            return
    当前指纹 = 服务指纹.算服务指纹()
    if 当前指纹 in (服务指纹.启动指纹, 服务对象._拒绝指纹):
        return
    入口路径 = 服务对象.仓根 / "开发工具" / "MCP服务_http.py"
    通过, 说明 = 自愈预检.预检入口(入口路径, 服务对象.仓根)
    if not 通过:
        拒绝重载(服务对象, 当前指纹, 说明)
        return
    if 服务指纹.算服务指纹() != 当前指纹:
        return
    监听套接字 = 服务对象.socket
    原继承值 = 监听套接字.get_inheritable()
    原环境值 = os.environ.get(监听环境键)
    try:
        监听套接字.set_inheritable(True)
        os.environ[监听环境键] = json.dumps({"描述符": 监听套接字.fileno(),
                                          "地址": list(服务对象.server_address)})
        print(json.dumps({"event": "mcp.http.selfheal.exec", "指纹": 当前指纹},
                         ensure_ascii=False), file=sys.stderr, flush=True)
        sys.stdout.flush()
        os.execv(sys.executable, _重启参数())
    except OSError as 错误:
        拒绝重载(服务对象, 当前指纹, "exec 失败：%s" % 错误)
    finally:
        监听套接字.set_inheritable(原继承值)
        if 原环境值 is None:
            os.environ.pop(监听环境键, None)
        else:
            os.environ[监听环境键] = 原环境值
