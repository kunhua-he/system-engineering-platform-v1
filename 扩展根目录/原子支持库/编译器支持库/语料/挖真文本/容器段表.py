# -*- coding: utf-8 -*-
"""挖真文本 · 容器段表 —— 从字节流里解出「段表」并按偏移定位所属段（硬证据的容器面）。"""
from .常量 import CONST_RE, HDR, HDR_END


# ── 容器段表 ──────────────────────────────────────────────────────────────
def seg_table(b):
    out, i = [], 0
    while True:
        j = b.find(HDR, i)
        if j < 0:
            break
        t = b[j + 0x0B]
        if b[j + 8:j + 0x0B] == HDR_END and b[j + 0x27:j + 0x2A] == HDR_END and t:
            nm = b[j + 0x0C:j + 0x27]
            key = bytes([0x73, 0x00, t, 0x19])
            dec = bytes(nm[k] ^ key[k % 4] for k in range(len(nm)))
            try:
                out.append((j, t, dec.split(b"\x00")[0].decode("gbk")))
            except UnicodeDecodeError:
                pass
        i = j + 1
    out.sort()
    return out


def seg_of(tab, off):
    cur = None
    for st, t, n in tab:
        if st <= off:
            cur = (st, t, n)
        else:
            break
    return cur


def const_name(b, off, back=4096):
    best = None
    for m in CONST_RE.finditer(b, max(0, off - back), off):
        try:
            best = (m.start(), m.group(1).decode("gbk"))
        except UnicodeDecodeError:
            continue
    return best
