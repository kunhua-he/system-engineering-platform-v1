#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""信息核心 · 验证 —— 批量走**库规则**，不靠 agent 自觉。

华哥 2026-09-28：「验证器，直接批量走 db 规则去验证。例如说命名是否存在，纯靠 agent 自觉，
肯定会漂移。直接一个调用代码地图，拆解函数或者变量命名，然后一个对比脚本，库里面这个变量是否
存在定义，不存在定义的直接返回，该变量不存在。」

用法（经唯一壳 `信息核心.py` —— 本件**不是入口**，直跑本件恒 0 字节退 0 = 假绿）：
    python3 开发工具/信息核心/信息核心.py 验证            # 全跑，打读数
    python3 开发工具/信息核心/信息核心.py 验证 --契约      # 只跑契约参数越界

退出码：0 = 无红；1 = 有红。
★ 为何不补 `if __name__ == "__main__"`：那会把本件变成**入口**，而判据 ⑲ 要求入口零实现
  （本件 83 行全是实现）⇒ 补 `__main__` 当场把 ⑲ 顶红。故用法一律指回壳。
"""
import sqlite3
import sys
import time
from pathlib import Path

起始时刻 = time.monotonic()
仓根 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(仓根))
sys.path.insert(0, str(仓根 / "开发工具"))
sys.path.insert(0, str(仓根 / "构建装配" / "一键验证"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import 表定义  # noqa: E402


# ── 取库 ──────────────────────────────────────────────────────────
def 连信息核心库():
    库文件 = 表定义.库路径(仓根)
    if not 库文件.is_file():
        return None, 库文件
    return 表定义.连规则库(仓根), 库文件


# ── 规则二：契约参数有没有越过定义 ───────────────────────────
def 查契约(连接) -> list:
    类型集 = {标签 for (标签,) in 连接.execute("select 标签 from 类型")}
    越界表 = []
    for 编号, 序号, 名称, 类型, 方向 in 连接.execute(
        "select 编号,序号,名,类型,方向 from 能力参数"
    ):
        if 类型 not in 类型集:
            越界表.append((编号, f"{方向}{序号}", 名称, f"类型标签 {类型} 不在类型表里"))
    for 编号, 能力名, 返回类型 in 连接.execute("select 编号,名称,返回类型 from 能力"):
        if 返回类型 and 返回类型 not in 类型集:
            越界表.append((编号, "返回", 能力名, f"返回类型 {返回类型} 不在类型表里"))
    错误码集 = {码值 for (码值,) in 连接.execute("select 码 from 错误码")}
    for 编号, 能力名, 可抛 in 连接.execute("select 编号,名称,可抛错误码 from 能力"):
        for 码值 in [一项 for 一项 in (可抛 or "").split(",") if 一项]:
            if int(码值) not in 错误码集:
                越界表.append((编号, "可抛错误码", 能力名, f"码 {码值} 不在错误码表里"))
    return 越界表


# ── 入口 ────────────────────────────────────────────────────────
def 入口函数(参数表: list) -> int:
    连接, 库文件 = 连信息核心库()
    if 连接 is None:
        print(f"库不在：{库文件}\n先跑：python3 开发工具/信息核心/信息核心.py 建库", file=sys.stderr)
        return 1
    # 派生表（`代码名` · `类型` · `能力参数` …）住在 `信息核心_派生.db`（不进版本库）⇒
    # 新克隆 / 每条工作树都没有它。缺了不该抛未捕获 traceback，而是**可读提示**（与缺索引库同口径）。
    if (not 参数表 or "--契约" in 参数表) and not 表定义.派生库路径(仓根).is_file():
        print(f"派生库不在：{表定义.派生库路径(仓根)}\n"
              "先跑：python3 开发工具/信息核心/信息核心.py 建库"
              "（`代码名` / `类型` … 是派生表，每次建库重抽，不进版本库）", file=sys.stderr)
        return 1
    红数 = 0
    if not 参数表 or "--契约" in 参数表:
        越界表 = 查契约(连接)
        print(f"【契约】参数/返回/错误码越界：{len(越界表)} 处")
        for 记录条 in 越界表[:25]:
            print(f"    ✗ 能力 {记录条[0]} 的{记录条[1]}（{记录条[2]}）：{记录条[3]}")
        红数 += len(越界表)
    连接.close()
    print(f"\n共 {红数} 处红。" if 红数 else "\n无红。")
    return 1 if 红数 else 0
