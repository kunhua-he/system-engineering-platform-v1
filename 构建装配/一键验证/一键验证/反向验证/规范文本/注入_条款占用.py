# -*- coding: utf-8 -*-
"""注入样本 · 判据 68（条款写口占用保护）。"""
from __future__ import annotations

from pathlib import Path


# 反向样本的靶件：一份**只有 insert or replace、没有占用保护**的条款写口。
条款写口件 = "构建装配/样例/条款写口样本.py"


def 注入_条款写口无占用(临根: Path) -> str:
    """在合成仓里放一份缺占用保护的条款写口 ⇒ 判据 68 当场红。

    形状就是修前那个写口：直写 `insert or replace`，只读档位、不查占用 —— 于是同序号已有
    非空正文时整节被静默替换（实测 1824 字 → 681 字，库行数不变）。
    """
    路径 = 临根 / 条款写口件
    路径.parent.mkdir(parents=True, exist_ok=True)
    路径.write_text(
        "# 反向样本：条款写口无占用保护（同键非空正文会被静默替换）。\n"
        "\n"
        "\n"
        "def 写(连接, 文档路径: str, 序号: int, 标题: str, 正文: str) -> None:\n"
        "    已有 = 连接.execute(\"select 权威档 from " + "条" + "款 where 文档路径 = ? and 序号 = ?\",\n"
        "                      (文档路径, 序号)).fetchone()\n"
        "    连接.execute(\"insert or replace into " + "条" + "款 values(?,?,?,?,?)\",\n"
        "                 (文档路径, 序号, 标题, 正文, \"\"))\n",
        encoding="utf-8",
    )
    return 条款写口件
