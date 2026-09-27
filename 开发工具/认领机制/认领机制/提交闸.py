# -*- coding: utf-8 -*-
"""提交闸 —— 改动路径 ⊆ 认领集？（这是 §五 说的「真正的强制点」）。

账本说谁占了什么，vs diff 里实际改了哪些路径。口径（说明.md §六 第 2 条）：
**默认只报不拦**，硬拦是显式开关（模式由 `闸模式.py::gate_mode` 归一）。

★ 这里**不做「谁改的」归属推断**：git 的 diff 里没有腿标识，账本里也没有提交。
  所以闸只回答一个问题：「本次要提交的路径，是不是全都在**你报的那个腿**的认领集里」。
  腿标识由提交者显式给出（`--腿` / `CLAIM_LEG`）—— 推断不出来就不许猜（猜了就是假绿）。
"""

import os
import subprocess

from .仓根 import ROOT
from .常量 import EXIT_OK, EXIT_USAGE, GATE_WARN
from .时间 import now_ts
from .路径 import norm_paths
from .语义 import lease_status


def git_toplevel(cwd=None):
    """→ 当前目录所属 git 仓的仓根，读不到给 None。

    ★ 为什么要它、而不用脚本自身的 `ROOT`：账本里的路径是**仓根相对**的，
    `git diff --cached` 吐出来的路径也是**仓根相对**的 —— 两边必须同一个基准。
    脚本的 `ROOT` 是「脚本住在哪个仓」，提交发生在「你站在哪个仓」；**两者可以不是同一个**
    （例：在别处 import 本件、或脚本被拷去守另一个仓）。基准一旦悄悄错开，
    比对就退化成「比两份互不相干的字符串」——**全绿而什么都没判**（假绿）。
    故这里显式取 cwd 的仓根，并与 ROOT 对不上时报「判不了」（见 op_gate）。
    """
    try:
        进程 = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                           capture_output=True, cwd=cwd)
    except OSError:
        return None
    if 进程.returncode != 0:
        return None
    top = 进程.stdout.decode("utf-8", "surrogateescape").strip()
    return os.path.realpath(top) if top else None


def leg_from_branch(cwd=None):
    """→ 当前分支按 `腿/<腿名>` 约定推出的腿标识；不是这条约定就给 None。

    ★ 为什么允许推：`开发工具/并行工作树.sh 新建 <腿名>` 建的分支就叫 `腿/<腿名>`
    —— **分支名就是腿标识**，这是机制一已经定下的落点，这里只是读它，没有另立一套。
    不是 `腿/` 开头的分支（收口方在主树、或人在别的分支上提交）⇒ 返回 None，
    闸报「判不了」（**不许猜**：猜错腿名 = 拿别人的认领集去判，那是假绿）。
    """
    try:
        进程 = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                           capture_output=True, cwd=cwd)
    except OSError:
        return None
    if 进程.returncode != 0:
        return None
    腿标识 = 进程.stdout.decode("utf-8", "surrogateescape").strip()
    return 腿标识[len("腿/"):] if 腿标识.startswith("腿/") and len(腿标识) > len("腿/") else None


def git_staged_paths(root=ROOT):
    """→ (路径集, 说明, 退出码)。走 `git diff --cached`，**不是**工作区 diff ——
    闸问的是「将要提交的那些路径」，工作区里没暂存的改动不算（`git commit` 不会带上它们）。

    两条实测口径：
      · 必须在**仓根**跑：`git -C <子目录> diff --cached --name-only` 仍出**仓根相对**路径，
        故这里显式 `-C root`，让「读出来的路径」与「账本里的路径」同一套基准；
      · `--no-renames`：改名必须**两边都报**（旧路径 + 新路径）。默认的改名探测只报新路径，
        于是「旧租约挂在 a 上、b 没人认领」这条（说明.md §五 第 5 条）就漏过去了。
    """
    cmd = ["git", "-C", root, "diff", "--cached", "--name-only", "-z",
           "--no-renames", "--diff-filter=ACMRDT"]
    try:
        进程 = subprocess.run(cmd, capture_output=True)
    except OSError as 错:
        return None, "调不起 git（%r）" % (错,), EXIT_USAGE
    if 进程.returncode != 0:
        return None, "git 退出码 %d：%s" % (
            进程.returncode, 进程.stderr.decode("utf-8", "replace").strip()), EXIT_USAGE
    raw = 进程.stdout.decode("utf-8", "surrogateescape")
    return [路径项 for 路径项 in raw.split("\0") if 路径项], "git diff --cached --name-only", EXIT_OK


