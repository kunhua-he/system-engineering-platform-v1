# -*- coding: utf-8 -*-
"""出报告 —— 把 `反解` 的读数打成六节文本（原 `接缝反解.py::出报告`，纯搬家）。"""

import struct

from .常量 import (库信息大小, 导出名, 命令项大小, 命令字段, 参数项大小, 参数字段,
                   常量项大小, 常量字段, 类型项大小, 类型字段, 命令状态位, 库状态位)
from .字段 import 解表
from PE形状 import 解析错误


def 出报告(读数):
    字典, pe = 读数["字典"], 读数["pe"]
    基 = pe.转偏移(读数["结构rva"])
    print("=" * 78 + "\n样本 %s（%d 字节）｜ 机器 0x%04x · %d 节 · 魔数 0x%x(PE32) · ImageBase 0x%08x"
          % (读数["路径"], 读数["字节数"], pe.机器, pe.节数, pe.魔数, pe.基址))
    print("  节：" + " ".join("%s[rva %x vsz %x raw %x]" % (节名, 虚址, 虚长, 原址) for 节名, 虚址, 虚长, 原址, _ in pe.节))
    print("① 导出 %s：序号 %d · RVA 0x%x · 前 8 字节 %s ｜ 返回值形式：%s"
          % (导出名.decode(), 读数["序号"], 读数["导出rva"], 读数["机器码"].hex(" "), 读数["形式"]))
    print("   静态结构 RVA 0x%x（文件偏移 0x%x）；原始字节：" % (读数["结构rva"], 基))
    print("     " + pe.原始字节[基:基 + 库信息大小].hex(" "))
    print("② LIB_INFO 逐字段（偏移 · 宽 · 名 · 值 · 可读）：")
    for 偏移, 宽, 名, 类, 值, 读 in 读数["字段"]:
        print("   +0x%02x %2d  %-24s 0x%08x  %s" % (偏移, 宽, 名, 值 & 0xFFFFFFFF, 读))
    print("   m_dwState=0x%08x → %s" % (字典["m_dwState"], " · ".join(
        表值 for 键, 表值 in 库状态位.items() if 字典["m_dwState"] & (1 << 键)) or "（0，无位）"))
    print("③ 字符串表（结构里的 str 类指针指向的串）：")
    for 偏移, 宽, 名, 类, 值, 读 in 读数["字段"]:
        if 类 == "str" and 值:
            print("   +0x%02x  %-22s 0x%08x  %s" % (偏移, 名, 值, 读.split("→", 1)[-1].strip()))
    if 字典["m_nCategoryCount"]:
        文偏移, 类 = pe.转偏移(pe.取址(字典["m_szzCategory"])), []
        for _ in range(字典["m_nCategoryCount"]):
            尾 = pe.原始字节.find(b"\0", 文偏移); 类.append(pe.原始字节[文偏移:尾].decode("gbk", "replace")); 文偏移 = 尾 + 1
        print("   类别表（m_nCategoryCount=%d）：%s" % (字典["m_nCategoryCount"], 类))
    print("④ 命令表：表项 %d 字节 · 声明数 m_nCmdCount=%d · 物理槽数(观察，非解码依据)=%s"
          % (命令项大小, 字典["m_nCmdCount"], 读数["物理槽"][0]))
    print("   表项逐字段偏移：" + " · ".join("%s@+0x%x/%dB" % (名长, 文偏移, 字段宽) for 文偏移, 字段宽, 名长, _ in 命令字段))
    for 序, 文偏移, 字段项 in 读数["命令"]:
        print("   [%2d] @RVA 0x%x %-14s %-24s cat=%2d state=0x%04x(%s) ret=0x%08x argc=%d func=%s"
              % (序, pe.取址(字典["m_pBeginCmdInfo"]) + 序 * 命令项大小, 字段项["m_szName"][1], 字段项["m_szEgName"][1],
                 字段项["m_shtCategory"][0], 字段项["m_wState"][0], "·".join(
                     表值 for 键, 表值 in 命令状态位.items() if 字段项["m_wState"][0] & (1 << 键)) or "无",
                 字段项["m_dtRetValType"][0], 字段项["m_nArgCount"][0],
                 ("0x%08x" % 读数["函数"][序]) if 序 < len(读数["函数"]) else "<无>"))
        for 位次, _, 组读数 in 解表(pe, 字段项["m_nArgCount"][0], 字段项["m_pBeginArgInfo"][0], 参数项大小, 参数字段):
            print("        参数%d %-12s type=0x%08x state=0x%08x default=%d"
                  % (位次, 组读数["m_szName"][1], 组读数["m_dtType"][0], 组读数["m_dwState"][0], 组读数["m_nDefault"][0]))
    for 序, _, 读 in 读数["物理槽"][1]:
        print("   ⚠ 声明数与物理槽数不齐：表外第 %d 槽仍是命令项：%s" % (序, 读))
    print("⑤ 常量表：声明数 m_nLibConstCount=%d" % 字典["m_nLibConstCount"])
    for 序, _, 组读数 in 解表(pe, 字典["m_nLibConstCount"], 字典["m_pLibConst"], 常量项大小, 常量字段):
        print("   [%d] name=%s reserved=%s type=%s text=%s value=%s" % (
            序, 组读数["m_szName"][1], 组读数["m_shtReserved"][1], 组读数["m_shtType"][1], 组读数["m_szText"][1], 组读数["m_dbValue"][1]))
    print("⑥ 类型表：声明数 m_nDataTypeCount=%d" % 字典["m_nDataTypeCount"])
    for 序, _, 组读数 in 解表(pe, 字典["m_nDataTypeCount"], 字典["m_pDataType"], 类型项大小, 类型字段):
        下标 = []
        if 组读数["m_pnCmdsIndex"][0] and 组读数["m_nCmdCount"][0]:
            try:
                下标 = list(struct.unpack_from("<%di" % 组读数["m_nCmdCount"][0], pe.原始字节,
                            pe.转偏移(pe.取址(组读数["m_pnCmdsIndex"][0]))))
            except 解析错误:
                下标 = ["<指向不合法>"]
        print("   [%d] %s eg=%s state=0x%08x 成员命令下标=%s 事件=%d 属性=%d 元素=%d"
              % (序, 组读数["m_szName"][1], 组读数["m_szEgName"][1], 组读数["m_dwState"][0], 下标,
                 组读数["m_nEventCount"][0], 组读数["m_nPropertyCount"][0], 组读数["m_nElementCount"][0]))
    print()
