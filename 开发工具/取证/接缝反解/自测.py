# -*- coding: utf-8 -*-
"""自测 —— 反向样本断言（判据可信性）（原 `接缝反解.py::自测`，纯搬家）。"""

import os
import struct

from .常量 import 库格式号, 库信息字段, 命令项大小, 命令字段
from .接缝 import 解接缝
from .字段 import 读字段, 解结构表
from PE形状 import PE, 解析错误
from .反解 import 反解接缝


def 跑自测(样本路径="/tmp/易语言源码/lib/shellEx.fne"):
    合格样本 = open(样本路径, "rb").read()
    坏样本表 = [("空文件", b""), ("只有 DOS 头 0x40", 合格样本[:0x40]), ("截断到 PE 头中间", 合格样本[:0xC8]), ("截断到节表中间", 合格样本[:0x1A0]),
          ("整份砍掉后半", 合格样本[:len(合格样本) // 2]), ("随机字节流", bytes(range(256)) * 4), ("无 MZ 签名", b"ZZ" + 合格样本[2:])]
    try:
        pe = PE(合格样本)
        结构偏移 = pe.转偏移(解接缝(pe)[3])
        改例 = [("格式号改成 0", 0x00, b"\0\0\0\0"), ("命令数改成 99（表外）", 0x64, (99).to_bytes(4, "little")),
               ("命令表指针清 0 而计数非 0", 0x68, b"\0\0\0\0"), ("GUID 指针指到镜像外", 0x04, b"\xff\xff\xff\xff"),
               ("命令表指针指向文件尾外", 0x68, (pe.基址 + 0x700000).to_bytes(4, "little"))]
        for 名称, 字段偏移, 待处理值 in 改例:
            样本字节 = bytearray(合格样本); 样本字节[结构偏移 + 字段偏移:结构偏移 + 字段偏移 + 4] = 待处理值
            坏样本表.append((名称, bytes(样本字节)))
        样本字节 = bytearray(合格样本); 文偏移 = pe.转偏移(解接缝(pe)[1]); 样本字节[文偏移:文偏移 + 6] = b"\x0f\x0b\x0f\x0b\x0f\x0b"
        坏样本表.append(("GetNewInf 机器码换成 ud2", bytes(样本字节)))
    except 解析错误 as ex:
        print("警告：好样本自身就解不动（%s），反向样本只跑通用那批" % ex)
    print("自测：喂 %d 个坏样本，断言「报错且不产出字段」" % len(坏样本表))
    失败 = 0
    for 名称, 文件字节 in 坏样本表:
        try:
            pe = PE(文件字节, 名称)
            字典 = {字段项[2]: 字段项[4] for 字段项 in 读字段(pe, pe.转偏移(解接缝(pe)[3]), 库信息字段)}
            if 字典["m_dwLibFormatVer"] != 库格式号:
                raise 解析错误("格式号不符 0x%08x" % 字典["m_dwLibFormatVer"])
            解结构表(pe, 字典["m_nCmdCount"], 字典["m_pBeginCmdInfo"], 命令项大小, 命令字段)
            print("  ✗ %-26s 竟然解析成功 —— 假绿" % 名称); 失败 += 1
        except 解析错误 as ex:
            print("  ✓ %-26s 报错：%s" % (名称, ex))
        except (struct.error, IndexError, ValueError, OverflowError, TypeError) as ex:
            print("  ✗ %-26s 抛了非解析错误（%s: %s）" % (名称, type(ex).__name__, ex)); 失败 += 1
    try:
        print("  ✓ 正向样本 %s 解析成功（命令 %d 条）" % (os.path.basename(样本路径), len(反解接缝(样本路径)["命令"])))
    except 解析错误 as ex:
        print("  ✗ 正向样本反而失败：%s" % ex); 失败 += 1
    print("自测结论：%s（失败 %d）" % ("通过" if 失败 == 0 else "不通过", 失败))
    return 1 if 失败 else 0
