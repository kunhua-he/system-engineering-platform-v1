"""命令行参数 —— 端口三档来源（命令行 > 环境变量 > 默认）与本地用法错。"""

import os

from .客户端常量 import 默认端口, 端口环境变量


class 用法错误(Exception):
    """本地参数写错 —— 与后端的业务失败无关。"""


def 取端口(命令行参数: list) -> int:
    """端口：命令行 > 环境变量 > 默认。返回 `(端口, 剩余参数)`。"""
    剩余参数 = []
    监听端口 = None
    参数游标 = 0
    while 参数游标 < len(命令行参数):
        这项 = 命令行参数[参数游标]
        if 这项 == "--端口":
            if 参数游标 + 1 >= len(命令行参数):
                raise 用法错误("--端口 后面要给一个数")
            监听端口 = 取端口号(命令行参数[参数游标 + 1])
            参数游标 += 2
            continue
        if 这项.startswith("--端口="):
            监听端口 = 取端口号(这项.split("=", 1)[1])
            参数游标 += 1
            continue
        剩余参数.append(这项)
        参数游标 += 1
    if 监听端口 is not None:
        return 监听端口, 剩余参数
    for 名称 in 端口环境变量:
        原值 = os.environ.get(名称)
        if 原值:
            return 取端口号(原值), 剩余参数
    return 默认端口, 剩余参数


def 取端口号(原值: str) -> int:
    端口号 = int(原值.strip())
    if not (0 < 端口号 < 65536):
        raise 用法错误("端口必须在 1–65535：{}".format(原值))
    return 端口号
