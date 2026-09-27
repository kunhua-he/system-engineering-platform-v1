# -*- coding: utf-8 -*-
"""注入样本 · 判据 ㊲（超时设置上限五秒）。"""
from __future__ import annotations

from pathlib import Path


def 注入_超时设置超上限(临根: Path) -> str:
    """造一处**超时设置大于 5 秒**的代码件 ⇒ 判据 ㊲ 当场红。

    形状取现场实测那一类（`构建装配/演示/常量.py` 的健康超时曾写 30.0 秒、
    `前端呈现/视觉对拍.py` 的 `goto` 曾写 `timeout=15000` 毫秒）：这里一次给
    **形①「秒」**与**形③「`timeout=` 字面量」**两处 —— 证明两种写法都拦得住。
    两个值都取**读数明确**的（30 秒 / 30 秒口径），不走「101–999 单位分不出」那条未判路。
    """
    路径 = 临根 / "构建装配" / "样例" / "超时常量.py"
    路径.parent.mkdir(parents=True, exist_ok=True)
    路径.write_text(
        "# 反向样本：超时设置大于 5 秒。\n"
        "健康超时秒 = 30.0\n"
        "timeout=30\n",
        encoding="utf-8",
    )
    return "构建装配/样例/超时常量.py"
