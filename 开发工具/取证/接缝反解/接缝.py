# -*- coding: utf-8 -*-
"""接缝 —— 定位 `GetNewInf` 导出并判定返回值形式（原 `接缝反解.py::解接缝`，纯搬家）。"""

import struct

from .常量 import 导出名
from .形状 import 解析错误


def 解接缝(pe):
    """返回 (序号, 导出RVA, 机器码前8字节, 结构RVA, 形式串)。判不出形式就抛错。"""
    命中 = [导出项 for 导出项 in pe.导出() if 导出项[0] == 导出名]
    if not 命中:
        raise 解析错误("导出表里没有 %s" % 导出名.decode())
    _, 序号, 当前 = 命中[0]
    导出rva = 当前
    码 = pe.d[pe.转偏移(当前):pe.转偏移(当前) + 16]
    形式 = []
    for _ in range(4):                       # 最多跟 4 层 thunk
        if 码[0] in (0xE8, 0xE9) and (码[0] != 0xE8 or 码[5] == 0xC3):
            目标 = 当前 + 5 + struct.unpack_from("<i", 码, 1)[0]
            形式.append(("call" if 码[0] == 0xE8 else "jmp") + " 0x%x" % 目标)
            当前 = 目标
            码 = pe.d[pe.转偏移(当前):pe.转偏移(当前) + 16]
        else:
            break
    if 码[0] == 0xB8 and 码[5] == 0xC3:                       # mov eax, imm32 ; ret
        址 = struct.unpack_from("<I", 码, 1)[0]
        形式.append("mov eax, 0x%08x; ret" % 址)
    elif 码[:2] == b"\x8d\x05":                              # lea eax, [abs32]
        址 = struct.unpack_from("<I", 码, 2)[0]
        形式.append("lea eax, [0x%08x]" % 址)
    elif 码[0] == 0xA1:   # mov eax,[abs32]：取内存槽里的指针，不是返回静态结构首址
        raise 解析错误("形式非「返回静态结构首址」：%s · mov eax,[0x%08x]"
                    % (" · ".join(形式), struct.unpack_from("<I", 码, 1)[0]))
    else:
        raise 解析错误("无法判定返回值形式，机器码前 8 字节：%s（不猜）" % 码[:8].hex(" "))
    结构rva = pe.取址(址)
    if 结构rva is None:
        raise 解析错误("返回值 0x%x 为 NULL" % 址)
    return 序号, 导出rva, 码[:8], 结构rva, " · ".join(形式)
