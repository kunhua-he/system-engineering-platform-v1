# -*- coding: utf-8 -*-
# 命令行 —— 参数解析与分派（原 `带高.py::main`，纯搬家）。
# 下面那段字符串是**原入口的用法文本**，逐字保留：`main` 无参时 `print(__doc__)` 打的正是它，
# 搬进本件后 `__doc__` 取本件的字符串 ⇒ 输出逐字不变（注释在 docstring 之前不影响 `__doc__`）。
"""带高 —— 逐行主导色换色，数每条带的高度。只用标准库 + PIL。
用法：python3 带高.py 图1 [图2 ...]   退出码：0 = 出完读数。
"""

import sys

from .逐行 import 带


def main(argv):
    if len(argv) < 1:
        print(__doc__)
        return 1
    for 参数 in argv:
        try:
            带(参数)
        except OSError as 错:
            print(f"打不开 {参数}：{错}", file=sys.stderr)
            return 1
    return 0
