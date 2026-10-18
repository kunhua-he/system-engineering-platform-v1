# -*- coding: utf-8 -*-
"""注入样本 · 判据 60（样本在临时仓里跑 git 必须环境隔离）。

反向样本的靶：一件「名字含样本」的 `.py`，直调 git 却不带 `env=` ⇒ 当场红（541 / 545 同类漏用）。
"""
from __future__ import annotations

from pathlib import Path

样本件路径 = "开发工具/MCP服务/样例样本.py"


def 注入_样本git无环境(临根: Path) -> str:
    """往夹具放一件直调 git、不带 `env=` 的样本件 ⇒ 判据 60 当场红。"""
    路径 = 临根 / 样本件路径
    路径.parent.mkdir(parents=True, exist_ok=True)
    路径.write_text(
        "# 反向样本：样本在临时仓里跑 git 却不带 env=（会继承外层 GIT_* 定位键）\n"
        "import subprocess\n\n"
        'subprocess.run(["git", "add", "样例.py"], cwd="/tmp", capture_output=True)\n',
        encoding="utf-8",
    )
    return 样本件路径
