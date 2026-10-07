# -*- coding: utf-8 -*-
"""Shell 执行器 —— `v1_shell` 的实现：**本地秒级执行 shell 命令**。

**为什么要它**（2026-10-05 华哥要的）：`git status` / `ls` / `cat 一段` 这类活，走模型侧的
Bash 工具每次都要一次往返；MCP 服务是**本地长驻进程** ⇒ 在它里面跑没有那次往返，秒级返回。

**它不是「适配层」**：其余工具都只**转发**仓内已有入口，本件**自身就是执行器**。
⇒ 它**不在四道闸之内**：拿它写盘 = 绕过账本（认领 / 指纹 / 旧内容定位全不查）。
口径写在工具说明里（「改文件仍走 `v1_edit`」），**靠模型守，不靠机制拦**。

**在哪棵树里跑**（2026-10-07 接上工具面时定）：调用方**只传 `开工ID`**（可选）—— 给了就在那条
开工的工作树里跑（问 git 精确定位，与 `上下文.py` 同一份口径）；不给就在**当前服务仓根**
（服务进程的 cwd）里跑。**没有「任意路径」参数** —— 不许拿它换到仓外去。

**超时上限 5 秒**（判据 ㊲）：默认值与上限都是 5；传更大的 `超时` **压回 5 并在回执里如实报出**
（不拒收 —— 拒收只会让模型反复试，压回更省事）。

**输出有界**：stdout / stderr 各最多回 `输出上限` 字符；超了就截断、把完整输出落到**系统临时
目录**的一个日志件里，回执给出它的绝对路径（不落仓内源码树 —— 判据 ⑰ / ⑳）。

**用法**：
    v1_shell(命令="git status")
    v1_shell(命令="ls -la", 开工ID="v1-100440", 超时=3)

**退出码语义**（与工具面其余件同一张表，见 `工具.py` 顶部）：
`0` 成功 · `1` 命令本身失败（非零退出码，回执里带 stdout/stderr）·
`2` 参数错（未知键 / 命令为空 / `开工ID` 形状错或工作树不在 / `超时` 非整数或 ≤0）·
`-1` 超时（5 秒硬顶）。

**安全边界**：`shell=True` ⇒ 命令原样交给 `/bin/sh`，**不解析、不过滤**（本地开发工具，跑什么
由调用方负责）；不设 `check` ⇒ 命令失败折成退出码 1 + 回执正文，**不抛异常**（协议层一帧畸形
输入 = 进程死 = 工具从模型侧全部消失，见 `协议.py` 主循环那段）。本工具**不授权**：绕 `v1_edit`
改源码 · 跳闸 · 远端推送 · 杀陌生进程。
"""

import os
import re
import subprocess
import tempfile
from pathlib import Path

from .仓操作 import 禁终端提示环境, 找工作树

# 默认超时秒数 = 上限（判据 ㊲：全项目 ≤5 秒 —— 它是「容忍度」，不是「目标」）
超时秒 = 5
# 单个流最多回多少字符；超了截断并把完整输出落到系统临时目录（不落仓）
输出上限 = 16000
# 只认这三个键 —— 未知键一次拒（不猜调用方意图）
有效键 = ("命令", "开工ID", "超时")
# `开工ID` 的形状（与 `上下文.py` 同一份口径）
开工号形状 = re.compile(r"v1-[0-9]{6}")


def _落完整日志(命令: str, 目标树: Path, 标准输出: str, 标准错误: str) -> str:
    """把完整输出落到**系统临时目录**的一个日志件 ⇒ 它的绝对路径（不落仓内源码树）。"""
    句柄, 日志路径 = tempfile.mkstemp(prefix="v1_shell_", suffix=".log")
    with os.fdopen(句柄, "w", encoding="utf-8", errors="replace") as 日志件:
        日志件.write("命令：%s\n工作目录：%s\n\n=== 标准输出 ===\n%s\n\n=== 标准错误 ===\n%s\n"
                  % (命令, 目标树, 标准输出, 标准错误))
    return 日志路径


