#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全接口冒烟 —— 入口（路由：声明子模块 · 再导出 · 入口函数，零实现）。

给每个能力配真参数发一次请求，看能不能真跑通；判据三档（成功 / 参数错 / 协议错）。
实现全在**同名字文件夹** `测试验证/全接口冒烟/` 里，一个关注点一件；本件只做两件事：
让那个包能被导入、把壳挂上（起表点在 import 业务包之前）。

用法：python3 测试验证/全接口冒烟.py [库名]
产出：测试验证/全接口冒烟_回执.json
"""

import os
import sys
import time

起始时刻 = time.monotonic()  # 壳起表点：必须在 import 业务包**之前**（见 构建装配/门禁/命令壳.py）

本件目录 = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, 本件目录)
sys.path.insert(0, os.path.dirname(本件目录))  # 仓根：取共享壳

from 构建装配.门禁 import 自门禁  # noqa: E402
from 全接口冒烟 import *  # noqa: E402,F401,F403 —— 再导出公开面（`全接口冒烟/__init__.py`）
from 全接口冒烟 import 入口函数  # noqa: E402 —— CLI 入口

if __name__ == '__main__':
    sys.exit(自门禁(起始时刻, 入口函数(sys.argv[1:]), 尾巴余量毫秒=200,
                   修法="整轮要发两百多次真请求；要缩就按库名分片跑（`全接口冒烟.py <库名>`），"
                       "别放宽单次超时、也别省掉协议错那一档"))
