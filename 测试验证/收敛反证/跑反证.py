#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跑反证 —— 运行数据收敛三组反证的可重跑入口（日志 · 临时件 · 守护壳）。

用法：`python3 测试验证/收敛反证/跑反证.py`
      有红项退 1；全绿退 0。每行一条断言：`✓/✗ 组名 ｜ 断言名 ｜ 读数`。

**回执那一组的反证不在这里**：轮转实现在 `测试验证/测试案例/跑案例/src/回执.rs::收敛回执`，
它的反证是同 crate 的单元测试 —— `cargo test -p v1-case-runner 收敛回执`（1200 行假回执 ⇒
只留最近 500 次运行 · 不够界一个字节不动 · 坏行自成一组）。
"""

import sys
import time
from pathlib import Path

起始时刻 = time.monotonic()     # ← 必须在 import 业务包之前（壳口径）

仓根 = Path(__file__).resolve().parents[2]
for 追加路径 in (str(仓根), str(仓根 / "开发工具"), str(Path(__file__).resolve().parent)):
    if 追加路径 not in sys.path:
        sys.path.insert(0, 追加路径)

from 构建装配.门禁 import 自门禁  # noqa: E402
from 反证样本 import 跑全部组  # noqa: E402


def 入口函数(命令行参数):
    """跑三组反证 ⇒ 逐条打读数；有红项退 1（不吞红，也不把红算成「未判」）。"""
    结果表 = 跑全部组()
    红项表 = []
    for 组名, 断言名, 通过, 读数 in 结果表:
        print("%s %s ｜ %s ｜ %s" % ("✓" if 通过 else "✗", 组名, 断言名, 读数))
        if not 通过:
            红项表.append("%s／%s" % (组名, 断言名))
    print("─" * 68)
    print("反证读数：%d 条断言 · 红 %d 条 · 回执组另跑 `cargo test -p v1-case-runner 收敛回执`"
          % (len(结果表), len(红项表)))
    if 红项表:
        print("红项：%s" % "；".join(红项表))
    return 1 if 红项表 else 0


if __name__ == "__main__":
    sys.exit(自门禁(起始时刻, 入口函数(sys.argv[1:]), 尾巴余量毫秒=200,
                    修法="反证是「造脏再收」的活：慢就查临时目录（mkdtemp）与 400 份假件的造法，别放宽断言。"))
