# -*- coding: utf-8 -*-
"""Shell 执行器 —— `v1_shell` 的实现：在 MCP 长驻进程里本地执行 shell 命令。

**它不是「适配层」**：其余工具都只转发仓内已有入口，本件自身就是执行器 ⇒ 不在四道闸之内
（拿它写盘 = 绕过账本）。口径写在工具说明里（改文件仍走 `v1_edit`），靠模型守、不靠机制拦。

**在哪棵树里跑**：只传 `开工ID`（可选）—— 给了就在那条开工的工作树里跑（问 git 精确定位，
与 `上下文.py` 同一份口径）；不给就在当前服务仓根跑。**不接任意路径**。

**无开工ID ⇒ 主干写盘兜底**（见未完成台账「无开工ID 时的 cwd 策略」条）：不给 `开工ID` 时 cwd 是**主干工作区**，而本工具不在四道
闸内 ⇒ 一条写盘命令就能绕过写盘闸与开工ID 重定向（实证：记条款被写进主干）。故不给 `开工ID` 时
**跑前跑后各取一次主干快照**：已跟踪件被改 / 删 ⇒ 当场 `git checkout --` 还原并在回执里点明；
新增未跟踪件 ⇒ 如实报出（不擅自删）。带 `开工ID` 时写盘发生在腿树里、是正路 ⇒ 不介入。

**Git 目标**：目标树若是 **bare 仓根**（本仓主目录 `core.bare=true`），子进程会拿到注入的
`GIT_DIR`/`GIT_WORK_TREE`（否则那棵树里 git 报「must be run in a work tree」）—— 这两键是**进程级**的，
会把该回执里的**所有** git（含 `git -C <别的树>`）都带回本仓。回执会如实点明这一点。跨树读用顶层
`开工ID`（在那条工作树里跑）或 `v1_tree`；要显式点另一棵树用 `git --git-dir=<树>/.git --work-tree=<树>`
（显式参数盖过环境）。

**超时**：整数 1..5（`bool` 不算整数）；>5 明确拒（schema 已声明 `maximum: 5`）。上限 5 依据判据 ㊲。

**输出有界**：每个流最多留 `输出上限` 字符在内存；超出即把完整输出落到系统临时目录的日志件
（懒创建，至多 `日志上限` 字符），回执给路径；未超则不留件。

**安全边界**：命令原样交给 `/bin/sh`（不解析、不过滤）；失败折成退出码 1 + 回执，不抛异常。
本工具不授权：绕 `v1_edit` 改源码 · 跳闸 · 远端推送 · 杀陌生进程。
"""

import os
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from .仓操作 import 禁终端提示环境, 找工作树
from .主干写盘兜底 import 兜底, 取主干快照

# 超时上限 5 秒（判据 ㊲：全项目超时设置 ≤5 秒）
超时秒 = 5
# 每个流最多留多少字符在内存；超出走完整日志件
输出上限 = 16000
# 完整日志件最多写多少字符（防跑飞占满磁盘）
日志上限 = 8 * 1024 * 1024
# 只认这三个键 —— 未知键一次拒（不猜调用方意图）
有效键 = ("命令", "开工ID", "超时")
# `开工ID` 的形状（与 `上下文.py` 同一份口径）
开工号形状 = re.compile(r"v1-[0-9]{6}")
# 子进程不许继承的 Git 定位变量：会把子进程的 git 带到别的树 / 别的 index 上
继承定位变量 = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
             "GIT_COMMON_DIR", "GIT_ALTERNATE_OBJECT_DIRECTORIES")
# Git 的**配置注入**键（`git -c …` ⇒ `GIT_CONFIG_PARAMETERS`；新版 ⇒ `GIT_CONFIG_COUNT` +
# `GIT_CONFIG_KEY_<n>` / `GIT_CONFIG_VALUE_<n>`）：与定位键同属**进程级注入** ⇒ 子进程会跑外层钩子、
# 读外层配置（实测 v1-100675）。`GIT_CONFIG_PARAMETERS` 与 `GIT_CONFIG_COUNT` 是**整名**；
# `GIT_CONFIG_KEY_` 与 `GIT_CONFIG_VALUE_` 的键名**带序号** ⇒ 只能按**前缀**剔。
继承配置键 = ("GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")
# 每次从管道读多少字符
读块大小 = 65536


def _判裸仓根(目标树: Path) -> bool:
    """目标树是不是 **bare 仓根**（它的 `.git/config` 里 `bare = true`）⇒ 真假。

    **一处实现**：`_执行环境` 的注入判断与派发回执的 Git 目标提示共用这一份。判据是目标树本地的
    `.git/config`，不看宿主环境（`目标树/.git` 不是目录 ⇒ 假 —— 例如 linked 工作树的 `.git` 是文件）。
    """
    仓库元目录 = 目标树 / ".git"
    if not 仓库元目录.is_dir():
        return False
    try:
        配置文本 = (仓库元目录 / "config").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return bool(re.search(r"^\s*bare\s*=\s*true\s*$", 配置文本, re.M))


