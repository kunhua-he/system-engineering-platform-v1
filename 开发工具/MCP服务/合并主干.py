#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并主干 —— 把一条已释放/待合并的腿在隔离集成树里合进主干的仓内入口（命令行，不是 MCP 工具）。

用法（在仓根跑）：
    python3 开发工具/MCP服务/合并主干.py <开工ID> [--推送 | --查看现场 | --恢复现场 | --清理现场 | --对齐索引]

入参最小：开工ID（必填，形状 `v1-` 加六位数字）· 推送（可选，默认假）。
出参：成功/退出码 · 目标树与 HEAD · 合并前后 SHA · 门禁读数摘要 + 完整日志路径 ·
      源库差集（表:主键）· 冲突表。

五步：① 校验腿状态与腿树闸0 ② 建隔离集成树 + 合腿 + 源库按主键逻辑重放
      ③ 集成树跑闸0 + 判据自测 + 全案例（与 pre-commit 同口径）④ 绿后推进主干（ff-only 优先）
      ⑤ 同步主目录工作区/index 并复核三方一致。

权限：默认不推；远端动作须显式 `--推送`；不打印令牌、不外传源码密钥、不默认建 PR。
"""

import os
import sys
import time
from pathlib import Path

起始时刻 = time.monotonic()

sys.path.insert(0, str(Path(__file__).resolve().parents[0]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from 构建装配.门禁 import 报告环境步  # noqa: E402
from 开发工具.MCP服务.集成管理.合主干编排 import 派发  # noqa: E402


def 入口函数(命令行参数):
    开工号 = ""
    推送 = False
    现场操作 = "合并"
    for 一个参数 in 命令行参数:
        if 一个参数 in ("--推送", "-p"):
            推送 = True
        elif 一个参数 in ("--查看现场", "--恢复现场", "--清理现场", "--对齐索引"):
            现场操作 = 一个参数[2:]
        elif 一个参数 in ("--help", "-h"):
            print(__doc__)
            return 0
        elif 一个参数.startswith("-"):
            print("不认的参数：%s（用法见 --help）" % 一个参数, file=sys.stderr)
            return 2
        elif not 开工号:
            开工号 = 一个参数
        else:
            print("只认一个开工ID；多给了 %r" % 一个参数, file=sys.stderr)
            return 2
    退出码, 输出文本 = 派发(开工号, 推送, Path(__file__).resolve().parents[2], 操作标识=现场操作)
    print(输出文本)
    return 退出码


if __name__ == "__main__":
    # ★ 解释器唯一化（入口层）：本件常被当脚本直跑（也常被样本夹具仓复制后跑）⇒ sys.path[0]
    #   是脚本目录、不是仓根，**不许 import 仓内模块**，一行赋值即可；语义同 `作业.确保注入()`。
    os.environ.setdefault("V1_PY", sys.executable)
    sys.exit(报告环境步(起始时刻, 入口函数(sys.argv[1:]),
                     说明="合并 + 全量验证 + 全案例：一趟就是它自身的长度（§四 环境步，不判 5 秒顶）"))
