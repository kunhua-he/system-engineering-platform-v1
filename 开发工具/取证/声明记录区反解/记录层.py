# -*- coding: utf-8 -*-
"""记录层 —— 记录级反解（**只证一条记录在不在**，不证分区边界）。"""

import struct

from .公共 import 串长上限, 语句操作码甲, 语句操作码乙, DLL令牌类别, 数据类型掩码

# ── 记录级反解（**只证一条记录在不在**，不证分区边界）────────────────────────────

def 合法GBK(bs):
    """全字节可解 GBK、无 NUL、无控制字符（含 0x7F..0xA0 区）。"""
    if not bs or b"\x00" in bs:
        return False
    try:
        串 = bs.decode("gbk")
    except Exception:
        return False
    for c in 串:
        o = ord(c)
        if o < 0x20 or 0x7F <= o <= 0xA0:
            return False
    return True


def 试串记录(q, i):
    """`u32 串长` + `串长` 字节 GBK + `00`。返回 (记录, 下一位置) 或 None。"""
    if i + 5 > len(q):
        return None
    L = struct.unpack_from("<I", q, i)[0]
    if not (1 <= L <= 串长上限):
        return None
    if i + 4 + L + 1 > len(q) or q[i + 4 + L] != 0x00:
        return None
    if not 合法GBK(q[i + 4:i + 4 + L]):
        return None
    return {"种类": "串记录", "起": i, "止": i + 4 + L + 1, "串长": L,
            "串": q[i + 4:i + 4 + L].decode("gbk")}, i + 4 + L + 1


def 试语句字节码(q, i):
    """`37 1A`/`37 18` + `u32 长度`（**含尾 NUL**）+ 文本。返回 (记录, 下一位置) 或 None。"""
    if i + 7 > len(q) or q[i] != 语句操作码甲 or q[i + 1] not in 语句操作码乙:
        return None
    L = struct.unpack_from("<I", q, i + 2)[0]
    if not (1 <= L <= 1 << 20) or i + 6 + L > len(q):
        return None
    if q[i + 6 + L - 1] != 0x00:
        return None
    if not 合法GBK(q[i + 6:i + 6 + L - 1]):
        return None
    return {"种类": "语句字节码", "起": i, "止": i + 6 + L, "长度": L,
            "文本": q[i + 6:i + 6 + L - 1].decode("gbk")}, i + 6 + L


def 试DLL命令记录(q, i):
    """`u32 L1`+使用名 + `u32 L2`+库名 + `u32 L3`+命令名 + `u32 参数个数` + `u32 保留`
    + 参数个数 × `<u16 号> <u8 甲> <u8 0x45>`。返回 (记录, 下一位置) 或 None。"""
    p, 名表 = i, []
    for _ in ("使用名", "库名", "命令名"):
        if p + 4 > len(q):
            return None
        L = struct.unpack_from("<I", q, p)[0]
        if not (1 <= L <= 256) or p + 4 + L > len(q) or not 合法GBK(q[p + 4:p + 4 + L]):
            return None
        名表.append(q[p + 4:p + 4 + L].decode("gbk"))
        p += 4 + L
    if p + 8 > len(q):
        return None
    N, 保留 = struct.unpack_from("<II", q, p)
    if not (0 <= N <= 64) or p + 8 + N * 4 > len(q):
        return None
    if 保留 > 0xFFFF:                      # 既有件 8 个实测点全 ≤ 0xFF；>0xFFFF 判为误切（fail-closed）
        return None
    参 = q[p + 8:p + 8 + N * 4]
    if any(参[t + 3] != DLL令牌类别 for t in range(0, len(参), 4)):
        return None
    出 = {"种类": "DLL命令记录", "起": i, "止": p + 8 + N * 4, "参数个数": N, "保留": 保留,
          "使用名": 名表[0], "库名": 名表[1], "命令名": 名表[2],
          "号": [struct.unpack_from("<H", 参, t)[0] for t in range(0, len(参), 4)],
          "甲": sorted(set(参[t + 2] for t in range(0, len(参), 4)))}
    return 出, p + 8 + N * 4


def 试数据类型码(q, i):
    """`u32` 且高 16 位 == 0x8000（`sdk/cpp/elib/lib2.h` 的 DATA_TYPE 编码）。"""
    if i + 4 > len(q):
        return None
    v = struct.unpack_from("<I", q, i)[0]
    if v >> 16 != 数据类型掩码:
        return None
    return {"种类": "数据类型码", "起": i, "止": i + 4, "值": v}, i + 4


试法 = (试DLL命令记录, 试语句字节码, 试数据类型码, 试串记录)


def 走记录(q, 起点=0, 止=None):
    """从 `起点` 贪心走：每处依次试四种可证记录形态，命中即收，否则前进 1 字节（记「未解字节」）。

    **只证「某处是一条 X 记录」**；不证分区边界、不证记录头字段语义（那些标 `不判`）。
    """
    止 = len(q) if 止 is None else 止
    i, 记录, 未解 = 起点, [], 0
    while i < 止:
        for 法 in 试法:
            r = 法(q, i)
            if r is not None:
                记录.append(r[0])
                未解 += 0
                i = r[1]
                break
        else:
            未解 += 1
            i += 1
    return 记录, 未解
