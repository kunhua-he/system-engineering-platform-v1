#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""恢复主目录 —— 主目录未提交漂移的仓内**受控恢复入口**（命令行，不是 MCP 工具）。

用法（在仓根跑）：
    python3 开发工具/MCP服务/恢复主目录.py --预期提交 <SHA> --保全位置 <证据目录> --计划 <计划.json>
    python3 开发工具/MCP服务/恢复主目录.py --自测

`计划.json` = 逐件 `[{"路径": …, "当前指纹": …, "目标指纹": …}]`（当前指纹 = 盘上现量 blob，
目标指纹 = `预期提交:路径` 的 blob）。主目录只由公共 Git 元目录解析 ⇒ **不接任意目录输入**。

硬边界（全批先验，任一不过即整批拒、一个字节都不写）：
  ① 主目录只由公共 `--git-common-dir` 解析；② `预期提交` == 主目录当前 `主干` HEAD；
  ③ 主目录 index == `预期提交` 树，且 tracked 漂移集逐件 == 计划表（多一件未知 tracked 差异即拒）；
  ④ 每件盘上 blob == 当前指纹、提交 blob == 目标指纹，`保全位置` 逐件 sha256 与盘上现量一致。

仅复原 tracked 件；未跟踪件与用户目录原样保留。不 clean / 不 reset / 不删树 / 不改 config / 不改 hooks。
"""

import json
import sys
import time
from pathlib import Path

起始时刻 = time.monotonic()

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from 构建装配.门禁 import 报告环境步  # noqa: E402
from 开发工具.MCP服务.恢复主目录编排 import 派发  # noqa: E402


def 入口函数(命令行参数):
    """解析 `--预期提交 / --保全位置 / --计划 / --自测` ⇒ 退出码。"""
    预期提交 = ""
    保全位置 = ""
    表文件 = ""
    序号 = 0
    while 序号 < len(命令行参数):
        实参 = 命令行参数[序号]
        if 实参 == "--自测":
            from 开发工具.MCP服务 import 恢复主目录样本
            return 恢复主目录样本.跑样本()
        if 实参 in ("--help", "-h"):
            print(__doc__)
            return 0
        if 实参 in ("--预期提交", "--保全位置", "--计划"):
            序号 += 1
            if 序号 >= len(命令行参数):
                print("`%s` 后面缺值" % 实参, file=sys.stderr)
                return 2
            值 = 命令行参数[序号]
            if 实参 == "--预期提交":
                预期提交 = 值
            elif 实参 == "--保全位置":
                保全位置 = 值
            else:
                表文件 = 值
        else:
            print("不认的参数：%s（用法见 --help）" % 实参, file=sys.stderr)
            return 2
        序号 += 1
    if not (预期提交 and 保全位置 and 表文件):
        print("三个参数都要给：--预期提交 · --保全位置 · --计划", file=sys.stderr)
        return 2
    退出码, 输出文本 = 派发({"预期提交": 预期提交, "保全位置": 保全位置,
                       "拟恢复文件表": json.loads(Path(表文件).read_text(encoding="utf-8"))},
                      Path(__file__).resolve().parents[2])
    print(输出文本)
    return 退出码


if __name__ == "__main__":
    sys.exit(报告环境步(起始时刻, 入口函数(sys.argv[1:]),
                     说明="受控主目录恢复：一趟即它的长度（不判 5 秒顶）"))
