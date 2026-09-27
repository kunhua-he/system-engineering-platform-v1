# -*- coding: utf-8 -*-
"""物理槽 —— 命令表「声明数 vs 物理槽数」的观察与判定（原 `接缝反解.py::探物理槽数/计数判定`，纯搬家）。"""

from .常量 import 命令项大小, 命令字段
from .字段 import 读字段
from .形状 import 解析错误


def 探物理槽数(pe, 字典):
    """物理槽数**只是观察**，不参与解码。仅在「两指针都在 · 函数表在命令表之后 ·
    间距是 36 的整数倍」三条同时成立时才有定义；否则 None（未判），绝不硬凑。"""
    if not 字典["m_nCmdCount"] and not 字典["m_pBeginCmdInfo"]:
        return 0, []
    if not (字典["m_pCmdsFunc"] and 字典["m_pBeginCmdInfo"]):
        return None, []
    起, 止 = pe.取址(字典["m_pBeginCmdInfo"]), pe.取址(字典["m_pCmdsFunc"])
    if 止 <= 起 or (止 - 起) % 命令项大小:
        return None, []
    槽数 = (止 - 起) // 命令项大小
    多 = []
    for 命令序 in range(字典["m_nCmdCount"], min(槽数, 字典["m_nCmdCount"] + 16)):
        try:
            字段表 = {字段项[2]: (字段项[4], 字段项[5]) for 字段项 in 读字段(pe, pe.转偏移(起 + 命令序 * 命令项大小), 命令字段)}
            多.append((命令序, 字段表["m_szName"][0], 字段表["m_szName"][1]))
        except 解析错误:
            多.append((命令序, 0, "<解不出命令项>"))
    return 槽数, 多


def 计数判定(读数):
    """齐 / 不齐 / 不适用。**不齐必须有证据**：表外那一槽得真解出一个命令名指针。"""
    声明数, (槽数, 多) = 读数["字典"]["m_nCmdCount"], 读数["物理槽"]
    if 槽数 is None:
        return "不适用"
    if 槽数 == 声明数:
        return "齐"
    return "不齐" if (多 and 多[0][1]) else "不适用（间距不是表扩展）"
