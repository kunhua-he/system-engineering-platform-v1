# -*- coding: utf-8 -*-
"""扫全部 —— 全目录「计数自洽性」扫描（原 `接缝反解.py::扫全部`，纯搬家）。"""

import glob
import os

from .常量 import 命令项大小
from .反解 import 反解
from .形状 import PE, 解析错误
from .物理槽 import 计数判定


def 扫全部(目录):
    print("全树 %s：导出面 · 声明数 m_nCmdCount vs 物理槽数 (funcPtr-cmdPtr)/%d" % (目录, 命令项大小))
    print("%-24s %5s %6s %8s  %s" % ("文件", "导出", "声明", "物理槽", "判"))
    不齐, 未判, 分布, 总 = [], [], {}, 0
    for p in sorted(glob.glob(os.path.join(目录, "**", "*.fne"), recursive=True)):
        总 += 1
        try:
            ex = PE(open(p, "rb").read(), p).导出(); 分布[len(ex)] = 分布.get(len(ex), 0) + 1
            r = 反解(p); n = r["字典"]["m_nCmdCount"]; s, 多 = r["物理槽"]; 判 = 计数判定(r)
            print("%-24s %5d %6d %8s  %s" % (os.path.basename(p), len(ex), n, "不适用" if s is None else s, 判))
            if 判 == "不齐":
                不齐.append((os.path.basename(p), n, s, 多[0][2]))
        except 解析错误 as ex:
            print("%-24s %5s %6s %8s  未判：%s" % (os.path.basename(p), "?", "-", "-", str(ex)[:34]))
            未判.append(os.path.basename(p))
    print("共 %d 个 .fne · 齐 %d · 不齐 %d · 未判 %d · 导出个数分布 %s"
          % (总, 总 - len(不齐) - len(未判), len(不齐), len(未判), dict(sorted(分布.items()))))
    print("不齐清单（文件, 声明数, 物理槽数, 表外第一槽名）：%s" % 不齐)
    print("未判清单：%s" % 未判)
    return 0
