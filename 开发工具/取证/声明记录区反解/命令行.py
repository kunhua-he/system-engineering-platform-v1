# -*- coding: utf-8 -*-
"""命令行 —— 参数解析与分派（入口文件只调 `主`，本件装全部命令行实现）。"""

import argparse
import sys

from .报告 import 出报告
from .全语料 import 扫全部, 扫一片
from .自测 import 自测


def 建解析器():
    ap = argparse.ArgumentParser(description="声明记录区静态反解（只读字节，不执行语料）")
    ap.add_argument("--样本", default="/tmp/易语言源码/lib/krnln/samples/第一个程序.e")
    ap.add_argument("--目录", default="/tmp/易语言源码")
    ap.add_argument("--全部", action="store_true",
                    help="全量读数：**只归并**已算好的逐件缓存（不自己算 ⇒ 必进顶）；"
                         "缓存不齐时报出缺多少件并非 0")
    ap.add_argument("--分片", default=None, metavar="i/n",
                    help="只算第 i 片（共 n 片）—— 全量由跑齐 n 条分片命令完成（每片一条命令）")
    ap.add_argument("--建议分片数", action="store_true",
                    help="由缓存里的实测毫秒推 n（stdout 只印这个整数，依据走 stderr）")
    ap.add_argument("--进程数", type=int, default=None,
                    help="（已不用：归并是加法、不并行。留作旧调用面兼容）")
    ap.add_argument("--自测", action="store_true")
    ap.add_argument("--转储", action="store_true")
    return ap


def 主(参数):
    a = 建解析器().parse_args(参数)
    if a.自测:
        return 自测(a.样本)
    if a.建议分片数:
        from .分片 import 建议分片数
        from .运行数据根 import 缓存目录
        n, 依据 = 建议分片数(a.目录, 缓存目录())
        print(依据, file=sys.stderr)
        print(n)
        return 0 if n > 0 else 1
    if a.分片:
        from .分片 import 解析分片形
        i, n = 解析分片形(a.分片)
        return 扫一片(a.目录, i, n)
    if a.全部:
        return 扫全部(a.目录, a.进程数)
    return 出报告(a.样本, a.转储)
