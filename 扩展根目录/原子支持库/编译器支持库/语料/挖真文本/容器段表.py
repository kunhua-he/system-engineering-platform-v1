# -*- coding: utf-8 -*-
"""挖真文本 · 容器段表 —— 从字节流里解出「段表」并按偏移定位所属段（硬证据的容器面）。"""
from .常量 import 常量记录正则, 段头魔数, 段头终止


# ── 容器段表 ──────────────────────────────────────────────────────────────
def 段表(字节流):
    out, 扫描位 = [], 0
    while True:
        头位 = 字节流.find(段头魔数, 扫描位)
        if 头位 < 0:
            break
        段型 = 字节流[头位 + 0x0B]
        if 字节流[头位 + 8:头位 + 0x0B] == 段头终止 and 字节流[头位 + 0x27:头位 + 0x2A] == 段头终止 and 段型:
            nm = 字节流[头位 + 0x0C:头位 + 0x27]
            key = bytes([0x73, 0x00, 段型, 0x19])
            dec = bytes(nm[位次] ^ key[位次 % 4] for 位次 in range(len(nm)))
            try:
                out.append((头位, 段型, dec.split(b"\x00")[0].decode("gbk")))
            except UnicodeDecodeError:
                pass
        扫描位 = 头位 + 1
    out.sort()
    return out


def 偏移所属段(tab, off):
    cur = None
    for st, 段型, 段名 in tab:
        if st <= off:
            cur = (st, 段型, 段名)
        else:
            break
    return cur


def 取常量名(字节流, off, back=4096):
    best = None
    for 匹配 in 常量记录正则.finditer(字节流, max(0, off - back), off):
        try:
            best = (匹配.start(), 匹配.group(1).decode("gbk"))
        except UnicodeDecodeError:
            continue
    return best
