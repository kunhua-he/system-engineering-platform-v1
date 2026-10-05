# -*- coding: utf-8 -*-
"""Shell 执行器 —— `v1_shell` 的实现：**本地秒级执行 shell 命令**。

**为什么要它**（2026-10-05 华哥要的）：`git status` / `ls` / `cat 一段` 这类活，走模型侧的
Bash 工具每次都要一次往返；MCP 服务是**本地长驻进程** ⇒ 在它里面跑没有那次往返，秒级返回。

**它不是第五个「适配层」**：前四个工具都只**转发**仓内已有入口，本件**自身就是执行器**。
⇒ 它**不在四道闸之内**：拿它写盘 = 绕过账本（认领 / 指纹 / 旧内容定位全不查）。
口径写在工具说明里（「改文件仍走 `v1_edit`」），**靠模型守，不靠机制拦**。

**超时上限 5 秒**（判据 ㊲）：全项目超时设置一律 ≤5 秒
（`决策记录/2026-09-27_所有运行五秒硬顶.md` §一，华哥原话「整个项目所有超时设置上限就是 5 秒」）。
故默认值与上限都是 5；传更大的 `超时` **压回 5 并在回执里如实报出**（不拒收 —— 拒收只会让模型
反复试，压回更省事）。

**用法**：
    v1_shell(命令="git status")
    v1_shell(命令="ls -la", 工作目录="/Users/hekunhua/Documents")

**退出码语义**（与工具面其余四件同一张表，见 `工具.py` 顶部）：
`0` 成功 · `1` 命令本身失败（非零退出码，回执里带 stdout/stderr）·
`2` 参数错（命令为空 / 工作目录不存在 / `超时` 非整数或 ≤0）· `-1` 超时（5 秒硬顶）。

**安全边界**：`shell=True` ⇒ 命令原样交给 `/bin/sh`，**不解析、不过滤**（本地开发工具，跑什么
由调用方负责）；不设 `check` ⇒ 命令失败折成退出码 1 + 回执正文，**不抛异常**（协议层一帧畸形
输入 = 进程死 = 五个工具从模型侧全部消失，见 `协议.py` 主循环那段）。
"""

import subprocess
import sys
from pathlib import Path

# 默认超时秒数 = 上限（判据 ㊲：全项目 ≤5 秒 —— 它是「容忍度」，不是「目标」）
超时秒 = 5


def 派发(参数表: dict, 仓根) -> tuple:
    """`v1_shell` 的入口。

    参数：
        命令: 要执行的 shell 命令（必填）
        工作目录: 执行命令的工作目录（可选，默认仓根）
        超时: 超时秒数（可选，默认 5；>5 会被压回 5）

    返回：
        (退出码, 输出文本)
    """
    命令 = str(参数表.get("命令") or "").strip()
    工作目录 = str(参数表.get("工作目录") or "").strip()
    输出行 = []

    # 超时：缺省取默认；给了就要整数且 > 0；超过上限**压回并如实报出**（判据 ㊲）
    超时 = 参数表.get("超时")
    if 超时 in (None, ""):
        超时 = 超时秒
    else:
        try:
            超时 = int(超时)
        except (TypeError, ValueError):
            return 2, "`超时` 要是整数秒，收到：%r" % (超时,)
        if 超时 <= 0:
            return 2, "`超时` 要 > 0 秒，收到：%r" % (超时,)
        if 超时 > 超时秒:
            输出行.append("★ 传的超时 %d 秒 > 上限 %d 秒 ⇒ 压回 %d 秒（判据 ㊲：全项目超时设置 ≤5 秒）"
                        % (超时, 超时秒, 超时秒))
            超时 = 超时秒

    # 参数验证
    if not 命令:
        return 2, "命令不能为空"

    # 确定工作目录：绝对路径照用；相对路径按仓根解析
    if not 工作目录:
        查询根 = Path(仓根).resolve()
    elif 工作目录.startswith("/"):
        查询根 = Path(工作目录).resolve()
    else:
        查询根 = (Path(仓根) / 工作目录).resolve()

    if not 查询根.is_dir():
        return 2, "工作目录不存在：%s" % 查询根

    # 执行命令
    try:
        回执 = subprocess.run(
            命令,
            shell=True,
            cwd=str(查询根),
            capture_output=True,
            text=True,
            timeout=超时,
        )

        输出行.append("命令：%s" % 命令)
        输出行.append("工作目录：%s" % 查询根)
        输出行.append("退出码：%d" % 回执.returncode)
        输出行.append("")

        if 回执.stdout:
            输出行.append("=== 标准输出 ===")
            输出行.append(回执.stdout.rstrip())
            输出行.append("")

        if 回执.stderr:
            输出行.append("=== 标准错误 ===")
            输出行.append(回执.stderr.rstrip())
            输出行.append("")

        输出文本 = "\n".join(输出行)

        # 命令自身非零 ⇒ 退出码 1（回执里带 stdout/stderr，供人判）
        if 回执.returncode != 0:
            return 1, 输出文本

        return 0, 输出文本

    except subprocess.TimeoutExpired:
        return -1, "命令超时（%d 秒）：%s" % (超时, 命令)
    except Exception as 错误:
        return 1, "执行失败：%s\n命令：%s" % (错误, 命令)
