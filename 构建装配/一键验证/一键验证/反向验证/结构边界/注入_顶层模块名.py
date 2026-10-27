# -*- coding: utf-8 -*-
"""注入样本 · 判据 62（顶层模块名必有导入）。"""
from __future__ import annotations

from pathlib import Path


def 注入_顶层模块名缺导入(临根: Path) -> str:
    """造一件**用了 `os.` 却没 import os** 的 `.py` ⇒ 判据 62 当场红。

    形状取现场实测那一类（`开发工具/MCP服务/作业执行/命令执行.py` 缺 `sys`、三个命令行入口缺 `os`）。

    ★ 本件自身的样本内容是**字符串**：判据用 AST，不解析字符串 ⇒ 不会扫到本件（这正是
      选 AST 而非正则的理由；正则版本会把本件也算一处）。
    """
    路径 = 临根 / "构建装配" / "样例" / "缺导入样本.py"
    路径.parent.mkdir(parents=True, exist_ok=True)
    路径.write_text(
        "# 反向样本：用了 os. 却没 import os。\n"
        "def 取当前目录():\n"
        "    return os.getcwd()\n",
        encoding="utf-8",
    )
    return "构建装配/样例/缺导入样本.py"
