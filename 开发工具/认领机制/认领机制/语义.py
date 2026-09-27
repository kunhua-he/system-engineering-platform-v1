# -*- coding: utf-8 -*-
"""语义 —— 租约状态与核心四操作（CLI 与 自检 用的是**同一份**实现，无测试专用旁路）。"""

from .常量 import DEFAULT_TTL_SEC, LEG_CHARS
from .时间 import fmt_ts, now_ts, parse_ts
from .路径 import norm_paths


# ── 语义 3 的判读：到期只是「可回收」，不等于「已回收」 ────────────────────────

def lease_status(lease, now):
    return "已过期" if parse_ts(lease["到期时间"]) <= now else "活跃"


# ── 核心四操作：CLI 与 自检.py 用的是**同一份**实现（不许有测试专用旁路） ────────

def op_claim(led, leg, raw_paths, ttl=DEFAULT_TTL_SEC, now=None):
    """语义 1（原子）· 语义 2（所有者=腿标识，不是路径）· 语义 4（释放后立即可再认领）。"""
    now = now_ts() if now is None else now
    paths, outside = norm_paths(raw_paths)
    if outside:
        return {"结果": "参数错", "腿标识": leg, "仓外路径": outside}
    if not paths:
        return {"结果": "参数错", "腿标识": leg, "缺什么": "路径集为空（空集不是认领）"}
    if any(ch not in LEG_CHARS for ch in leg) or not leg:
        return {"结果": "参数错", "腿标识": leg, "缺什么": "腿标识只能用 ASCII 字母/数字/短横线/下划线"}

    # 语义 2 的判据在这里：问的是「这条路径是不是被**别人**占」，不是「这条路径有人占吗」。
    # 旧版实测缺陷正是后者 —— A 占 X、B 写 X 照样通过。
    holders = {}
    for lease in led.data["租约"]:
        for p in lease["路径集"]:
            holders.setdefault(p, lease)
    conflicts = []
    for p in paths:
        held = holders.get(p)
        if held is not None and held["腿标识"] != leg:
            conflicts.append({"路径": p, "被谁占": held["腿标识"],
                              "状态": lease_status(held, now), "到期时间": held["到期时间"]})
    if conflicts:
        # 语义 1：任一条被占 ⇒ 整体失败，一条都不占（这里直接 return，不碰账本）。
        return {"结果": "冲突", "腿标识": leg, "冲突": conflicts,
                "已占路径": [], "提示": "到期只是可回收；回收要显式：回收 --腿 <腿标识>"}

    mine = None
    for lease in led.data["租约"]:
        if lease["腿标识"] == leg:
            mine = lease
            break
    added = paths
    if mine is None:
        mine = {"腿标识": leg, "路径集": paths, "认领时间": fmt_ts(now),
                "到期时间": fmt_ts(now + ttl)}
        led.data["租约"].append(mine)
    else:
        # 语义 2 后半：同一腿重复认领自己已占的路径 ⇒ 成功（幂等）；顺带续租 + 并入新路径。
        added = sorted(set(paths) - set(mine["路径集"]))
        mine["路径集"] = sorted(set(mine["路径集"]) | set(paths))
        mine["到期时间"] = fmt_ts(now + ttl)
    led.save()
    return {"结果": "成功", "腿标识": leg, "路径集": mine["路径集"],
            "新增": added, "认领时间": mine["认领时间"], "到期时间": mine["到期时间"]}


def op_release(led, leg, now=None):
    """语义 4：释放后立刻可再认领。释放不存在的租约**不算成功**（如实报「无此租约」）。"""
    before = len(led.data["租约"])
    gone = [l for l in led.data["租约"] if l["腿标识"] == leg]
    if not gone:
        return {"结果": "无此租约", "腿标识": leg, "账本读到总条数": before}
    led.data["租约"] = [l for l in led.data["租约"] if l["腿标识"] != leg]
    led.save()
    return {"结果": "成功", "腿标识": leg, "释放条数": len(gone),
            "释放路径集": gone[0]["路径集"]}


def op_reclaim(led, leg=None, all_expired=False, force=False, now=None):
    """语义 3：到期只是「可回收」，回收**必须显式**（没有自动静默回收这条路）。"""
    now = now_ts() if now is None else now
    kept, done, skipped = [], [], []
    for lease in led.data["租约"]:
        expired = lease_status(lease, now) == "已过期"
        hit = (leg is not None and lease["腿标识"] == leg) or all_expired
        if hit and (expired or force):
            done.append({"腿标识": lease["腿标识"], "路径集": lease["路径集"],
                         "到期时间": lease["到期时间"], "是否已过期": expired,
                         "方式": "强收（人确认该腿已死）" if force and not expired else "到期回收"})
            continue
        if hit and leg is not None:
            skipped.append({"腿标识": lease["腿标识"], "到期时间": lease["到期时间"],
                            "原因": "未到期，不回收（要强收须 --腿 X --强制）"})
        kept.append(lease)
    if done:
        led.data["租约"] = kept
        led.save()
    return {"结果": "成功" if done else "未回收", "回收": done, "未回收": skipped}


def op_query(led, only_active=True, now=None):
    """查活跃：每条活跃租约报 腿标识 · 路径集 · 认领时间 · 到期时间。
    读数三元：返回条数为 0 ⇒ 「未判（空集）」，**不算通过**（判据的可信性.md §二）。"""
    now = now_ts() if now is None else now
    rows = [{"腿标识": l["腿标识"], "路径集": l["路径集"], "认领时间": l["认领时间"],
             "到期时间": l["到期时间"], "状态": lease_status(l, now),
             "剩余秒": int(parse_ts(l["到期时间"]) - now)} for l in led.data["租约"]]
    if only_active:
        rows = [r for r in rows if r["状态"] == "活跃"]
    return {"结果": "成功", "租约": rows, "返回条数": len(rows),
            "账本读到总条数": len(led.data["租约"]),
            "读数": "判得了" if rows else "未判（空集不算通过）"}
