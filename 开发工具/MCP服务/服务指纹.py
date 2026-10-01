# -*- coding: utf-8 -*-
"""服务指纹 —— MCP 服务**自身源码**的指纹：启动记一次，每次调用比对，不一致就报该重启。

**为什么要有它**（实测 2026-10-01）：MCP 是 ZCode 启动时拉起的**长驻进程** —— 改 `MCP服务/**`
不重启就跑旧码。腿 204 加了 `功能=6 源件记账`，而跑着的服务里根本没有它，只能直接 import 自证。
故服务启动时记下自身文件指纹，每次调用比对 ⇒ 不一致就在回执头打一行「服务代码已过期」。

**面 = 服务源码**：`MCP服务/*.py` ＋ 入口 `MCP服务.py`。**一处算法**（`算服务指纹`），
启动记录与每次比对都用它。
"""

import hashlib
from pathlib import Path

服务根 = Path(__file__).resolve().parent
入口件 = 服务根.parent / "MCP服务.py"


def 算服务指纹() -> str:
    """服务源码的合并指纹 ⇒ 16 位十六进制（按件名排序后逐件摘要 —— 顺序无关）。"""
    摘要 = hashlib.sha256()
    件表 = sorted(服务根.glob("*.py")) + ([入口件] if 入口件.is_file() else [])
    for 源码件 in 件表:
        try:
            内容 = 源码件.read_bytes()
        except OSError:
            内容 = b""
        摘要.update(源码件.name.encode("utf-8"))
        摘要.update(内容)
    return 摘要.hexdigest()[:16]


启动指纹 = 算服务指纹()


def 过期提示行() -> str:
    """启动时的指纹 ≠ 现在盘上的 ⇒ 提示行；一致 ⇒ 空串（不编话）。"""
    if 算服务指纹() == 启动指纹:
        return ""
    return "★ 服务代码已过期，请重启 ZCode（MCP 是长驻进程，改了不重启跑的是旧码）"
