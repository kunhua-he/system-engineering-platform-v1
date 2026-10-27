"""主流程 —— 命令行入口本体：定基线 → 读两侧 → 数影响面 → 比四栏 → 打印与退出码。"""

import argparse

from .基线口径常量 import 冻结登记相对路径
from .比冻结面 import 取待查串, 比冻结面
from .扫引用 import 数引用件
from .读基线 import 取基线引用, 读基线登记, 读当前登记
from .输出 import 打印四栏


def 入口函数(命令行参数: list) -> int:
    解析器 = argparse.ArgumentParser(description="冻结面变更影响评估（只读）")
    解析器.add_argument("--基线", default="", help="基线 git ref；不给 = 上一次改动冻结登记的提交")
    命名空间 = 解析器.parse_args(命令行参数)
    基线引用 = 命名空间.基线.strip() or 取基线引用(冻结登记相对路径)
    if not 基线引用:
        print("基线取不到：git 历史里没有改动过 " + 冻结登记相对路径 + " 的提交")
        return 1
    基线登记, 基线说明 = 读基线登记(基线引用)
    当前登记, 当前说明 = 读当前登记()
    if 基线登记 is None or 当前登记 is None:
        print("读不动：" + (基线说明 or 当前说明))
        return 1
    基线符号, 基线路径 = 取待查串(基线登记)
    当前符号, 当前路径 = 取待查串(当前登记)
    落点清单 = 基线符号 + 当前符号 + 基线路径 + 当前路径
    引用表 = 数引用件(落点清单)
    比对结果 = 比冻结面(基线登记, 当前登记, 引用表)
    打印四栏(基线引用, 比对结果)
    return 1 if 比对结果["越界条目"] else 0
