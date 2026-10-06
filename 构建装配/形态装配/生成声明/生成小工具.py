# -*- coding: utf-8 -*-
"""生成小工具 —— 读字节 / 读 JSON / 指纹 / 取字段 / Rust 字面量渲染。

只用 Python 标准库（hashlib · json · math · os · sys）。不许 pip、不许联网。
确定性：所有遍历按编号/键名排序，缩进与换行固定，产物里不含时间戳、绝对路径、随机数。

★ `读JSON件` 的错误策略是**有意的（抛 `生成失败`：把底层 Unicode / JSON 错收成生成器统一错误）**
—— 生成器只认 `生成失败` 这一种失败。与别处同名读器（`形状检查/形状.py` 不吞原样抛 ·
`代码地图/形参面.py` 吞 `OSError` 返空串）**不是同一事实，勿合并**。
"""

import hashlib
import json
import os

from .路径形状 import 仓根, 生成失败


def 读字节(相对路径):
    with open(os.path.join(仓根, 相对路径), "rb") as 句柄:
        return 句柄.read()


def 读JSON件(相对路径):
    try:
        源文本 = 读字节(相对路径).decode("utf-8")
    except UnicodeDecodeError as 错误:
        raise 生成失败("%s 不是合法 UTF-8：%s" % (相对路径, 错误))
    try:
        return json.loads(源文本)
    except json.JSONDecodeError as 错误:
        raise 生成失败("%s 不是合法 JSON：%s" % (相对路径, 错误))


def 源指纹(相对路径):
    """sha256 前 16 位十六进制。"""
    return hashlib.sha256(读字节(相对路径)).hexdigest()[:16]


def 列目录JSON件(相对目录):
    """目录下全部 .json，按文件名升序。返回 [(文件名, 相对路径)]。"""
    绝对目录 = os.path.join(仓根, 相对目录)
    if not os.path.isdir(绝对目录):
        raise 生成失败("目录不存在：%s" % 相对目录)
    名单 = sorted(名字 for 名字 in os.listdir(绝对目录) if 名字.endswith(".json"))
    return [(名字, 相对目录 + "/" + 名字) for 名字 in 名单]


def 取整(容器, 字段键, 来源, 下界值=None, 上界值=None):
    待处理值 = 容器.get(字段键)
    if 待处理值 is None:
        raise 生成失败("%s 缺字段「%s」" % (来源, 字段键))
    if isinstance(待处理值, bool) or not isinstance(待处理值, int):
        raise 生成失败("%s 的「%s」不是整数：%r" % (来源, 字段键, 待处理值))
    if 下界值 is not None and 待处理值 < 下界值:
        raise 生成失败("%s 的「%s」=%d 小于 %d" % (来源, 字段键, 待处理值, 下界值))
    if 上界值 is not None and 待处理值 > 上界值:
        raise 生成失败("%s 的「%s」=%d 大于 %d" % (来源, 字段键, 待处理值, 上界值))
    return 待处理值


def 取串(容器, 字段键, 来源, 允许空=False):
    待处理值 = 容器.get(字段键)
    if 待处理值 is None:
        raise 生成失败("%s 缺字段「%s」" % (来源, 字段键))
    if not isinstance(待处理值, str):
        raise 生成失败("%s 的「%s」不是字符串：%r" % (来源, 字段键, 待处理值))
    if not 允许空 and 待处理值 == "":
        raise 生成失败("%s 的「%s」是空串" % (来源, 字段键))
    return 待处理值


def 取表(容器, 字段键, 来源):
    待处理值 = 容器.get(字段键)
    if 待处理值 is None:
        raise 生成失败("%s 缺字段「%s」" % (来源, 字段键))
    if not isinstance(待处理值, list):
        raise 生成失败("%s 的「%s」不是数组：%r" % (来源, 字段键, 待处理值))
    return 待处理值


def 取逻辑(容器, 字段键, 来源):
    待处理值 = 容器.get(字段键)
    if not isinstance(待处理值, bool):
        raise 生成失败("%s 的「%s」不是逻辑型：%r" % (来源, 字段键, 待处理值))
    return 待处理值


def 是标识符(名字):
    """Rust 与 Python 同用 Unicode 标识符规则（XID_Start/XID_Continue），够用。"""
    return 名字.isidentifier()


def 转字符串字面量(源文本):
    """把文本渲染成 Rust 字符串字面量（含引号）。控制字符走 \\u{..}。"""
    输出缓冲 = ['"']
    for 单字符 in 源文本:
        错误码 = ord(单字符)
        if 单字符 == "\\":
            输出缓冲.append("\\\\")
        elif 单字符 == '"':
            输出缓冲.append('\\"')
        elif 单字符 == "\n":
            输出缓冲.append("\\n")
        elif 单字符 == "\r":
            输出缓冲.append("\\r")
        elif 单字符 == "\t":
            输出缓冲.append("\\t")
        elif 错误码 == 0:
            输出缓冲.append("\\0")
        elif 错误码 < 0x20 or 错误码 == 0x7F:
            输出缓冲.append("\\u{%X}" % 错误码)
        else:
            输出缓冲.append(单字符)
    输出缓冲.append('"')
    return "".join(输出缓冲)


def 注释行(源文本, 缩进=""):
    """单行注释；内部换行折成空格，保证产物行数确定。"""
    平整文本 = " ".join(源文本.split())
    return "%s// %s" % (缩进, 平整文本) if 平整文本 else "%s//" % 缩进


def 版本三元组(容器, 来源):
    """实现/提供版本：**三段 `i32`**（主 · 次 · 构建）。

    段数与宽度照参照实现 `LIB_INFO`（`m_nMajorVersion` + `m_nMinorVersion` +
    `m_nBuildNumber` = 3×i32，`项目文档/设计文档/接缝实测.md` §七.1）。
    2026-09-27 前这里是 4 段 u16（多一个「修订」段），属无理由偏离。
    """
    if not isinstance(容器, dict):
        raise 生成失败("%s 不是对象：%r" % (来源, 容器))
    return tuple(取整(容器, 键名, 来源, -2147483648, 2147483647) for 键名 in ("主", "次", "构建"))


def 版本要求(容器, 来源):
    """要求版本：**两段 `i32`**（主 · 次）—— **无修订段**。

    照参照实现的要求版本（`m_nRqSysMajorVer` + `m_nRqSysMinorVer` = 2×i32，
    `项目文档/设计文档/接缝实测.md` §七.1）。与「提供/实现版本」不同型：
    要求是门槛（两段），提供是三段。
    """
    if not isinstance(容器, dict):
        raise 生成失败("%s 不是对象：%r" % (来源, 容器))
    return tuple(取整(容器, 键名, 来源, -2147483648, 2147483647) for 键名 in ("主", "次"))
