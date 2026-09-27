# -*- coding: utf-8 -*-
"""字段 —— 结构逐字段读值与表解码（原 `接缝反解.py::读字段/解表`，纯搬家）。"""

import struct

from .常量 import 数值格式
from PE形状 import 解析错误


def 读字段(pe, 基偏移, 表):
    """返回 [(偏移, 宽, 名, 类, 值, 可读串)]。"""
    out = []
    for 偏移, 宽, 名, 类 in 表:
        值起 = 基偏移 + 偏移
        if 值起 + 宽 > len(pe.原始字节):
            raise 解析错误("字段 %s @+0x%x 越界" % (名, 偏移))
        if 类 in 数值格式:
            值 = struct.unpack_from(数值格式[类], pe.原始字节, 值起)[0]
            读 = "%r" % 值 if 类 == "f64" else "%d" % 值
        else:                                                # ptr / str
            值 = pe.读u32(值起); 读 = "0x%08x" % 值
            if 类 == "str" and 值:
                读 += " → %r" % pe.读串(值)     # 指向不合法即抛错：fail-closed，不编串
        out.append((偏移, 宽, 名, 类, 值, 读))
    return out


def 解表(pe, 数, 表址, 项大小, 字段表):
    if 数 <= 0:
        return []
    if not 表址:
        raise 解析错误("声明有 %d 项但表指针为 0 —— 不自洽，不编表" % 数)
    基 = pe.转偏移(pe.取址(表址))
    项 = []
    for 项序 in range(数):
        项起 = 基 + 项序 * 项大小
        if 项起 + 项大小 > len(pe.原始字节):
            raise 解析错误("表项第 %d 项越界（表 @RVA 0x%x）" % (项序, pe.取址(表址)))
        项.append((项序, 项起, {字段项[2]: (字段项[4], 字段项[5]) for 字段项 in 读字段(pe, 项起, 字段表)}))
    return 项
