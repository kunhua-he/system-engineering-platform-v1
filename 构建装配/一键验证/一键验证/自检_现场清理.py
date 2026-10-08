# -*- coding: utf-8 -*-
"""自检_现场清理 —— 失败集成现场恢复/清理的常驻身份证（挂 `一键验证.py --自测`）。

为什么挂 `--自测`、不挂 `MCP服务.py --自检`：闭环要起真 git 仓、走 `--恢复现场` 完整五步，
`--自检` 的子进程是 5 秒硬顶，装不下（同 `自检_集成接管.py`）。
读数：子进程跑仓内真 git 夹具（系统临时目录，仓一个字节不改）的退出码。
"""

import subprocess
import sys
from pathlib import Path

from .常量 import 硬顶毫秒


def 自检_现场清理闭环() -> list:
    """⇒ `[(名称, 是否好, 说明)]`；起不来 / 非 0 退出即不过。"""
    仓根 = Path(__file__).resolve().parents[3]
    工具目录 = 仓根 / "开发工具"
    脚本 = ("import sys\n"
          "from MCP服务.现场清理样本 import 现场清理样本\n"
          "样本表 = 现场清理样本()\n"
          "for 说明, 通过 in 样本表:\n"
          "    print(('OK ' if 通过 else 'XX '), 说明)\n"
          "sys.exit(0 if 样本表 and all(通过 for _, 通过 in 样本表) else 1)\n")
    try:
        回执 = subprocess.run([sys.executable, "-c", 脚本], cwd=str(工具目录),
                          capture_output=True, text=True, timeout=硬顶毫秒 / 1000)
    except Exception as 错误:
        return [("现场清理 端到端闭环", False, "起不来 / 超时：%r" % (错误,))]
    通过 = 回执.returncode == 0
    说明 = "退出码 %d · 闭环样本：\n%s" % (回执.returncode, (回执.stdout or "")[-1600:])
    if not 通过:
        说明 += "\n标准错误：\n" + (回执.stderr or "")[-800:]
    return [("现场清理 正反样本（① DB-only UU 恢复收敛 · ② 旧主干基清理 · ③ 代码冲突仍拒 · ④ 无现场仍拒）",
             通过, 说明)]
