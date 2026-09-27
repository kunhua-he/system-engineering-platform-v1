# -*- coding: utf-8 -*-
"""声明侧读取 —— 声明根 与 能力声明 / 错误码表 / 类型声明 / 包。"""
from __future__ import annotations

import json

from .常量 import 契约目录名, 扩展三类, 声明根标记

def 找声明根(件表: dict) -> list:
    根 = []
    if 契约目录名 in {件键.split("/")[0] for 件键 in 件表}:
        根.append(契约目录名)
    for 键 in 件表:
        if 键.split("/")[0] not in 扩展三类 and not 键.startswith("扩展根目录/"):
            continue
        段 = 键.split("/")
        if len(段) < 3:
            continue
        目录 = "/".join(段[:-1])
        if 段[-1] in 声明根标记:
            根.append(目录)
    return sorted(set(根))


def 读声明侧(件表: dict) -> dict:
    """返回 {声明根: {"能力声明": {编号: (数据, 键)}, "错误码表": …, "类型声明": …, "包": 数据}}。"""
    根表 = {}
    for 键, 文本 in 件表.items():
        if not 键.endswith(".json") or 文本 is None:
            continue
        根 = None
        for 声明根 in 找声明根(件表):
            if 键 == f"{声明根}/包声明.json" or 键.startswith(声明根 + "/"):
                根 = 声明根
                break
        if 根 is None:
            continue
        try:
            数据 = json.loads(文本)
        except json.JSONDecodeError:
            continue
        if not isinstance(数据, dict):
            continue
        项 = 根表.setdefault(
            根, {"能力声明": {}, "错误码表": {}, "类型声明": {}, "包": None}
        )
        尾 = 键[len(根) + 1 :]
        if 尾 == "包声明.json" or 尾 == "平台声明.json":
            项["包"] = (数据, 键)
        elif 尾.startswith("能力声明/") and 尾.endswith(".json"):
            项["能力声明"][键] = (数据, 键)
        elif 尾.startswith("错误码表/") and 尾.endswith(".json"):
            项["错误码表"][键] = (数据, 键)
        elif 尾.startswith("类型声明/") and 尾.endswith(".json"):
            项["类型声明"][键] = (数据, 键)
    return 根表
