# -*- coding: utf-8 -*-
"""判据 J1/J2 —— 认领原子与「第二次必冲突」· 所有者 = 腿标识。"""

from .夹具 import claim, leases
from .核心 import P1, P2, P3, P4


# ── J1 原子 + 「第二次必冲突」 ────────────────────────────────────────────────

def j1_rev(p):
    r1 = claim(p, "leg-a", [P1, P2])
    r2 = claim(p, "leg-b", [P1, P2])
    got = [c["路径"] for c in r2.get("冲突", [])]
    who = sorted({c["被谁占"] for c in r2.get("冲突", [])})
    ok = (r1["结果"] == "成功" and r2["结果"] == "冲突" and set(got) == {P1, P2}
          and who == ["leg-a"] and leases(p) == [("leg-a", frozenset({P1, P2}))])
    return ok, "第二次=%s；冲突路径=%s；被谁占=%s；账本=%s（leg-b 无半占）" % (
        r2["结果"], got, who, [l[0] for l in leases(p)])


def j1_pos(p):
    r1 = claim(p, "leg-a", [P1, P2])
    r2 = claim(p, "leg-b", [P3, P4])
    inter = frozenset(r1.get("路径集", [])) & frozenset(r2.get("路径集", []))
    ok = (r1["结果"] == "成功" and r2["结果"] == "成功" and not inter
          and len(leases(p)) == 2)
    return ok, "两条腿都=%s；路径集交集=%s；账本条数=%d" % (
        (r1["结果"], r2["结果"]), sorted(inter), len(leases(p)))


def j1_rev_spelling(p):
    """反向样本（覆盖）：同一个文件换一种拼法，必须判成同一条路径。"""
    r1 = claim(p, "leg-a", ["开发工具/认领机制/说明.md"])
    r2 = claim(p, "leg-b", ["./开发工具//认领机制/说明.md"])
    ok = r1["结果"] == "成功" and r2["结果"] == "冲突"
    return ok, "换拼法再认领=%s（若成功 ⇒ 归一化漏判，J1 覆盖不到）" % r2["结果"]


# ── J2 所有者 = 腿标识（旧版缺陷：只问「有人占吗」不问「是谁占」） ──────────────

def j2_rev(p):
    claim(p, "leg-a", [P1])
    r = claim(p, "leg-b", [P1, P3])          # P1 被别人占、P3 空闲
    ok = (r["结果"] == "冲突" and [c["路径"] for c in r["冲突"]] == [P1]
          and r["已占路径"] == [] and leases(p) == [("leg-a", frozenset({P1}))])
    return ok, "跨所有者写被拒=%s；冲突=%s；空闲的 P3 也没被占 ⇒ 原子；账本=%s" % (
        r["结果"], [c["路径"] for c in r["冲突"]], [l[0] for l in leases(p)])


def j2_pos(p):
    r1 = claim(p, "leg-a", [P1, P2])
    r2 = claim(p, "leg-a", [P1, P2])         # 同一腿重复认领自己已占的路径
    ok = (r1["结果"] == "成功" and r2["结果"] == "成功" and r2["新增"] == []
          and leases(p) == [("leg-a", frozenset({P1, P2}))])
    return ok, "重复认领=%s；新增=%s；账本条数=%d（幂等）" % (
        r2["结果"], r2["新增"], len(leases(p)))
