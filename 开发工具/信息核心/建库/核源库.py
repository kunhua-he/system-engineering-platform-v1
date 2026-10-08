# -*- coding: utf-8 -*-
"""建库 · 核源库 —— 核「源件权威 ↔ 规则库」一致：`未完成.json` 四栏 · 活 md 抽取。

为何要它（2026-10-08 · 收口方实测）：合主干的三方重放对**源件权威**表（`未完成` · 活 md 的
`条款` 片）只「跳过」并说「建库 重抽」；没真跑重抽时库就停在主干版 —— 实测合主干绿而
`未完成.json` 四行、库只两行。本件把那条口径变成**可判**：重抽后逐条核，失配即非 0 退出，
调用方据此 fail-closed（不推进主干、不假报）。
"""
from pathlib import Path

import 表定义

from .条款 import 拆节
from .通用 import 读JSON件, 读文本
from .路径 import 仓根

未完成源件相对路径 = "开发工具/信息核心/未完成.json"
未完成表名 = "未完成"
条款表名 = "条款"


def 核源库(指定根: Path = None) -> tuple:
    """核 `未完成.json` ↔ 库 `未完成`（四栏）· 活 md ↔ 库 `条款`（抽取）⇒ (退出码, 行表)。"""
    import sqlite3

    根目录 = Path(指定根 or 仓根)
    库件 = 表定义.库路径(根目录)
    差异表 = []
    源件 = 根目录 / 未完成源件相对路径
    if 源件.is_file():
        JSON行表 = [tuple(数据行) for 数据行 in ((读JSON件(源件) or {}).get("行") or [])]
        连接 = sqlite3.connect("file:%s?mode=ro" % 库件, uri=True)
        try:
            库行表 = [tuple(数据行) for 数据行 in 连接.execute("select * from %s" % 未完成表名)]
        finally:
            连接.close()
        if sorted(JSON行表, key=repr) != sorted(库行表, key=repr):
            差异表.append("未完成.json %d 行 ≠ 库 `未完成` %d 行（库台账仍是旧版 ⇒ 重抽没落库）"
                       % (len(JSON行表), len(库行表)))
    else:
        差异表.append("未完成.json 不在（%s）⇒ 判不了台账四栏" % 源件)
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
    行表 = ["核源库：未完成四栏与 %d 份活 md 抽取逐条核" % len(库分片表)]
    if 差异表:
        return 1, 行表 + ["   ★ " + 差异项 for 差异项 in 差异表]
    return 0, 行表 + ["   未完成四栏一致 · 活 md %d 份逐节一致" % len(库分片表)]
