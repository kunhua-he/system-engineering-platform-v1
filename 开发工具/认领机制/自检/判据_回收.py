# -*- coding: utf-8 -*-
"""判据 J3/J4 —— 到期只是「可回收」· 释放后立即可再认领。"""

from .夹具 import claim, leases, query, reclaim, release
from .核心 import P1, P2, P3, T0, core


# ── J3 到期只是「可回收」，回收必须显式 ──────────────────────────────────────

def j3_rev(p):
    claim(p, "leg-a", [P1], ttl=60.0, now=T0)
    late = T0 + 120.0
    q = query(p, only_active=False, now=late)
    r = claim(p, "leg-b", [P1], now=late)
    ok = (q["租约"][0]["状态"] == "已过期" and r["结果"] == "冲突"
          and [c["状态"] for c in r["冲突"]] == ["已过期"]
          and leases(p) == [("leg-a", frozenset({P1}))])
    return ok, "过期读数=%s；leg-b 再认领=%s（自动静默回收会变成功 ⇒ 判据抓得住）" % (
        q["租约"][0]["状态"], r["结果"])


def j3_rev_early(p):
    claim(p, "leg-a", [P1], ttl=1800.0, now=T0)
    rc = reclaim(p, leg="leg-a", now=T0 + 1)
    r = claim(p, "leg-b", [P1], now=T0 + 1)
    ok = (rc["结果"] == "未回收" and rc["回收"] == [] and r["结果"] == "冲突"
          and leases(p) == [("leg-a", frozenset({P1}))])
    return ok, "未到期就回收=%s（%s）；leg-b 仍=%s" % (
        rc["结果"], rc["未回收"][0]["原因"], r["结果"])


def j3_rev_scope(p):
    """反向样本：回收的目标必须**精确** —— 收 leg-b 的租约，不许连带收走 leg-a 的过期租约。"""
    claim(p, "leg-a", [P1], ttl=60.0, now=T0)
    claim(p, "leg-b", [P3], ttl=60.0, now=T0)
    rc = reclaim(p, leg="leg-b", now=T0 + 120.0)
    ok = (rc["结果"] == "成功" and [d["腿标识"] for d in rc["回收"]] == ["leg-b"]
          and leases(p) == [("leg-a", frozenset({P1}))])
    return ok, "只收 leg-b ⇒ 实收=%s；账本剩=%s（leg-a 的过期租约必须还在，等它自己显式回收）" % (
        [d["腿标识"] for d in rc["回收"]], [l[0] for l in leases(p)])


def j3_pos(p):
    claim(p, "leg-a", [P1], ttl=60.0, now=T0)
    rc = reclaim(p, leg="leg-a", now=T0 + 120.0)
    r = claim(p, "leg-b", [P1], now=T0 + 120.0)
    ok = (rc["结果"] == "成功" and len(rc["回收"]) == 1 and r["结果"] == "成功"
          and leases(p) == [("leg-b", frozenset({P1}))])
    return ok, "显式回收=%s（%d 条，%s）；之后 leg-b 认领=%s" % (
        rc["结果"], len(rc["回收"]), rc["回收"][0]["方式"] if rc["回收"] else "-", r["结果"])


# ── J4 释放后立即可再认领 ────────────────────────────────────────────────────

def j4_rev(p):
    """反向样本：造一个「释放没生效」的账本（陈旧租约还留着）⇒ 再认领必被拒。"""
    with core.Ledger(p) as led:
        led.data["租约"].append({"腿标识": "leg-a", "路径集": [P1],
                                 "认领时间": core.fmt_ts(T0),
                                 "到期时间": core.fmt_ts(T0 + 1800.0)})
        led.save()
    r = claim(p, "leg-b", [P1], now=T0 + 1)
    ok = r["结果"] == "冲突" and r["冲突"][0]["被谁占"] == "leg-a"
    return ok, "陈旧租约未清 ⇒ leg-b=%s（若这里成功，J4 是空转）" % r["结果"]


def j4_pos(p):
    claim(p, "leg-a", [P1, P2])
    rel = release(p, "leg-a")
    r = claim(p, "leg-b", [P1, P2], now=T0 + 1)
    ok = (rel["结果"] == "成功" and rel["释放条数"] == 1 and r["结果"] == "成功"
          and leases(p) == [("leg-b", frozenset({P1, P2}))])
    return ok, "释放=%s（%d 条）；立刻再认领=%s；账本=%s" % (
        rel["结果"], rel["释放条数"], r["结果"], [l[0] for l in leases(p)])