def _杀进程组(子进程) -> None:
    """超时 ⇒ 杀**整个进程组**（shell 及其子进程）⇒ 不留孤儿（`start_new_session` 开的组）。"""
    import signal
    try:
        os.killpg(os.getpgid(子进程.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        子进程.wait(timeout=2)
    except subprocess.TimeoutExpired:
        子进程.kill()


def 派发(参数表: dict, 仓根) -> tuple:
    """`v1_shell` 的入口。

    参数：
        命令: 要执行的 shell 命令（必填）
        开工ID: 可选；给了就在这条开工的工作树里跑，不给就在当前服务仓根跑
        超时: 超时秒数（可选，默认 5；>5 会被压回 5）

    返回：
        (退出码, 输出文本)
    """
    if not isinstance(参数表, dict):
        return 2, "参数拒绝：arguments 要是对象"
    未知键 = sorted(set(参数表) - set(有效键))
    if 未知键:
        return 2, "参数拒绝：未知键 %s；本工具只认 %s" % (
            "、".join(未知键), "、".join(有效键))
    命令 = str(参数表.get("命令") or "").strip()
    if not 命令:
        return 2, "参数拒绝：缺 `命令`（要执行的 shell 命令，必填）"

    # 超时：缺省取默认；给了就要整数且 > 0；超过上限**压回并如实报出**（判据 ㊲）
    超时 = 超时秒
    压回行 = ""
    if 参数表.get("超时") not in (None, ""):
        try:
            请求超时 = int(参数表["超时"])
        except (TypeError, ValueError):
            return 2, "参数拒绝：`超时` 要是整数秒，收到 %r" % (参数表.get("超时"),)
        if 请求超时 <= 0:
            return 2, "参数拒绝：`超时` 要 > 0 秒，收到 %r" % (请求超时,)
        if 请求超时 > 超时秒:
            压回行 = ("★ 传的超时 %d 秒 > 上限 %d 秒 ⇒ 压回 %d 秒（判据 ㊲：全项目超时设置 ≤5 秒）"
                    % (请求超时, 超时秒, 超时秒))
        else:
            超时 = 请求超时

    # 目标树：给了 `开工ID` 就问 git 精确定位那条开工的工作树；不给就用当前服务仓根。
    # **不接任意路径** —— 不许拿它换到仓外去。
    开工号 = str(参数表.get("开工ID") or "").strip()
    目标树 = Path(仓根).resolve()
    if 开工号:
        if not 开工号形状.fullmatch(开工号):
            return 2, "参数拒绝：`开工ID` 形状要是 `v1-` 加六位数字，收到 %r" % (开工号,)
        工作树 = 找工作树(仓根, 开工号)
        if 工作树 is None or not 工作树.is_dir():
            return 2, "参数拒绝：开工 %s 的工作树不在（问 git 问不到）⇒ 不执行" % (开工号,)
        目标树 = 工作树.resolve()

    # 执行：命令原样交给 /bin/sh（不解析、不过滤）；带上 git 禁终端提示（远端认证会永挂）。
    # 超时**杀整个进程组**（`start_new_session` + `killpg`）—— 只杀 shell 会留下它的子进程（孤儿）。
    环境表 = dict(os.environ)
    环境表.update(禁终端提示环境)
    try:
        子进程 = subprocess.Popen(命令, shell=True, cwd=str(目标树),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, env=环境表, start_new_session=True)
    except OSError as 起不来:
        return 1, "起不了：%r\n命令：%s" % (起不来, 命令)
    try:
        标准输出, 标准错误 = 子进程.communicate(timeout=超时)
    except subprocess.TimeoutExpired:
        _杀进程组(子进程)
        return -1, "命令超时（%d 秒）：%s\n工作目录：%s" % (超时, 命令, 目标树)
    回执码 = 子进程.returncode

    标准输出 = 标准输出 or ""
    标准错误 = 标准错误 or ""
    截断行表 = []
    if len(标准输出) > 输出上限 or len(标准错误) > 输出上限:
        完整日志路径 = _落完整日志(命令, 目标树, 标准输出, 标准错误)
        标准输出 = 标准输出[:输出上限]
        标准错误 = 标准错误[:输出上限]
        截断行表.append("★ 输出超 %d 字符已截断；完整日志：%s" % (输出上限, 完整日志路径))

    输出行 = ["命令：%s" % 命令, "工作目录：%s" % 目标树,
             "退出码：%d" % 回执码, "超时：%d 秒（上限 %d 秒）" % (超时, 超时秒)]
    if 压回行:
        输出行.append(压回行)
    输出行.append("")
    if 标准输出:
        输出行 += ["=== 标准输出 ===", 标准输出.rstrip(), ""]
    if 标准错误:
        输出行 += ["=== 标准错误 ===", 标准错误.rstrip(), ""]
    输出行 += 截断行表
    输出文本 = "\n".join(输出行)
    return (1 if 回执码 != 0 else 0), 输出文本
