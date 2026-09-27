# -*- coding: utf-8 -*-
"""字段 —— 结构逐字段读值与表解码（原 `接缝反解.py::读字段/解表`，纯搬家）。"""

import struct

from .常量 import 数值格式
from .形状 import 解析错误


def 读字段(pe, 基偏移, 表):
    """返回 [(偏移, 宽, 名, 类, 值, 可读串)]。"""
    out = []
    for 偏移, 宽, 名, 类 in 表:
        p = 基偏移 + 偏移
        if p + 宽 > len(pe.d):
            raise 解析错误("字段 %s @+0x%x 越界" % (名, 偏移))
        if 类 in 数值格式:
            值 = struct.unpack_from(数值格式[类], pe.d, p)[0]
            读 = "%r" % 值 if 类 == "f64" else "%d" % 值
        else:                                                # ptr / str
            值 = pe.读u32(p); 读 = "0x%08x" % 值
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
    for i in range(数):
        o = 基 + i * 项大小
        if o + 项大小 > len(pe.d):
            raise 解析错误("表项第 %d 项越界（表 @RVA 0x%x）" % (i, pe.取址(表址)))
        项.append((i, o, {f[2]: (f[4], f[5]) for f in 读字段(pe, o, 字段表)}))
    return 项
