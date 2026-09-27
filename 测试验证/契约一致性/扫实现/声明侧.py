# -*- coding: utf-8 -*-
"""声明侧读取 —— 声明根 与 能力声明 / 错误码表 / 类型声明 / 包。"""
from __future__ import annotations

import json

from .常量 import 契约目录名, 扩展三类, 声明根标记

def 找声明根(件表: dict) -> list:
    根目录 = []
    if 契约目录名 in {件键.split("/")[0] for 件键 in 件表}:
        根目录.append(契约目录名)
    for 键名 in 件表:
        if 键名.split("/")[0] not in 扩展三类 and not 键名.startswith("扩展根目录/"):
            continue
        号段 = 键名.split("/")
        if len(号段) < 3:
            continue
        目录 = "/".join(号段[:-1])
        if 号段[-1] in 声明根标记:
            根目录.append(目录)
    return sorted(set(根目录))


def 读声明侧(件表: dict) -> dict:
    """返回 {声明根: {"能力声明": {编号: (数据, 键)}, "错误码表": …, "类型声明": …, "包": 数据}}。"""
    根表 = {}
    for 键, 文本 in 件表.items():
        if not 键.endswith(".json") or 文本 is None:
            continue
        根目录 = None
        for 声明根 in 找声明根(件表):
            if 键 == f"{声明根}/包声明.json" or 键.startswith(声明根 + "/"):
                根目录 = 声明根
                break
        if 根目录 is None:
            continue
        try:
            数据 = json.loads(文本)
        except json.JSONDecodeError:
            continue
        if not isinstance(数据, dict):
            continue
        一项 = 根表.setdefault(
            根目录, {"能力声明": {}, "错误码表": {}, "类型声明": {}, "包": None}
        )
        尾部 = 键[len(根目录) + 1 :]
        if 尾部 == "包声明.json" or 尾部 == "平台声明.json":
            一项["包"] = (数据, 键)
        elif 尾部.startswith("能力声明/") and 尾部.endswith(".json"):
            一项["能力声明"][键] = (数据, 键)
        elif 尾部.startswith("错误码表/") and 尾部.endswith(".json"):
            一项["错误码表"][键] = (数据, 键)
        elif 尾部.startswith("类型声明/") and 尾部.endswith(".json"):
            一项["类型声明"][键] = (数据, 键)
    return 根表
