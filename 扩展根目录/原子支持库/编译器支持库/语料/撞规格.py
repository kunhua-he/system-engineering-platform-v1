#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""撞规格 —— 拿真文本逐条撞 `项目文档/设计文档/程序文本格式.md` 第二节的规格。

一条命令复跑：  python3 撞规格.py [--json]

读 `真文本/*.txt`（UTF-8，由 挖真文本.py 从 GBK 原文转来）。
**分析按原字节做**：把样本重新编回 GBK，得到真文本在参照实现里的原始字节，
再按规格的 11 种记号去切 —— 规格里 `记号流::原文` 的类型是 `Vec<u8>`，区间是**字节区间**。

判据（规格 §二）：
  编码 UTF-8（参照 GBK）· 换行写出 LF / 读入认 CRLF+LF · 缩进 4 半角空格 ·
  关键字以 `.` 开头（少数不带点：`返回` `置入代码`）· 注释 `'` 至行尾且不含行尾换行 ·
  文本字面量全角 `“…”`（读入也认半角 `"…"`）· 常量引用 `#名字` ·
  运算符全角 `＝ ＋ ÷` · 界符半角 `( ) [ ] , . & { }` · 空实参有意义
"""
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

起始时刻 = time.monotonic()  # 壳起表点：必须在 import 业务包**之前**（见 构建装配/门禁/壳.py）

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))  # 仓根：取共享门禁
from 构建装配.门禁 import 自门禁  # noqa: E402

语料目录 = os.path.dirname(os.path.abspath(__file__))
真文本目录 = os.path.join(语料目录, "真文本")

from 撞规格 import 报表, 统计
from 撞规格.读样本 import 读样本


def 入口函数():
    rows = 读样本(真文本目录)
    读数 = 统计.统计读数(rows)
    tier_bytes = 统计.分层字节(rows)
    报表.打印报表读数(读数, rows, tier_bytes)
    if "--json" in sys.argv:
        报表.落读数件(读数, tier_bytes)


if __name__ == "__main__":
    # `main()` 不返回码（它只打印）⇒ 码恒 0，壳只负责「超顶即红」。
    sys.exit(
        自门禁(
            起始时刻, 入口函数() or 0, 尾巴余量毫秒=200,
            修法="本件逐条撞真文本（实测约 1.1 秒）—— 样本会长，超顶就按样本分片，别减判据条数。",
        )
    )
