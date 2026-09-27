# -*- coding: utf-8 -*-
"""跑 —— 逐条跑样本 · 报元判据 · 出三元总读数（`main`）。"""

import os
import shutil
import tempfile

from .判据_元 import meta_check
from .样本表 import CASES


def main():
    print("认领机制 · 自检 —— 扫描面：账本的「租约」数组全部条目（每条判据都报它读到多少条）")
    print()
    rows = []
    for 用例 in CASES:
        临时目录 = tempfile.mkdtemp(prefix="claim-selftest-")
        try:
            ok, detail = 用例["跑"](os.path.join(临时目录, "账本.json"))
        except Exception as 错:                       # 判据自己崩了也要报，不许静默当通过
            ok, detail = False, "异常：%r" % (错,)
        finally:
            shutil.rmtree(临时目录, ignore_errors=True)
        rows.append((用例, ok))
        print("[%s] %s %s  %s" % ("通过" if ok else "失败", 用例["判据"], 用例["类型"], 用例["名"]))
        print("        %s" % detail)

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
