# -*- coding: utf-8 -*-
"""建库 · 核源库 —— 核「活 md 抽取 ↔ 规则库 `条款`」一致。

为何要它（2026-10-08 · 收口方实测）：合主干的三方重放对**源件权威**表（活 md 的 `条款` 片）
只「跳过」并说「建库 重抽」；没真跑重抽时库就停在主干版 —— 实测合主干绿而库里还是旧节。
本件把那条口径变成**可判**：重抽后逐条核，失配即非 0 退出，调用方据此 fail-closed。

★ 2026-10-13：`未完成` 那一半**已删** —— 台账改「库即存本」（仓内源件 `未完成.json` 已删，
见 `表定义.py` 的 `源件表` 段）：没有源件就无可比对，那半条判据失去对象。
"""
from pathlib import Path

import 表定义

from .条款 import 拆节
from .通用 import 读文本
from .路径 import 仓根

条款表名 = "条款"


def 核源库(指定根: Path = None) -> tuple:
    """核 活 md 抽取 ↔ 库 `条款` ⇒ (退出码, 行表)。"""
    import sqlite3

    根目录 = Path(指定根 or 仓根)
    库件 = 表定义.库路径(根目录)
    差异表 = []
    连接 = sqlite3.connect("file:%s?mode=ro" % 库件, uri=True)
    try:
        库分片表 = {}
        for 文档路径, 序号, 标题, 正文, 权威档 in 连接.execute(
                "select 文档路径, 序号, 标题, 正文, 权威档 from %s" % 条款表名):
            库分片表.setdefault(文档路径, []).append((序号, 标题, 正文))
    finally:
        连接.close()
    for 文档路径 in sorted(库分片表):
        件路径 = 根目录 / 文档路径
        if not 件路径.is_file():
            continue
        现抽 = [(节号, 节题, 节体) for 节号, (节题, 节体) in enumerate(拆节(读文本(件路径)))]
        if sorted(库分片表[文档路径]) != sorted(现抽):
            差异表.append("活 md 抽取不一致：%s（库 %d 节 ≠ 现抽 %d 节）"
                       % (文档路径, len(库分片表[文档路径]), len(现抽)))
    行表 = ["核源库：%d 份活 md 抽取逐条核" % len(库分片表)]
    if 差异表:
        return 1, 行表 + ["   ★ " + 差异项 for 差异项 in 差异表]
    return 0, 行表 + ["   活 md %d 份逐节一致" % len(库分片表)]
