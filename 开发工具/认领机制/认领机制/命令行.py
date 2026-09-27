# -*- coding: utf-8 -*-
"""命令行 —— 参数解析 · usage · 动作分派（`main`）。"""

import json
import os
import sys

from .仓根 import ledger_path
from .常量 import (
    DEFAULT_TTL_SEC,
    EXIT_CONFLICT,
    EXIT_NOT_FOUND,
    EXIT_OK,
    EXIT_USAGE,
    GATE_BLOCK,
    GATE_BLOCK_ALIASES,
    GATE_WARN,
)
from .账本 import Ledger
from .提交闸 import git_staged_paths, leg_from_branch, op_gate
from .渲染 import (
    render_claim,
    render_gate,
    render_query,
    render_reclaim,
    render_release,
)
from .语义 import op_claim, op_query, op_reclaim, op_release
from .闸模式 import gate_mode

BOOL_FLAGS = ("强制", "全部过期", "含过期", "json", "硬拦")


def parse_args(args):
    pos, flags = [], {}
    游标 = 0
    while 游标 < len(args):
        实参 = args[游标]
        if 实参.startswith("--"):
            key = 实参[2:]
            if key in BOOL_FLAGS:
                flags[key] = True
                游标 += 1
                continue
            if 游标 + 1 >= len(args):
                raise ValueError("旗标 --%s 缺值" % key)
            flags[key] = args[游标 + 1]
            游标 += 2
            continue
        pos.append(实参)
        游标 += 1
    return pos, flags


