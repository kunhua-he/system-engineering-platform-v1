# -*- coding: utf-8 -*-
"""扫全部 —— 全目录「计数自洽性」扫描（原 `接缝反解.py::扫全部`，纯搬家）。"""

import glob
import os

from .常量 import 命令项大小
from .反解 import 反解接缝
from PE形状 import PE, 解析错误
from .物理槽 import 计数判定


def 扫全部(目录路径):
    print("全树 %s：导出面 · 声明数 m_nCmdCount vs 物理槽数 (funcPtr-cmdPtr)/%d" % (目录路径, 命令项大小))
    print("%-24s %5s %6s %8s  %s" % ("文件", "导出", "声明", "物理槽", "判"))
    不齐, 未判, 分布, 总件数 = [], [], {}, 0
    for 样本路径 in sorted(glob.glob(os.path.join(目录路径, "**", "*.fne"), recursive=True)):
        总件数 += 1
        try:
            ex = PE(open(样本路径, "rb").read(), 样本路径).解导出表(); 分布[len(ex)] = 分布.get(len(ex), 0) + 1
            读数 = 反解接缝(样本路径); 声明数 = 读数["字典"]["m_nCmdCount"]; 槽数, 溢出槽表 = 读数["物理槽"]; 判词 = 计数判定(读数)
            print("%-24s %5d %6d %8s  %s" % (os.path.basename(样本路径), len(ex), 声明数, "不适用" if 槽数 is None else 槽数, 判词))
            if 判词 == "不齐":
                不齐.append((os.path.basename(样本路径), 声明数, 槽数, 溢出槽表[0][2]))
        except 解析错误 as ex:
            print("%-24s %5s %6s %8s  未判：%s" % (os.path.basename(样本路径), "?", "-", "-", str(ex)[:34]))
            未判.append(os.path.basename(样本路径))
    print("共 %d 个 .fne · 齐 %d · 不齐 %d · 未判 %d · 导出个数分布 %s"
          % (总件数, 总件数 - len(不齐) - len(未判), len(不齐), len(未判), dict(sorted(分布.items()))))
    print("不齐清单（文件, 声明数, 物理槽数, 表外第一槽名）：%s" % 不齐)
    print("未判清单：%s" % 未判)
    return 0
