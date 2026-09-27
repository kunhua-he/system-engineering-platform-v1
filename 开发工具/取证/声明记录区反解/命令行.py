# -*- coding: utf-8 -*-
"""命令行 —— 参数解析与分派（入口文件只调 `主`，本件装全部命令行实现）。"""

import argparse

from .报告 import 出报告
from .全语料 import 扫全部
from .自测 import 自测


def 建解析器():
    ap = argparse.ArgumentParser(description="声明记录区静态反解（只读字节，不执行语料）")
    ap.add_argument("--样本", default="/tmp/易语言源码/lib/krnln/samples/第一个程序.e")
    ap.add_argument("--目录", default="/tmp/易语言源码")
    ap.add_argument("--全部", action="store_true")
    ap.add_argument("--自测", action="store_true")
    ap.add_argument("--转储", action="store_true")
    return ap


def 主(参数):
    a = 建解析器().parse_args(参数)
    if a.自测:
        return 自测(a.样本)
    if a.全部:
        return 扫全部(a.目录)
    return 出报告(a.样本, a.转储)
