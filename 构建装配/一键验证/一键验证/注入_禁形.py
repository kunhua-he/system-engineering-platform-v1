# -*- coding: utf-8 -*-
"""注入样本 · 判据 ㊺（命名定义现状禁形）。

反向样本注入到**干净合成仓**（不依赖仓库现状 ⇒ 可重复）。夹具的最小规则库里每一行都是
`（名即语义）`（`夹具规则库.py` 派生）⇒ 把一行改成「列了禁形」，并在命名面里真用那个禁形
⇒ 必然是「新增」⇒ 当场红。

★ 禁形名用**样本名**（`禁形样例旧名`）—— 它不在夹具的名册里、也不在任何行的 `唯一名` 栏
⇒ 豁免条件不成立。
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

_样本件 = "运行内核/实例状态/src/禁形样本.rs"


def _取表定义():
    """惰性取**表结构主人**（`开发工具/信息核心/表定义.py`）—— 库路径只此一份。"""
    工具根 = Path(__file__).resolve().parents[3]
    根目录 = str(工具根 / "开发工具" / "信息核心")
    if 根目录 not in sys.path:
        sys.path.insert(0, 根目录)
    import 表定义

    return 表定义


def 注入_禁形在用(临根: Path) -> str:
    """往合成仓的命名面里塞一个**禁形**，并在库 `命名定义` 里把它列为 `现状` ⇒ 判据 ㊺ 当场红。"""
    路径 = 临根 / _样本件
    路径.parent.mkdir(parents=True, exist_ok=True)
    路径.write_text(
        "pub fn 禁形样例() -> u32 { let 禁形样例旧名 = 1; 禁形样例旧名 }\n",
        encoding="utf-8",
    )
    库件 = 临根 / _取表定义().库相对路径
    连接 = sqlite3.connect(库件)
    try:
        连接.execute("insert or replace into 命名定义 values(?,?,?)",
                   ("禁形样例语义", "`禁形样例新名`", "`禁形样例旧名`"))
        连接.commit()
    finally:
        连接.close()
    return _样本件
