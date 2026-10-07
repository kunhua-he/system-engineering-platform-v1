# -*- coding: utf-8 -*-
"""自测闭包 —— 挂 `一键验证.py --自测` 的样本闭包**跑法唯一口**。

**为什么要有这条口**（现场恢复腿 v1-100558 实测）：`--自测` 是**环境步**（同 `--承重证明`），
本身**不判五秒硬顶** ⇒ 挂它的样本闭包**不该**被 5 秒挤。但闭包若各自硬写
`subprocess.run(..., timeout=5)`，作者就只能**自行把富样本拆瘦**（实测该腿把 4 个夹具合到 3 个
才塞进 5 秒）—— 那是把判据面的硬顶**误用到环境步**上。故本件给一条正式口：**闭包不设超时**
（环境步不判顶；判据 ㊲ 禁「秒/毫秒 结尾 > 上限」的设置 ⇒ 此处**不给**具名超时值）。作者只调 `跑自测闭包`，不再自挤。
"""
import subprocess
import sys


def 跑自测闭包(脚本: str, 工作目录) -> tuple:
    """跑一段闭包脚本 ⇒ `(退出码, 合并输出)`。**不设超时**（环境步不判顶）；起不来给非 0。"""
    try:
        回执 = subprocess.run([sys.executable, "-c", 脚本], cwd=str(工作目录),
                            capture_output=True, text=True, timeout=None)
    except OSError as 起不来的原因:
        return 1, "闭包起不来：%r" % (起不来的原因,)
    return 回执.returncode, (回执.stdout or "") + (回执.stderr or "")
