# -*- coding: utf-8 -*-
"""判据 J5 —— 提交闸：改动路径 ⊆ 认领集（且**默认只报不拦**）。"""

import os
import subprocess
import sys
import tempfile

from .子进程 import edit, git_repo, run_claim, run_gate, stage


def j5_rev(账本路径):
    """反向样本：改了**没认领**的路径 ⇒ 闸必须把它报出来（这是判据的主断言）。
    警告模式与硬拦模式**报出来的内容是同一份**，差别只在拒不拒（另有一条样本专测）。"""
    仓目录 = tempfile.mkdtemp(prefix="claim-gate-")
    root, script, why = git_repo(仓目录, {"已认领.rs": "x", "没认领.rs": "y"})
    if root is None:
        return False, why
    run_claim(仓目录, script, "认领", "leg-a", "已认领.rs")
    edit(仓目录, "没认领.rs")
    stage(仓目录, "没认领.rs")
    outs = {}
    for tag, flag in (("警告", []), ("硬拦", ["--硬拦"])):
        运行读数 = run_gate(仓目录, script, "--腿", "leg-a", *flag)
        happy = "没认领.rs" in 运行读数.stdout and "已认领.rs" not in 运行读数.stdout
        outs[tag] = (运行读数.returncode, happy)
    ok = all(happy for _, happy in outs.values())
    return ok, "两种模式都报出「没认领.rs」=%s（警告退出码 %d · 硬拦退出码 %d）" % (
        ok, outs["警告"][0], outs["硬拦"][0])


def j5_pos(账本路径):
    """正向样本：改动**全在**认领集里 ⇒ 报「全在集里」且退出码 0（不误报）。"""
    仓目录 = tempfile.mkdtemp(prefix="claim-gate-")
    root, script, why = git_repo(仓目录, {"已认领.rs": "x", "没认领.rs": "y"})
    if root is None:
        return False, why
    run_claim(仓目录, script, "认领", "leg-a", "已认领.rs")
    edit(仓目录, "已认领.rs")
    stage(仓目录, "已认领.rs")
    运行读数 = run_gate(仓目录, script, "--腿", "leg-a", "--硬拦")
    ok = 运行读数.returncode == 0 and "全在认领集里" in 运行读数.stdout
    return ok, "硬拦模式下全在集里 ⇒ 退出码 %d，读数「全在认领集里」=%s" % (
        运行读数.returncode, "全在认领集里" in 运行读数.stdout)


def j5_mode_rev(账本路径):
    """反向样本（**本件的硬要求**）：默认必须**只报不拦** —— 同样的越界改动，
    不显式开开关时必须退出码 0；显式开 `--硬拦` 才退 3。
    若默认就退 3，这一条会红：那正是「现在没人在用认领机制 ⇒ 硬拦挡掉所有提交」。"""
    仓目录 = tempfile.mkdtemp(prefix="claim-gate-")
    root, script, why = git_repo(仓目录, {"已认领.rs": "x", "没认领.rs": "y"})
    if root is None:
        return False, why
    run_claim(仓目录, script, "认领", "leg-a", "已认领.rs")
    edit(仓目录, "没认领.rs")
    stage(仓目录, "没认领.rs")
    r_默认 = run_gate(仓目录, script, "--腿", "leg-a")
    r_硬 = run_gate(仓目录, script, "--腿", "leg-a", "--硬拦")
    r_环 = run_gate(仓目录, script, "--腿", "leg-a", env={"CLAIM_GATE": "硬拦"})
    ok = (r_默认.returncode == 0 and r_硬.returncode == 3 and r_环.returncode == 3)
    return ok, "默认(没设开关)=%d（**必须 0**）· --硬拦=%d（必须 3）· CLAIM_GATE=硬拦=%d（必须 3）" % (
        r_默认.returncode, r_硬.returncode, r_环.returncode)


def j5_mode_mispell(账本路径):
    """反向样本（覆盖）：开关**拼错**不许静默变成硬拦 —— 必须退回警告、出声、且不拒。"""
    仓目录 = tempfile.mkdtemp(prefix="claim-gate-")
    root, script, why = git_repo(仓目录, {"已认领.rs": "x", "没认领.rs": "y"})
    if root is None:
        return False, why
    run_claim(仓目录, script, "认领", "leg-a", "已认领.rs")
    edit(仓目录, "没认领.rs")
    stage(仓目录, "没认领.rs")
    运行读数 = run_gate(仓目录, script, "--腿", "leg-a", env={"CLAIM_GATE": "硬欄"})
    spoke = "认不得的模式" in (运行读数.stdout + 运行读数.stderr)
    ok = 运行读数.returncode == 0 and spoke
    return ok, "CLAIM_GATE=硬欄（错字）⇒ 退出码 %d（必须 0，不许静默变硬拦）；出声=%s" % (
        运行读数.returncode, spoke)


