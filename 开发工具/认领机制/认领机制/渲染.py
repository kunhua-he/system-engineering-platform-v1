# -*- coding: utf-8 -*-
"""渲染 —— 人读的那一版输出（认领 · 查活跃 · 收工释放 · 回收 · 提交闸）。"""

import json

from .常量 import GATE_BLOCK, GATE_WARN


def render_gate(res):
    mode = res.get("模式", GATE_WARN)
    head = {"全在集里": "提交闸：全在认领集里 ⇒ 放行",
            "有不在集里": "提交闸：有路径不在认领集里",
            "判不了": "提交闸：判不了（不算通过）"}.get(res["结果"], "提交闸：%s" % res["结果"])
    out = ["%s（模式=%s）" % (head, mode),
           "  腿标识   : %s" % (res.get("腿标识") or "（没给）"),
           "  基准     : %s" % res.get("基准", "-")]
    if res["结果"] == "判不了":
        out.append("  缺什么   : %s" % res.get("缺什么", "-"))
        if res.get("提示"):
            out.append("  提示     : %s" % res["提示"])
        if "账本读到总条数" in res:
            out.append("  账本     : 读到 %d 条租约" % res["账本读到总条数"])
        return "\n".join(out)

    out += ["  改动路径 : %d 条（账本里本腿认领 %d 条，租约%s）" % (
        res["改动路径数"], res["认领集大小"], res.get("租约状态", "-"))]
    if res["结果"] == "全在集里":
        return "\n".join(out)
    out.append("  不在认领集里 %d 条：" % len(res["不在认领集"]))
    for 路径 in res["不在认领集"]:
        who = res["被别人占"].get(路径)
        out.append("    %s%s" % (路径, "（被 %s 占）" % who if who else "（没人认领）"))
    out.append("  ⇒ %s" % ("**只报不拦**（警告模式）—— 要它拒提交，见 开发工具/认领机制/说明.md §六："
                           "设 CLAIM_GATE=硬拦 或给 --硬拦"
                           if mode != GATE_BLOCK else
                           "**硬拦模式**：这些路径不在你的认领集里 ⇒ 拒提交。"))
    return "\n".join(out)


def render_claim(res):
    if res["结果"] == "成功":
        return "\n".join(["认领成功 —— %s 独占 %d 条路径" % (res["腿标识"], len(res["路径集"])),
                          "  新增路径 : %s" % ("、".join(res["新增"]) or "（无，全是自身已占的）"),
                          "  路径集   : %s" % "、".join(res["路径集"]),
                          "  认领时间 : %s" % res["认领时间"],
                          "  到期时间 : %s（到期只是可回收，不会自动回收）" % res["到期时间"]])
    if res["结果"] == "冲突":
        out = ["认领冲突 —— 整体失败，一条路径都没占（原子）",
               "  腿标识   : %s" % res["腿标识"],
               "  被占 %d 条 :" % len(res["冲突"])]
        for 冲突条 in res["冲突"]:
            out.append("    %s" % 冲突条["路径"])
            out.append("      被 %s 占（%s，到期 %s）" % (冲突条["被谁占"], 冲突条["状态"], 冲突条["到期时间"]))
        out.append("  提示     : %s" % res["提示"])
        return "\n".join(out)
    return "认领失败 —— %s：%s" % (res["结果"], json.dumps(res, ensure_ascii=False))


def render_query(res, only_active):
    out = ["查活跃 —— 返回 %d 条（账本里读到 %d 条）· 读数：%s" % (
        res["返回条数"], res["账本读到总条数"], res["读数"])]
    for 租约条 in res["租约"]:
        out += ["  %s" % 租约条["腿标识"],
                "    路径集   : %s" % "、".join(租约条["路径集"]),
                "    认领时间 : %s" % 租约条["认领时间"],
                "    到期时间 : %s" % 租约条["到期时间"],
                "    状态     : %s（剩余 %d 秒）" % (租约条["状态"], 租约条["剩余秒"])]
    if not res["租约"]:
        out.append("  （返回 0 条 ⇒ 未判，不是通过。"
                   + ("要看已过期的加 --含过期）" if only_active else "账本是空的）"))
    return "\n".join(out)


def render_release(res):
    if res["结果"] == "成功":
        return "收工释放 —— %s 释放 %d 条，路径集 %s 立刻可被任何腿再认领" % (
            res["腿标识"], res["释放条数"], "、".join(res["释放路径集"]))
    return "收工释放 —— %s：无此租约（账本里读到 %d 条）。没占过就不算释放成功。" % (
        res["腿标识"], res["账本读到总条数"])


def render_reclaim(res):
    out = ["回收 —— %s" % res["结果"]]
    for 回收条 in res["回收"]:
        out.append("  已回收 %s（%s，到期 %s，是否已过期=%s）" % (
            回收条["腿标识"], 回收条["方式"], 回收条["到期时间"], 回收条["是否已过期"]))
    for 未回收条 in res["未回收"]:
        out.append("  未回收 %s：%s（到期 %s）" % (未回收条["腿标识"], 未回收条["原因"], 未回收条["到期时间"]))
    if not res["回收"]:
        out.append("  一条都没回收 —— 回收必须显式指定目标，且只有「已过期」或「--强制」才收。")
    return "\n".join(out)
