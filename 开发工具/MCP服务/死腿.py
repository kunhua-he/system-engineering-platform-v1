#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""死腿 —— 只读列出疑似死掉的子代理腿（`~/.zcode/cli/agents`）。

用法：
    python3 开发工具/MCP服务/死腿.py                 # 默认阈值 900 秒 · 上限 20 条
    python3 开发工具/MCP服务/死腿.py --阈值秒 600 --上限 50
    python3 开发工具/MCP服务/死腿.py --自测          # 反向样本：夹具树，断言抓得住

实现全在 `MCP服务/死腿检测.py`（入口零实现，照 `开发规范.md` §六「主文件是路由」）。
只读：零写盘 · 不杀进程 · 不发消息。依据：审计给出的可直接判死判据 —— `status == "running"`
且 `createdAt` 距今 > 阈值 且同目录无 `output.txt`（`status` 会撒谎，实测 4 条死腿全写 running）。
"""
import argparse
import sys
import time
from pathlib import Path

起始时刻 = time.monotonic()  # 壳起表点：必须在 import 业务包**之前**（见 构建装配/门禁/壳.py）

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 仓根：取 构建装配.门禁
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # 开发工具：取 MCP服务 包

from 构建装配.门禁 import 自门禁  # noqa: E402
from MCP服务.死腿检测 import 跑一遍, 跑自测  # noqa: E402


def 入口函数(argv=None):
    解析器 = argparse.ArgumentParser(description="只读列出疑似死掉的子代理腿")
    解析器.add_argument("--阈值秒", type=int, default=900, help="判死的年龄阈值（秒），默认 900")
    解析器.add_argument("--上限", type=int, default=20, help="最多列出几条，默认 20")
    解析器.add_argument("--代理根", default=None, help="默认 ~/.zcode/cli/agents")
    解析器.add_argument("--自测", action="store_true", help="反向样本自测")
    命令行参数 = 解析器.parse_args(argv)
    if 命令行参数.自测:
        return 跑自测()
    return 跑一遍(命令行参数.代理根, 命令行参数.阈值秒, 命令行参数.上限)


if __name__ == "__main__":
    sys.exit(自门禁(起始时刻, 入口函数(), 尾巴余量毫秒=200,
                    修法="本件只读扫一个本地元数据目录，毫秒级；慢就是目录大到离谱或磁盘卡住。"))
