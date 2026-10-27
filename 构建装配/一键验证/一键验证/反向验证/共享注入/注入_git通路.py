# -*- coding: utf-8 -*-
"""注入样本 · 判据 69（Git 路径读数形式）。"""
from __future__ import annotations

from pathlib import Path


def 注入_git读方无零分隔(临根: Path) -> str:
    """往合成仓放一个**违规读方**（`git status --porcelain` 不带 `-z` + `.strip('"')`）⇒ 判据 69 当场红。

    前置由 `合成仓.py` 提供（该仓自带一份**合规**的 `开发工具/样例读方.py` ⇒ 对象数非 0 ——
    这条判据靠对象数区分「没量到」与「量到且合规」）。
    """
    路径 = 临根 / "开发工具" / "违规读方.py"
    路径.parent.mkdir(parents=True, exist_ok=True)
    路径.write_text(
        "import subprocess\n\n\n"
        "def 读脏件(仓根):\n"
        "    回执 = subprocess.run([\"git\", \"status\", \"--porcelain\"], cwd=仓根, capture_output=True, text=True)\n"
        "    return [行.strip().strip('\"') for 行 in 回执.stdout.splitlines() if 行.strip()]\n",
        encoding="utf-8")
    return "开发工具/违规读方.py"