def _主仓根(目标树: Path) -> Path:
    """目标树所属的**主仓根** —— 仓内 venv（唯一解释器）只住这里，腿里不另建。

    linked 工作树的 `.git` 是**文件**（内容 `gitdir: <主仓>/.git/worktrees/<腿名>`）⇒ 上溯三级。
    读不出 ⇒ 返回目标树自身（调用方按「解释器不在」处理，不猜、不回落）。
    """
    仓库元目录 = 目标树 / ".git"
    if 仓库元目录.is_dir():
        return 目标树
    try:
        首行 = 仓库元目录.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return 目标树
    if not 首行.startswith("gitdir:"):
        return 目标树
    指向 = Path(首行.split(":", 1)[1].strip())
    for _ in range(3):          # <主仓>/.git/worktrees/<腿名> ⇒ 上溯三级到 <主仓>
        指向 = 指向.parent
    return 指向 if (指向 / "构建环境").is_dir() else 目标树


def _仓内解释器夹(目标树: Path) -> str:
    """仓内 venv 的 `bin` 目录（解释器唯一那份 3.14）；取不到 ⇒ 空串。

    ★ 取不到**不抛错**：`v1_shell` 是**通用 shell 面**（跑 git / ls 也是它），目标树可能根本不是
    仓（夹具 / 临时目录）⇒ 那里没有 venv 是正常的，此时**不注入 PATH**；也**不另找** PATH 上的
    `python3` 顶替（没有第二条腿）。Python 面的唯一真源是**服务进程的解释器**（见 `作业.py`）。
    """
    解释器夹 = _主仓根(目标树) / "构建环境/python/bin"
    return str(解释器夹) if (解释器夹 / "python3").exists() else ""


def _执行环境(目标树: Path) -> dict:
    """子进程环境：剔除继承的 Git 定位变量 + 禁 git 终端提示。目标树若是 **bare 仓根**
    （判据见 `_判裸仓根`），显式给 `GIT_DIR`/`GIT_WORK_TREE` —— 否则子进程 git 会报
    「must be run in a work tree」。

    ★ 这两键是**进程级**的 ⇒ 会把子进程里**所有** git（含 `git -C <别的树>`）都带回本仓；
    派发回执会如实点明（见 `派发` 的 Git 目标提示）。要显式点另一棵树，用
    `git --git-dir=<树>/.git --work-tree=<树>`（显式参数盖过环境）。
    """
    环境表 = dict(os.environ)
    for 键名 in 继承定位变量:
        环境表.pop(键名, None)
    for 键前缀 in 继承配置键:
        for 键名 in [键名 for 键名 in 环境表 if 键名.startswith(键前缀)]:
            环境表.pop(键名, None)
    环境表.update(禁终端提示环境)
    # ★ 解释器唯一化（3.14 · 唯一一份 · 无回落）：仓内 venv 取到了就把它的 bin 前置进子进程
    #   PATH，并把**唯一来源** `V1_PY` 一起注入 —— 子进程里任何裸 `python3` 与 `$V1_PY` 都落在
    #   3.14 上。★ 为何必须注入 `V1_PY`：实测「git 给钩子的干净环境」里 PATH 可能没有
    #   `python3` ⇒ 命令串写裸 `python3` 会 `command not found`、作业 300 ms 内即失败。
    解释器夹 = _仓内解释器夹(目标树)
    if 解释器夹:
        环境表["PATH"] = 解释器夹 + os.pathsep + 环境表.get("PATH", "")
    # ★ `V1_PY` **无条件**注入（不受「目标树里有没有仓内 venv」影响）：样本夹具仓里没有
    #   `构建环境/python`，但那不等于「没有解释器」—— 唯一来源就是**本进程**的解释器。
    环境表["V1_PY"] = sys.executable
    if _判裸仓根(目标树):
        环境表["GIT_DIR"] = str(目标树 / ".git")
        环境表["GIT_WORK_TREE"] = str(目标树)
    return 环境表


def _建日志夹(流名: str) -> dict:
    """一个流的日志夹：懒开的完整日志件 + 多线程共用的锁。"""
    return {"流名": 流名, "路径": None, "文件": None, "锁": threading.Lock(),
            "已写": 0, "截顶": False}


