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
import subprocess
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

# ── 提交闸的模式 ──────────────────────────────────────────────────────────────
# ★ **默认警告**：只报不拦。理由（说明.md §六 第 2 条）：现在没人在用认领机制
#   （账本实测为空）⇒ 硬拦会挡住**所有**提交，把闸门变成「谁都不能提交」。
#   硬拦是**显式开关**：命令行 `--硬拦`，或环境变量 `CLAIM_GATE=硬拦`（别名 block/1/true）。
#   模式的定义只此一处 —— 命令行与环境变量都得经过 gate_mode() 归一。
GATE_WARN = "警告"
GATE_BLOCK = "硬拦"
GATE_BLOCK_ALIASES = ("硬拦", "block", "1", "true", "on", "yes")


def gate_mode(raw=None, forced=False):
    """→ (模式, 读到的原值, 认不认得)。认不得的值**退回警告**并回报「不认得」——
    拼错一个环境变量就静默变成硬拦，比不拦更坏。"""
    if forced:
        return GATE_BLOCK, "命令行 --硬拦", True
    raw = os.environ.get("CLAIM_GATE", "") if raw is None else raw
    if not raw.strip():
        return GATE_WARN, "（没设）", True
    v = raw.strip()
    if v in GATE_BLOCK_ALIASES:
        return GATE_BLOCK, v, True
    if v in (GATE_WARN, "warn", "警告"):
        return GATE_WARN, v, True
    return GATE_WARN, v, False

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


# ── 提交闸：改动路径 ⊆ 认领集？ ───────────────────────────────────────────────
# 这是 §五 说的「真正的强制点」：账本说谁占了什么，vs diff 里实际改了哪些路径。
# 口径（说明.md §六 第 2 条）：**默认只报不拦**，硬拦是显式开关。
#
# ★ 这里**不做「谁改的」归属推断**：git 的 diff 里没有腿标识，账本里也没有提交。
#   所以闸只回答一个问题：「本次要提交的路径，是不是全都在**你报的那个腿**的认领集里」。
#   腿标识由提交者显式给出（`--腿` / `CLAIM_LEG`）—— 推断不出来就不许猜（猜了就是假绿）。

def git_toplevel(cwd=None):
    """→ 当前目录所属 git 仓的仓根，读不到给 None。

    ★ 为什么要它、而不用脚本自己的 `ROOT`：账本里的路径是**仓根相对**的，
    `git diff --cached` 吐出来的路径也是**仓根相对**的 —— 两边必须同一个基准。
    脚本的 `ROOT` 是「脚本住在哪个仓」，提交发生在「你站在哪个仓」；**两者可以不是同一个**
    （例：在别处 import 本件、或脚本被拷去守另一个仓）。基准一旦悄悄错开，
    比对就退化成「比两份互不相干的字符串」——**全绿而什么都没判**（假绿）。
    故这里显式取 cwd 的仓根，并与 ROOT 对不上时报「判不了」（见 op_gate）。
    """
    try:
        p = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                           capture_output=True, cwd=cwd)
    except OSError:
        return None
    if p.returncode != 0:
        return None
    top = p.stdout.decode("utf-8", "surrogateescape").strip()
    return os.path.realpath(top) if top else None


def leg_from_branch(cwd=None):
    """→ 当前分支按 `腿/<腿名>` 约定推出的腿标识；不是这条约定就给 None。

    ★ 为什么允许推：`开发工具/并行工作树.sh 新建 <腿名>` 建的分支就叫 `腿/<腿名>`
    —— **分支名就是腿标识**，这是机制一已经定下的落点，这里只是读它，没有另立一套。
    不是 `腿/` 开头的分支（收口方在主树、或人在别的分支上提交）⇒ 返回 None，
    闸报「判不了」（**不许猜**：猜错腿名 = 拿别人的认领集去判，那是假绿）。
    """
    try:
        p = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                           capture_output=True, cwd=cwd)
    except OSError:
        return None
    if p.returncode != 0:
        return None
    b = p.stdout.decode("utf-8", "surrogateescape").strip()
    return b[len("腿/"):] if b.startswith("腿/") and len(b) > len("腿/") else None


