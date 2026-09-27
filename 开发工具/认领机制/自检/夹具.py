# -*- coding: utf-8 -*-
"""账本夹具 —— 样本用的小工具（全部走核心实现，不另写一套）。"""

from .核心 import T0, core


def claim(p, leg, paths, ttl=1800.0, now=T0):
    with core.Ledger(p) as led:
        return core.op_claim(led, leg, paths, ttl, now=now)


def release(p, leg, now=T0):
    with core.Ledger(p) as led:
        return core.op_release(led, leg, now=now)


def reclaim(p, **kw):
    with core.Ledger(p) as led:
        return core.op_reclaim(led, **kw)


def query(p, only_active=True, now=T0):
    with core.Ledger(p) as led:
        return core.op_query(led, only_active=only_active, now=now)


def leases(p):
    """账本里的（腿标识, 路径集）—— 用来断言「没留下半占」「释放真的删了」。"""
    with core.Ledger(p) as led:
        return sorted((l["腿标识"], frozenset(l["路径集"])) for l in led.data["租约"])
