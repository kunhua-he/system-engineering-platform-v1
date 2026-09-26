#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 认领机制 —— 「谁有权改哪条路径」（机制二）
# 规格：项目文档/设计文档/并行开发与工作区.md「机制二：认领机制」。用法见本文件 usage()（`--help`）。
#
# ★ 协作式：只挡得住愿意来认领的腿，挡不住什么逐条见 说明.md。
# ★ 标识符一律 ASCII（函数名 · 变量名 · 旗标名），与 开发工具/并行工作树.sh 同一条风格。
#   账本**字段名**用中文是数据不是标识符 —— 中文键让 `git diff` 直接读懂「谁占着哪条路径」。
# ★ 零第三方依赖（只用标准库）。账本是 JSON 不是 sqlite：要能被 `git diff` 看出变化；
#   写账走「临时文件 + os.replace」，认领走「flock 互斥 + 读改写」⇒ 原子性由内核锁保证。

import datetime
import fcntl
import hashlib
import json
import os
import sys
import tempfile
import time

FORMAT_VERSION = 1
LEDGER_BASENAME = "账本.json"
DEFAULT_TTL_SEC = 1800.0          # 默认租期 30 分钟
TIME_FMT = "%Y-%m-%d %H:%M:%S%z"

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_CONFLICT = 3
EXIT_NOT_FOUND = 4

LEG_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"


# ── 仓根与账本落点 ────────────────────────────────────────────────────────────

def repo_root():
    """向上找 rust-toolchain.toml 定仓根；找不到就退回脚本的上两级。"""
    d = os.path.dirname(os.path.abspath(__file__))
    while True:
        if os.path.isfile(os.path.join(d, "rust-toolchain.toml")):
            return d
        up = os.path.dirname(d)
        if up == d:
            return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        d = up


ROOT = repo_root()
DEFAULT_LEDGER = os.path.join(ROOT, "开发工具", "认领机制", LEDGER_BASENAME)


def ledger_path():
    """账本落点。CLAIM_LEDGER 只给自检用（它要往临时账本里写）。"""
    return os.environ.get("CLAIM_LEDGER") or DEFAULT_LEDGER


# ── 时间 ─────────────────────────────────────────────────────────────────────

def now_ts():
    return time.time()


def fmt_ts(ts):
    return datetime.datetime.fromtimestamp(ts).astimezone().strftime(TIME_FMT)


def parse_ts(s):
    return datetime.datetime.strptime(s, TIME_FMT).timestamp()


# ── 路径归一化：两条腿写同一个文件的不同拼法，必须判成同一条路径 ────────────────

def norm_paths(raw, root=ROOT):
    """→ (归一化后的路径集, 仓外路径)。相对路径按仓根解析，统一 `/` 分隔。"""
    good, outside = [], []
    for p in raw:
        ap = os.path.normpath(p if os.path.isabs(p) else os.path.join(root, p))
        rel = os.path.relpath(ap, root).replace(os.sep, "/")
        if rel == ".." or rel.startswith("../"):
            outside.append(p)
        else:
            good.append(rel)
    return sorted(set(good)), outside


# ── 账本：flock 互斥 + 原子替换 ───────────────────────────────────────────────

class Ledger:
    """with Ledger(path) as led: 读改写全在锁内。锁文件落 /tmp（不进仓、不进版本库）。"""

    def __init__(self, path):
        self.path = path
        self.fd = None
        self.data = None

    def _lockpath(self):
        h = hashlib.sha1(os.path.abspath(self.path).encode("utf-8")).hexdigest()[:16]
        return os.path.join(tempfile.gettempdir(), "claim-ledger-%s.lock" % h)

    def _load(self):
        if not os.path.exists(self.path):
            return {"格式版本": FORMAT_VERSION, "租约": []}
        with open(self.path, "r", encoding="utf-8") as f:
            raw = f.read().strip()
        if not raw:
            return {"格式版本": FORMAT_VERSION, "租约": []}
        data = json.loads(raw)
        if not isinstance(data, dict) or not isinstance(data.get("租约"), list):
            raise ValueError("账本形状不对（缺「租约」数组）：%s" % self.path)
        return data

    def __enter__(self):
        d = os.path.dirname(self.path) or "."
        os.makedirs(d, exist_ok=True)
        self.fd = os.open(self._lockpath(), os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(self.fd, fcntl.LOCK_EX)          # 认领/释放/回收的原子性靠它
        try:
            self.data = self._load()
        except BaseException:                        # 账本坏 ⇒ 关 fd 放锁再抛，
            self.__exit__(None, None, None)          # 否则锁被本进程的另一处 flock 永久挡住
            raise
        return self

    def __exit__(self, *exc):
        try:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
        finally:
            os.close(self.fd)
        return False

    def save(self):
        self.data["租约"].sort(key=lambda l: l["腿标识"])   # 稳定序 ⇒ diff 只显示真变化
        d = os.path.dirname(self.path) or "."
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".账本-", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, self.path)


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


