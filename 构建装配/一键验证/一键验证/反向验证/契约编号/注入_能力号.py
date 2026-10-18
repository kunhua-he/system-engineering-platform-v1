# -*- coding: utf-8 -*-
"""注入样本 · 判据 ㊻（底座不硬写能力号）。

反向样本注入到**干净合成仓**（不依赖仓库现状 ⇒ 可重复）。号**从夹具的声明里现取**
（`契约声明/能力声明/9001.json` 的 `编号`）—— 不写死一个真号：检测表变了，样本跟着变。
"""
from __future__ import annotations

import json
from pathlib import Path

_样本件 = "运行内核/实例状态/src/能力号样本.rs"


def 注入_硬写能力号(临根: Path) -> str:
    """往合成仓的底座代码面塞一个**已声明能力号** ⇒ 判据 ㊻ 当场红。"""
    声明件 = 临根 / "契约声明" / "能力声明" / "9001.json"
    号值 = json.loads(声明件.read_text(encoding="utf-8"))["编号"]
    路径 = 临根 / _样本件
    路径.parent.mkdir(parents=True, exist_ok=True)
    路径.write_text(
        "/// 反向样本：底座硬写已声明的能力号（判据 ㊻ 该抓）。\n"
        f"pub const 编译链: [u32; 1] = [{号值}];\n",
        encoding="utf-8",
    )
    return _样本件
