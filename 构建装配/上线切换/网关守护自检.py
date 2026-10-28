#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""网关守护壳自检 —— 可重跑的**真跑式**反证（`sh -n` 查不出运行期 `bad substitution`）。

    python3 构建装配/上线切换/网关守护自检.py            # 跑同目录那份壳
    python3 构建装配/上线切换/网关守护自检.py <壳路径>    # 跑指定的壳（反证 / 排障用）

有红项退 1，全绿退 0。五条断言（自检 / 覆盖 / 轮转 ×3）的实现在同目录
`网关守护自检实现.py`，本件只做入口：取壳路径 · 打读数 · 交自门禁。
判据 71 在一键验证里真跑那份实现 —— 改了壳不跑就红。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

起点时刻 = time.monotonic()   # ← 必须在装载业务件之前（命令级硬顶从这一刻起算）

本目录 = Path(__file__).resolve().parent
仓根 = 本目录.parents[1]
for 追加路径 in (str(本目录), str(仓根)):
    if 追加路径 not in sys.path:
        sys.path.insert(0, 追加路径)

from 网关守护自检实现 import 守护壳件名, 跑自检, 自检断言条数  # noqa: E402
from 构建装配.门禁 import 自门禁  # noqa: E402


def 入口函数(命令行参数: list) -> int:
    """跑一遍自检 ⇒ 逐条打读数；有红项退 1（不吞红，也不把红算成「未判」）。"""
    壳路径 = Path(命令行参数[0]).resolve() if 命令行参数 else 本目录 / 守护壳件名
    结果表 = 跑自检(壳路径)
    红项表 = []
    for 断言名, 通过, 读数 in 结果表:
        print("%s %s ｜ %s" % ("✓" if 通过 else "✗", 断言名, 读数))
        if not 通过:
            红项表.append(断言名)
    print("─" * 68)
    print("网关守护壳自检：%d 条断言（应为 %d）· 红 %d 条 · 壳 %s"
          % (len(结果表), 自检断言条数, len(红项表), 壳路径))
    return 1 if 红项表 or len(结果表) != 自检断言条数 else 0


if __name__ == "__main__":
    sys.exit(自门禁(起点时刻, 入口函数(sys.argv[1:]), 尾巴余量毫秒=200,
                    修法="自检是「造脏再收」的活：慢就查临时目录（mkdtemp）与 6 MiB 造件，别放宽断言。"))
