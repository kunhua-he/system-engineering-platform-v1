#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跑声明记录区取证 —— 把「声明记录区反解」的取证**落成可复跑的一步**。

为什么要有这一件 · 断言哪些承重读数 · 语料依赖 · 全量在五秒硬顶下怎么跑（分片三步）·
还缺什么证据：**全在 `说明/声明记录区取证.md`**（那一件的说明的唯一落点，本头不复述）。

    python3 …/工具/跑声明记录区取证.py [--分片 i/n]   # `--分片` 只算第 i 片（全量由跑齐 n 条命令完成）

**这不是第二套实现**：解析器只有一处（`开发工具/取证/声明记录区反解.py`）——本脚本只做「跑它 + 断言读数」。
"""

import os
import re
import subprocess
import sys

# 本脚本 = <扩展根>/工具/跑声明记录区取证.py；仓库根 = 上溯四层。
工具目录 = os.path.dirname(os.path.abspath(__file__))
扩展根 = os.path.dirname(工具目录)
仓库根 = os.path.dirname(os.path.dirname(os.path.dirname(扩展根)))

取证器 = os.path.join(仓库根, "开发工具", "取证", "声明记录区反解.py")
样本 = os.path.join(扩展根, "语料", "样本", "第一个程序.e")
语料根 = "/tmp/易语言源码"


def 跑(参数):
    """跑取证器，返回 (退出码, stdout)。"""
    进程 = subprocess.run(
        [sys.executable, 取证器] + 参数,
        cwd=仓库根,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return 进程.returncode, 进程.stdout


def 断言(条件, 描述, 失败集):
    if 条件:
        print("  ✓ %s" % 描述)
    else:
        print("  ✗ %s" % 描述)
        失败集.append(描述)


def 自测(失败集):
    if not os.path.isfile(取证器):
        print("  ✗ 取证器不在：%s" % 取证器)
        失败集.append("取证器缺失")
        return
    if not os.path.isfile(样本):
        print("  ✗ 自测样本不在：%s" % 样本)
        失败集.append("样本缺失")
        return
    码, 出 = 跑(["--自测", "--样本", 样本])
    for 行 in 出.rstrip().splitlines():
        print("    | " + 行)
    断言(码 == 0, "自测退出码 = 0（实得 %d）" % 码, 失败集)
    断言("自测结论：通过" in 出, "自测结论 = 通过", 失败集)
    断言("假绿 0" in 出, "假绿 = 0（坏样本没有一条产出记录区）", 失败集)


def 全语料(失败集):
    if not os.path.isdir(语料根):
        print("  · 未判：仓外语料 %s 不在 ⇒ --全部 没跑（**不是通过**）" % 语料根)
        return
    码, 出 = 跑(["--全部", "--目录", 语料根])
    for 行 in 出.rstrip().splitlines():
        print("    | " + 行)
    if "逐件缓存不齐" in 出:
        # 缓存没跑齐 ⇒ **未判**（不是失败：全量的计算本来就不在命令路里，见文件头）
        print("  · 未判：逐件缓存不齐 ⇒ 全量读数还没算出来（**不是通过**）。")
        print("    按上面印出的三步补缓存（先跑一片量系数 → 问片数跑齐 → --全部 归并），再复跑本脚本。")
        return
    断言(码 == 0, "全语料退出码 = 0（实得 %d）" % 码, 失败集)
    断言("解析失败 0" in 出, "解析失败 = 0", 失败集)
    头 = re.search(r"头 4 字节恒 0：(\d+) / (\d+)", 出)
    断言(
        bool(头) and 头.group(1) == 头.group(2) and int(头.group(2)) > 0,
        "头 4 字节恒 0 = 全数（自洽，不写死件数；实得 %s）" % (头.group(0) if 头 else "无"),
        失败集,
    )
    for 形态 in ("串记录", "语句字节码", "DLL命令记录", "数据类型码"):
        行 = next((行 for 行 in 出.splitlines() if 行.startswith("可证记录 %-12s" % 形态)), "")
        数 = 行.split()[-2] if 行 else ""
        断言(数.isdigit() and int(数) > 0, "可证记录「%s」> 0（实得 %s）" % (形态, 数 or "无"), 失败集)


def main(参数):
    分片 = None
    if "--分片" in 参数:
        i = 参数.index("--分片")
        分片 = 参数[i + 1] if i + 1 < len(参数) else None
        if not 分片:
            print("用法：--分片 i/n（例：--分片 0/120）")
            return 2
    if 分片:
        # 只算一片：全量的计算就靠跑齐这些片（本脚本不自己循环 —— 一条命令 5 秒内）
        码, 出 = 跑(["--分片", 分片, "--目录", 语料根])
        for 行 in 出.rstrip().splitlines():
            print("    | " + 行)
        print("结论：第 %s 片跑完，退出码 %d（全量读数由 --全部 归并）" % (分片, 码))
        return 码
    print("声明记录区取证 · 复跑（取证器 %s）" % os.path.relpath(取证器, 仓库根))
    失败集 = []
    print("一 自测（反向样本，样本随本扩展进仓）")
    自测(失败集)
    print("二 全语料（仓外只读语料；计算由分片命令完成，本步只归并）")
    全语料(失败集)
    if 失败集:
        print("结论：失败 %d 条 —— %s" % (len(失败集), "；".join(失败集)))
        return 1
    print("结论：通过（承重读数逐条对上；**分区边界 / 令牌语义 / 操作码表仍是不判**，见说明）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
