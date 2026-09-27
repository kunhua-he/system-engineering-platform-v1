# -*- coding: utf-8 -*-
"""资源树 —— 递归走 PE 资源目录到叶子（原 `界面反解.py::走资源树`，纯搬家）。"""

import struct

from .形状 import 解析错误


def 走资源树(pe):
    """递归到叶子，逐层校验：目录必须在 .rsrc 内、层数 ≤ 3、不重入、数据项不越界。"""
    起, 止 = pe.节区间(".rsrc")
    根 = pe.转偏移(pe.资源目录[0])
    if not (起 <= 根 < 止):
        raise 解析错误("资源目录根 RVA 0x%x 不在 .rsrc 内" % pe.资源目录[0])
    叶子, 见过 = [], set()

    def 串(base, off):
        o = base + off
        if o + 2 > len(pe.d):
            raise 解析错误("资源名字符串越界 @0x%x" % o)
        n = pe.读u16(o)
        if o + 2 + 2 * n > len(pe.d):
            raise 解析错误("资源名字符串长度 %d 越界 @0x%x" % (n, o))
        return pe.d[o + 2:o + 2 + 2 * n].decode("utf-16le", "replace")

    def 走(偏移, 路径, 层):
        if 层 > 3:
            raise 解析错误("资源目录层数 > 3（id 表/名字表/语言表三层为上限）")
        if not (起 <= 偏移 and 偏移 + 16 <= 止):
            raise 解析错误("资源目录节点 0x%x 不在 .rsrc[0x%x,0x%x) 内" % (偏移, 起, 止))
        if 偏移 in 见过:
            raise 解析错误("资源目录自指环 @0x%x" % 偏移)
        见过.add(偏移)
        具名数, ID数 = pe.读u16(偏移 + 12), pe.读u16(偏移 + 14)
        项数 = 具名数 + ID数
        if 项数 == 0 or 项数 > 0x4000:
            raise 解析错误("资源目录项数 %d 不合理 @0x%x" % (项数, 偏移))
        for i in range(项数):
            e = 偏移 + 16 + i * 8
            if e + 8 > 止:
                raise 解析错误("资源目录项第 %d 条越界 @0x%x" % (i, e))
            名域, 指域 = pe.读u32(e), pe.读u32(e + 4)
            if 名域 & 0x80000000:
                键 = 串(根, 名域 & 0x7FFFFFFF)
            else:
                键 = 名域
            子 = 根 + (指域 & 0x7FFFFFFF)
            if 指域 & 0x80000000:
                走(子, 路径 + [键], 层 + 1)
            else:
                if not (起 <= 子 and 子 + 16 <= 止):
                    raise 解析错误("资源数据项 0x%x 不在 .rsrc 内" % 子)
                rva, 大小, 代码页, _ = struct.unpack_from("<IIII", pe.d, 子)
                数据偏移 = pe.转偏移(rva)
                if 数据偏移 + 大小 > len(pe.d):
                    raise 解析错误("资源(type=%s id=%s) 数据越界：0x%x+%d" % (路径[0], 键, 数据偏移, 大小))
                全 = 路径 + [键]
                叶子.append({"路径": 全, "类型": 全[0], "id": 全[1], "语言": 全[-1],
                             "rva": rva, "大小": 大小, "代码页": 代码页,
                             "数据项偏移": 子, "数据偏移": 数据偏移})
    走(根, [], 0)
    if not 叶子:
        raise 解析错误("资源目录走到底没有叶子")
    for 叶 in 叶子:
        if len(叶["路径"]) != 3:
            raise 解析错误("资源叶子路径深 %d != 3（类型/id/语言）：目录结构非预期，不猜"
                        % len(叶["路径"]))
    return 叶子
