# -*- coding: utf-8 -*-
"""命令行 —— 参数解析与分派（原 `界面反解.py::main`，纯搬家；保持原无参入口形状）。"""

import argparse

from .出报告 import 出报告
from .反解 import 反解
from .自测 import 自测


def main():
    ap = argparse.ArgumentParser(description="e.exe 界面资源静态反解（只读字节，不执行语料）")
    ap.add_argument("--样本", default="/tmp/易语言源码/e.exe")
    ap.add_argument("--自测", action="store_true")
    a = ap.parse_args()
    if a.自测:
        return 自测(a.样本)
    出报告(反解(a.样本))
    return 0