def git_staged_paths(root=ROOT):
    """→ (路径集, 说明, 退出码)。走 `git diff --cached`，**不是**工作区 diff ——
    闸问的是「将要提交的那些路径」，工作区里没暂存的改动不算（`git commit` 不会带上它们）。

    两条实测口径：
      · 必须在**仓根**跑：`git -C <子目录> diff --cached --name-only` 仍出**仓根相对**路径，
        故这里显式 `-C root`，让「读出来的路径」与「账本里的路径」同一套基准；
      · `--no-renames`：改名必须**两边都报**（旧路径 + 新路径）。默认的改名探测只报新路径，
        于是「旧租约挂在 a 上、b 没人认领」这条（说明.md §五 第 5 条）就漏过去了。
    """
    cmd = ["git", "-C", root, "diff", "--cached", "--name-only", "-z",
           "--no-renames", "--diff-filter=ACMRDT"]
    try:
        p = subprocess.run(cmd, capture_output=True)
    except OSError as e:
        return None, "调不起 git（%r）" % (e,), EXIT_USAGE
    if p.returncode != 0:
        return None, "git 退出码 %d：%s" % (
            p.returncode, p.stderr.decode("utf-8", "replace").strip()), EXIT_USAGE
    raw = p.stdout.decode("utf-8", "surrogateescape")
    return [f for f in raw.split("\0") if f], "git diff --cached --name-only", EXIT_OK


def op_gate(led, leg, staged_raw, mode=GATE_WARN, now=None, root=ROOT):
    """比对「本次改动涉及的文件」与「账本里本腿的认领集」，报出不在集里的。

    返回的 `结果` 三态：
      · `全在集里`  —— 每条改动路径都在本腿认领集里（闸放行）
      · `有不在集里` —— 列出了 `不在认领集` 与 `没人认领`（闸在硬拦模式下拒）
      · `判不了`    —— 缺腿标识 / 本腿无租约 / 仓外路径 / 基准不一致（**不算通过**）
    """
    now = now_ts() if now is None else now
    out = {"腿标识": leg, "模式": mode, "基准": "git diff --cached（将要提交的路径）"}

    if not leg:
        out.update({"结果": "判不了", "缺什么": "没给腿标识（--腿 <腿标识> 或 CLAIM_LEG）",
                    "提示": "git 的 diff 与账本里都没有「谁改的」⇒ 腿标识只能显式给，不许猜"})
        return out

    # ★ 基准一致性：账本路径基准（root）必须与本次提交的仓根同源，否则比对无意义。
    top = git_toplevel()
    if top is not None and top != os.path.realpath(root):
        out.update({"结果": "判不了",
                    "缺什么": "本次提交的仓根（%s）与账本所在的仓根（%s）不是同一个" % (top, root),
                    "提示": "账本路径是仓根相对的 ⇒ 两个仓根不同则比对不成立（不许按字符串硬比）。"
                            "每条腿请在自己的工作树里跑：那里脚本与账本都在同一棵树内"})
        return out

    paths, outside = norm_paths(staged_raw, root=root)
    out["改动路径数"] = len(paths)
    out["改动路径"] = paths
    if outside:
        out.update({"结果": "判不了", "缺什么": "改动里有仓外路径：%s" % "、".join(outside)})
        return out

    holders = {}
    for lease in led.data["租约"]:
        for p in lease["路径集"]:
            holders.setdefault(p, lease)

    mine = None
    for lease in led.data["租约"]:
        if lease["腿标识"] == leg:
            mine = lease
            break
    if mine is None:
        out.update({"结果": "判不了",
                    "缺什么": "账本里没有腿 %s 的租约（本腿一条路径都没认领）" % leg,
                    "账本读到总条数": len(led.data["租约"]),
                    "提示": "先认领：认领 %s <路径>..." % leg})
        return out

    claimed = set(mine["路径集"])
    out.update({"认领集": sorted(claimed), "认领集大小": len(claimed),
                "到期时间": mine["到期时间"], "租约状态": lease_status(mine, now)})

    if not paths:
        out.update({"结果": "判不了", "缺什么": "本次没有要提交的路径（空集不算通过）"})
        return out

    不在 = [p for p in paths if p not in claimed]
    没人认领 = [p for p in 不在 if p not in holders]
    被谁占 = {p: holders[p]["腿标识"] for p in 不在 if p in holders}
    out["不在认领集"] = 不在
    out["没人认领"] = 没人认领
    out["被别人占"] = 被谁占
    out["结果"] = "全在集里" if not 不在 else "有不在集里"
    return out


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
    for p in res["不在认领集"]:
        who = res["被别人占"].get(p)
        out.append("    %s%s" % (p, "（被 %s 占）" % who if who else "（没人认领）"))
    out.append("  ⇒ %s" % ("**只报不拦**（警告模式）—— 要它拒提交，见 开发工具/认领机制/说明.md §六："
                           "设 CLAIM_GATE=硬拦 或给 --硬拦"
                           if mode != GATE_BLOCK else
                           "**硬拦模式**：这些路径不在你的认领集里 ⇒ 拒提交。"))
    return "\n".join(out)


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