def j5_empty(账本路径):
    """反向样本（读数三元）：空集不算通过 —— 没有腿标识、或账本里没有本腿租约、
    或本次没有要提交的路径，都必须报「判不了」，不许报「全在集里」。
    （空集若算通过，闸在「什么都没配」时全绿 —— 这正是假绿。）"""
    仓目录 = tempfile.mkdtemp(prefix="claim-gate-")
    root, script, why = git_repo(仓目录, {"a.rs": "x"})
    if root is None:
        return False, why
    edit(仓目录, "a.rs")
    stage(仓目录, "a.rs")
    r1 = run_gate(仓目录, script)                              # 没腿标识
    r2 = run_gate(仓目录, script, "--腿", "leg-a")             # 账本里没这条腿
    subprocess.run(["git", "-C", 仓目录, "reset", "-q"], capture_output=True)
    subprocess.run(["git", "-C", 仓目录, "checkout", "-q", "--", "a.rs"], capture_output=True)
    run_claim(仓目录, script, "认领", "leg-a", "a.rs")
    r3 = run_gate(仓目录, script, "--腿", "leg-a")             # 干净工作区：没有要提交的路径
    got = ["判不了" in 运行读数.stdout for 运行读数 in (r1, r2, r3)]
    nofalse = all("全在认领集里" not in 运行读数.stdout for 运行读数 in (r1, r2, r3))
    ok = all(got) and nofalse
    return ok, "没腿标识=%s · 账本无此腿=%s · 无待提交路径=%s（三条都必须「判不了」）；没有假绿=%s" % (
        got[0], got[1], got[2], nofalse)


def j5_rename(账本路径):
    """反向样本（覆盖 §五 第 5 条那个漏洞）：**改名必须两边都报**（旧路径 + 新路径）。

    只认领了旧路径 ⇒ 新路径必须报「没人认领」；且**改动路径数必须是 2**
    （旧 + 新）—— 旧路径在本腿认领集里，故它不会出现在「不在集里」名单里，
    只能靠**条数**判它有没有被报出来。

    ★ 这条样本第一版**只断言了新路径**，于是「去掉 `--no-renames`」这个变异**没被抓住**
    （实测：默认的改名探测只报新路径，而新路径恰好也不在集里 ⇒ 断言照样绿）。
    是**变异测试**发现样本没牙的（`说明.md` §四 的教训 3 同一类：
    判据在 ≠ 判据覆盖）。现在改用「条数 = 2」⇒ 变异抓得住。
    """
    仓目录 = tempfile.mkdtemp(prefix="claim-gate-")
    root, script, why = git_repo(仓目录, {"旧名.rs": "x"})
    if root is None:
        return False, why
    run_claim(仓目录, script, "认领", "leg-b", "旧名.rs")
    subprocess.run(["git", "-C", 仓目录, "mv", "旧名.rs", "新名.rs"], capture_output=True)
    运行读数 = run_gate(仓目录, script, "--腿", "leg-b")
    seen_new = "新名.rs" in 运行读数.stdout and "没人认领" in 运行读数.stdout
    both = "改动路径 : 2 条" in 运行读数.stdout
    ok = seen_new and both
    return ok, "改名后：新路径报「没人认领」=%s · 改动路径数=2（旧+新都报）=%s —— 去掉 --no-renames 会让后者变 1 条" % (
        seen_new, both)


def j5_subdir(账本路径):
    """反向样本（覆盖）：在**子目录**里跑，路径基准必须仍是仓根 ——
    否则读出来的相对路径与账本里的对不上，闸会假绿。"""
    仓目录 = tempfile.mkdtemp(prefix="claim-gate-")
    root, script, why = git_repo(仓目录, {"子/里面.rs": "x", "外面.rs": "y"})
    if root is None:
        return False, why
    run_claim(仓目录, script, "认领", "leg-a", "子/里面.rs")
    edit(仓目录, "外面.rs")
    stage(仓目录, "外面.rs")
    运行读数 = subprocess.run([sys.executable, script, "提交闸", "--腿", "leg-a"],
                       capture_output=True, text=True,
                       cwd=os.path.join(仓目录, "子"),
                       env={环境键: 环境值 for 环境键, 环境值 in os.environ.items() if 环境键 != "CLAIM_GATE"})
    caught = "外面.rs" in 运行读数.stdout and "判不了" not in 运行读数.stdout
    return caught, "在 子/ 里跑 ⇒ 报出仓根相对的「外面.rs」=%s（基准是仓根，不是当前目录）" % caught