def _写溢出(日志夹: dict, 溢出文本: str, 头部文本: str) -> None:
    """溢出内容落进日志件；首次调用懒开件并落下头部 ⇒ 日志件是完整输出（至多 `日志上限` 字符）。"""
    with 日志夹["锁"]:
        if 日志夹["路径"] is None:
            句柄, 日志夹["路径"] = tempfile.mkstemp(prefix="v1_shell_", suffix=".log")
            日志夹["文件"] = os.fdopen(句柄, "w", encoding="utf-8", errors="replace")
            日志夹["文件"].write("=== %s ===\n%s" % (日志夹["流名"], 头部文本))
            日志夹["已写"] = len(头部文本)
        if 日志夹["已写"] >= 日志上限:
            日志夹["截顶"] = True
            return
        可写 = 溢出文本[:日志上限 - 日志夹["已写"]]
        日志夹["文件"].write(可写)
        日志夹["已写"] += len(可写)
        if len(可写) < len(溢出文本):
            日志夹["截顶"] = True


def _关日志夹(日志夹: dict) -> None:
    if 日志夹["文件"] is not None:
        日志夹["文件"].close()


def _收流(输入流, 日志夹: dict) -> tuple:
    """读干一个流 ⇒ `(内存留存文本, 是否溢出)`。前 `输出上限` 字符留内存；超出即把完整内容
    （头部 + 后续）落进日志夹。**必须读干** —— 不读干，子进程会堵在写满的管道上（假超时）。
    """
    留存表 = []
    留存长 = 0
    溢出 = False
    while True:
        数据块 = 输入流.read(读块大小)
        if not 数据块:
            break
        if 留存长 < 输出上限:
            头部块 = 数据块[:输出上限 - 留存长]
            留存表.append(头部块)
            留存长 += len(头部块)
            数据块 = 数据块[len(头部块):]
        if 数据块:
            溢出 = True
            _写溢出(日志夹, 数据块, "".join(留存表))
    return "".join(留存表), 溢出


def _取工作树(仓根, 开工号):
    """问 git 定位这条开工的工作树 —— **先剔除宿主继承的 Git 定位键与配置注入键**（否则问的是被
    污染的仓，不是本仓）。与 `上下文.py` 同一份 `找工作树`，只是把环境摆干净。
    """
    暂存表 = {}
    for 键名 in [键名 for 键名 in os.environ
              if 键名 in 继承定位变量
              or any(键名.startswith(键前缀) for 键前缀 in 继承配置键)]:
        暂存表[键名] = os.environ.pop(键名)
    try:
        return 找工作树(仓根, 开工号)
    finally:
        os.environ.update(暂存表)


