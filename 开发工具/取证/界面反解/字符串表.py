# -*- coding: utf-8 -*-
"""字符串表 —— 类型 6 每块 ≤16 条、每条 WORD 字符数（原 `界面反解.py::解字符串表`，纯搬家）。"""

import struct

from PE形状 import 解析错误


def 解字符串表(块字节, 块id):
    游标, 字节串 = 0, []
    for 条序 in range(16):
        if 游标 >= len(块字节):
            break
        if 游标 + 2 > len(块字节):
            raise 解析错误("字符串块 %s 第 %d 条长度字段越界 @0x%x" % (块id, 条序, 游标))
        串长 = struct.unpack_from("<H", 块字节, 游标)[0]
        游标 += 2
        if 串长 == 0:
            字节串.append("")
            continue
        if 游标 + 2 * 串长 > len(块字节):
            raise 解析错误("字符串块 %s 第 %d 条声明 %d 字符越界" % (块id, 条序, 串长))
        字节串.append(块字节[游标:游标 + 2 * 串长].decode("utf-16le").rstrip("\0"))
        游标 += 2 * 串长
    if 游标 != len(块字节):
        raise 解析错误("字符串块 %s 消耗 %d != 声明 %d" % (块id, 游标, len(块字节)))
    return 字节串
