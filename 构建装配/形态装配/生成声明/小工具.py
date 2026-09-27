# -*- coding: utf-8 -*-
"""小工具 —— 读字节 / 读 JSON / 指纹 / 取字段 / Rust 字面量渲染。

只用 Python 标准库（hashlib · json · math · os · sys）。不许 pip、不许联网。
确定性：所有遍历按编号/键名排序，缩进与换行固定，产物里不含时间戳、绝对路径、随机数。
"""

import hashlib
import json
import os

from .路径形状 import 仓根, 生成失败


def 读字节(相对路径):
    with open(os.path.join(仓根, 相对路径), "rb") as 句柄:
        return 句柄.read()


def 读json(相对路径):
    try:
        文本 = 读字节(相对路径).decode("utf-8")
    except UnicodeDecodeError as 错:
        raise 生成失败("%s 不是合法 UTF-8：%s" % (相对路径, 错))
    try:
        return json.loads(文本)
    except json.JSONDecodeError as 错:
        raise 生成失败("%s 不是合法 JSON：%s" % (相对路径, 错))


def 源指纹(相对路径):
    """sha256 前 16 位十六进制。"""
    return hashlib.sha256(读字节(相对路径)).hexdigest()[:16]


def 列目录json(相对目录):
    """目录下全部 .json，按文件名升序。返回 [(文件名, 相对路径)]。"""
    绝对目录 = os.path.join(仓根, 相对目录)
    if not os.path.isdir(绝对目录):
        raise 生成失败("目录不存在：%s" % 相对目录)
    名单 = sorted(名字 for 名字 in os.listdir(绝对目录) if 名字.endswith(".json"))
    return [(名字, 相对目录 + "/" + 名字) for 名字 in 名单]


def 取整(容器, 键, 来源, 下界=None, 上界=None):
    值 = 容器.get(键)
    if 值 is None:
        raise 生成失败("%s 缺字段「%s」" % (来源, 键))
    if isinstance(值, bool) or not isinstance(值, int):
        raise 生成失败("%s 的「%s」不是整数：%r" % (来源, 键, 值))
    if 下界 is not None and 值 < 下界:
        raise 生成失败("%s 的「%s」=%d 小于 %d" % (来源, 键, 值, 下界))
    if 上界 is not None and 值 > 上界:
        raise 生成失败("%s 的「%s」=%d 大于 %d" % (来源, 键, 值, 上界))
    return 值


def 取串(容器, 键, 来源, 允许空=False):
    值 = 容器.get(键)
    if 值 is None:
        raise 生成失败("%s 缺字段「%s」" % (来源, 键))
    if not isinstance(值, str):
        raise 生成失败("%s 的「%s」不是字符串：%r" % (来源, 键, 值))
    if not 允许空 and 值 == "":
        raise 生成失败("%s 的「%s」是空串" % (来源, 键))
    return 值


def 取表(容器, 键, 来源):
    值 = 容器.get(键)
    if 值 is None:
        raise 生成失败("%s 缺字段「%s」" % (来源, 键))
    if not isinstance(值, list):
        raise 生成失败("%s 的「%s」不是数组：%r" % (来源, 键, 值))
    return 值


def 取逻辑(容器, 键, 来源):
    值 = 容器.get(键)
    if not isinstance(值, bool):
        raise 生成失败("%s 的「%s」不是布尔：%r" % (来源, 键, 值))
    return 值


def 是标识符(名字):
    """Rust 与 Python 同用 Unicode 标识符规则（XID_Start/XID_Continue），够用。"""
    return 名字.isidentifier()


def rust串(文本):
    """把文本渲染成 Rust 字符串字面量（含引号）。控制字符走 \\u{..}。"""
    出 = ['"']
    for 字符 in 文本:
        码 = ord(字符)
        if 字符 == "\\":
            出.append("\\\\")
        elif 字符 == '"':
            出.append('\\"')
        elif 字符 == "\n":
            出.append("\\n")
        elif 字符 == "\r":
            出.append("\\r")
        elif 字符 == "\t":
            出.append("\\t")
        elif 码 == 0:
            出.append("\\0")
        elif 码 < 0x20 or 码 == 0x7F:
            出.append("\\u{%X}" % 码)
        else:
            出.append(字符)
    出.append('"')
    return "".join(出)


def 注释行(文本, 缩进=""):
    """单行注释；内部换行折成空格，保证产物行数确定。"""
    平 = " ".join(文本.split())
    return "%s// %s" % (缩进, 平) if 平 else "%s//" % 缩进


def 版本三元组(容器, 来源):
    if not isinstance(容器, dict):
        raise 生成失败("%s 不是对象：%r" % (来源, 容器))
    return tuple(取整(容器, 键, 来源, 0, 65535) for 键 in ("主", "次", "修订", "构建"))