def _杀进程组(子进程) -> None:
    """超时 ⇒ 杀整个进程组（shell 及其子进程）⇒ 不留孤儿（`start_new_session` 开的组）。

    `start_new_session=True` ⇒ 子进程就是组长，组号 = 子进程号 ⇒ 直接 `killpg(pid)`，
    不再 `getpgid`（组长已退出时 `getpgid` 会抛，反而漏杀组内残留）。
    """
    import signal
    try:
        os.killpg(子进程.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        子进程.wait(timeout=2)
    except subprocess.TimeoutExpired:
        子进程.kill()


def 派发(参数表: dict, 仓根) -> tuple:
    """`v1_shell` 的入口 ⇒ `(退出码, 输出文本)`。

    参数：`命令`（必填，非空字符串）· `开工ID`（可选，字符串）· `超时`（可选，整数 1..5）。
    """
    if not isinstance(参数表, dict):
        return 2, "参数拒绝：arguments 要是对象"
    未知键 = sorted(set(参数表) - set(有效键))
    if 未知键:
        return 2, "参数拒绝：未知键 %s；本工具只认 %s" % ("、".join(未知键), "、".join(有效键))
    命令 = 参数表.get("命令")
    if not isinstance(命令, str) or not 命令.strip():
        return 2, "参数拒绝：`命令` 要是非空字符串（收到 %r）" % (命令,)
    命令 = 命令.strip()

    # 超时：严格整数 1..5（`bool` 不算整数）；>5 明确拒（schema 已声明 maximum: 5）
    超时 = 超时秒
    if "超时" in 参数表:
        超时值 = 参数表["超时"]
        if type(超时值) is not int:
            return 2, "参数拒绝：`超时` 要是整数 1..%d，收到 %r" % (超时秒, 超时值)
        if not 1 <= 超时值 <= 超时秒:
            return 2, "参数拒绝：`超时` 要在 1..%d 之间（schema 声明 maximum=%d），收到 %d" % (
                超时秒, 超时秒, 超时值)
        超时 = 超时值

    开工号 = 参数表.get("开工ID")
    if 开工号 is not None and not isinstance(开工号, str):
        return 2, "参数拒绝：`开工ID` 要是字符串（收到 %r）" % (开工号,)
    开工号 = (开工号 or "").strip()

    # 目标树：给了 `开工ID` 就问 git 精确定位那条开工的工作树；不给就用当前服务仓根。
    # 不接任意路径 —— 不许拿它换到仓外去。
    目标树 = Path(仓根).resolve()
    if 开工号:
        if not 开工号形状.fullmatch(开工号):
            return 2, "参数拒绝：`开工ID` 形状要是 `v1-` 加六位数字，收到 %r" % (开工号,)
        工作树 = _取工作树(仓根, 开工号)
        if 工作树 is None or not 工作树.is_dir():
            return 2, "参数拒绝：开工 %s 的工作树不在（问 git 问不到）⇒ 不执行" % (开工号,)
        目标树 = 工作树.resolve()

    # ★ 无开工ID ⇒ 主干写盘兜底：跑前取一次主干快照（带开工ID 时腿树内写盘是正路，不介入）
    兜底开 = not 开工号
    前快照 = 取主干快照(目标树)[0] if 兜底开 else None

    # 执行：命令原样交给 /bin/sh；stdout/stderr 由两条线程**边读边截断**（前 `输出上限` 字符留内存，
    # 超出落日志件）—— 不整块进内存、不堵管道；编码 utf-8 + errors=replace（坏字节不炸工具）。
    try:
        环境表 = _执行环境(目标树)
    except OSError as 环境不成立:
        return 1, "%s\n命令：%s" % (环境不成立, 命令)
    try:
        子进程 = subprocess.Popen(命令, shell=True, cwd=str(目标树),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             encoding="utf-8", errors="replace",
                             env=环境表, start_new_session=True)
    except OSError as 起不来:
        return 1, "起不了：%r\n命令：%s" % (起不来, 命令)

    标准输出夹 = _建日志夹("标准输出")
    标准错误夹 = _建日志夹("标准错误")
    收集表 = {}
    线程表 = [
        threading.Thread(target=lambda: 收集表.update({"out": _收流(子进程.stdout, 标准输出夹)})),
        threading.Thread(target=lambda: 收集表.update({"err": _收流(子进程.stderr, 标准错误夹)})),
    ]
    for 线程 in 线程表:
        线程.start()
    超时了 = False
    try:
        子进程.wait(timeout=超时)
    except subprocess.TimeoutExpired:
        超时了 = True
        _杀进程组(子进程)
    for 线程 in 线程表:
        线程.join(timeout=3)
    _关日志夹(标准输出夹)
    _关日志夹(标准错误夹)
    标准输出, 输出溢出 = 收集表.get("out", ("", False))
    标准错误, 错误溢出 = 收集表.get("err", ("", False))
    回执码 = -1 if 超时了 else 子进程.returncode

    截断行表 = []
    if 输出溢出 or 错误溢出:
        日志件表 = [日志夹["路径"] for 日志夹 in (标准输出夹, 标准错误夹) if 日志夹["路径"]]
        截断行表.append("★ 输出超 %d 字符已截断；完整日志：%s" % (输出上限, " ；".join(日志件表)))
        if 标准输出夹["截顶"] or 标准错误夹["截顶"]:
            截断行表.append("★ 完整日志也已到上限 %d 字符（命令输出过大）" % 日志上限)
    输出行 = ["命令：%s" % 命令, "工作目录：%s" % 目标树,
             "退出码：%d" % 回执码, "超时：%d 秒（上限 %d 秒）" % (超时, 超时秒)]
    if _判裸仓根(目标树):
        输出行.append("★ Git 目标：本目标是 **bare 仓根**（无工作树）⇒ 已给子进程注入 "
                  "GIT_DIR/GIT_WORK_TREE = 本仓；故 `git` 一律作用在 **本仓主目录** 上，"
                  "`git -C <别的树>` 会被环境带回本仓（**不切目标**）。")
        输出行.append("   跨树：用顶层 `开工ID`（在那条工作树里跑）或 `v1_tree`；要显式点另一棵树，用 "
                  "`git --git-dir=<树>/.git --work-tree=<树> ...`（显式参数盖过环境）。")
    if 超时了:
        输出行.append("★ 命令超时（%d 秒）⇒ 已杀整进程组；下面是已收到的部分输出" % 超时)
    输出行.append("")
    if 标准输出:
        输出行 += ["=== 标准输出 ===", 标准输出.rstrip(), ""]
    if 标准错误:
        输出行 += ["=== 标准错误 ===", 标准错误.rstrip(), ""]
    输出行 += 截断行表
    if 兜底开:
        后快照, 未跟踪表 = 取主干快照(目标树)
        输出行 += 兜底(目标树, 前快照, 后快照, 未跟踪表)
    # 工具面退出码：0 成功 · 1 命令失败 · -1 超时（回执里带命令的真实退出码）
    return (-1 if 超时了 else (1 if 回执码 != 0 else 0)), "\n".join(输出行)
