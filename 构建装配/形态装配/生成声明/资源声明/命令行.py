# -*- coding: utf-8 -*-
"""资源声明 · 命令行 —— 用法行 · 帮助文本 · 主资源声明(参数)（三档退出码）。

三档退出码（与 `生成声明.py` 同一条口径）：**0 一致 · 1 不新鲜（只从 `--检查` 来）·
2 生成失败**（fail-closed，产物未动）。
"""

import sys

from ..路径形状 import 生成失败
from .路径与枚举 import 生成器相对路径, 建资源根
from .落盘 import 生成资源声明, 检查资源声明

用法文本 = "用法：python3 %s [--声明根 <目录>] [--检查]" % 生成器相对路径


def 帮助文本():
    return [
        用法文本,
        "",
        "  --声明根 <目录>  一份资源声明的根。源 = <目录>/资源声明/*.json，",
        "                  落点 = <目录>/src/资源声明.rs（src/ 必须已存在）。只认仓内相对路径。",
        "  --检查          重新生成到内存，与落盘件逐字节比对（0 新鲜 / 1 不新鲜），不落盘。",
        "  -h / --帮助      本说明。",
        "",
        "不带参数 = 默认声明根（当前没有默认的资源声明根，故必须显式给 --声明根）。",
    ]


def 资源声明入口(参数):
    声明根参数 = None
    检查模式 = False
    未知 = []
    序号 = 0
    while 序号 < len(参数):
        参数词 = 参数[序号]
        if 参数词 == "--检查":
            检查模式 = True
        elif 参数词 in ("-h", "--帮助"):
            for 源码行 in 帮助文本():
                print(源码行)
            return 0
        elif 参数词 == "--声明根":
            if 序号 + 1 >= len(参数):
                print("--声明根 后面要跟一个目录", file=sys.stderr)
                print(用法文本, file=sys.stderr)
                return 2
            序号 += 1
            声明根参数 = 参数[序号]
        elif 参数词.startswith("--声明根="):
            声明根参数 = 参数词.split("=", 1)[1]
        else:
            未知.append(参数词)
        序号 += 1
    if 未知:
        print("不认的参数：%s" % " ".join(sorted(未知)), file=sys.stderr)
        print(用法文本, file=sys.stderr)
        return 2
    if 声明根参数 is None:
        print("必须给 --声明根（资源声明没有默认根）", file=sys.stderr)
        print(用法文本, file=sys.stderr)
        return 2
    try:
        根目录 = 建资源根(声明根参数)
        if 检查模式:
            return 检查资源声明(根目录)
        return 生成资源声明(根目录)
    except 生成失败 as 错误:
        print("生成失败（fail-closed，产物未动）：%s" % 错误, file=sys.stderr)
        return 2
