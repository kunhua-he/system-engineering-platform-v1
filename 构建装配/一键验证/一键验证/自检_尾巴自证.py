# -*- coding: utf-8 -*-
"""⑱ 的**尾巴自证**样本 —— 从 `自检_延迟与两遍.py` 分出（那个件已顶 400 行硬数）。

量的是：⑱ 的读数（进程启动 → 两遍判据跑完）与**真墙钟**（再含结果装配 + 打印）之差。
`--缺口` 里登记的那条「读数不含 80 ms 尾巴」不靠估，这里直接量（要求 0 ≤ 尾巴 < 200）。
"""

from __future__ import annotations

import io
import tempfile
import time
from pathlib import Path

from .合成仓 import 造干净仓
from .常量 import 起始时刻
from .注入 import 注入_常量重定义
from .打印 import 打印验证结果
from .验证 import 跑全量判据


def 尾巴自证样本() -> tuple:
    """⇒ `(说明, 通过?, 读数行)` —— 调用方（`自检_延迟判据承重`）直接 append 进样本表。"""
    with tempfile.TemporaryDirectory(prefix="一键验证延迟尾巴-") as 临时目录:
        临根 = Path(临时目录) / "仓"
        造干净仓(临根)
        注入_常量重定义(临根)  # 造一条失败明细，让「打印」那段尾巴真的发生
        尾巴果 = 跑全量判据(临根)
        读数 = 尾巴果["上下文"].get("本命令墙钟毫秒")
        打印验证结果(尾巴果, io.StringIO())
        真墙钟 = int((time.perf_counter() - 起始时刻) * 1000)
    尾巴 = 真墙钟 - (读数 or 0)
    return (
        "尾巴自证：⑱ 读数 与 真墙钟（含结果装配 + 打印）之差 < 200 ms",
        0 <= 尾巴 < 200,
        f"读数 {读数} ms · 真墙钟 {真墙钟} ms · 尾巴 {尾巴} ms（要求 0 ≤ 尾巴 < 200）",
    )