def usage():
    print("""认领机制 —— 谁有权改哪条路径（机制二）
  python3 开发工具/认领机制/认领机制.py 认领 <腿标识> <路径> [<路径>...] [--租期秒 N]
  python3 开发工具/认领机制/认领机制.py 收工释放 <腿标识>
  python3 开发工具/认领机制/认领机制.py 查活跃 [--含过期]
  python3 开发工具/认领机制/认领机制.py 回收 (--腿 <腿标识> [--强制] | --全部过期)
  python3 开发工具/认领机制/认领机制.py 提交闸 [--腿 <腿标识>] [--硬拦]
  加 --json 出机器可读的一版。退出码：0 成功 · 2 用法/参数错 · 3 冲突或被拒 · 4 无此租约。
腿标识用 ASCII（字母/数字/短横线/下划线），与 开发工具/并行工作树.sh 的腿名一致。
它只挡得住**愿意来认领的腿**；挡不住什么逐条见 开发工具/认领机制/说明.md。

提交闸（比对「将要提交的路径」与账本里本腿的认领集）：
  ★ **默认只报不拦**（警告模式）—— 现在没人在用认领机制，硬拦会挡掉所有提交。
  硬拦要显式开：`--硬拦` 或环境变量 `CLAIM_GATE=硬拦`（别名 block/1/true）。
  腿标识怎么来（三级，先到先用）：`--腿 <腿标识>` → 环境变量 `CLAIM_LEG` →
  **当前分支按 `腿/<腿名>` 推**（机制一 建的分支就叫这个名，腿标识 = 腿名）。
  三级都没有 ⇒ 读数「判不了」（**不许猜**：猜错腿名就是拿别人的认领集判，那是假绿）。
  退出码**按模式给**（模式的定义只此一处，调用方只写 `exit $CODE`，不许自己再判模式）：
    警告模式：**一律 0** —— 只报不拦，连「判不了」也不拦。
    硬拦模式：全在集里 0 · 有不在集里 3 · 判不了 2（fail-closed：开了硬拦又没配腿标识 = 配置错）。""")


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "帮助"):
        usage()
        return EXIT_OK
    action, rest = argv[0], argv[1:]
    try:
        pos, flags = parse_args(rest)
    except ValueError as 错:
        print("参数错：%s" % 错, file=sys.stderr)
        usage()
        return EXIT_USAGE
    want_json = bool(flags.get("json"))

    def emit(res, render, code):
        print(json.dumps(res, ensure_ascii=False, indent=2) if want_json else render())
        return code

    # ── 提交闸：**单独一条路** ────────────────────────────────────────────────
    # 为什么不能并进下面那个 try：账本坏 ⇒ 那里一律 EXIT_USAGE，而**默认警告模式下
    # 连「判不了」都不许拦**（硬要求：只报不拦）。账本坏不是提交者的错，
    # 更不该在「没人在用认领机制」的时候把所有人的提交挡住 —— 那样闸门就成了「谁都不能提交」。
    if action == "提交闸":
        leg = flags.get("腿") or os.environ.get("CLAIM_LEG") or leg_from_branch()
        mode, raw, known = gate_mode(forced=bool(flags.get("硬拦")))
        if not known:
            print("提交闸：认不得的模式 %r（按 %s 跑）—— 认得的有 %s" % (
                raw, GATE_WARN, "、".join(GATE_BLOCK_ALIASES + (GATE_WARN,))),
                file=sys.stderr)
        staged, how, _ = git_staged_paths()
        try:
            if staged is None:
                raise ValueError(how)
            with Ledger(ledger_path()) as led:
                res = op_gate(led, leg, staged, mode=mode)
            res["基准"] = "git diff --cached（将要提交的路径）· %s" % how
        except (ValueError, OSError, json.JSONDecodeError) as 错:
            # 读数「判不了」，**不是**「通过」——账本读不出时闸什么都没判。
            res = {"结果": "判不了", "腿标识": leg, "模式": mode,
                   "基准": "git diff --cached（将要提交的路径）· %s" % how,
                   "缺什么": "账本或 git 读不出：%r" % (错,),
                   "提示": "账本坏不是提交者的错 ⇒ 警告模式下不拦；修好账本再让它有牙"}
        # ★ 退出码按**模式**给，不按事实给 —— 模式的定义只此一处（gate_mode），
        #   于是调用方（pre-commit 钩子）只写 `exit $CODE` 就对了，不许自己再判模式：
        #   两处各判一次模式 = 两处定义同一件事。
        #   警告模式：**一律 0**（只报不拦，连「判不了」也不拦）；
        #   硬拦模式：全在集里 0 · 有不在集里 3 · 判不了 2（fail-closed：
        #   开了硬拦又没配腿标识 / 账本坏，那是配置错，不是「可以提交」）。
        if mode == GATE_BLOCK:
            gate_code = {"全在集里": EXIT_OK, "有不在集里": EXIT_CONFLICT}.get(
                res["结果"], EXIT_USAGE)
        else:
            gate_code = EXIT_OK
        return emit(res, lambda: render_gate(res), gate_code)

    try:
        with Ledger(ledger_path()) as led:
            if action == "认领":
                if len(pos) < 2:
                    print("参数错：认领 要 <腿标识> 和至少一条 <路径>", file=sys.stderr)
                    return EXIT_USAGE
                res = op_claim(led, pos[0], pos[1:], float(flags.get("租期秒", DEFAULT_TTL_SEC)))
                code = {"成功": EXIT_OK, "冲突": EXIT_CONFLICT}.get(res["结果"], EXIT_USAGE)
                return emit(res, lambda: render_claim(res), code)
            if action == "收工释放":
                if len(pos) != 1:
                    print("参数错：收工释放 要且只要一个 <腿标识>", file=sys.stderr)
                    return EXIT_USAGE
                res = op_release(led, pos[0])
                return emit(res, lambda: render_release(res),
                            EXIT_OK if res["结果"] == "成功" else EXIT_NOT_FOUND)
            if action == "查活跃":
                only_active = not flags.get("含过期")
                res = op_query(led, only_active)
                return emit(res, lambda: render_query(res, only_active), EXIT_OK)
            if action == "回收":
                leg = flags.get("腿")
                all_expired = bool(flags.get("全部过期"))
                force = bool(flags.get("强制"))
                if (leg is None) == (not all_expired):
                    print("参数错：回收 要且只要一个目标（--腿 <腿标识> 或 --全部过期）", file=sys.stderr)
                    return EXIT_USAGE
                if force and leg is None:
                    print("参数错：--强制 只能配 --腿（强收必须指名道姓）", file=sys.stderr)
                    return EXIT_USAGE
                res = op_reclaim(led, leg=leg, all_expired=all_expired, force=force)
                return emit(res, lambda: render_reclaim(res),
                            EXIT_OK if res["结果"] == "成功" else EXIT_CONFLICT)
            if action == "提交闸":
                pass                                     # 已在上面的专门铁轨里处理
            print("未知动作：%s" % action, file=sys.stderr)
            usage()
            return EXIT_USAGE
    except (ValueError, OSError, json.JSONDecodeError) as 错:
        print("账本读写出错：%r" % (错,), file=sys.stderr)
        return EXIT_USAGE
