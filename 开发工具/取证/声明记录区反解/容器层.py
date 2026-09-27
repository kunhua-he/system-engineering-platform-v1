# -*- coding: utf-8 -*-
"""容器层 —— `.e` / `.ec` 容器的段表反解（段边界靠扫描，本格式无段长字段）。"""

from .公共 import (
    魔数, 段头长度, 段头魔术甲, 段头魔术乙, 段类型白名单,
    段类型_无名七, 段类型_程序加固, 解析错误,
)

# ── 容器层 ────────────────────────────────────────────────────────────────────

def 是段头(d, pos):
    """段头结构是否成立。判据与 `src/容器/反解定义.rs::是段头起点` 一致。"""
    if pos + 段头长度 > len(d):
        return False
    h = d[pos:pos + 段头长度]
    if h[0:2] != 段头魔术甲 or h[2:4] != 段头魔术乙:
        return False
    if h[8:10] != 段头魔术甲 or h[10] != 0x00:
        return False
    号 = h[11]
    if 号 not in 段类型白名单:
        return False
    尾 = h[0x27:0x2C]
    if 号 == 段类型_无名七:
        return 尾 == b"\x00\x00\x00\x00\x00"
    if 号 == 段类型_程序加固:
        return 尾 == b"\x19\x73\x00\x03\x00"
    return 尾 == b"\x19\x73\x00\x00\x00"


def 找下一段头(d, 起点):
    for p in range(起点, len(d) - 段头长度 + 1):
        if 是段头(d, p):
            return p
    return None


def 反解容器(d):
    """容器字节 → [(段类型, 段数据起点, 段数据止, 段头起点)]。段边界靠扫描（本格式无段长字段）。"""
    if len(d) < len(魔数) or d[:len(魔数)] != 魔数:
        raise 解析错误("无 CNWTEPRG 魔数，不是易程序容器")
    pos, 段 = len(魔数), []
    while pos < len(d):
        if len(d) - pos < 段头长度:
            raise 解析错误("段头截断 @0x%x（剩 %d 字节）" % (pos, len(d) - pos))
        if not 是段头(d, pos):
            raise 解析错误("段头标记/类型号不符 @0x%x" % pos)
        号 = d[pos + 11]
        下一 = 找下一段头(d, pos + 段头长度)
        尾 = 下一 if 下一 is not None else len(d)
        段.append((号, pos + 段头长度, 尾, pos))
        if 下一 is None:
            break
        pos = 下一
    return 段
