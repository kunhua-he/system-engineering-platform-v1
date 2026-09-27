#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""代码地图 —— 本仓的**符号索引**（独立一套，不走 MCP）。

用法：
    python3 开发工具/代码地图.py 建             # 建/刷索引（环境步：照实报墙钟，不判顶）
    python3 开发工具/代码地图.py 查 <关键词>     # 按短名/限定名/声明/路径子串查符号
    python3 开发工具/代码地图.py 引用 <限定名>   # 该符号的全部出现（定义处也算）
    python3 开发工具/代码地图.py 状态           # 索引在不在、多大、哪几条腿跑了

**它买的是什么**：`rg` 快（实测 31 ms）但**没有语义** —— 它分不清「定义」与「引用」、
也认不出两个同名符号。本工具用 **SCIP**（Sourcegraph 开源，业界标准）预建索引，
查的时候只读文件：`rg` 管「哪几行有这个字」，代码地图管「谁是定义、谁在引用它」——
而且三种语言**同一套口径**（每条记录带由符号串唯一决定的 `限定名`，跨模块同名分得开）。

**索引器**（四条，都是**环境依赖**，不是底座能力）：`rust-analyzer` · `scip-python` ·
`scip-typescript` · `scip`。缺哪条 ⇒ 那条腿不跑，`建` 如实报「哪条腿没跑」，其余照跑。

**落点**：`<运行数据根>/缓存/代码地图/`（判据 ⑳：不落源码树）。

**五秒硬顶**：`建` 是环境步（三条腿要加载整棵工程，实测 ≈ 19 s）⇒ 用 `报告环境步` 照实报；
`查`/`引用`/`状态` 只读预建文件（实测 0.2 s 级）⇒ 用 `自门禁` 判顶。
依据：`项目文档/决策记录/2026-09-27_代码地图.md` · `2026-09-27_构建段归环境步.md` §四。
"""
import sys
import time
from pathlib import Path

起 = time.monotonic()  # 壳起表点：必须在 import 业务包**之前**（见 构建装配/门禁/壳.py）

仓根 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(仓根))            # 取 构建装配.门禁
sys.path.insert(0, str(仓根 / "开发工具"))  # 取 运行数据根 包

from 构建装配.门禁 import 报告环境步, 自门禁  # noqa: E402

from 代码地图 import 建, 报缺工具, 缺什么, 索引状态, 查行, 引用行, 状态行  # noqa: E402

用法 = "用法：python3 开发工具/代码地图.py {建|查 <关键词>|引用 <限定名>|状态}"


def main(argv=None):
    参 = list(sys.argv[1:] if argv is None else argv)
    子令 = 参[0] if 参 else "状态"

    if 子令 == "建":
        if 缺什么():
            return 报缺工具()
        码, 毫秒, 说明 = 建(仓根)
        print("代码地图 · 建索引：%s" % 说明)
        print("  冷构建墙钟 %d ms（环境步：照实报，不判顶）" % 毫秒)
        return 码

    if 子令 == "状态":
        状 = 索引状态()
        print("\n".join(状态行(状)))
        return 0 if 状["有"] else 1

    if 子令 in ("查", "引用"):
        if len(参) < 2:
            print(用法)
            return 2
        if not 索引状态()["有"]:
            print("代码地图：还没有索引 ⇒ 先跑 `python3 开发工具/代码地图.py 建`")
            return 1
        print("\n".join(查行(参[1]) if 子令 == "查" else 引用行(参[1])))
        return 0

    print(用法)
    return 2


if __name__ == "__main__":
    建模式 = bool(sys.argv[1:]) and sys.argv[1] == "建"
    码 = main()
    if 建模式:
        sys.exit(
            报告环境步(
                起, 码,
                "代码地图 · 建索引 —— 三条 SCIP 腿全量索引（一次性冷构建，属环境步）",
            )
        )
    sys.exit(
        自门禁(
            起, 码, 尾巴余量毫秒=200,
            修法="本命令只读预建的 JSONL 索引（不加载工程）。索引长大它自己会超顶 —— "
                 "修法是建索引时裁面（`--exclude-vendored-libraries` 已开）或分片，别改成现查。",
        )
    )
