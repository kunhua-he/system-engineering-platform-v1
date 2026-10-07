# -*- coding: utf-8 -*-
"""自检_长样本 —— 长样本套件（合主干回归 + 释放行为）的身份证（挂 `一键验证.py --自测`）。

为什么放这儿、不放 `MCP服务.py --自检`：长样本要起真 bare 仓、走源库重放三态（合主干 8 例
约 23 秒 + 释放 16 态约 8 秒），远超判据 ㊽ 对 `--自检` 的 **5 秒硬顶** ⇒ 与 `自检_集成接管` 同先例，
挂 `--自测`（环境步，预算宽松）。`--自检` 一个字节都不加。

读数：子进程跑仓内真入口 `MCP服务.py --长样本` 的退出码（不另写一套实现）。
"""

import subprocess
import sys
from pathlib import Path


def 自检_长样本() -> list:
    """⇒ `[(名称, 是否好, 说明)]`；起不来 / 超时 / 非 0 退出即不过。"""
    仓根 = Path(__file__).resolve().parents[3]
    工具目录 = 仓根 / "开发工具"
    脚本 = ("import sys\n"
          "sys.path.insert(0, r'%s')\n"
          "from MCP服务.长样本 import 长样本\n"
          "sys.exit(长样本(r'%s'))\n" % (工具目录, 仓根))
    try:
        # 环境步：长样本一趟约 30 秒 > 5 秒硬顶 ⇒ **不设 subprocess 超时**（同 `合主干有界跑` 的
        # `超时秒数=None` 口径；判据 ㊲ 只卡「超时设置」，不设即不受 5 秒上限）
        回执 = subprocess.run([sys.executable, "-c", 脚本], cwd=str(仓根),
                          capture_output=True, text=True)
    except Exception as 错误:
        return [("长样本套件（合主干回归 + 释放行为）", False, "起不来 / 超时：%r" % (错误,))]
    通过 = 回执.returncode == 0
    说明 = "退出码 %d · %s" % (回执.returncode, (回执.stdout or "")[-1500:])
    if not 通过:
        说明 += "\n标准错误：\n" + (回执.stderr or "")[-800:]
    return [("长样本套件：合主干回归（8 例 + 源库重放三态）· 释放行为（16 态）—— 不得孤儿",
             通过, 说明)]
