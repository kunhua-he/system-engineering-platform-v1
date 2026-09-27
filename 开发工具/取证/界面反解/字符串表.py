# -*- coding: utf-8 -*-
"""字符串表 —— 类型 6 每块 ≤16 条、每条 WORD 字符数（原 `界面反解.py::解字符串表`，纯搬家）。"""

import struct

from .形状 import 解析错误


def 解字符串表(b, 块id):
    i, 串 = 0, []
    for k in range(16):
        if i >= len(b):
            break
        if i + 2 > len(b):
            raise 解析错误("字符串块 %s 第 %d 条长度字段越界 @0x%x" % (块id, k, i))
        L = struct.unpack_from("<H", b, i)[0]
        i += 2
        if L == 0:
            串.append("")
            continue
        if i + 2 * L > len(b):
            raise 解析错误("字符串块 %s 第 %d 条声明 %d 字符越界" % (块id, k, L))
        串.append(b[i:i + 2 * L].decode("utf-16le").rstrip("\0"))
        i += 2 * L
    if i != len(b):
        raise 解析错误("字符串块 %s 消耗 %d != 声明 %d" % (块id, i, len(b)))
    return 串
