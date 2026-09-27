#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""钩子 —— `装钩子.py` 的实现：把「改文件只能走 MCP」写进 ZCode 的 PreToolUse 钩子（幂等）。

**为什么要有它**：钩子住在**用户级配置**（`~/.zcode/cli/config.json`）—— 版本库外。
不把「怎么装」版本化，别人 clone 下来钩子闸等于不存在（同 `装门禁.sh` 的理由）。

**钩子闸的形状：零逻辑 · 一张名单**。名单写在 `matcher` 里（大小写敏感的正则，匹配工具名），
钩子体只做一件事：打印「该走哪个工具」然后 `exit 2`（MCP 协议：2 = 拦）。
名单只认这四个 —— `Edit` / `Write` / `MultiEdit` / `NotebookEdit`。
**`Bash` 放行**：钩子分不出 Bash 的读与写，硬拦会让 agent 连 `闸0.py` 和 `git status` 都跑不了；
绕过 MCP 的 Bash 写由**指纹对账**兜（`v1_edit` 的第 ③ 道闸 + `v1_gate` 的绕过检测）。

**配置口径**（`zcode-guide:diagnosing-hooks`）：配置文件的钩子**默认不跑** ⇒ 必须
`hooks.enabled: true`；事件名只有七个，`PreToolUse` 是其一；`command` 钩子的 `timeout` 单位是**秒**。
"""

import json
import sys
from pathlib import Path

配置文件 = Path.home() / ".zcode" / "cli" / "config.json"
自家标记 = "V1 开工闸"                    # 认它做幂等：命令串里带这个标记就是自家那条
拦的工具 = "Edit|Write|MultiEdit|NotebookEdit"
钩子命令 = (f"printf '%s\\n' '[{自家标记}] 改代码只能走 MCP：请调 v1_edit"
        "（先用 v1_task 功能=1 登记拿开工ID，再功能=2 认领文件）' >&2; exit 2")


def _读配置() -> dict:
    if not 配置文件.is_file():
        return {}
    try:
        数据 = json.loads(配置文件.read_text(encoding="utf-8"))
    except ValueError as 解不动的原因:
        raise SystemExit("读不动 %s（不是合法 JSON）：%s\n本件不替你改它 —— 先修好它再跑"
                         % (配置文件, 解不动的原因))
    return 数据 if isinstance(数据, dict) else {}


def _自家条(一条) -> bool:
    return any(自家标记 in str(一个.get("command") or "")
              for 一个 in (一条.get("hooks") or []) if isinstance(一个, dict))


def 装钩子() -> int:
    数据 = _读配置()
    钩子块 = 数据.get("hooks")
    if not isinstance(钩子块, dict):
        钩子块 = {}
    钩子块["enabled"] = True                     # ★ 配置文件的钩子默认不跑，这一行不能少
    事件表 = 钩子块.get("events")
    if not isinstance(事件表, dict):
        事件表 = {}
    前事件 = 事件表.get("PreToolUse")
    if not isinstance(前事件, list):
        前事件 = []
    # 幂等：先把自家旧条摘掉，再插一条新的（重复跑不叠加；**别人的条一律不动**）
    别人的条 = [条 for 条 in 前事件 if not (isinstance(条, dict) and _自家条(条))]
    前事件 = 别人的条 + [{"matcher": 拦的工具,
                      "hooks": [{"type": "command", "command": 钩子命令, "timeout": 5}]}]
    事件表["PreToolUse"] = 前事件
    钩子块["events"] = 事件表
    数据["hooks"] = 钩子块
    配置文件.parent.mkdir(parents=True, exist_ok=True)
    配置文件.write_text(json.dumps(数据, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("装钩子：已写进 %s" % 配置文件)
    print("        拦：%s（其余工具一律放行，含 Bash / Read / Grep）" % 拦的工具)
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
    留下的条 = [条 for 条 in 前事件 if not (isinstance(条, dict) and _自家条(条))]
    摘掉数 = len(前事件) - len(留下的条)
    if 摘掉数 == 0:
        print("装钩子：没有自家那条（标记 `%s`）⇒ 没动" % 自家标记)
        return 0
    if 留下的条:
        钩子块["events"]["PreToolUse"] = 留下的条
    else:
        del 钩子块["events"]["PreToolUse"]        # 一条不剩就把这一格删掉，不留空壳
    数据["hooks"] = 钩子块
    配置文件.write_text(json.dumps(数据, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("装钩子：摘掉自家 %d 条，别人的一条没动。重启 ZCode 生效。" % 摘掉数)
    return 0


def 入口函数(argv=None) -> int:
    参 = list(sys.argv[1:] if argv is None else argv)
    if "--卸" in 参 or "--uninstall" in 参:
        return 卸钩子()
    return 装钩子()
