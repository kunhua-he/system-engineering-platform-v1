# -*- coding: utf-8 -*-
"""跑 —— 逐条跑样本 · 报元判据 · 出三元总读数（`main`）。

**样本并发跑**：29 条彼此独立（每条自造一个临时仓，重活都在子进程里的 git / python），
故用线程池。为什么必须并发：串行实测 **4.9 秒** ⇒ 超 `自门禁` 的 4800 ms 阈值，
五秒硬顶当场判红。修法是**提速**，不是放宽上限、更不是砍样本
（`项目文档/决策记录/2026-09-27_所有运行五秒硬顶.md` §一：五秒硬顶无例外）。
"""

import os
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor

from .判据_元 import meta_check
from .样本表 import CASES

并发度 = 8


def _跑一条(样例):
    """跑一条样本 ⇒ `(ok, detail)`。自带临时仓 ⇒ 与别的样本无共享状态。"""
    临时目录 = tempfile.mkdtemp(prefix="claim-selftest-")
    try:
        return 样例["跑"](os.path.join(临时目录, "账本.json"))
    except Exception as 错:                      # 判据自己崩了也要报，不许静默当通过
        return False, "异常：%r" % (错,)
    finally:
        shutil.rmtree(临时目录, ignore_errors=True)


def main():
    print("认领机制 · 自检 —— 扫描面：账本的「租约」数组全部条目（每条判据都报它读到多少条）")
    print()
    with ThreadPoolExecutor(max_workers=min(并发度, len(CASES))) as 池:
        结果 = list(池.map(_跑一条, CASES))     # map 保序 ⇒ 打印顺序与 CASES 一致
    rows = [(样例, ok) for 样例, (ok, _详情) in zip(CASES, 结果)]
    for (样例, ok), (_ok, 详情) in zip(rows, 结果):
        print("[%s] %s %s  %s" % ("通过" if ok else "失败", 样例["判据"], 样例["类型"], 样例["名"]))
        print("        %s" % 详情)

    meta = meta_check(CASES)
    print()
    print("判据 × 样本（元判据 §六：缺任一方 ⇒ 未验证，其「通过」不计入通过数）")
    for 判据名 in sorted(meta):
        判据元 = meta[判据名]
        print("  %s  反向 %d · 正向 %d  ⇒ %s%s" % (
            判据名, 判据元["反向"], 判据元["正向"], 判据元["状态"],
            ("（缺 %s）" % "、".join(判据元["缺"])) if 判据元["缺"] else ""))
    n_pass = sum(1 for _, ok in rows if ok)
    n_fail = len(rows) - n_pass
    unverified = sorted(判据名 for 判据名 in meta if meta[判据名]["状态"] == "未验证")
    verdict = "失败" if n_fail else ("未判" if unverified else "通过")
    print()
    print("样本层：通过 %d · 失败 %d（共 %d 条）" % (n_pass, n_fail, len(rows)))
    print("判据层：已验证 %d · 未验证 %d%s" % (
        len(meta) - len(unverified), len(unverified),
        ("（%s）" % "、".join(unverified)) if unverified else ""))
    print("总读数：%s（三元：通过 / 失败 / 未判；空集与未验证都不算通过）" % verdict)
    return 0 if verdict == "通过" else 1