BOOL_FLAGS = ("强制", "全部过期", "含过期", "json", "硬拦")


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
  python3 开发工具/认领机制/认领机制.py 提交闸 [--腿 <腿标识>] [--硬拦]
  加 --json 出机器可读的一版。退出码：0 成功 · 2 用法/参数错 · 3 冲突或被拒 · 4 无此租约。
腿标识用 ASCII（字母/数字/短横线/下划线），与 开发工具/并行工作树.sh 的腿名一致。
它只挡得住**愿意来认领的腿**；挡不住什么逐条见 开发工具/认领机制/说明.md。

提交闸（比对「将要提交的路径」与账本里本腿的认领集）：
  ★ **默认只报不拦**（警告模式）—— 现在没人在用认领机制，硬拦会挡掉所有提交。
  硬拦要显式开：`--硬拦` 或环境变量 `CLAIM_GATE=硬拦`（别名 block/1/true）。
  腿标识怎么来（三级，先到先用）：`--腿 <腿标识>` → 环境变量 `CLAIM_LEG` →
  **当前分支按 `腿/<腿名>` 推**（机制一 建的分支就叫这个名，腿标识 = 腿名）。
  三级都没有 ⇒ 读数「判不了」（**不许猜**：猜错腿名就是拿别人的认领集判，那是假绿）。
  退出码**按模式给**（模式的定义只此一处，调用方只写 `exit $CODE`，不许自己再判模式）：
    警告模式：**一律 0** —— 只报不拦，连「判不了」也不拦。
    硬拦模式：全在集里 0 · 有不在集里 3 · 判不了 2（fail-closed：开了硬拦又没配腿标识 = 配置错）。""")


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

    # ── 提交闸：**单独一条路** ────────────────────────────────────────────────
    # 为什么不能并进下面那个 try：账本坏 ⇒ 那里一律 EXIT_USAGE，而**默认警告模式下
    # 连「判不了」都不许拦**（硬要求：只报不拦）。账本坏不是提交者的错，
    # 更不该在「没人在用认领机制」的时候把所有人的提交挡住 —— 那样闸门就成了「谁都不能提交」。
    if action == "提交闸":
        leg = flags.get("腿") or os.environ.get("CLAIM_LEG") or leg_from_branch()
        mode, raw, known = gate_mode(forced=bool(flags.get("硬拦")))
        if not known:
            print("提交闸：认不得的模式 %r（按 %s 跑）—— 认得的有 %s" % (
                raw, GATE_WARN, "、".join(GATE_BLOCK_ALIASES + (GATE_WARN,))),
                file=sys.stderr)
        staged, how, _ = git_staged_paths()
        try:
            if staged is None:
                raise ValueError(how)
            with Ledger(ledger_path()) as led:
                res = op_gate(led, leg, staged, mode=mode)
            res["基准"] = "git diff --cached（将要提交的路径）· %s" % how
        except (ValueError, OSError, json.JSONDecodeError) as e:
            # 读数「判不了」，**不是**「通过」——账本读不出时闸什么都没判。
            res = {"结果": "判不了", "腿标识": leg, "模式": mode,
                   "基准": "git diff --cached（将要提交的路径）· %s" % how,
                   "缺什么": "账本或 git 读不出：%r" % (e,),
                   "提示": "账本坏不是提交者的错 ⇒ 警告模式下不拦；修好账本再让它有牙"}
        # ★ 退出码按**模式**给，不按事实给 —— 模式的定义只此一处（gate_mode），
        #   于是调用方（pre-commit 钩子）只写 `exit $CODE` 就对了，不许自己再判模式：
        #   两处各判一次模式 = 两处定义同一件事。
        #   警告模式：**一律 0**（只报不拦，连「判不了」也不拦）；
        #   硬拦模式：全在集里 0 · 有不在集里 3 · 判不了 2（fail-closed：
        #   开了硬拦又没配腿标识 / 账本坏，那是配置错，不是「可以提交」）。
        if mode == GATE_BLOCK:
            gate_code = {"全在集里": EXIT_OK, "有不在集里": EXIT_CONFLICT}.get(
                res["结果"], EXIT_USAGE)
        else:
            gate_code = EXIT_OK
        return emit(res, lambda: render_gate(res), gate_code)

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
            if action == "提交闸":
                pass                                     # 已在上面的专门铁轨里处理
            print("未知动作：%s" % action, file=sys.stderr)
            usage()
            return EXIT_USAGE
    except (ValueError, OSError, json.JSONDecodeError) as e:
        print("账本读写出错：%r" % (e,), file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
