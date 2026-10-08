#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""释放入口 —— `释放` 后台作业的**命令行入口**（带壳；不是 MCP 工具）。

用法（由 `释放作业.释放命令` 拼好；人工排障也可直接跑）：
    python3 开发工具/MCP服务/释放入口.py <开工ID> <仓根> [--跳过验证] [--推送]

它跑**在后台作业进程里**（`作业.起作业` 起的那条），所以「验证是长活」这件事在这里没有 5 秒顶：
跨阈只反馈、不杀活；真验证 + pre-commit 钩子跑完才提交、才翻状态。真实现只有一份
（`释放作业.释放主体`）—— 本件只解析旗标并转交。
"""

import sys
import time
from pathlib import Path

起始时刻 = time.monotonic()

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from 构建装配.门禁 import 报告环境步  # noqa: E402


def 入口函数(命令行参数):
    开工号 = ""
    仓根 = ""
    跳过验证 = False
    推送 = False
    for 一个参数 in 命令行参数:
        if 一个参数 == "--跳过验证":
            跳过验证 = True
        elif 一个参数 == "--推送":
            推送 = True
        elif 一个参数 in ("--help", "-h"):
            print(__doc__)
            return 0
        elif 一个参数.startswith("-"):
            print("不认的参数：%s（用法见 --help）" % 一个参数, file=sys.stderr)
            return 2
        elif not 开工号:
            开工号 = 一个参数
        elif not 仓根:
            仓根 = 一个参数
        else:
            print("只认 开工ID + 仓根 两个位置参；多给了 %r" % 一个参数, file=sys.stderr)
            return 2
    if not 开工号 or not 仓根:
        print("用法：释放入口.py <开工ID> <仓根> [--跳过验证] [--推送]", file=sys.stderr)
        return 2
    from 开发工具.MCP服务.释放作业 import 释放主体
    退出码, 输出文本 = 释放主体(Path(仓根), 开工号, 跳过验证, 推送)
    print(输出文本)
    return 退出码


if __name__ == "__main__":
    sys.exit(报告环境步(起始时刻, 入口函数(sys.argv[1:]),
                     说明="释放：前置 + 验证 + 提交 + 钩子 —— 一趟就是它自身的长度（§四 环境步，不判 5 秒顶）"))
