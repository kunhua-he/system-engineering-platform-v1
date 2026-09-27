# -*- coding: utf-8 -*-
"""跑声明记录区取证 · 检查 —— 自测（反向样本）与全语料（归并逐件缓存）两条承重读数。"""
import os
import re

from .常量 import 取证器, 样本, 语料根
from .跑取证 import 跑取证, 断言


def 自测(失败集):
    if not os.path.isfile(取证器):
        print("  ✗ 取证器不在：%s" % 取证器)
        失败集.append("取证器缺失")
        return
    if not os.path.isfile(样本):
        print("  ✗ 自测样本不在：%s" % 样本)
        失败集.append("样本缺失")
        return
    码, 出 = 跑取证(["--自测", "--样本", 样本])
    for 行 in 出.rstrip().splitlines():
        print("    | " + 行)
    断言(码 == 0, "自测退出码 = 0（实得 %d）" % 码, 失败集)
    断言("自测结论：通过" in 出, "自测结论 = 通过", 失败集)
    断言("假绿 0" in 出, "假绿 = 0（坏样本没有一条产出记录区）", 失败集)


def 全语料(失败集):
    if not os.path.isdir(语料根):
        print("  · 未判：仓外语料 %s 不在 ⇒ --全部 没跑（**不是通过**）" % 语料根)
        return
    码, 出 = 跑取证(["--全部", "--目录", 语料根])
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
