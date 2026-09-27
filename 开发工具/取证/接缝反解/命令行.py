# -*- coding: utf-8 -*-
"""命令行 —— 参数解析与分派（原 `接缝反解.py::main`，纯搬家；保持原无参入口形状）。"""

import argparse

from .出报告 import 出报告
from .反解 import 反解
from .扫全部 import 扫全部
from .自测 import 自测


def main():
    ap = argparse.ArgumentParser(description="GetNewInf 接缝静态反解（只读字节，不执行语料）")
    ap.add_argument("--样本", default="/tmp/易语言源码/lib/shellEx.fne")
    ap.add_argument("--目录", default="/tmp/易语言源码")
    ap.add_argument("--全部", action="store_true"); ap.add_argument("--自测", action="store_true")
    参数 = ap.parse_args()
    if not 参数.自测 and not 参数.全部:
        出报告(反解(参数.样本)); return 0
    return (自测(参数.样本) if 参数.自测 else 0) | (扫全部(参数.目录) if 参数.全部 else 0)
