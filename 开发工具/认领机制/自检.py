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


# ── J5 提交闸：改动路径 ⊆ 认领集（且**默认只报不拦**） ─────────────────────────
#
# 为什么这些样本要**真起一个 git 仓**：提交闸读的是 `git diff --cached`。
# 用假数据喂 `op_gate` 只能验「集合比对」这一层，验不到「路径基准是仓根不是子目录」
# 「改名两边都报」这两条 —— 而那两条正是 §五 第 5 条那个漏洞的入口。
# 判据要覆盖输出层与 git 层，故这里起真仓、真 `git add`、真子进程。

def git_repo(d, files):
    """在 d 里造一个**能跑真命令行**的仓：git 仓 + `rust-toolchain.toml` + 一份本件脚本。

    为什么要连脚本一起拷进去：脚本的仓根靠「向上找 `rust-toolchain.toml`」定，
    而账本里的路径是**仓根相对**的。若脚本住在 A 仓、提交发生在 B 仓，两个仓根错开
    ⇒ 比对退化（假绿）。提交闸对这种情况报「判不了」（`op_gate` 里的基准一致性检查）。
    所以样本必须让「脚本所在仓」与「提交所在仓」是同一个 —— 这才是真部署的样子。
    → (仓根, 脚本路径, 说明)
    """
    def run(*args):
        return subprocess.run(["git", "-C", d] + list(args),
                              capture_output=True, text=True)
    if run("init", "-q", ".").returncode != 0:
        return None, None, "git init 失败"
    run("config", "user.email", "selftest@local")
    run("config", "user.name", "selftest")
    with open(os.path.join(d, "rust-toolchain.toml"), "w", encoding="utf-8") as f:
        f.write('channel = "stable"\n')
    files = dict(files)
    files["开发工具/认领机制/自检占位.txt"] = "占位（本仓只是样本的舞台）\n"
    for rel, body in files.items():
        p = os.path.join(d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(body)
    shutil.copyfile(os.path.join(HERE, "认领机制.py"),
                    os.path.join(d, "开发工具", "认领机制", "认领机制.py"))
    if run("add", "-A").returncode != 0:
        return None, None, "git add 失败"
    c = run("commit", "-qm", "init")
    return (d, os.path.join(d, "开发工具", "认领机制", "认领机制.py"),
            "git 仓就绪" if c.returncode == 0 else "git commit 失败")


def run_gate(d, script, *args, env=None):
    """在真仓 d 里跑提交闸子进程（cwd=d ⇒ 仓根就是 d）。env 用来试 CLAIM_GATE 这个开关。"""
    e = dict(os.environ)
    e.pop("CLAIM_GATE", None)              # 不许外面环境漏进来干扰「默认」那一条
    e.update(env or {})
    return subprocess.run([sys.executable, script, "提交闸"] + list(args),
                          capture_output=True, text=True, cwd=d, env=e)


def run_claim(d, script, *args):
    """在真仓 d 里跑 `认领` 子进程（账本就落该仓自己的目录里）。"""
    return subprocess.run([sys.executable, script] + list(args),
                          capture_output=True, text=True, cwd=d)


def stage(d, *rels):
    return subprocess.run(["git", "-C", d, "add"] + list(rels),
                          capture_output=True, text=True).returncode == 0


def edit(d, rel, text="改了一行\n"):
    with open(os.path.join(d, rel), "a", encoding="utf-8") as f:
        f.write(text)


def j5_rev(p):
    """反向样本：改了**没认领**的路径 ⇒ 闸必须把它报出来（这是判据的主断言）。
    警告模式与硬拦模式**报出来的内容是同一份**，差别只在拒不拒（另有一条样本专测）。"""
    d = tempfile.mkdtemp(prefix="claim-gate-")
    root, script, why = git_repo(d, {"已认领.rs": "x", "没认领.rs": "y"})
    if root is None:
        return False, why
    run_claim(d, script, "认领", "leg-a", "已认领.rs")
    edit(d, "没认领.rs")
    stage(d, "没认领.rs")
    outs = {}
    for tag, flag in (("警告", []), ("硬拦", ["--硬拦"])):
        r = run_gate(d, script, "--腿", "leg-a", *flag)
        happy = "没认领.rs" in r.stdout and "已认领.rs" not in r.stdout
        outs[tag] = (r.returncode, happy)
    ok = all(happy for _, happy in outs.values())
    return ok, "两种模式都报出「没认领.rs」=%s（警告退出码 %d · 硬拦退出码 %d）" % (
        ok, outs["警告"][0], outs["硬拦"][0])


def j5_pos(p):
    """正向样本：改动**全在**认领集里 ⇒ 报「全在集里」且退出码 0（不误报）。"""
    d = tempfile.mkdtemp(prefix="claim-gate-")
    root, script, why = git_repo(d, {"已认领.rs": "x", "没认领.rs": "y"})
    if root is None:
        return False, why
    run_claim(d, script, "认领", "leg-a", "已认领.rs")
    edit(d, "已认领.rs")
    stage(d, "已认领.rs")
    r = run_gate(d, script, "--腿", "leg-a", "--硬拦")
    ok = r.returncode == 0 and "全在认领集里" in r.stdout
    return ok, "硬拦模式下全在集里 ⇒ 退出码 %d，读数「全在认领集里」=%s" % (
        r.returncode, "全在认领集里" in r.stdout)


def j5_mode_rev(p):
    """反向样本（**本件的硬要求**）：默认必须**只报不拦** —— 同样的越界改动，
    不显式开开关时必须退出码 0；显式开 `--硬拦` 才退 3。
    若默认就退 3，这一条会红：那正是「现在没人在用认领机制 ⇒ 硬拦挡掉所有提交」。"""
    d = tempfile.mkdtemp(prefix="claim-gate-")
    root, script, why = git_repo(d, {"已认领.rs": "x", "没认领.rs": "y"})
    if root is None:
        return False, why
    run_claim(d, script, "认领", "leg-a", "已认领.rs")
    edit(d, "没认领.rs")
    stage(d, "没认领.rs")
    r_默认 = run_gate(d, script, "--腿", "leg-a")
    r_硬 = run_gate(d, script, "--腿", "leg-a", "--硬拦")
    r_环 = run_gate(d, script, "--腿", "leg-a", env={"CLAIM_GATE": "硬拦"})
    ok = (r_默认.returncode == 0 and r_硬.returncode == 3 and r_环.returncode == 3)
    return ok, "默认(没设开关)=%d（**必须 0**）· --硬拦=%d（必须 3）· CLAIM_GATE=硬拦=%d（必须 3）" % (
        r_默认.returncode, r_硬.returncode, r_环.returncode)


def j5_mode_mispell(p):
    """反向样本（覆盖）：开关**拼错**不许静默变成硬拦 —— 必须退回警告、出声、且不拒。"""
    d = tempfile.mkdtemp(prefix="claim-gate-")
    root, script, why = git_repo(d, {"已认领.rs": "x", "没认领.rs": "y"})
    if root is None:
        return False, why
    run_claim(d, script, "认领", "leg-a", "已认领.rs")
    edit(d, "没认领.rs")
    stage(d, "没认领.rs")
    r = run_gate(d, script, "--腿", "leg-a", env={"CLAIM_GATE": "硬欄"})
    spoke = "认不得的模式" in (r.stdout + r.stderr)
    ok = r.returncode == 0 and spoke
    return ok, "CLAIM_GATE=硬欄（错字）⇒ 退出码 %d（必须 0，不许静默变硬拦）；出声=%s" % (
        r.returncode, spoke)


def j5_empty(p):
    """反向样本（读数三元）：空集不算通过 —— 没有腿标识、或账本里没有本腿租约、
    或本次没有要提交的路径，都必须报「判不了」，不许报「全在集里」。
    （空集若算通过，闸在「什么都没配」时全绿 —— 这正是假绿。）"""
    d = tempfile.mkdtemp(prefix="claim-gate-")
    root, script, why = git_repo(d, {"a.rs": "x"})
    if root is None:
        return False, why
    edit(d, "a.rs")
    stage(d, "a.rs")
    r1 = run_gate(d, script)                              # 没腿标识
    r2 = run_gate(d, script, "--腿", "leg-a")             # 账本里没这条腿
    subprocess.run(["git", "-C", d, "reset", "-q"], capture_output=True)
    subprocess.run(["git", "-C", d, "checkout", "-q", "--", "a.rs"], capture_output=True)
    run_claim(d, script, "认领", "leg-a", "a.rs")
    r3 = run_gate(d, script, "--腿", "leg-a")             # 干净工作区：没有要提交的路径
    got = ["判不了" in r.stdout for r in (r1, r2, r3)]
    nofalse = all("全在认领集里" not in r.stdout for r in (r1, r2, r3))
    ok = all(got) and nofalse
    return ok, "没腿标识=%s · 账本无此腿=%s · 无待提交路径=%s（三条都必须「判不了」）；没有假绿=%s" % (
        got[0], got[1], got[2], nofalse)


def j5_rename(p):
    """反向样本（覆盖 §五 第 5 条那个漏洞）：**改名必须两边都报**（旧路径 + 新路径）。

    只认领了旧路径 ⇒ 新路径必须报「没人认领」；且**改动路径数必须是 2**
    （旧 + 新）—— 旧路径在本腿认领集里，故它不会出现在「不在集里」名单里，
    只能靠**条数**判它有没有被报出来。

    ★ 这条样本第一版**只断言了新路径**，于是「去掉 `--no-renames`」这个变异**没被抓住**
    （实测：默认的改名探测只报新路径，而新路径恰好也不在集里 ⇒ 断言照样绿）。
    是**变异测试**发现样本没牙的（`说明.md` §四 的教训 3 同一类：
    判据在 ≠ 判据覆盖）。现在改用「条数 = 2」⇒ 变异抓得住。
    """
    d = tempfile.mkdtemp(prefix="claim-gate-")
    root, script, why = git_repo(d, {"旧名.rs": "x"})
    if root is None:
        return False, why
    run_claim(d, script, "认领", "leg-b", "旧名.rs")
    subprocess.run(["git", "-C", d, "mv", "旧名.rs", "新名.rs"], capture_output=True)
    r = run_gate(d, script, "--腿", "leg-b")
    seen_new = "新名.rs" in r.stdout and "没人认领" in r.stdout
    both = "改动路径 : 2 条" in r.stdout
    ok = seen_new and both
    return ok, "改名后：新路径报「没人认领」=%s · 改动路径数=2（旧+新都报）=%s —— 去掉 --no-renames 会让后者变 1 条" % (
        seen_new, both)


def j5_subdir(p):
    """反向样本（覆盖）：在**子目录**里跑，路径基准必须仍是仓根 ——
    否则读出来的相对路径与账本里的对不上，闸会假绿。"""
    d = tempfile.mkdtemp(prefix="claim-gate-")
    root, script, why = git_repo(d, {"子/里面.rs": "x", "外面.rs": "y"})
    if root is None:
        return False, why
    run_claim(d, script, "认领", "leg-a", "子/里面.rs")
    edit(d, "外面.rs")
    stage(d, "外面.rs")
    r = subprocess.run([sys.executable, script, "提交闸", "--腿", "leg-a"],
                       capture_output=True, text=True,
                       cwd=os.path.join(d, "子"),
                       env={k: v for k, v in os.environ.items() if k != "CLAIM_GATE"})
    caught = "外面.rs" in r.stdout and "判不了" not in r.stdout
    return caught, "在 子/ 里跑 ⇒ 报出仓根相对的「外面.rs」=%s（基准是仓根，不是当前目录）" % caught


def j5_badledger(p):
    """反向样本（**实跑逼出来的**）：账本坏（形状不对）时 ——
    警告模式**必须仍然不拦**（账本坏不是提交者的错，更不该在没人用认领机制时挡住所有人）；
    硬拦模式才 fail-closed 报「判不了」。且两种模式都**不许报「通过」**（假绿）。"""
    d = tempfile.mkdtemp(prefix="claim-gate-")
    root, script, why = git_repo(d, {"a.rs": "x"})
    if root is None:
        return False, why
    led = os.path.join(d, "开发工具", "认领机制", "账本.json")
    with open(led, "w", encoding="utf-8") as f:
        f.write('{"格式版本": 1}\n')             # 缺「租约」数组
    edit(d, "a.rs")
    stage(d, "a.rs")
    r_warn = run_gate(d, script, "--腿", "leg-a")
    r_block = run_gate(d, script, "--腿", "leg-a", "--硬拦")
    ok = (r_warn.returncode == 0 and r_block.returncode == 2
          and "判不了" in r_warn.stdout and "判不了" in r_block.stdout
          and "全在认领集里" not in r_warn.stdout and "全在认领集里" not in r_block.stdout)
    return ok, "坏账本 ⇒ 警告退出码 %d（必须 0，不许挡提交）· 硬拦退出码 %d（必须 2，fail-closed）· 两边都报「判不了」" % (
        r_warn.returncode, r_block.returncode)


def j5_branch(p):
    """正向样本：腿标识不给时按**当前分支** `腿/<腿名>` 推（机制一 建的分支就叫这个名）。
    反向的一半：不是 `腿/` 开头的分支 ⇒ 必须「判不了」，**不许猜**。"""
    d = tempfile.mkdtemp(prefix="claim-gate-")
    root, script, why = git_repo(d, {"已认领.rs": "x", "没认领.rs": "y"})
    if root is None:
        return False, why
    run_claim(d, script, "认领", "leg-a", "已认领.rs")
    edit(d, "没认领.rs")
    stage(d, "没认领.rs")
    # 分支名 = 腿/leg-a ⇒ 不给 --腿 也应认出 leg-a（越界改动照样报出来）
    subprocess.run(["git", "-C", d, "checkout", "-q", "-b", "腿/leg-a"], capture_output=True)
    r1 = run_gate(d, script)
    ok_branch = "leg-a" in r1.stdout and "没认领.rs" in r1.stdout
    # 分支不是 腿/ 开头 ⇒ 判不了（不许猜）
    subprocess.run(["git", "-C", d, "checkout", "-q", "-b", "主干", "HEAD~0"], capture_output=True)
    r2 = run_gate(d, script)
    ok_main = "判不了" in r2.stdout
    ok = ok_branch and ok_main
    return ok, "分支 腿/leg-a ⇒ 自动认出 leg-a 并报出越界=%s · 分支「主干」⇒ 判不了（不猜）=%s" % (
        ok_branch, ok_main)


def j5_bench(p):
    """反向样本（**这条是实跑逼出来的**）：脚本所在仓与提交所在仓**不是同一个**时，
    闸必须报「判不了」，不许拿两套不同基准的路径硬比 —— 硬比会全绿而什么都没判。
    造法：在 A 仓跑脚本，把 cwd 放到 B 仓（A≠B）。"""
    a = tempfile.mkdtemp(prefix="claim-gate-a-")
    b = tempfile.mkdtemp(prefix="claim-gate-b-")
    rootA, scriptA, whyA = git_repo(a, {"x.rs": "1"})
    rootB, scriptB, whyB = git_repo(b, {"x.rs": "1"})
    if rootA is None or rootB is None:
        return False, whyA + whyB
    run_claim(a, scriptA, "认领", "leg-a", "x.rs")
    edit(b, "x.rs")
    stage(b, "x.rs")
    r = subprocess.run([sys.executable, scriptA, "提交闸", "--腿", "leg-a"],
                       capture_output=True, text=True, cwd=b,
                       env={k: v for k, v in os.environ.items() if k != "CLAIM_GATE"})
    said = "判不了" in r.stdout and "不是同一个" in r.stdout
    return said, "脚本在 A 仓、提交在 B 仓 ⇒ 报「判不了（两个仓根不是同一个）」=%s（硬比会假绿）" % said


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
    {"判据": "J5", "类型": "反向", "名": "提交闸：改了没认领的路径 ⇒ 必须报出来（起真 git 仓，两种模式都报）", "跑": j5_rev},
    {"判据": "J5", "类型": "正向", "名": "提交闸：改动全在认领集里 ⇒ 报「全在集里」且退出码 0（不误报）", "跑": j5_pos},
    {"判据": "J5", "类型": "反向", "名": "★提交闸默认只报不拦：不设开关必退 0，--硬拦/CLAIM_GATE=硬拦 才退 3", "跑": j5_mode_rev},
    {"判据": "J5", "类型": "反向", "名": "提交闸：开关拼错不许静默变硬拦（退回警告 + 出声 + 不拒）", "跑": j5_mode_mispell},
    {"判据": "J5", "类型": "反向", "名": "提交闸：空集不算通过（没腿标识/无此租约/无待提交路径 ⇒ 判不了）", "跑": j5_empty},
    {"判据": "J5", "类型": "反向", "名": "提交闸：改名时旧路径与新路径都要报（默认改名探测只报新路径）", "跑": j5_rename},
    {"判据": "J5", "类型": "正向", "名": "提交闸：在子目录里跑，路径基准仍是仓根（否则与账本对不上 ⇒ 假绿）", "跑": j5_subdir},
    {"判据": "J5", "类型": "反向", "名": "提交闸：脚本所在仓 ≠ 提交所在仓 ⇒ 必须「判不了」，不许硬比两套基准", "跑": j5_bench},
    {"判据": "J5", "类型": "反向", "名": "提交闸：账本坏时警告模式仍不拦、硬拦才 fail-closed（且都不许报通过）", "跑": j5_badledger},
    {"判据": "J5", "类型": "正向", "名": "提交闸：腿标识按分支 `腿/<腿名>` 推；不是这条约定就判不了（不猜）", "跑": j5_branch},
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
