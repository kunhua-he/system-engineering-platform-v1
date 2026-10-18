# -*- coding: utf-8 -*-
"""自检_长样本 —— 长样本套件的身份证（合主干回归 + 释放行为 + 反馈专项），挂 `一键验证.py --自测`。

为什么挂 `--自测`、不挂 `MCP服务.py --自检`：长样本要起真 bare 仓、走源库重放三态（合主干 8 例
约 23 秒 + 释放行为约 8 秒 + 反馈专项约 25 秒，合计约 55 秒），远超判据 ㊽ 对 `--自检` 的
**5 秒硬顶** ⇒ 与 `自检_集成接管` 同先例，挂 `--自测`（环境步，预算宽松）。`--自检` 一个字节都不加。

**两个 CLI 入口各归其位（不偷换已发布入口语义）**：
  · `MCP服务.py --长样本`（已发布）= 重事务认领链 7 场景（`认领样本.入口`，约 3 秒，硬顶 10 秒内）；
  · `MCP服务.py --长样本全套`（本包追加）= 合主干 + 释放 + 反馈专项 全套长回归（`长样本.入口`）。

读数：**子进程跑仓内真入口** `MCP服务.py --长样本全套` 的退出码（不另写一套实现，也不直接 import
模块绕过 CLI —— 绕过 CLI 正是「长样本无 CLI 入口」漂移的假绿来源）；另附已发布入口 `--长样本`
仍可达（7 场景）与**反样本**（注入反馈专项失败 ⇒ `长样本.入口` 非 0，证明入口真把反馈专项聚合进
退出码，不是「只认领绿」）。
"""

import subprocess
import sys
from pathlib import Path


def 自检_长样本() -> list:
    """⇒ `[(名称, 是否好, 说明)]`；起不来 / 超时 / 非 0 退出即不过。"""
    仓根 = Path(__file__).resolve().parents[4]
    入口件 = 仓根 / "开发工具" / "MCP服务.py"
    样本表 = []
    if not 入口件.is_file():
        return [("长样本全套真入口 `MCP服务.py --长样本全套`", False, "入口件不在：%s" % 入口件)]
    # ① 真入口：全套长回归（合主干 + 释放 + 反馈专项）。环境步：约 55 秒 > 5 秒硬顶 ⇒ 不设 subprocess 超时
    #    （同 `合主干有界跑` 的 `超时秒数=None` 口径；判据 ㊲ 只卡「超时设置」，不设即不受 5 秒上限）。
    try:
        回执 = subprocess.run([sys.executable, str(入口件), "--长样本全套"],
                          cwd=str(仓根), capture_output=True, text=True)
    except Exception as 错误:
        样本表.append(("长样本全套真入口 `MCP服务.py --长样本全套`", False, "起不来：%r" % (错误,)))
        return 样本表
    通过 = 回执.returncode == 0 and "长样本全过" in (回执.stdout or "")
    说明 = "退出码 %d · %s" % (回执.returncode, (回执.stdout or "")[-1200:])
    if not 通过:
        说明 += "\n标准错误：\n" + (回执.stderr or "")[-800:]
    样本表.append(("长样本全套真入口 `MCP服务.py --长样本全套`（合主干回归 8 例 + 源库重放三态 · "
             "释放行为全套 · 反馈专项）—— 不得孤儿", 通过, 说明))
    # ② 已发布入口 `--长样本` 仍可达（7 场景），语义没被 `--长样本全套` 换掉。
    try:
        子进程 = subprocess.run([sys.executable, str(入口件), "--长样本", "--列"],
                          cwd=str(仓根), capture_output=True, text=True)
    except Exception as 错误:
        样本表.append(("已发布入口 `MCP服务.py --长样本` 仍可达（7 场景）", False, "起不来：%r" % (错误,)))
        return 样本表
    行表 = [文本行 for 文本行 in (子进程.stdout or "").splitlines() if 文本行.strip()]
    样本表.append(("已发布入口 `MCP服务.py --长样本` 仍可达：%d 个认领链场景（语义未被 `--长样本全套` 偷换）"
             % len(行表), 子进程.returncode == 0 and len(行表) >= 7,
             "退出码 %d · 首行 %s" % (子进程.returncode, 行表[0] if 行表 else "（无）")))
    # ③ 反样本（承重证明）：注入反馈专项失败 ⇒ `长样本.入口` 非 0；注入通过 ⇒ 0 ——
    #    证入口真把反馈专项聚合进退出码，不是「只认领绿」（这正是本包要修的漂移）。
    脚本 = ("import sys\nsys.path.insert(0, r'{工具目录}')\nfrom unittest.mock import patch\nfrom MCP服务.验证管理 import 长样本 as 模块\nfrom MCP服务.验证样本.集成管理 import 合主干样本, 空改主干样本\nfrom MCP服务.验证样本.施工管理 import 释放样本, 释放作业样本\nfrom MCP服务.验证样本.反馈治理 import 反馈长样本\ndef 跑(反馈码):\n    # ★ 本反样本只证一件事：入口把**反馈专项**的退出码聚合进总退出码（不是「只认领绿」）。\n    #   其余四个套件与这条声明无关 ⇒ 一并 mock 掉：它们原先真跑、且跑两遍（跑(1) + 跑(0)），\n    #   实测占本单元 ~26 s（本单元总 38 s、全套本体只 12 s）。mock 后声明面一条不减。\n    #   （2026-10-11「超 5 秒自动反馈」机制移除 ⇒ 两个套件件已删，同步摘出 mock 面。）\n    注入表 = [('注入', True)]\n    with patch.object(合主干样本, '跑样本', lambda: 0), \\\n         patch.object(释放样本, '释放样本', lambda: 注入表), \\\n         patch.object(反馈长样本, '反馈长样本', lambda 仓根: (反馈码, [])), \\\n         patch.object(释放作业样本, '样本列表', lambda 仓根: 注入表), \\\n         patch.object(空改主干样本, '旧路复现样本', lambda: 注入表), \\\n         patch.object(空改主干样本, '空改主干样本', lambda: 注入表):\n        return 模块.入口([], r'{仓根}')\n失败码 = 跑(1)\n通过码 = 跑(0)\nprint('【注入反样本·预期失败】注入反馈失败码=%d 注入反馈通过码=%d（**故意注入**，不是真运行）' % (失败码, 通过码))\nsys.exit(0 if (失败码 != 0 and 通过码 == 0) else 1)\n").format(工具目录=仓根 / "开发工具", 仓根=仓根)
    try:
        子进程 = subprocess.run([sys.executable, "-c", 脚本], cwd=str(仓根), capture_output=True, text=True)
    except Exception as 错误:
        样本表.append(("反样本：注入反馈专项失败 ⇒ 长样本入口非 0", False, "起不来：%r" % (错误,)))
        return 样本表
    通过 = 子进程.returncode == 0
    样本表.append(("反样本：注入反馈专项失败 ⇒ `长样本.入口` 非 0；注入通过 ⇒ 0（入口真聚合反馈专项，非只认领绿）",
             通过, "【注入反样本】退出码 %d · %s%s" % (子进程.returncode, (子进程.stdout or "").strip(),
                                    (" · 标准错误 " + (子进程.stderr or "")[-400:]) if not 通过 else "")))
    return 样本表