def j5_badledger(账本路径):
    """反向样本（**实跑逼出来的**）：账本坏（形状不对）时 ——
    警告模式**必须仍然不拦**（账本坏不是提交者的错，更不该在没人用认领机制时挡住所有人）；
    硬拦模式才 fail-closed 报「判不了」。且两种模式都**不许报「通过」**（假绿）。"""
    仓目录 = tempfile.mkdtemp(prefix="claim-gate-")
    root, script, why = git_repo(仓目录, {"a.rs": "x"})
    if root is None:
        return False, why
    led = os.path.join(仓目录, "开发工具", "认领机制", "账本.json")
    with open(led, "w", encoding="utf-8") as 柄:
        柄.write('{"格式版本": 1}\n')             # 缺「租约」数组
    edit(仓目录, "a.rs")
    stage(仓目录, "a.rs")
    r_warn = run_gate(仓目录, script, "--腿", "leg-a")
    r_block = run_gate(仓目录, script, "--腿", "leg-a", "--硬拦")
    ok = (r_warn.returncode == 0 and r_block.returncode == 2
          and "判不了" in r_warn.stdout and "判不了" in r_block.stdout
          and "全在认领集里" not in r_warn.stdout and "全在认领集里" not in r_block.stdout)
    return ok, "坏账本 ⇒ 警告退出码 %d（必须 0，不许挡提交）· 硬拦退出码 %d（必须 2，fail-closed）· 两边都报「判不了」" % (
        r_warn.returncode, r_block.returncode)


def j5_branch(账本路径):
    """正向样本：腿标识不给时按**当前分支** `腿/<腿名>` 推（机制一 建的分支就叫这个名）。
    反向的一半：不是 `腿/` 开头的分支 ⇒ 必须「判不了」，**不许猜**。"""
    仓目录 = tempfile.mkdtemp(prefix="claim-gate-")
    root, script, why = git_repo(仓目录, {"已认领.rs": "x", "没认领.rs": "y"})
    if root is None:
        return False, why
    run_claim(仓目录, script, "认领", "leg-a", "已认领.rs")
    edit(仓目录, "没认领.rs")
    stage(仓目录, "没认领.rs")
    # 分支名 = 腿/leg-a ⇒ 不给 --腿 也应认出 leg-a（越界改动照样报出来）
    subprocess.run(["git", "-C", 仓目录, "checkout", "-q", "-b", "腿/leg-a"], capture_output=True)
    r1 = run_gate(仓目录, script)
    ok_branch = "leg-a" in r1.stdout and "没认领.rs" in r1.stdout
    # 分支不是 腿/ 开头 ⇒ 判不了（不许猜）
    subprocess.run(["git", "-C", 仓目录, "checkout", "-q", "-b", "主干", "HEAD~0"], capture_output=True)
    r2 = run_gate(仓目录, script)
    ok_main = "判不了" in r2.stdout
    ok = ok_branch and ok_main
    return ok, "分支 腿/leg-a ⇒ 自动认出 leg-a 并报出越界=%s · 分支「主干」⇒ 判不了（不猜）=%s" % (
        ok_branch, ok_main)


def j5_bench(账本路径):
    """反向样本（**这条是实跑逼出来的**）：脚本所在仓与提交所在仓**不是同一个**时，
    闸必须报「判不了」，不许拿两套不同基准的路径硬比 —— 硬比会全绿而什么都没判。
    造法：在 A 仓跑脚本，把 cwd 放到 B 仓（A≠B）。"""
    脚本仓目录 = tempfile.mkdtemp(prefix="claim-gate-a-")
    提交仓目录 = tempfile.mkdtemp(prefix="claim-gate-b-")
    rootA, scriptA, whyA = git_repo(脚本仓目录, {"x.rs": "1"})
    rootB, scriptB, whyB = git_repo(提交仓目录, {"x.rs": "1"})
    if rootA is None or rootB is None:
        return False, whyA + whyB
    run_claim(脚本仓目录, scriptA, "认领", "leg-a", "x.rs")
    edit(提交仓目录, "x.rs")
    stage(提交仓目录, "x.rs")
    运行读数 = subprocess.run([sys.executable, scriptA, "提交闸", "--腿", "leg-a"],
                       capture_output=True, text=True, cwd=提交仓目录,
                       env={环境键: 环境值 for 环境键, 环境值 in os.environ.items() if 环境键 != "CLAIM_GATE"})
    said = "判不了" in 运行读数.stdout and "不是同一个" in 运行读数.stdout
    return said, "脚本在 A 仓、提交在 B 仓 ⇒ 报「判不了（两个仓根不是同一个）」=%s（硬比会假绿）" % said
