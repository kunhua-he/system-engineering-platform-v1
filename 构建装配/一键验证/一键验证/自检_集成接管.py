# -*- coding: utf-8 -*-
"""自检_集成接管 —— 集成接管**端到端闭环**的常驻身份证（挂 `一键验证.py --自测`）。

为什么放这儿、不放 `MCP服务.py --自检`：闭环要起真 git 裸主仓、走 `--恢复现场` 五步（约 2 秒），
而判据 ㊽ 对 `--自检` 的子进程是 **5 秒硬顶**（`判据_MCP自检.py`）—— 基线已 3.4 秒，装不下。
`--自测` 是环境步、预算宽松（同 `--承重证明`）⇒ 集成接管的**全部**样本都挂这儿（`--自检`
一个字节都不加，`闸 1` 的墙钟余量不动）。

读数：子进程跑仓内真 git 夹具（系统临时目录，仓一个字节不改）的退出码。
"""

import subprocess
import sys
from pathlib import Path


def 自检_集成接管闭环() -> list:
    """⇒ `[(名称, 是否好, 说明)]`；起不来 / 超时 / 非 0 退出即不过。"""
    仓根 = Path(__file__).resolve().parents[3]
    工具目录 = 仓根 / "开发工具"
    脚本 = ("import sys\n"
          "from MCP服务.集成接管样本 import 接管样本\n"
          "样本表 = 接管样本(r'%s', None)\n"
          "for 说明, 通过 in 样本表:\n"
          "    print(('OK ' if 通过 else 'XX '), 说明)\n"
          "sys.exit(0 if 样本表 and all(通过 for _, 通过 in 样本表) else 1)\n" % 仓根)
    try:
        回执 = subprocess.run([sys.executable, "-c", 脚本], cwd=str(工具目录),
                          capture_output=True, text=True, timeout=5)
    except Exception as 错误:
        return [("集成接管端到端闭环", False, "起不来 / 超 5 秒：%r" % (错误,))]
    通过 = 回执.returncode == 0
    说明 = "退出码 %d · 闭环样本：\n%s" % (回执.returncode, (回执.stdout or "")[-1200:])
    if not 通过:
        说明 += "\n标准错误：\n" + (回执.stderr or "")[-800:]
    return [("集成接管 绑定档 + 拒绝档 + 端到端闭环（接管 → v1_edit → 暂存 → 恢复现场 → 清树 + 解除接管）",
             通过, 说明)]
