# -*- coding: utf-8 -*-
"""自检_续缺口 —— 合主干 ① 门禁复跑 / 暂存非冲突件 / 恢复现场重跑的常驻身份证（挂 `--自测`）。

为什么单挂一件：`自检_现场清理.py` 的闭包已 3.5 秒（含真 `--恢复现场` 五步），再并这三条会挤过
`判据 ㊲` 的子进程 5 秒上限；单开一件各守各的 5 秒。
"""

import subprocess
import sys
from pathlib import Path


def 自检_续缺口闭环() -> list:
    """⇒ `[(名称, 是否好, 说明)]`；起不来 / 非 0 退出即不过。"""
    仓根 = Path(__file__).resolve().parents[3]
    工具目录 = 仓根 / "开发工具"
    脚本 = ("import sys\n"
          "from MCP服务.合主干续缺口样本 import 续缺口样本\n"
          "样本表 = 续缺口样本()\n"
          "for 说明, 通过 in 样本表:\n"
          "    print(('OK ' if 通过 else 'XX '), 说明)\n"
          "sys.exit(0 if 样本表 and all(通过 for _, 通过 in 样本表) else 1)\n")
    try:
        回执 = subprocess.run([sys.executable, "-c", 脚本], cwd=str(工具目录),
                          capture_output=True, text=True, timeout=5)
    except Exception as 错误:
        return [("合主干续缺口 端到端闭环", False, "起不来 / 超时：%r" % (错误,))]
    通过 = 回执.returncode == 0
    说明 = "退出码 %d · 闭环样本：\n%s" % (回执.returncode, (回执.stdout or "")[-1600:])
    if not 通过:
        说明 += "\n标准错误：\n" + (回执.stderr or "")[-800:]
    return [("合主干续缺口（① 门禁负载红复跑 · 真判据红仍拒 · 暂存非冲突件 · 恢复现场可重跑）",
             通过, 说明)]
