# -*- coding: utf-8 -*-
"""全语料 —— 扫整个语料目录的硬读数。"""

import glob
import os

from .公共 import 解析错误
from .段数据层 import 取声明记录区
from .记录层 import 走记录


def 扫全部(目录):
    """全语料读数 —— 本腿的**唯一硬读数**。"""
    文件 = sorted(set(glob.glob(os.path.join(目录, "**", "*.e"), recursive=True)
                    + glob.glob(os.path.join(目录, "**", "*.ec"), recursive=True)
                    + glob.glob(os.path.join(目录, "**", "*.E"), recursive=True)
                    + glob.glob(os.path.join(目录, "**", "*.EC"), recursive=True)))
    段数 = 首4零 = 全零 = 0
    区长 = []
    计 = {}
    未解总 = 字节总 = 0
    坏 = []
    for p in 文件:
        try:
            with open(p, "rb") as fh:
                d = fh.read()
            区表 = 取声明记录区(d)
        except 解析错误 as ex:
            坏.append((p, str(ex)))
            continue
        for _, _, _, q, _ in 区表:
            段数 += 1
            区长.append(len(q))
            if len(q) >= 4 and q[:4] == b"\x00\x00\x00\x00":
                首4零 += 1
            if not any(q):
                全零 += 1
            记录, 未解 = 走记录(q)
            for x in 记录:
                计[x["种类"]] = 计.get(x["种类"], 0) + 1
            未解总 += 未解
            字节总 += len(q)
    区长.sort()
    print("=" * 78)
    print("全语料 %s：文件 %d · 程序段 %d · 解析失败 %d" % (目录, len(文件), 段数, len(坏)))
    if 坏:
        for p, e in 坏[:5]:
            print("   失败样例 %s：%s" % (p, e))
    print("声明记录区长度：min %d · 中位 %d · max %d" % (区长[0], 区长[len(区长) // 2], 区长[-1]))
    print("头 4 字节恒 0：%d / %d" % (首4零, 段数))
    print("整区全零（空程序）：%d / %d" % (全零, 段数))
    for k in ("串记录", "语句字节码", "DLL命令记录", "数据类型码"):
        print("可证记录 %-12s %d 条" % (k, 计.get(k, 0)))
    print("可证记录覆盖字节 %d / %d（%.2f%%）；其余 %d 字节（%.2f%%）**不判**"
          % (字节总 - 未解总, 字节总, 100.0 * (字节总 - 未解总) / 字节总,
             未解总, 100.0 * 未解总 / 字节总))
    return 0
