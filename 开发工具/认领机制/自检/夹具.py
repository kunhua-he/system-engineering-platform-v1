# -*- coding: utf-8 -*-
"""账本夹具 —— 样本用的小工具（全部走核心实现，不另写一套）。"""

from .核心 import T0, core


def claim(账本路径, leg, paths, ttl=1800.0, now=T0):
    with core.Ledger(账本路径) as led:
        return core.op_claim(led, leg, paths, ttl, now=now)


def release(账本路径, leg, now=T0):
    with core.Ledger(账本路径) as led:
        return core.op_release(led, leg, now=now)


def reclaim(账本路径, **kw):
    with core.Ledger(账本路径) as led:
        return core.op_reclaim(led, **kw)


def query(账本路径, only_active=True, now=T0):
    with core.Ledger(账本路径) as led:
        return core.op_query(led, only_active=only_active, now=now)


def leases(账本路径):
    """账本里的（腿标识, 路径集）—— 用来断言「没留下半占」「释放真的删了」。"""
    with core.Ledger(账本路径) as led:
        return sorted((租约条["腿标识"], frozenset(租约条["路径集"])) for 租约条 in led.data["租约"])
