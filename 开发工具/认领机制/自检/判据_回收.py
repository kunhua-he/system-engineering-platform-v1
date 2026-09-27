# -*- coding: utf-8 -*-
"""判据 J3/J4 —— 到期只是「可回收」· 释放后立即可再认领。"""

from .夹具 import claim, leases, query, reclaim, release
from .核心 import P1, P2, P3, T0, core


# ── J3 到期只是「可回收」，回收必须显式 ──────────────────────────────────────

def j3_rev(账本路径):
    claim(账本路径, "leg-a", [P1], ttl=60.0, now=T0)
    late = T0 + 120.0
    查询读数 = query(账本路径, only_active=False, now=late)
    认领读数 = claim(账本路径, "leg-b", [P1], now=late)
    ok = (查询读数["租约"][0]["状态"] == "已过期" and 认领读数["结果"] == "冲突"
          and [冲突条["状态"] for 冲突条 in 认领读数["冲突"]] == ["已过期"]
          and leases(账本路径) == [("leg-a", frozenset({P1}))])
    return ok, "过期读数=%s；leg-b 再认领=%s（自动静默回收会变成功 ⇒ 判据抓得住）" % (
        查询读数["租约"][0]["状态"], 认领读数["结果"])


def j3_rev_early(账本路径):
    claim(账本路径, "leg-a", [P1], ttl=1800.0, now=T0)
    rc = reclaim(账本路径, leg="leg-a", now=T0 + 1)
    认领读数 = claim(账本路径, "leg-b", [P1], now=T0 + 1)
    ok = (rc["结果"] == "未回收" and rc["回收"] == [] and 认领读数["结果"] == "冲突"
          and leases(账本路径) == [("leg-a", frozenset({P1}))])
    return ok, "未到期就回收=%s（%s）；leg-b 仍=%s" % (
        rc["结果"], rc["未回收"][0]["原因"], 认领读数["结果"])


def j3_rev_scope(账本路径):
    """反向样本：回收的目标必须**精确** —— 收 leg-b 的租约，不许连带收走 leg-a 的过期租约。"""
    claim(账本路径, "leg-a", [P1], ttl=60.0, now=T0)
    claim(账本路径, "leg-b", [P3], ttl=60.0, now=T0)
    rc = reclaim(账本路径, leg="leg-b", now=T0 + 120.0)
    ok = (rc["结果"] == "成功" and [回收条["腿标识"] for 回收条 in rc["回收"]] == ["leg-b"]
          and leases(账本路径) == [("leg-a", frozenset({P1}))])
    return ok, "只收 leg-b ⇒ 实收=%s；账本剩=%s（leg-a 的过期租约必须还在，等它自己显式回收）" % (
        [回收条["腿标识"] for 回收条 in rc["回收"]], [租约条[0] for 租约条 in leases(账本路径)])


def j3_pos(账本路径):
    claim(账本路径, "leg-a", [P1], ttl=60.0, now=T0)
    rc = reclaim(账本路径, leg="leg-a", now=T0 + 120.0)
    认领读数 = claim(账本路径, "leg-b", [P1], now=T0 + 120.0)
    ok = (rc["结果"] == "成功" and len(rc["回收"]) == 1 and 认领读数["结果"] == "成功"
          and leases(账本路径) == [("leg-b", frozenset({P1}))])
    return ok, "显式回收=%s（%d 条，%s）；之后 leg-b 认领=%s" % (
        rc["结果"], len(rc["回收"]), rc["回收"][0]["方式"] if rc["回收"] else "-", 认领读数["结果"])


# ── J4 释放后立即可再认领 ────────────────────────────────────────────────────

def j4_rev(账本路径):
    """反向样本：造一个「释放没生效」的账本（陈旧租约还留着）⇒ 再认领必被拒。"""
    with core.Ledger(账本路径) as led:
        led.data["租约"].append({"腿标识": "leg-a", "路径集": [P1],
                                 "认领时间": core.fmt_ts(T0),
                                 "到期时间": core.fmt_ts(T0 + 1800.0)})
        led.save()
    认领读数 = claim(账本路径, "leg-b", [P1], now=T0 + 1)
    ok = 认领读数["结果"] == "冲突" and 认领读数["冲突"][0]["被谁占"] == "leg-a"
    return ok, "陈旧租约未清 ⇒ leg-b=%s（若这里成功，J4 是空转）" % 认领读数["结果"]


def j4_pos(账本路径):
    claim(账本路径, "leg-a", [P1, P2])
    rel = release(账本路径, "leg-a")
    认领读数 = claim(账本路径, "leg-b", [P1, P2], now=T0 + 1)
    ok = (rel["结果"] == "成功" and rel["释放条数"] == 1 and 认领读数["结果"] == "成功"
          and leases(账本路径) == [("leg-b", frozenset({P1, P2}))])
    return ok, "释放=%s（%d 条）；立刻再认领=%s；账本=%s" % (
        rel["结果"], rel["释放条数"], 认领读数["结果"], [租约条[0] for 租约条 in leases(账本路径)])
