# -*- coding: utf-8 -*-
"""建库 · 文档 —— 全仓 md 定档：账本显式件优先，其次按路径规则，最后「未定义」。"""
from pathlib import Path

from .读件工具 import 读JSON件, 扫md


def 装文档(根目录: Path) -> list:
    账本 = 读JSON件(根目录 / "项目文档" / "文档账本.json") or {}
    显式 = {}
    for 账本条目 in 账本.get("件") or []:
        if isinstance(账本条目, dict) and isinstance(账本条目.get("路径"), str):
            显式[账本条目["路径"]] = 账本条目
    定档规则 = [
        账本条目 for 账本条目 in (账本.get("按路径定档") or [])
        if isinstance(账本条目, dict) and isinstance(账本条目.get("前缀"), str)
    ]
    输出行 = []
    for 文档路径 in 扫md(根目录):
        if 文档路径 in 显式:
            输出行.append((文档路径, str(显式[文档路径].get("档")),
                          str(显式[文档路径].get("表达什么") or "")))
            continue
        for 账本条目 in 定档规则:
            if 文档路径.startswith(账本条目["前缀"]):
                输出行.append((文档路径, str(账本条目.get("档")),
                              "（按路径规则）" + 文档路径.rsplit("/", 1)[-1]))
                break
        else:
            输出行.append((文档路径, "（未定义）", "—— 账本里没有它（判据 ㊶ 会报红）"))
    return 输出行
