# -*- coding: utf-8 -*-
"""登记 —— 往规则库的 `命名定义` 表登记新名（**改命名规则的唯一写路径**）。

用法：
    python3 开发工具/信息核心/信息核心.py 登记 <名> [<名>…] [--语义 <一句话>]

**为何要它**：名册住规则库（华哥 2026-09-29「全规则都在 db 里面。外部不留」）⇒ 登记不能再靠
改一份 json（库里是唯一存本，不再有源件）。写库走**生成物记账**那条路（`v1_task` 功能 = 5）
—— `v1_edit` 是文本替换，二进制件它改不了。

**语义**：默认「名即语义」（与旧名册的 txt 一行一名同口径）；一个名指多件事的，
用 `--语义` 写清楚，或改由「一个语义一行」的方式登记。
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

仓根 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import 表定义  # noqa: E402


def 登记(名表: list, 语义: str = "") -> int:
    """把 `名表` 逐个登记进 `命名定义`（已存在的只刷新 `现状`）⇒ 退出码。"""
    if not 名表:
        print("用法：信息核心.py 登记 <名> [<名>…] [--语义 <一句话>]", file=sys.stderr)
        return 2
    连接 = sqlite3.connect(表定义.库路径(仓根))
    try:
        for 登记名 in 名表:
            连接.execute("insert or replace into 命名定义 values(?,?,?)",
                       (语义 or 登记名, 登记名, "（名即语义）"))
        连接.commit()
    finally:
        连接.close()
    print("登记 %d 个名：%s" % (len(名表), " · ".join(名表)))
    return 0
