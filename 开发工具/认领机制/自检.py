#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 认领机制 · 自检 —— 判据 + 反向样本 + 正向样本
# 依据：项目文档/设计文档/判据的可信性.md §五（判据的身份证）· §六（元判据）· §二（读数三元）
#
#   反向样本 = 故意造一个该判据**该抓**的违规 ⇒ 断言报红，且报出正确位置与原因（证明判据不空转）
#   正向样本 = 一份干净输入 ⇒ 断言通过（证明判据不误报）
#   缺任一方 ⇒ 该判据标「未验证（未判）」，它的「通过」**不计入通过数**
#
#   读数三元：通过 / 失败 / 未判。**空集不算通过**。
# ★ 本文件与命令行用的是**同一份**核心实现（加载 认领机制.py，不是复制一份）—— 无测试专用旁路。
#   样本里的时间全部**显式传 now**（T0 起算），不 sleep ⇒ 到期判据可复现，且不靠等。
# ★ 标识符一律 ASCII（函数名 · 变量名 · 键名除样本元数据）；中文只在注释与输出串里。

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def load_core():
    spec = importlib.util.spec_from_file_location(
        "claim_core", os.path.join(HERE, "认领机制.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


core = load_core()

T0 = 1700000000.0                                   # 固定基准时刻：样本可复现
P1 = "开发工具/认领机制/说明.md"
P2 = "开发工具/认领机制/账本.json"
P3 = "开发工具/并行工作树.sh"
P4 = "项目文档/设计文档/并行开发与工作区.md"


# ── 样本用的小工具（全部走核心实现，不另写一套） ──────────────────────────────

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


# ── 元判据 M：判据自己的可信性 ────────────────────────────────────────────────

def meta_check(cases):
    meta = {}
    for c in cases:
        m = meta.setdefault(c["判据"], {"反向": 0, "正向": 0, "缺": []})
        m[c["类型"]] += 1
    for m in meta.values():
        m["缺"] = [k for k in ("反向", "正向") if m[k] == 0]
        m["状态"] = "未验证" if m["缺"] else "已验证"
    return meta


def m1_rev(p):
    """反向样本：注入一条「只有正向样本」的判据，元判据必须报它。"""
    meta = meta_check([{"判据": "J9", "类型": "正向"}])
    ok = meta["J9"]["状态"] == "未验证" and meta["J9"]["缺"] == ["反向"]
    return ok, "注入只有正向样本的判据 J9 ⇒ 元判据报 %s（缺 %s）" % (
        meta["J9"]["状态"], meta["J9"]["缺"])


def m1_pos(p):
    """正向样本：成对的判据 ⇒ 元判据报「已验证」（证明元判据不误报）。"""
    meta = meta_check([{"判据": "J9", "类型": "正向"}, {"判据": "J9", "类型": "反向"}])
    ok = meta["J9"]["状态"] == "已验证" and meta["J9"]["缺"] == []
    return ok, "成对样本的判据 J9 ⇒ 元判据报 %s" % meta["J9"]["状态"]


def m2_pos(p):
    """正向样本：读入一份**已知答案**的账本 ⇒ 报出它读到了多少（判据可信性 §三 #5）。"""
    with core.Ledger(p) as led:
        led.data["租约"] = [
            {"腿标识": "leg-a", "路径集": [P1], "认领时间": core.fmt_ts(T0),
             "到期时间": core.fmt_ts(T0 + 1800.0)},
            {"腿标识": "leg-b", "路径集": [P3], "认领时间": core.fmt_ts(T0),
             "到期时间": core.fmt_ts(T0 + 1800.0)},
        ]
        led.save()
    q = query(p, now=T0 + 1)
    ok = (q["账本读到总条数"] == 2 and q["返回条数"] == 2
          and {r["腿标识"] for r in q["租约"]} == {"leg-a", "leg-b"})
    return ok, "手写 2 条租约 ⇒ 读到总条数=%d · 返回=%d" % (
        q["账本读到总条数"], q["返回条数"])


def m2_rev(p):
    """反向样本：账本形状坏了必须**报错**，不许静默当空账本（静默空 ⇒ 把「判不了」算成「通过」）。"""
    with open(p, "w", encoding="utf-8") as f:
        f.write('{"格式版本": 1}\n')                 # 缺「租约」数组
    raised = None
    try:
        query(p, now=T0)
    except Exception as e:
        raised = e
    ok = isinstance(raised, ValueError)
    return ok, "坏账本 ⇒ %s（若静默返回 0 条，就是假绿）" % (
        type(raised).__name__ if raised is not None else "没报错")


def m3_rev(p):
    """反向样本：空集必须判「未判」，不许算通过（判据可信性 §二 · §三 #4）。"""
    q = query(p, now=T0)
    ok = q["返回条数"] == 0 and q["读数"].startswith("未判")
    return ok, "空账本 ⇒ 返回 %d 条 · 读数「%s」（若算通过就是假绿）" % (q["返回条数"], q["读数"])


def m3_pos(p):
    """正向样本：非空账本 ⇒ 读数「判得了」。"""
    claim(p, "leg-a", [P1])
    q = query(p, now=T0 + 1)
    ok = q["返回条数"] == 1 and q["读数"] == "判得了"
    return ok, "非空账本 ⇒ 返回 %d 条 · 读数「%s」" % (q["返回条数"], q["读数"])


def run_cli(ledger, *args):
    return subprocess.run([sys.executable, os.path.join(HERE, "认领机制.py")] + list(args),
                          capture_output=True, text=True,
                          env=dict(os.environ, CLAIM_LEDGER=ledger))


def m4_pos(p):
    """正向样本（**命令行层**）：跑真命令行，输出必须含「被谁占」、退出码必须是 3。
    为什么要有这条：样本只用核心函数 ⇒ 判据覆盖不到渲染/参数层。**本件实测**：`emit` 曾把
    渲染函数本身当结果打印（`<function ...>`），核心样本 17 条全绿，是这条样本逼出来的。"""
    a = run_cli(p, "认领", "leg-a", P1)
    b = run_cli(p, "认领", "leg-b", P1)
    ok = (a.returncode == 0 and b.returncode == 3 and "冲突" in b.stdout
          and "被 leg-a 占" in b.stdout and "<function" not in b.stdout)
    return ok, "第一次退出码=%d · 第二次退出码=%d · 报出被谁占=%s" % (
        a.returncode, b.returncode, "被 leg-a 占" in b.stdout)


def m4_rev(p):
    """反向样本：用法错的命令行不许静默成功（退出码必须 2，且账本一个字没动）。"""
    a = run_cli(p, "认领", "leg-a")            # 缺路径
    b = run_cli(p, "回收")                      # 缺目标
    c = run_cli(p, "认领", "leg-a", "../../../etc/hosts")   # 仓外路径
    ok = a.returncode == 2 and b.returncode == 2 and c.returncode == 2 and leases(p) == []
    return ok, "缺路径=%d · 缺回收目标=%d · 仓外路径=%d · 账本=%s" % (
        a.returncode, b.returncode, c.returncode, leases(p))


CASES = [
    {"判据": "J1", "类型": "反向", "名": "同一路径集两条腿两次认领 ⇒ 第二次必冲突，报出被谁占，不留半占", "跑": j1_rev},
    {"判据": "J1", "类型": "反向", "名": "同一文件换拼法再认领 ⇒ 仍判成同一条路径（覆盖）", "跑": j1_rev_spelling},
    {"判据": "J1", "类型": "正向", "名": "两条腿认领不相交的路径集 ⇒ 都成功，交集为空", "跑": j1_pos},
    {"判据": "J2", "类型": "反向", "名": "跨所有者写同一路径必被拒，且同批空闲路径也不占（原子）", "跑": j2_rev},
    {"判据": "J2", "类型": "正向", "名": "同一腿重复认领自己已占的路径 ⇒ 成功（幂等）", "跑": j2_pos},
    {"判据": "J3", "类型": "反向", "名": "租约过期后别人仍认领不到 ⇒ 没有自动静默回收", "跑": j3_rev},
    {"判据": "J3", "类型": "反向", "名": "未到期的租约不得回收", "跑": j3_rev_early},
    {"判据": "J3", "类型": "反向", "名": "回收目标必须精确：不许连带收走别人的过期租约", "跑": j3_rev_scope},
    {"判据": "J3", "类型": "正向", "名": "显式回收过期租约 ⇒ 成功，之后可再认领", "跑": j3_pos},
    {"判据": "J4", "类型": "反向", "名": "释放没生效（陈旧租约还在）⇒ 再认领必被拒", "跑": j4_rev},
    {"判据": "J4", "类型": "正向", "名": "真释放 ⇒ 账本里已无该腿，且立即可再认领", "跑": j4_pos},
    {"判据": "M1", "类型": "反向", "名": "元判据不空转：只有正向样本的判据必须被报「未验证」", "跑": m1_rev},
    {"判据": "M1", "类型": "正向", "名": "成对样本的判据 ⇒ 元判据报「已验证」（不误报）", "跑": m1_pos},
    {"判据": "M2", "类型": "正向", "名": "解析器自检：读入已知答案的账本 ⇒ 报出读到多少条", "跑": m2_pos},
    {"判据": "M2", "类型": "反向", "名": "账本形状坏 ⇒ 必须报错，不许静默当空账本", "跑": m2_rev},
    {"判据": "M3", "类型": "反向", "名": "空集不算通过：空账本 ⇒ 读数「未判」", "跑": m3_rev},
    {"判据": "M3", "类型": "正向", "名": "非空账本 ⇒ 读数「判得了」", "跑": m3_pos},
    {"判据": "M4", "类型": "正向", "名": "命令行层：认领冲突的输出必须报出被谁占，退出码 3", "跑": m4_pos},
    {"判据": "M4", "类型": "反向", "名": "命令行层：用法错不许静默成功（退出码 2，账本不动）", "跑": m4_rev},
]


def main():
    print("认领机制 · 自检 —— 扫描面：账本的「租约」数组全部条目（每条判据都报它读到多少条）")
    print()
    rows = []
    for c in CASES:
        d = tempfile.mkdtemp(prefix="claim-selftest-")
        try:
            ok, detail = c["跑"](os.path.join(d, "账本.json"))
        except Exception as e:                       # 判据自己崩了也要报，不许静默当通过
            ok, detail = False, "异常：%r" % (e,)
        finally:
            shutil.rmtree(d, ignore_errors=True)
        rows.append((c, ok))
        print("[%s] %s %s  %s" % ("通过" if ok else "失败", c["判据"], c["类型"], c["名"]))
        print("        %s" % detail)

    meta = meta_check(CASES)
    print()
    print("判据 × 样本（元判据 §六：缺任一方 ⇒ 未验证，其「通过」不计入通过数）")
    for j in sorted(meta):
        m = meta[j]
        print("  %s  反向 %d · 正向 %d  ⇒ %s%s" % (
            j, m["反向"], m["正向"], m["状态"],
            ("（缺 %s）" % "、".join(m["缺"])) if m["缺"] else ""))
    n_pass = sum(1 for _, ok in rows if ok)
    n_fail = len(rows) - n_pass
    unverified = sorted(j for j in meta if meta[j]["状态"] == "未验证")
    verdict = "失败" if n_fail else ("未判" if unverified else "通过")
    print()
    print("样本层：通过 %d · 失败 %d（共 %d 条）" % (n_pass, n_fail, len(rows)))
    print("判据层：已验证 %d · 未验证 %d%s" % (
        len(meta) - len(unverified), len(unverified),
        ("（%s）" % "、".join(unverified)) if unverified else ""))
    print("总读数：%s（三元：通过 / 失败 / 未判；空集与未验证都不算通过）" % verdict)
    return 0 if verdict == "通过" else 1


if __name__ == "__main__":
    sys.exit(main())
