# -*- coding: utf-8 -*-
"""加速键 —— 类型 9 ACCEL 8 字节一条（原 `界面反解.py::解加速键`，纯搬家）。"""

import struct

from .格式名称表 import 虚拟键名
from PE形状 import 解析错误


def 解加速键(表字节, 资源id):
    if not 表字节 or len(表字节) % 8:
        raise 解析错误("加速键 %s 长度 %d 不是 8 的整数倍" % (资源id, len(表字节)))
    输出表 = []
    for 项起 in range(0, len(表字节), 8):
        fVirt, 键码, cmd, 填充字段 = struct.unpack_from("<HHHH", 表字节, 项起)
        if fVirt & 0xFF00:
            raise 解析错误("加速键 %s 第 %d 条 fVirt=0x%04x 高字节非 0：对齐判错" % (资源id, 项起 // 8, fVirt))
        标志表 = []
        if fVirt & 0x01:
            标志表.append("FVIRTKEY")
        if fVirt & 0x02:
            标志表.append("FNOINVERT")
        if fVirt & 0x04:
            标志表.append("FSHIFT")
        if fVirt & 0x08:
            标志表.append("FCONTROL")
        if fVirt & 0x10:
            标志表.append("FALT")
        输出表.append({"fVirt": fVirt, "标志": "|".join(标志表) or "0", "键": 键码,
                    "键名": 虚拟键名.get(键码, "0x%02x" % 键码), "命令": cmd})
    return 输出表
