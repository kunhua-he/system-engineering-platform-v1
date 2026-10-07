#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""翻译器测试 —— 跑翻译器的单元自测（夹具在临时目录现造，不碰仓里任何件）。

用法（仓根）：

    python3 构建装配/翻译器/翻译器测试.py

退出码：0 = 全过；1 = 有失败。
"""

import sys
import time
import unittest
from pathlib import Path

起始时刻 = time.monotonic()  # 起表点：必须在 import 业务包之前

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 仓根：取共享门禁
sys.path.insert(0, str(Path(__file__).resolve().parent))      # 本目录：取翻译器自测

from 构建装配.门禁 import 自门禁  # noqa: E402


def 入口函数(命令行参数: list) -> int:
    """跑自测套件 ⇒ 0 = 全过。"""
    import 翻译器自测
    套件 = unittest.TestLoader().loadTestsFromModule(翻译器自测)
    跑结果 = unittest.TextTestRunner(verbosity=2).run(套件)
    return 0 if 跑结果.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(自门禁(起始时刻, 入口函数(sys.argv[1:]), 尾巴余量毫秒=200,
                   修法="自测只读临时目录，秒级；变慢多半是夹具落到了大目录上"))
