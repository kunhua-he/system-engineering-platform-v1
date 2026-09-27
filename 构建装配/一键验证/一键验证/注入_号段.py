# -*- coding: utf-8 -*-
"""注入样本 · 号段一类（判据 ④）：布局挖洞 · 命名空间边界缺一节 · 类型标签越段。

三条都对应 2026-09-27 的裁决（`决策记录/2026-09-27_判据口径十一条.md` §七/§八）：
  · 布局必须**无缝铺满**本空间 —— 挖一个洞 ⇒ 必红；
  · 全宽从 `号段图.json:命名空间边界` 读（判据不自带边界）—— 抽掉一节 ⇒ 必报「判不了无洞」；
  · 类型标签 `0–99` 为内核自有，`4294967295` 是**哨兵**不参与区间 —— 越段 ⇒ 必红，
    而哨兵本身**不许**被区间判红（这条是「不误报」那半边）。
"""
from __future__ import annotations

import json
from pathlib import Path

from .常量 import 契约目录名


def 注入_资源号段挖洞(临根: Path) -> str:
    """把 号段图.json 的资源号段第二段**整段抽掉** ⇒ `1–9999` 里出现 `9000–9999` 的洞 ⇒ 判 4 必红。"""
    路径 = 临根 / 契约目录名 / "号段图.json"
    数据 = json.loads(路径.read_text(encoding="utf-8"))
    数据["资源号段"] = [段 for 段 in 数据["资源号段"] if 段["起"] != 9000]
    路径.write_text(json.dumps(数据, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return f"{契约目录名}/号段图.json"


def 注入_命名空间边界缺一节(临根: Path) -> str:
    """抽掉 `命名空间边界.通知号` ⇒ 判 4 判不了通知号段的无洞 ⇒ 必报「判不了无洞」（**不是通过**）。"""
    路径 = 临根 / 契约目录名 / "号段图.json"
    数据 = json.loads(路径.read_text(encoding="utf-8"))
    del 数据["命名空间边界"]["通知号"]
    路径.write_text(json.dumps(数据, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return f"{契约目录名}/号段图.json"


def 注入_类型标签越内核段(临根: Path) -> str:
    """把 类型声明/0000.json 的 类型标签 改成 `100`（内核自有段是 `0–99`）⇒ 判 4 必红。

    文件名仍是 `0000.json` ⇒ 会连带触发判据 ①（编号与文件名一致）。**无妨**：
    本条样本断言的是「判 4 报出越段」，别的判据同时红是正常的（样本按 (样本名, 判据名) 定位）。
    """
    路径 = 临根 / 契约目录名 / "类型声明" / "0000.json"
    数据 = json.loads(路径.read_text(encoding="utf-8"))
    数据["类型标签"] = 100
    路径.write_text(json.dumps(数据, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return f"{契约目录名}/类型声明/0000.json"
