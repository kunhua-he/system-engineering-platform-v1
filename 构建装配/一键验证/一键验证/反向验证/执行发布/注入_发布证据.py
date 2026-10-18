# -*- coding: utf-8 -*-
"""判据 67 的反向样本：把夹具的兼容矩阵删掉一维。"""
from __future__ import annotations

import json
from pathlib import Path

矩阵相对路径 = "契约声明/兼容矩阵.json"


def 注入_发布证据缺一维(临根: Path) -> str:
    """夹具 `契约声明/兼容矩阵.json` 的 `四维` 删成三项 ⇒ 判据 67 当场红。

    为什么挑这一处：四维齐是兼容矩阵的头号断言 —— 少一维（执行模式）兼容结论就不成立，
    而盘上其余件一字未动 ⇒ 反向样本只打这一个断言，不误伤别的。
    夹具里没有那份矩阵时（老合成仓）本函数现写一份缺维的 —— 判据不能因「件不在」
    而落成未判，那正是这条反向样本要区分开的。
    """
    契约件 = 临根 / 矩阵相对路径
    契约件.parent.mkdir(parents=True, exist_ok=True)
    矩阵 = {"说明": "反向样本：四维缺一（执行模式）", "四维": [], "旧样本": []}
    if 契约件.is_file():
        try:
            矩阵 = json.loads(契约件.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    行表 = 矩阵.get("四维") or []
    矩阵["四维"] = [声明条目 for 声明条目 in 行表 if 声明条目.get("维度") != "执行模式"]
    契约件.write_text(json.dumps(矩阵, ensure_ascii=False, indent=2), encoding="utf-8")
    return 矩阵相对路径
