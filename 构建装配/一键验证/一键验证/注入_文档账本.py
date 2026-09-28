# -*- coding: utf-8 -*-
"""注入样本 · 判据 ㊶（文档账本）。"""
from __future__ import annotations

from pathlib import Path


def 注入_未登记文档(临根: Path) -> str:
    """往干净合成仓里放一份**账本没登记**的 `.md` ⇒ 判据 ㊶ 当场红。

    前置由 `合成仓.py` 提供：夹具自带的账本（`项目文档/文档账本.json`）登记了
    夹具自带的全部 `.md`；这里新增一份不登记 ⇒ 就是华哥口径里「没有定义权威的 md」。
    """
    路径 = 临根 / "项目文档" / "未登记说明.md"
    路径.parent.mkdir(parents=True, exist_ok=True)
    路径.write_text("# 未登记说明（反向样本：不在文档账本里）\n", encoding="utf-8")
    return "项目文档/未登记说明.md"