def op_gate(led, leg, staged_raw, mode=GATE_WARN, now=None, root=ROOT):
    """比对「本次改动涉及的文件」与「账本里本腿的认领集」，报出不在集里的。

    返回的 `结果` 三态：
      · `全在集里`  —— 每条改动路径都在本腿认领集里（闸放行）
      · `有不在集里` —— 列出了 `不在认领集` 与 `没人认领`（闸在硬拦模式下拒）
      · `判不了`    —— 缺腿标识 / 本腿无租约 / 仓外路径 / 基准不一致（**不算通过**）
    """
    now = now_ts() if now is None else now
    out = {"腿标识": leg, "模式": mode, "基准": "git diff --cached（将要提交的路径）"}

    if not leg:
        out.update({"结果": "判不了", "缺什么": "没给腿标识（--腿 <腿标识> 或 CLAIM_LEG）",
                    "提示": "git 的 diff 与账本里都没有「谁改的」⇒ 腿标识只能显式给，不许猜"})
        return out

    # ★ 基准一致性：账本路径基准（root）必须与本次提交的仓根同源，否则比对无意义。
    top = git_toplevel()
    if top is not None and top != os.path.realpath(root):
        out.update({"结果": "判不了",
                    "缺什么": "本次提交的仓根（%s）与账本所在的仓根（%s）不是同一个" % (top, root),
                    "提示": "账本路径是仓根相对的 ⇒ 两个仓根不同则比对不成立（不许按字符串硬比）。"
                            "每条腿请在自身的工作树里跑：那里脚本与账本都在同一棵树内"})
        return out

    paths, outside = norm_paths(staged_raw, root=root)
    out["改动路径数"] = len(paths)
    out["改动路径"] = paths
    if outside:
        out.update({"结果": "判不了", "缺什么": "改动里有仓外路径：%s" % "、".join(outside)})
        return out

    holders = {}
    for lease in led.data["租约"]:
        for 进程 in lease["路径集"]:
            holders.setdefault(进程, lease)

    mine = None
    for lease in led.data["租约"]:
        if lease["腿标识"] == leg:
            mine = lease
            break
    if mine is None:
        out.update({"结果": "判不了",
                    "缺什么": "账本里没有腿 %s 的租约（本腿一条路径都没认领）" % leg,
                    "账本读到总条数": len(led.data["租约"]),
                    "提示": "先认领：认领 %s <路径>..." % leg})
        return out

    claimed = set(mine["路径集"])
    out.update({"认领集": sorted(claimed), "认领集大小": len(claimed),
                "到期时间": mine["到期时间"], "租约状态": lease_status(mine, now)})

    if not paths:
        out.update({"结果": "判不了", "缺什么": "本次没有要提交的路径（空集不算通过）"})
        return out

    不在 = [进程 for 进程 in paths if 进程 not in claimed]
    没人认领 = [进程 for 进程 in 不在 if 进程 not in holders]
    被谁占 = {进程: holders[进程]["腿标识"] for 进程 in 不在 if 进程 in holders}
    out["不在认领集"] = 不在
    out["没人认领"] = 没人认领
    out["被别人占"] = 被谁占
    out["结果"] = "全在集里" if not 不在 else "有不在集里"
    return out
