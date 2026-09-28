# -*- coding: utf-8 -*-
"""记录层 —— 记录级反解（**只证一条记录在不在**，不证分区边界）。"""

import struct

from .公共 import 串长上限, 语句首操作码, 语句次操作码, DLL令牌类别, 数据类型掩码

# ── 记录级反解（**只证一条记录在不在**，不证分区边界）────────────────────────────

def 合法GBK(bs):
    """全字节可解 GBK、无 NUL、无控制字符（含 0x7F..0xA0 区）。"""
    if not bs or b"\x00" in bs:
        return False
    try:
        字节串 = bs.decode("gbk")
    except Exception:
        return False
    for 字符表 in 字节串:
        码点 = ord(字符表)
        if 码点 < 0x20 or 0x7F <= 码点 <= 0xA0:
            return False
    return True


def 试串记录(区字节, 起点位):
    """`u32 串长` + `串长` 字节 GBK + `00`。返回 (记录, 下一位置) 或 None。"""
    if 起点位 + 5 > len(区字节):
        return None
    串长 = struct.unpack_from("<I", 区字节, 起点位)[0]
    if not (1 <= 串长 <= 串长上限):
        return None
    if 起点位 + 4 + 串长 + 1 > len(区字节) or 区字节[起点位 + 4 + 串长] != 0x00:
        return None
    if not 合法GBK(区字节[起点位 + 4:起点位 + 4 + 串长]):
        return None
    return {"种类": "串记录", "起": 起点位, "止": 起点位 + 4 + 串长 + 1, "串长": 串长,
            "串": 区字节[起点位 + 4:起点位 + 4 + 串长].decode("gbk")}, 起点位 + 4 + 串长 + 1


def 试语句字节码(区字节, 起点位):
    """`37 1A`/`37 18` + `u32 长度`（**含尾 NUL**）+ 文本。返回 (记录, 下一位置) 或 None。"""
    if 起点位 + 7 > len(区字节) or 区字节[起点位] != 语句首操作码 or 区字节[起点位 + 1] not in 语句次操作码:
        return None
    串长 = struct.unpack_from("<I", 区字节, 起点位 + 2)[0]
    if not (1 <= 串长 <= 1 << 20) or 起点位 + 6 + 串长 > len(区字节):
        return None
    if 区字节[起点位 + 6 + 串长 - 1] != 0x00:
        return None
    if not 合法GBK(区字节[起点位 + 6:起点位 + 6 + 串长 - 1]):
        return None
    return {"种类": "语句字节码", "起": 起点位, "止": 起点位 + 6 + 串长, "长度": 串长,
            "文本": 区字节[起点位 + 6:起点位 + 6 + 串长 - 1].decode("gbk")}, 起点位 + 6 + 串长


def 试DLL命令记录(区字节, 起点位):
    """`u32 L1`+使用名 + `u32 L2`+库名 + `u32 L3`+命令名 + `u32 参数个数` + `u32 保留`
    + 参数个数 × `<u16 号> <u8 参中字节> <u8 0x45>`。返回 (记录, 下一位置) 或 None。"""
    游标, 名表 = 起点位, []
    for _ in ("使用名", "库名", "命令名"):
        if 游标 + 4 > len(区字节):
            return None
        串长 = struct.unpack_from("<I", 区字节, 游标)[0]
        if not (1 <= 串长 <= 256) or 游标 + 4 + 串长 > len(区字节) or not 合法GBK(区字节[游标 + 4:游标 + 4 + 串长]):
            return None
        名表.append(区字节[游标 + 4:游标 + 4 + 串长].decode("gbk"))
        游标 += 4 + 串长
    if 游标 + 8 > len(区字节):
        return None
    参数个数, 保留 = struct.unpack_from("<II", 区字节, 游标)
    if not (0 <= 参数个数 <= 64) or 游标 + 8 + 参数个数 * 4 > len(区字节):
        return None
    if 保留 > 0xFFFF:                      # 既有件 8 个实测点全 ≤ 0xFF；>0xFFFF 判为误切（fail-closed）
        return None
    参数 = 区字节[游标 + 8:游标 + 8 + 参数个数 * 4]
    if any(参数[参位 + 3] != DLL令牌类别 for 参位 in range(0, len(参数), 4)):
        return None
    结果 = {"种类": "DLL命令记录", "起": 起点位, "止": 游标 + 8 + 参数个数 * 4, "参数个数": 参数个数, "保留": 保留,
          "使用名": 名表[0], "库名": 名表[1], "命令名": 名表[2],
          "号": [struct.unpack_from("<H", 参数, 参位)[0] for 参位 in range(0, len(参数), 4)],
          "参中字节": sorted(set(参数[参位 + 2] for 参位 in range(0, len(参数), 4)))}
    return 结果, 游标 + 8 + 参数个数 * 4


def 试数据类型码(区字节, 起点位):
    """`u32` 且高 16 位 == 0x8000（`sdk/cpp/elib/lib2.h` 的 DATA_TYPE 编码）。"""
    if 起点位 + 4 > len(区字节):
        return None
    裸值 = struct.unpack_from("<I", 区字节, 起点位)[0]
    if 裸值 >> 16 != 数据类型掩码:
        return None
    return {"种类": "数据类型码", "起": 起点位, "止": 起点位 + 4, "值": 裸值}, 起点位 + 4


试法表 = (试DLL命令记录, 试语句字节码, 试数据类型码, 试串记录)


def 走记录(区字节, 起点=0, 区间终点=None):
    """从 `起点` 贪心走：每处依次试四种可证记录形态，命中即收，否则前进 1 字节（记「未解字节」）。

    **只证「某处是一条 X 记录」**；不证分区边界、不证记录头字段语义（那些标 `不判`）。
    """
    区间终点 = len(区字节) if 区间终点 is None else 区间终点
    起点位, 记录, 未解 = 起点, [], 0
    while 起点位 < 区间终点:
        for 试函数 in 试法表:
            试中 = 试函数(区字节, 起点位)
            if 试中 is not None:
                记录.append(试中[0])
                未解 += 0
                起点位 = 试中[1]
                break
        else:
            未解 += 1
            起点位 += 1
    return 记录, 未解
