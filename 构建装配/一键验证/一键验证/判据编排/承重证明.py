# -*- coding: utf-8 -*-
"""故障注入台：证明 ⑱ 抓得住真超 5 s 的慢（本命令墙钟必然 > 5 s）。"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from ..基础定义 import 常量


def 承重证明(源仓根: Path) -> int:
    """决策记录 §三.4 要的「承重证明」：把 ⑱ 的红在**真墙钟**上逼出来（可重复跑）。

    ★ 本命令（`--承重证明`）的墙钟**必然 > 5000 ms**：它存在的唯一意义就是造一条真超硬顶的
      命令来证明 ⑱ 抓得住 —— 决策记录 §三.4 原话就是「注入一次 5.1 s 慢命令 ⇒ 必红」。
      它不是维护命令路的一部分，是**故障注入台**；正常档（默认档 / `--自测`）都不含它。

    三条断言（都在真仓上跑，因为「退回一步 ⇒ 超顶」这件事只在真仓的量级上成立）：
      A **真 >5 s**：进程已跑过 5200 ms 再进判据 ⇒ ⑱ 红、读数带实际毫秒。
      B **退回一步**：置 `提速开关=False`（退回线程池 + 两遍全量）+ 0.8 s 真延时 ⇒ ⑱ 红。
        为什么还要加 0.8 s：旧行为本就在硬顶上蹭（决策记录记的实测 4793 / 4818 / 4900 /
        5226 / 5700），单靠「退回一步」会 4993 / 5078 两头跳 ⇒ 加一点真延时才**稳定**越顶。
      C **对照**：正常档（提速开关 True、不注入）⇒ ⑱ **不**红（证明 A / B 的红不是恒真）。

    ★ 每个用例都在**新起的子进程**里跑：⑱ 的读数是从**进程启动**起算的单调量，
      在同一个进程里连跑三次 验证 会把前面的耗时算进后面的读数 ⇒ 读数是假的
      （实测：一个进程里跑完 A 再跑 C，C 的读数变成 13774 ms）。故每例一个进程，
      读数才是「一条正常命令」的量级。
    """
    本件路径 = str(常量.入口文件)

    def 跑一例(注入慢毫秒: int, 提速: bool):
        代码 = (
            "import importlib.util, sys, time\n"
            f"spec = importlib.util.spec_from_file_location('yv', {本件路径!r})\n"
            "m = importlib.util.module_from_spec(spec)\n"
            "sys.modules['yv'] = m\n"
            "spec.loader.exec_module(m)\n"
            "import 一键验证.基础定义.常量 as _状态\n"
            f"_状态.提速开关 = {提速!r}\n"
            f"if {注入慢毫秒}:\n"
            f"    time.sleep({注入慢毫秒} / 1000)\n"
            "r = m.跑全量判据(m.找仓根())\n"
            "条 = [x['缺什么'] for x in r['失败']\n"
            "      if isinstance(x, dict) and x['检查'] == m.检查名[17]]\n"
            "print('⑱条:', 条)\n"
            "print('退出码:', m.算退出码(r))\n"
        )
        起始时刻 = time.perf_counter()
        判定汇总 = subprocess.run(
            [sys.executable, "-c", 代码],
            capture_output=True, text=True, cwd=str(源仓根),
        )
        墙钟 = int((time.perf_counter() - 起始时刻) * 1000)
        是否红 = "⑱条: []" not in 判定汇总.stdout and "⑱条:" in 判定汇总.stdout
        return 墙钟, 是否红, 判定汇总.stdout.strip().replace("\n", " ｜ "), 判定汇总.returncode

    print("承重证明（决策记录 §三.4）：⑱ 的红必须由真墙钟逼出来（本命令墙钟必然 > 5 s）")
    print("每例一个**新进程**（⑱ 的读数从进程启动起算，同进程连跑会把耗时算进去）")
    print("")
    用例 = (
        ("A 真 >5 s（注入 5200 ms）", 5200, True, True),
        ("B 退回一步（提速开关=False）+0.8 s", 800, False, True),
        ("C 对照（正常档）", 0, True, False),
    )
    全过 = True
    for 名称, 注入, 提速, 该红 in 用例:
        墙钟, 是否红, 源文本, 退出码 = 跑一例(注入, 提速)
        这过 = 是否红 == 该红
        全过 = 全过 and 这过
        print(f"{'✓' if 这过 else '✗'} {名称}：该红={该红} 实红={是否红} · 子进程墙钟 {墙钟} ms · {源文本}")
    print("")
    print(f"承重证明{'全部通过' if 全过 else '有不过的断言'}")
    return 0 if 全过 else 1
