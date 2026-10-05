#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""钩子 —— `装钩子.py` 的实现：把「改文件只能走 MCP」写进 ZCode 的 PreToolUse 钩子（幂等）。

**为什么要有它**：钩子住在**用户级配置**（`~/.zcode/cli/config.json`）—— 版本库外。
不把「怎么装」版本化，别人 clone 下来钩子闸等于不存在（同 `装门禁.sh` 的理由）。
**★ 用户级 ⇒ 拦本机所有项目**：`matcher` 只认工具名、**零路径逻辑** ⇒ 在**任何项目**里用 Edit/Write
都被 `exit 2` 拦，不止本仓（**拦全机是有意的**：提示里写本仓口径，但不按项目分流）。

**钩子闸的形状：零逻辑 · 一张名单**。名单写在 `matcher` 里（大小写敏感的正则，匹配工具名），
钩子体只做一件事：打印「该走哪个工具」然后 `exit 2`（MCP 协议：2 = 拦）。
名单只认这四个 —— `Edit` / `Write` / `MultiEdit` / `NotebookEdit`。
**`Bash` 放行**：钩子分不出 Bash 的读与写，硬拦会让 agent 连 `闸0.py` 和 `git status` 都跑不了；
绕过 MCP 的 Bash 写由**指纹对账**兜（`v1_edit` 的第 ③ 道闸 + `v1_gate` 的绕过检测）。

