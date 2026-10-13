#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布验收 runner —— 给 T06 / T07 / T08 / T09 四张卡一个带壳的入口（方案 §36 验收卡）。

    python3 测试验证/准入判据/发布验收.py            # 三张卡依次跑
    python3 测试验证/准入判据/发布验收.py T07        # 只跑一张

本文件是**路由**：解析卡号 → 调卡模块的公开面 → 打印 → 退出码；实现在
`发布验收/` 同名字文件夹（一个卡一个文件）—— **本件零实现**。

★ 读数属**夹具自证**（各卡如实报阻断），不是平台侧发布流程的证据：
  平台发布协议 / 意图账本 / 资源配额的本体在 Rust 侧，本树无 Python 可调口。
"""

import sys
import time
from pathlib import Path

起始时刻 = time.monotonic()  # 壳起表点：必须在 import 业务包**之前**（见 构建装配/门禁/命令壳.py）

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 仓根：取共享门禁
from 构建装配.门禁 import 自门禁  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))

from 发布验收 import 入口函数, 卡号表  # noqa: E402

if __name__ == "__main__":
    sys.exit(自门禁(起始时刻, 入口函数(sys.argv[1:]), 尾巴余量毫秒=200,
                   修法="三张卡都是轻量本地夹具（各 ~0.2 s）；慢了先查是不是有卡在做真子进程中止"))
