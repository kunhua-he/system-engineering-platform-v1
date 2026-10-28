# -*- coding: utf-8 -*-
"""注入样本 · 判据 71（守护壳真跑自检）。

反样本：往合成仓放一份**中文变量名**的守护壳 ⇒ 真跑必报 `bad substitution` ⇒ 判据 71 当场红。
这不是造型，是实测踩过的那个病：

  - 那份壳的 `sh -n` **退出码 0**（语法合法），所以它只能靠**真跑**抓 —— 这正是本条存在的理由；
  - 注入件只在反样本的夹具仓里，干净合成仓没有它 ⇒ 判据退回本仓那份壳、正向样本照样过。

正向对照（干净合成仓）不在这里造 —— 由 `合成仓.py` 提供。
"""
from __future__ import annotations

from pathlib import Path

# 反样本壳：四个可覆盖变量写成中文名 ⇒ macOS bash 3.2 运行期 `bad substitution`
反样本壳文本 = """#!/bin/sh
# 反证样本：可覆盖变量写中文名 ⇒ 运行期 bad substitution（`sh -n` 查不出）
RUNDIR="${V1_运行根:-/tmp/反证-运行}"
LOG="${V1_网关日志:-/tmp/反证.log}"
LOG_MAX_BYTES=5242880

rotate_log() {
  [ -f "$1" ] || return 0
  size=$(wc -c < "$1" 2>/dev/null | tr -d ' ')
  [ -n "$size" ] || return 0
  if [ "$size" -ge "$LOG_MAX_BYTES" ]; then
    mv -f "$1" "$1.1"
  fi
}

if [ "${V1_守护自检:-}" != "1" ]; then
  :
fi
"""


def 注入_中文变量名守护壳(临根: Path) -> str:
    """往合成仓放一份中文变量名的守护壳 ⇒ 真跑报 bad substitution ⇒ 判据 71 当场红。"""
    路径 = 临根 / "构建装配" / "上线切换" / "网关守护.sh"
    路径.parent.mkdir(parents=True, exist_ok=True)
    路径.write_text(反样本壳文本, encoding="utf-8")
    return "构建装配/上线切换/网关守护.sh"
