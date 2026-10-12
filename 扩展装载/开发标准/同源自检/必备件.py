# -*- coding: utf-8 -*-
"""同源自检 · 读必备件 —— 必备件清单与「哪几种要哪几件」的唯一读入口。

同源点：`测试验证/契约一致性/扫实现/不覆盖.py::读种类表` 读的是同一份清单
（`扩展装载/开发标准/必备件.json`）—— 本件不复述那张表，只按同一份事实取；
模板与真实扩展的比对都走这里，不另立第二套判定。
"""
from __future__ import annotations

import json
from pathlib import Path

本件目录 = Path(__file__).resolve().parent
开发标准根 = 本件目录.parent
仓根 = 开发标准根.parents[1]
必备件文件 = 开发标准根 / "必备件.json"


def 读必备件():
    """⇒ (必备件清单 dict, 错误 或 None)。读不到 / 解析不了 ⇒ (None, 原因)。"""
    if not 必备件文件.is_file():
        return None, f"必备件清单不在盘上（{必备件文件}）"
    try:
        源文本 = 必备件文件.read_text(encoding="utf-8")
    except OSError as 错误:
        return None, f"必备件清单读不动：{错误}"
    try:
        必备件清单 = json.loads(源文本)
    except ValueError as 错误:
        return None, f"必备件清单不是合法 JSON：{错误}"
    if not isinstance(必备件清单, dict):
        return None, "必备件清单不是 JSON 对象"
    return 必备件清单, None


def 取必备件表(必备件清单: dict):
    """⇒ [必备件条, …]（按清单里的先后顺序 —— 顺序就是报告里的顺序）。"""
    return [必备件条 for 必备件条 in (必备件清单.get("必备件") or []) if isinstance(必备件条, dict)]


def 取种类表(必备件清单: dict):
    """⇒ [(种类名, 默认目录), …]。

    种类名就是必备件条里那三个开关键（支持库 / 模块 / 技能）——
    「这一件该种类要不要」由 `必备件条.get(种类名)` 回答，与 `必备件.json` 同一份事实。
    """
    种类表 = []
    for 种类条 in (必备件清单.get("三类扩展") or []):
        if not isinstance(种类条, dict):
            continue
        种类名 = 种类条.get("种类")
        默认目录 = str(种类条.get("默认目录") or "").rstrip("/")
        if not 种类名 or not 默认目录:
            continue
        种类表.append((种类名, 默认目录))
    return 种类表
