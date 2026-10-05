# -*- coding: utf-8 -*-
"""注入样本 · 判据 ㊽（MCP 工具面自检）。"""
from __future__ import annotations

from pathlib import Path


def 注入_MCP自检(临根: Path) -> str:
    """在合成仓里放一个**自检退出非 0** 的 MCP 服务入口 ⇒ 判据 ㊽ 当场红。

    形状取「入口跑起来就非零退出」这一类（真缺陷长这样：协议层崩 / 工具名非 ASCII /
    拒绝样本没拒，都会让 `--自检` 退出非 0）。判据按被扫仓里的这一份跑，故合成夹具
    不必有真 MCP 服务 —— 注入这一份就够证「退出码非 0 必被抓」。
    """
    路径 = 临根 / "开发工具" / "MCP服务.py"
    路径.parent.mkdir(parents=True, exist_ok=True)
    路径.write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
    return "开发工具/MCP服务.py"
