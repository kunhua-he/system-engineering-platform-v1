# -*- coding: utf-8 -*-
"""闸零实现 —— 两条闸**并发**跑，各按各的退出码与读数报（闸 0 入口只做壳）。

**为什么搬到这里**（`开发规范.md` 第六节：入口 ≤160 行 · 零实现）：`闸0.py` 是薄壳
（起表 → 调本件 → 自门禁），并发调度与读数装配住本件。拆开只为行数硬顶，**行为逐字不变**
（跑法、退出码语义、打印排布全在 `闸0.py` 的文件头写清楚）。

**为什么现在是「并发」**（2026-10-08）：两条闸只读仓、互不写、互不 import ⇒ 本来就该并发。
此前被迫串行的唯一原因是闸 1 的判据 ⑱ 在进程内自量本命令墙钟：与闸 2 抢 CPU 时那段墙钟被
推过阈值 ⇒ 子步骤的**读数被污染**（不是真超顶）。现 ⑱ 改读**外层采样**（`墙钟采样.py`）：
本件在起子进程**之前**把外层起表点经 `采样环境变量` 送进去，子进程里的 ⑱ 量的是**外层这条
命令**的完整墙钟 —— 那正是 ⑱ 声明的对象，且覆盖得**更全**（含本件的调度 / 采集 / 收集）。
⇒ 并发不再污染任何读数，而「本命令超顶」照样当场报红（同一处判定 `墙钟采样.判定墙钟`）。

**约束（不许违反）**：**不许让闸 1 去 import 闸 2**（层序问题 —— `测试验证/` 不在产品层序里）。
所以本件用**子进程**调两条闸的**入口**，互不 import。
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# 两条闸的**入口**（子进程调它们，不 import —— 层序问题，见件头）。
闸表 = (
    ("闸 1 · 声明侧", "构建装配/一键验证/一键验证.py"),
    ("闸 2 · 实现侧", "测试验证/契约一致性/扫实现.py"),
)
读数行模式 = re.compile(r"^通过\s.*$", re.M)

# 外层采样环境变量的名字：**唯一主人**在 `一键验证/墙钟采样.py`（本件不另写一份字面量）。
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "构建装配" / "一键验证"))
from 一键验证.判据编排.墙钟采样 import 采样环境变量  # noqa: E402


def 跑一条闸(名称: str, 相对: str, 仓根: Path, 硬顶秒: float, 外层起表秒: float) -> tuple:
    """跑一条闸 ⇒ `(名称, 相对, 退出码或 None, 输出, 是否超时)`。**并发调**（外面套线程池）。

    子进程带 timeout（2026-10-05 修 · 审计 B-7）：原先只**事后量**、子进程无 timeout
    ⇒ CLI / pre-commit 路径一旦卡死就挂死。**从硬顶派生** —— 不写第二个数，否则内外不同步。
    超时 = 判红并报「超时」。
    """
    子进程环境 = dict(os.environ)
    子进程环境[采样环境变量] = repr(外层起表秒)  # 见件头：让子进程里的 ⑱ 量外层这条命令
    try:
        判定汇总 = subprocess.run(
            [sys.executable, str(仓根 / 相对)], cwd=str(仓根), capture_output=True, text=True,
            timeout=硬顶秒, env=子进程环境,
        )
    except subprocess.TimeoutExpired:
        return 名称, 相对, None, "（超时：本闸 > %g s 未返回 —— 硬顶无例外）" % 硬顶秒, True
    return 名称, 相对, 判定汇总.returncode, (判定汇总.stdout or "") + (判定汇总.stderr or ""), False


def 跑两条闸(仓根: Path, 硬顶毫秒: int, 外层起表秒: float) -> tuple:
    """并发跑两条闸 ⇒ `(是否全过, 明细表)`；明细表每项 = `(名称, 相对, 输出)`（只装失败的）。

    **按原序报**（声明侧在前）—— 并发只改「谁先跑完」，不改读数的排布。
    """
    硬顶秒 = 硬顶毫秒 / 1000
    两路 = {}
    with ThreadPoolExecutor(max_workers=len(闸表)) as 线程池:
        作业表 = {线程池.submit(跑一条闸, 名称, 相对, 仓根, 硬顶秒, 外层起表秒): 名称
                for 名称, 相对 in 闸表}
        for 作业 in 作业表:
            名称, 相对, 退出码, 输出, 超时 = 作业.result()
            两路[名称] = (相对, 退出码, 输出, 超时)
    全过 = True
    明细 = []
    print("闸 0：两条闸并发跑（声明侧 + 实现侧；子进程调入口，互不 import）")
    print("")
    for 名称, 相对 in 闸表:
        相对, 退出码, 输出, 超时 = 两路[名称]
        print(f"  {名称} ｜ {相对}")
        if 超时:
            全过 = False
            print(f"    退出码 超时 ｜ （{输出}）")
            明细.append((名称, 相对, 输出))
            continue
        命中 = 读数行模式.search(输出)
        读数 = 命中.group(0).strip() if 命中 else "（没有读出「通过 …」那一行）"
        全过 = 全过 and (退出码 == 0)
        print(f"    退出码 {退出码} ｜ {读数}")
        if 退出码 != 0:
            明细.append((名称, 相对, 输出))
    print("")
    if not 全过:
        for 名称, 相对, 原始 in 明细:
            print(f"── {名称}（{相对}）失败明细 ──")
            print(原始.rstrip())
            print("")
        print("闸 0：至少一条闸没过（退出码 1）")
        return False, 明细
    print("闸 0：两条闸都过（退出码 0）")
    return True, 明细


def 跑闸0带复用(仓根: Path, 硬顶毫秒: int, 外层起表秒: float) -> tuple:
    """闸 0 的对外跑法：先问复用（同一棵树同一份内容只跑一遍），不命中才真跑两条闸。

    复用口径住 `构建装配/门禁/闸0复用.py`（与 `复跑.py` 同一层）—— 本件只把**跑两条闸**
    这份实现传给它（避免调度器与门禁包互相 import）。
    """
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from 构建装配.门禁 import 跑闸0或复用
    return 跑闸0或复用(仓根, 硬顶毫秒, 外层起表秒, 跑两条闸)