# ── 输出渲染（人读的那一版） ─────────────────────────────────────────────────

def render_claim(res):
    if res["结果"] == "成功":
        return "\n".join(["认领成功 —— %s 独占 %d 条路径" % (res["腿标识"], len(res["路径集"])),
                          "  新增路径 : %s" % ("、".join(res["新增"]) or "（无，全是自己已占的）"),
                          "  路径集   : %s" % "、".join(res["路径集"]),
                          "  认领时间 : %s" % res["认领时间"],
                          "  到期时间 : %s（到期只是可回收，不会自动回收）" % res["到期时间"]])
    if res["结果"] == "冲突":
        out = ["认领冲突 —— 整体失败，一条路径都没占（原子）",
               "  腿标识   : %s" % res["腿标识"],
               "  被占 %d 条 :" % len(res["冲突"])]
        for c in res["冲突"]:
            out.append("    %s" % c["路径"])
            out.append("      被 %s 占（%s，到期 %s）" % (c["被谁占"], c["状态"], c["到期时间"]))
        out.append("  提示     : %s" % res["提示"])
        return "\n".join(out)
    return "认领失败 —— %s：%s" % (res["结果"], json.dumps(res, ensure_ascii=False))


def render_query(res, only_active):
    out = ["查活跃 —— 返回 %d 条（账本里读到 %d 条）· 读数：%s" % (
        res["返回条数"], res["账本读到总条数"], res["读数"])]
    for r in res["租约"]:
        out += ["  %s" % r["腿标识"],
                "    路径集   : %s" % "、".join(r["路径集"]),
                "    认领时间 : %s" % r["认领时间"],
                "    到期时间 : %s" % r["到期时间"],
                "    状态     : %s（剩余 %d 秒）" % (r["状态"], r["剩余秒"])]
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
    for d in res["回收"]:
        out.append("  已回收 %s（%s，到期 %s，是否已过期=%s）" % (
            d["腿标识"], d["方式"], d["到期时间"], d["是否已过期"]))
    for s in res["未回收"]:
        out.append("  未回收 %s：%s（到期 %s）" % (s["腿标识"], s["原因"], s["到期时间"]))
    if not res["回收"]:
        out.append("  一条都没回收 —— 回收必须显式指定目标，且只有「已过期」或「--强制」才收。")
    return "\n".join(out)


# ── 命令行 ───────────────────────────────────────────────────────────────────

BOOL_FLAGS = ("强制", "全部过期", "含过期", "json")


def parse_args(args):
    pos, flags = [], {}
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("--"):
            key = a[2:]
            if key in BOOL_FLAGS:
                flags[key] = True
                i += 1
                continue
            if i + 1 >= len(args):
                raise ValueError("旗标 --%s 缺值" % key)
            flags[key] = args[i + 1]
            i += 2
            continue
        pos.append(a)
        i += 1
    return pos, flags


def usage():
    print("""认领机制 —— 谁有权改哪条路径（机制二）
  python3 开发工具/认领机制/认领机制.py 认领 <腿标识> <路径> [<路径>...] [--租期秒 N]
  python3 开发工具/认领机制/认领机制.py 收工释放 <腿标识>
  python3 开发工具/认领机制/认领机制.py 查活跃 [--含过期]
  python3 开发工具/认领机制/认领机制.py 回收 (--腿 <腿标识> [--强制] | --全部过期)
  加 --json 出机器可读的一版。退出码：0 成功 · 2 用法/参数错 · 3 冲突或被拒 · 4 无此租约。
腿标识用 ASCII（字母/数字/短横线/下划线），与 开发工具/并行工作树.sh 的腿名一致。
它只挡得住**愿意来认领的腿**；挡不住什么逐条见 开发工具/认领机制/说明.md。""")


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "帮助"):
        usage()
        return EXIT_OK
    action, rest = argv[0], argv[1:]
    try:
        pos, flags = parse_args(rest)
    except ValueError as e:
        print("参数错：%s" % e, file=sys.stderr)
        usage()
        return EXIT_USAGE
    want_json = bool(flags.get("json"))

    def emit(res, render, code):
        print(json.dumps(res, ensure_ascii=False, indent=2) if want_json else render())
        return code

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
            print("未知动作：%s" % action, file=sys.stderr)
            usage()
            return EXIT_USAGE
    except (ValueError, OSError, json.JSONDecodeError) as e:
        print("账本读写出错：%r" % (e,), file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
