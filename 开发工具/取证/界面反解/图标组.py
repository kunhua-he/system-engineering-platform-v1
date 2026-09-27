# -*- coding: utf-8 -*-
"""图标组 —— 类型 12/14 ICONDIR + 条目（原 `界面反解.py::解图标组`，纯搬家）。"""

import struct

from PE形状 import 解析错误


def 解图标组(组字节, 资源id, 是光标):
    if len(组字节) < 6:
        raise 解析错误("%s组 %s 短于 ICONDIR" % ("光标" if 是光标 else "图标", 资源id))
    保留, 类型, 数 = struct.unpack_from("<HHH", 组字节, 0)
    期望 = 2 if 是光标 else 1
    if 类型 != 期望:
        raise 解析错误("%s组 %s 的 type=%d != %d" % ("光标" if 是光标 else "图标", 资源id, 类型, 期望))
    if 数 == 0 or 6 + (14 if 是光标 else 14) * 数 > len(组字节):
        raise 解析错误("%s组 %s 声明 %d 条，条目区越界" % ("光标" if 是光标 else "图标", 资源id, 数))
    一条 = []
    for 条序 in range(数):
        项起 = 6 + 14 * 条序
        if 是光标:
            宽, 高, 平面, 位深, 字节, rid = struct.unpack_from("<HHHHIH", 组字节, 项起)
            色数 = None
        else:
            宽, 高, 色数, _, 平面, 位深, 字节, rid = struct.unpack_from("<BBBBHHIH", 组字节, 项起)
        if 字节 == 0:
            raise 解析错误("%s组 %s 第 %d 条字节数为 0" % ("光标" if 是光标 else "图标", 资源id, 条序))
        一条.append({"宽": 宽, "高": 高, "色数": 色数, "平面": 平面, "位深": 位深, "字节": 字节, "id": rid})
    return {"类型": 类型, "条": 一条}
