# -*- coding: utf-8 -*-
"""自检_MCP事务 —— MCP 重事务认领链的**机制身份证**。

`一键验证.py --自测` 的「判据器自身机制」一节调它（提交长路，装不进闸 0 的 5 秒硬顶）。
对象 = `开发工具/MCP服务/施工管理/认领隔离.py` 的**事务认领 / 预留开工**链：并发同树只放一个、
事务失败不留部分认领、漂移拒洗账、bare 仓根树身份仍成立、外仓拒、已有开工回归；
外加**样本 git 环境隔离**（源头同 541 实测：裸仓根服务注入 `GIT_DIR`/`GIT_WORK_TREE` ⇒
样本继承 ⇒ `git add` 落到外层索引）：给子进程注入 `GIT_DIR`/`GIT_INDEX_FILE` 指向**别仓**，
跑完断言**别仓索引零写**（长路覆盖，与判据 60 的静态面互补）。

**为什么用子进程**：本件在 `构建装配/`（横切），`开发工具/` 不在产品层序里 ⇒ 直接 import
会踩层序；与 `判据_MCP自检.py` 同一口径（子进程调入口，互不 import）。**读数** = 子进程退出码
与逐场景 ✓/✗ 行。

★ **不设子进程超时**（同 `自测闭包.py` 的「环境步不判顶」）：`--自测` 是环境步，把**判据面的
硬顶**拿来卡它，正是 `自测闭包.py` 件头禁止的那件事（作者会为塞进超时而把富样本拆瘦；
实测：并发档 3 / 5 下本单元报超时，load 29–40 ⇒ 负载假红，调用方只能重跑）。
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from ..基础定义.判据取值常量 import 仓根


def 自检_MCP事务机制() -> list:
    """跑 `开发工具/MCP服务.py --长样本` ⇒ `[(名称, 是否好, 说明)]`。"""
    入口件 = Path(仓根) / "开发工具" / "MCP服务.py"
    if not 入口件.is_file():
        return [("MCP 重事务 7 场景（子进程 `MCP服务.py --长样本`）", False,
                 "入口件不在：%s ⇒ 这条机制没有对象" % 入口件)]
    with tempfile.TemporaryDirectory(prefix="v1样本环境隔离-") as 临时目录:
        别仓 = Path(临时目录) / "别仓"
        别仓.mkdir()
        # 先搭一个干净环境的别仓（剔掉外层 `GIT_*` 定位键 —— 否则 git init 也会被重定向）。
        环境表 = {键名: 值 for 键名, 值 in os.environ.items()
               if 键名 not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
                            "GIT_OBJECT_DIRECTORY", "GIT_COMMON_DIR",
                            "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_PREFIX")}
        环境表["GIT_TERMINAL_PROMPT"] = "0"
        subprocess.run(["git", "init", "-b", "别仓"], cwd=str(别仓),
                       capture_output=True, text=True, timeout=5, env=环境表)
        路径 = 别仓 / ".git" / "index"
        # 注入重定向键（源头同 541 实测）⇒ 跑 `--长样本`：剔键正确则别仓索引零写。
        环境表["GIT_DIR"] = str(别仓 / ".git")
        环境表["GIT_INDEX_FILE"] = str(路径)
        # ★ 不设超时（走 `自测闭包.跑自测闭包` 同口径）：`--自测` 是**环境步、不判顶**，
        #   原先按 `硬顶毫秒 / 1000`（临时放宽后 = 10 s）卡它 = 把判据面硬顶误用到环境步。
        #   实测：并发档 3 / 档 5 下本单元报「超时」（load 29–40）—— 负载假红。
        #   不设超时 ≠ 永不红：子进程真挂住只是拖长墙钟（环境步允许），退出码非 0 照样报红。
        子进程 = subprocess.run(
            [sys.executable, str(入口件), "--长样本"],
            cwd=str(仓根), capture_output=True, text=True, env=环境表,
        )
        输出 = (子进程.stdout or "") + (子进程.stderr or "")
        通过数 = 输出.count("✓")
        失败数 = 输出.count("✗")
        尾部读数 = [读数行.strip() for 读数行 in 输出.splitlines() if 读数行.strip()][-4:]
        return [
            ("MCP 重事务 7 场景 + 夹具 git 隔离样本（子进程 `MCP服务.py --长样本`，退出码 %d）"
             % 子进程.returncode,
             子进程.returncode == 0 and 通过数 >= 8 and 失败数 == 0,
             "✓ %d · ✗ %d ｜ 尾部读数：%s" % (通过数, 失败数, " ／ ".join(尾部读数))),
            ("样本跑 git 不污染外层索引（注 GIT_DIR/GIT_INDEX_FILE 跑 `--长样本` ⇒ 别仓索引零写）",
             not 路径.is_file(),
             "别仓索引%s被写 ｜ 修法：样本 subprocess 带 `env=干净环境()`，或走 `仓操作.跑命令`"
             "（已剔重定向键）" % ("**" if 路径.is_file() else "未")),
        ]
