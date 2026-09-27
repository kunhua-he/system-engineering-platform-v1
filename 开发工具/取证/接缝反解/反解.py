# -*- coding: utf-8 -*-
"""反解 —— 读文件 → LIB_INFO 结构 + 各表（原 `接缝反解.py::反解`，纯搬家）。"""

import struct

from .常量 import 库信息大小, 库格式号, 库信息字段, 命令项大小, 命令字段
from .接缝 import 解接缝
from .字段 import 读字段, 解表
from .形状 import PE, 解析错误
from .物理槽 import 探物理槽数


def 反解(路径):
    with open(路径, "rb") as fh:
        数据 = fh.read()
    pe = PE(数据, 路径)
    序号, 导出rva, 机器码, 结构rva, 形式 = 解接缝(pe)
    so = pe.转偏移(结构rva)
    if so + 库信息大小 > len(pe.原始字节):
        raise 解析错误("结构 @RVA 0x%x 越界（需 %d 字节）" % (结构rva, 库信息大小))
    字段 = 读字段(pe, so, 库信息字段)
    字典 = {字段项[2]: 字段项[4] for 字段项 in 字段}
    if 字典["m_dwLibFormatVer"] != 库格式号:
        raise 解析错误("格式号 0x%08x != 0x%08x —— 这不是易语言支持库的 LIB_INFO，拒绝解读"
                    % (字典["m_dwLibFormatVer"], 库格式号))
    命令 = 解表(pe, 字典["m_nCmdCount"], 字典["m_pBeginCmdInfo"], 命令项大小, 命令字段)
    函数 = []
    if 字典["m_pCmdsFunc"] and 字典["m_nCmdCount"]:
        函数表偏移 = pe.转偏移(pe.取址(字典["m_pCmdsFunc"]))
        函数 = list(struct.unpack_from("<%dI" % 字典["m_nCmdCount"], pe.原始字节, 函数表偏移))
    return {"路径": 路径, "字节数": len(数据), "pe": pe, "序号": 序号, "导出rva": 导出rva, "机器码": 机器码,
            "形式": 形式, "结构rva": 结构rva, "字段": 字段, "字典": 字典, "命令": 命令, "函数": 函数,
            "物理槽": 探物理槽数(pe, 字典)}
