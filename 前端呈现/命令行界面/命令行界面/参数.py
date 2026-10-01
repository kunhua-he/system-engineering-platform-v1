"""参数 —— 端口三档来源（命令行 > 环境变量 > 默认）与本地用法错。"""

import os

from .常量 import 默认端口, 端口环境变量


class 用法错误(Exception):
    """本地参数写错 —— 与后端的业务失败无关。"""


def 取端口(参数: list) -> int:
    """端口：命令行 > 环境变量 > 默认。返回 `(端口, 剩余参数)`。"""
    剩余 = []
    端口 = None
    位置 = 0
    while 位置 < len(参数):
        这项 = 参数[位置]
        if 这项 == "--端口":
            if 位置 + 1 >= len(参数):
                raise 用法错误("--端口 后面要给一个数")
            端口 = 取端口号(参数[位置 + 1])
            位置 += 2
            continue
        if 这项.startswith("--端口="):
            端口 = 取端口号(这项.split("=", 1)[1])
            位置 += 1
            continue
        剩余.append(这项)
        位置 += 1
    if 端口 is not None:
        return 端口, 剩余
    for 名称 in 端口环境变量:
        原值 = os.environ.get(名称)
        if 原值:
            return 取端口号(原值), 剩余
    return 默认端口, 剩余


def 取端口号(原值: str) -> int:
    个数 = int(原值.strip())
    if not (0 < 个数 < 65536):
        raise 用法错误("端口必须在 1–65535：{}".format(原值))
    return 个数