**配置口径**（`zcode-guide:diagnosing-hooks`）：配置文件的钩子**默认不跑** ⇒ 必须
`hooks.enabled: true`；事件名只有七个，`PreToolUse` 是其一；`command` 钩子的 `timeout` 单位是**秒**。
"""

import json
import os
import sys
import tempfile
from pathlib import Path

配置文件路径 = Path.home() / ".zcode" / "cli" / "config.json"
自家标记 = "V1 开工闸"                    # 认它做幂等：命令串里带这个标记就是自家那条
拦的工具 = "Edit|Write|MultiEdit|NotebookEdit"
钩子命令 = (f"printf '%s\\n' '[{自家标记}] 用户级钩子：本机所有项目的 Edit/Write 都被拦。"
        "本仓改代码走 MCP：请调 v1_edit（先用 v1_task 功能=1 登记拿开工ID，再功能=2 认领文件）' >&2; exit 2")


def _读配置() -> dict:
    if not 配置文件路径.is_file():
        return {}
    try:
        数据 = json.loads(配置文件路径.read_text(encoding="utf-8"))
    except ValueError as 解不动的原因:
        raise SystemExit("读不动 %s（不是合法 JSON）：%s\n本件不替你改它 —— 先修好它再跑"
                         % (配置文件路径, 解不动的原因))
    return 数据 if isinstance(数据, dict) else {}


def _是自家钩子条(一条) -> bool:
    return any(自家标记 in str(一个.get("command") or "")
              for 一个 in (一条.get("hooks") or []) if isinstance(一个, dict))


def 保存(路径: Path, 文本: str) -> None:
    """临时件 + `os.replace`（原子改名）—— ★ 这是**用户级配置**，写坏 = ZCode 起不来。

    `write_text` 先截断再写：进程被杀 / 磁盘满 / 并发写 ⇒ 半截 JSON。这里改成同目录临时件写完
    `fsync` 再 `os.replace`（同文件系统 ⇒ 原子：读者要么见旧要么见新）。写前的备份由调用方
    （`装钩子` 写 `.v1装前状态`）负责 —— 那份状态件同时是还原依据；这里失败一律清理临时件并抛出，
    **不碰原文件**。
    """
    路径.parent.mkdir(parents=True, exist_ok=True)
    原模式 = None
    try:
        原模式 = 路径.stat().st_mode
    except OSError:
        pass
    句柄, 临时名 = tempfile.mkstemp(dir=str(路径.parent),
                                prefix="." + 路径.name + ".", suffix=".tmp")
    try:
        with os.fdopen(句柄, "w", encoding="utf-8") as 文件句柄:
            文件句柄.write(文本)
            文件句柄.flush()
            os.fsync(文件句柄.fileno())
        if 原模式 is not None:
            os.chmod(临时名, 原模式)
        os.replace(临时名, 路径)
    except BaseException:
        try:
            os.unlink(临时名)
        except OSError:
            pass
        raise


def 装钩子() -> int:
    数据 = _读配置()
    已存在 = 配置文件路径.is_file()
    钩子块 = 数据.get("hooks")
    if not isinstance(钩子块, dict):
        钩子块 = {}
    暂存 = dict(钩子块) if 钩子块 else None       # ★ 装前快照（改之前取，还原 enabled 用）
    钩子块["enabled"] = True                     # ★ 配置文件的钩子默认不跑，这一行不能少
    事件表 = 钩子块.get("events")
    if not isinstance(事件表, dict):
        事件表 = {}
    前事件 = 事件表.get("PreToolUse")
    if not isinstance(前事件, list):
        前事件 = []
    # 幂等：先把自家旧条摘掉，再插一条新的（重复跑不叠加；**别人的条一律不动**）
    别人的条 = [一条 for 一条 in 前事件 if not (isinstance(一条, dict) and _是自家钩子条(一条))]
    前事件 = 别人的条 + [{"matcher": 拦的工具,
                      "hooks": [{"type": "command", "command": 钩子命令, "timeout": 5}]}]
    事件表["PreToolUse"] = 前事件
    钩子块["events"] = 事件表
    数据["hooks"] = 钩子块
    # 写前留备份 + 记装前样子（只在第一次装时写）：这份状态件同时是「卸钩子时按什么还原」的依据。
    配置文件路径.parent.mkdir(parents=True, exist_ok=True)
    备选路径 = 配置文件路径.with_name(配置文件路径.name + ".v1装前状态")
    if not 备选路径.is_file():
        原文 = 配置文件路径.read_text(encoding="utf-8") if 已存在 else ""
        备选路径.write_text(json.dumps({"有配置": 已存在, "原文": 原文, "钩子": 暂存},
                                   ensure_ascii=False), encoding="utf-8")
    保存(配置文件路径, json.dumps(数据, ensure_ascii=False, indent=2) + "\n")
    print("装钩子：已写进 %s" % 配置文件路径)
    print("        拦：%s（其余工具一律放行，含 Bash / Read / Grep）" % 拦的工具)
    print("        ★ 钩子写进**用户级配置** ⇒ **拦本机所有项目**的 Edit/Write，不止本仓（有意如此）。")
    print("        拦下时打印「该调哪个工具」并 exit 2 —— 报错必须带解法。")
    print("        别人的钩子一条没动；重复跑不叠加（认标记 `%s`）。" % 自家标记)
    print("        ★ 装完要**重启 ZCode** 才生效（钩子在会话启动时装载）。")
    return 0


def 卸钩子() -> int:
    数据 = _读配置()
    钩子块 = 数据.get("hooks")
    if not isinstance(钩子块, dict) or not isinstance(钩子块.get("events"), dict):
        print("装钩子：配置里没有 hooks 段 ⇒ 本来就没装")
        return 0
    前事件 = 钩子块["events"].get("PreToolUse")
    if not isinstance(前事件, list):
        print("装钩子：没有 PreToolUse 段 ⇒ 本来就没装")
        return 0
    留下的条 = [一条 for 一条 in 前事件 if not (isinstance(一条, dict) and _是自家钩子条(一条))]
    摘掉数 = len(前事件) - len(留下的条)
    if 摘掉数 == 0:
        print("装钩子：没有自家那条（标记 `%s`）⇒ 没动" % 自家标记)
        return 0
    # 装前状态件（`装钩子` 第一次装时留的）—— 按它还原 enabled 与「原本有没有配置」。
    备选路径 = 配置文件路径.with_name(配置文件路径.name + ".v1装前状态")
    已存在 = 备选路径.is_file()
    暂存 = {}
    if 已存在:
        try:
            暂存 = json.loads(备选路径.read_text(encoding="utf-8")) or {}
        except (OSError, ValueError):
            暂存 = {}
    if 留下的条:
        钩子块["events"]["PreToolUse"] = 留下的条
    else:
        del 钩子块["events"]["PreToolUse"]        # 一条不剩就把这一格删掉，不留空壳
        if not 钩子块["events"]:
            del 钩子块["events"]                  # 空 events 也是壳，删掉
    # ★ 按装前记录还原 `enabled`（装前没这个键 ⇒ 删掉）—— 否则原本 false 的会被永久翻成 true，
    #   连带激活别人的钩子。没有状态件（旧版装的）⇒ 不动 enabled（不猜）。
    if 已存在:
        if isinstance(暂存.get("钩子"), dict) and "enabled" in 暂存["钩子"]:
            钩子块["enabled"] = 暂存["钩子"]["enabled"]
        else:
            钩子块.pop("enabled", None)
    if 钩子块:
        数据["hooks"] = 钩子块
    else:
        数据.pop("hooks", None)                   # 全空 ⇒ 不留空壳
    保存(配置文件路径, json.dumps(数据, ensure_ascii=False, indent=2) + "\n")
    # 收尾：装前根本没配置 ⇒ 把建出来的那份也删掉，回到「没有」；撤掉状态件（下次装重新快照）。
    if 已存在:
        if not 暂存.get("有配置"):
            try:
                配置文件路径.unlink()
            except OSError:
                pass
        try:
            备选路径.unlink()
        except OSError:
            pass
    print("装钩子：摘掉自家 %d 条，别人的一条没动；enabled 按装前还原。重启 ZCode 生效。" % 摘掉数)
    return 0


def 入口函数(argv=None) -> int:
    命令行参数 = list(sys.argv[1:] if argv is None else argv)
    if "--卸" in 命令行参数 or "--uninstall" in 命令行参数:
        return 卸钩子()
    return 装钩子()
