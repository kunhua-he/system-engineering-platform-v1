# -*- coding: utf-8 -*-
"""建库 · 规则 —— 从各规范件的表 / 编号列表里抽 `规则` 表的行。"""
import re
from pathlib import Path

import 表定义

from .通用 import 读文本

表头词 = {"#", "层", "原则", "语义", "种类", "规则", "不做", "问", "档", "条", "腿", "工具", "判据", "形式", "单元"}


def 取节(源文本: str, 节前缀: str) -> list:
    输出行, 在内 = [], False
    for 文本行 in 源文本.splitlines():
        if 文本行.startswith("## "):
            在内 = 文本行.startswith(节前缀)
            continue
        if 在内:
            输出行.append(文本行)
    return 输出行


def 抽规则(类别值: str, 源文本: str, 节前缀: str, 形式: str) -> list:
    节行 = 取节(源文本, 节前缀)
    结果行 = []
    序号 = 0
    if 形式 == "table":
        for 文本行 in 节行:
            规则行 = 文本行.strip()
            if not 规则行.startswith("|"):
                continue
            格表 = [格值.strip() for 格值 in 规则行.strip("|").split("|")]
            if not 格表 or set("".join(格表)) <= set("-: "):
                continue
            if 格表[0] in 表头词:
                continue
            序号 += 1
            规则名 = 格表[0] if len(格表) > 1 else ""
            内容值 = " · ".join(格值 for 格值 in 格表[1:] if 格值)
            if 内容值:
                结果行.append((f"{类别值}-{序号}", 类别值, 规则名, 内容值, f"{节前缀}（表行）"))
    else:
        for 文本行 in 节行:
            正则匹配 = re.match(r"^\s*(\d+)\.\s+(.*)$", 文本行)
            if not 正则匹配:
                continue
            序号 += 1
            正文 = 正则匹配.group(2).strip()
            规则名 = 正则匹配.group(1)
            标题匹配 = re.match(r"^\*\*(.+?)\*\*[。：—\s]*(.*)$", 正文)
            if 标题匹配:
                规则名, 正文 = 标题匹配.group(1), (标题匹配.group(2).strip() or 标题匹配.group(1))
            结果行.append((f"{类别值}-{序号}", 类别值, 规则名[:60], 正文[:2000],
                          f"{节前缀}（编号 {正则匹配.group(1)}）"))
    return 结果行


def 装规则(根目录: Path) -> list:
    输出行 = []
    for 类别值, 件名, 节前缀, 形式名 in 表定义.规则来源:
        输出行 += 抽规则(类别值, 读文本(根目录 / 件名), 节前缀, 形式名)
    return 输出行
