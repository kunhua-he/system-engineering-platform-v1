# -*- coding: utf-8 -*-
"""注入样本 · 判据 ㉔（入口覆盖面）。"""
from __future__ import annotations

from pathlib import Path


def 注入_入口无壳不在白名单(临根: Path) -> str:
    """造一条**能跑完、无壳、不在白名单**的入口 ⇒ 判据 ㉔ 当场红。

    形状：有行首 `if __name__ == "__main__"` 的 `.py`，但既没有 `自门禁`/`报告环境步`
    （不带上壳），也不在 `入口白名单.json` 里（不属任何结构边界）。
    """
    路径 = 临根 / "运行内核" / "实例状态" / "src" / "假入口.py"
    路径.parent.mkdir(parents=True, exist_ok=True)
    路径.write_text(
        "import sys\n\n\nif __name__ == \"__main__\":\n    sys.exit(0)\n",
        encoding="utf-8",
    )
    return "运行内核/实例状态/src/假入口.py"
