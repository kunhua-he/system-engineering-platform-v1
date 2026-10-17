# -*- coding: utf-8 -*-
"""判据 64 的反向样本：把夹具的列表型参数类型名改成文本型。"""
from __future__ import annotations

import json
from pathlib import Path


def 注入_老项目链缺列表型参数(临根: Path) -> str:
    """夹具「落条目」的 `条目表` 参数类型由 `列表型` 改成 `文本型` ⇒ 参数表里不再有 100 号标签。

    为什么挑这一处：它是**三类类型里最容易被悄悄改坏**的一条 —— 类型名照写、标签不落，
    件还在、能过形状判据，只有真读回才看得出来。改完翻译器照样跑得通、保真损失照样空，
    只有「参数表里有没有 100 号」这一条会红 ⇒ 反向样本正好只打这一个断言，不误伤别的。
    """
    夹具件 = 临根 / "测试验证" / "老项目样本" / "样本接入模块" / "能力定义.json"
    定义 = json.loads(夹具件.read_text(encoding="utf-8"))
    for 能力项 in 定义.get("能力列表") or []:
        for 参数项 in 能力项.get("参数") or []:
            if 参数项.get("名称") == "条目表":
                参数项["类型"] = "文本型"
    夹具件.write_text(json.dumps(定义, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return "测试验证/老项目样本/样本接入模块/能力定义.json"
