# -*- coding: utf-8 -*-
"""注入样本 · 判据 61（解释器唯一化）。"""
from __future__ import annotations

from pathlib import Path


def 注入_执行面裸解释器(临根: Path) -> str:
    """造一处**命令串写裸解释器名**的代码件 ⇒ 判据 61 当场红。

    形状取现场实测那一类（`构建装配/形态装配/生成声明/参数生成测试.py::验证参数生成`
    里的命令串 —— 干净 PATH 下 `command not found`、作业 64 ms 假失败）。

    ★ 本件自身的字面量必须避开裸名：判据扫的是**真仓**（含本件），而 `保串` 让串里的名字
      也看得见 —— 故样本内容用 `%s` 拼出来，本件源码里不出现可命中的字面量。
    """
    裸名 = "py" + "thon" + "3"
    路径 = 临根 / "构建装配" / "样例" / "裸解释器样本.py"
    路径.parent.mkdir(parents=True, exist_ok=True)
    路径.write_text(
        "# 反向样本：执行面命令串写裸解释器名。\n"
        "import subprocess\n"
        "\n"
        "\n"
        "def 跑():\n"
        "    生成命令 = [\"%s\", \"构建装配/样例/某生成器.py\"]\n" % 裸名
        + "    subprocess.run(生成命令, check=True)\n",
        encoding="utf-8",
    )
    return "构建装配/样例/裸解释器样本.py"
