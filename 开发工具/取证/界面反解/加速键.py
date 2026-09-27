# -*- coding: utf-8 -*-
"""加速键 —— 类型 9 ACCEL 8 字节一条（原 `界面反解.py::解加速键`，纯搬家）。"""

import struct

from .常量 import 虚拟键名
from .形状 import 解析错误


def 解加速键(b, 资源id):
    if not b or len(b) % 8:
        raise 解析错误("加速键 %s 长度 %d 不是 8 的整数倍" % (资源id, len(b)))
    out = []
    for i in range(0, len(b), 8):
        fVirt, key, cmd, 垫 = struct.unpack_from("<HHHH", b, i)
        if fVirt & 0xFF00:
            raise 解析错误("加速键 %s 第 %d 条 fVirt=0x%04x 高字节非 0：对齐判错" % (资源id, i // 8, fVirt))
        标 = []
        if fVirt & 0x01:
            标.append("FVIRTKEY")
        if fVirt & 0x02:
            标.append("FNOINVERT")
        if fVirt & 0x04:
            标.append("FSHIFT")
        if fVirt & 0x08:
            标.append("FCONTROL")
        if fVirt & 0x10:
            标.append("FALT")
        out.append({"fVirt": fVirt, "标志": "|".join(标) or "0", "键": key,
                    "键名": 虚拟键名.get(key, "0x%02x" % key), "命令": cmd})
    return out
