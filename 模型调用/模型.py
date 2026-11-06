#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模型调用 —— 底座一个能力（2519 一次对话）包三行用法。

    from 模型 import 对话
    print(对话("你好"))

整条链（复用或拉起 → 等就绪 → 申请许可 → 连接 → 提交 → 取结果 → 清理）都在底座里办完。
本件只把参数拼成底座要的形状，不另拼十几步请求 —— 否则同一件事就有两套做法。

命令行：

    python 模型调用/模型.py              # 问一句默认的自我介绍
    python 模型调用/模型.py "你的问题"

本文件是**路由**（`项目文档/开发规范/开发规范.md` 第六节）：只做三件事 —— 声明子模块 ·
再导出公开面 · 零实现。实现在**同名字文件夹** `模型/` 里，一个关注点一个文件：

- `底座地址.py` —— 网关 · 调用路径 · 三个能力号 · 超时口径
- `底座应答.py` —— `模型错误` · 打一次底座 · 剥信封
- `对话请求.py` —— `对话`（消息形状 · 一句一答 · 任务句柄接着取）
- `看图请求.py` —— `看图`（本地图片读成 data URL）
- `资源状态.py` —— `状态`（现在跑着哪些模型）
- `命令入口.py` —— 命令行 `入口函数`

墙钟由壳照实报到 stderr（`构建装配/门禁`）—— stdout 只有答案本身。
"""

import os
import sys
import time

起始时刻 = time.monotonic()  # 壳起表点：必须在 import 业务包**之前**

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 仓根
from 构建装配.门禁 import 自门禁  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from 模型 import *  # noqa: E402,F401,F403 —— 再导出公开面（`模型/__init__.py`）
from 模型 import 入口函数  # noqa: E402 —— 命令行入口

if __name__ == "__main__":
    sys.exit(自门禁(起始时刻, 入口函数(sys.argv[1:]), 尾巴余量毫秒=200,
                   修法="本入口只发一个请求：慢在推理侧，热一次模型再跑；不要把超时拉长"))
