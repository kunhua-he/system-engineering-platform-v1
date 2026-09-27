# -*- coding: utf-8 -*-
"""注入样本 · 判据 ㉓（散文不落被忽略目录）。"""
from __future__ import annotations

from pathlib import Path


def 注入_散文落忽略目录(临根: Path) -> str:
    """往**被 git 忽略**的目录里放一份 `.md` ⇒ 判据 ㉓ 当场红。

    前置由 `合成仓.py` 提供：干净合成仓自己 `git init`，`.gitignore` 忽略
    `构建装配/制品产物/*`（并放一个被忽略的 `.bin` ⇒ 对象数非 0）。
    这里只放那份散文 —— 形状就是实测丢过的 `构建装配/制品产物/说明.md`。
    """
    路径 = 临根 / "构建装配" / "制品产物" / "说明.md"
    路径.parent.mkdir(parents=True, exist_ok=True)
    路径.write_text("# 制品产物说明（反向样本：住在被忽略的目录里）\n", encoding="utf-8")
    return "构建装配/制品产物/说明.md"
