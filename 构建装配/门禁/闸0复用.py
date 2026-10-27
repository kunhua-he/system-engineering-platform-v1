# -*- coding: utf-8 -*-
r"""闸 0 复用 —— 「同一棵树、同一份内容只跑一遍」（债务 Q2 · 2026-10-11）。

**为什么**：同一条腿的同一份内容会被验两遍 —— 释放主体先跑一遍闸 0，随后 `git commit` 的
pre-commit 钩子又跑一遍；空改腿更甚：`跑验证`（主干）与 `空改门禁`（主干）各跑一遍。
中间代码零改动 ⇒ 第二遍没有新信息，纯浪费（实测闸 0 约 7 s/遍）。

**正解** = 按**树指纹**复用：把「树指纹 → 闸 0 读数」记在**本树的 .git 下**
（`git rev-parse --git-path` 定位 ⇒ 不进版本库、不进扫描面、天然按树分），
指纹一致就直接回放上次读数、不再重跑。

**三条不许违反**：

  · **只记全过的那一次** —— 红的那次不落记录。否则一次「瞬时超顶」的假红会被固化，
    后续复跑读到同一份记录就永远红下去（那会把「复跑一次」这条兜底口径整个废掉）。
  · **指纹面 = 闸 0 实读的那份面** —— 全树走树（`跳过目录` / 临时件 / `扫描后缀`，
    与 `读文件.扫源文件` 同一口径）**＋ 两个真读却不在扫描后缀里的库**（`信息核心.db` ·
    `codegraph.db`）。面覆盖不到 ⇒ 内容变了却命中复用，那才是真的假绿。
  · **读不到 / 写不进 / 不是版本库 ⇒ 一律真跑** —— 复用是提速，不是判决；绝不因它放行。

**反样本（承重的那一条）**：内容一变，指纹必变 ⇒ 必须重跑；改判据面（也在扫描面里）同理。
身份证见 `自检_闸0复用`。
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

# 复用记录件名：住本树 `.git/` 下（不进版本库、不进扫描面）。
复用记录件名 = "v1-闸0复用.json"

# 闸 0 真读、却不在 `扫描后缀` 里的库（相对路径）—— 不覆盖它们 ⇒ 改库不重跑。
库件相对路径表 = ("开发工具/信息核心/信息核心.db", ".codegraph/codegraph.db")


def _取扫描口径():
    """惰性取闸 0 的读件口径（`跳过目录` / `临时目录前缀` / `扫描后缀`）—— 唯一主人在包内。

    惰性取的理由：本件被 `构建装配/门禁/__init__` 再导出，而 `自门禁` 是每条命令的热路；
    在模块级 import 会把整包 `一键验证.基础定义.常量`（连同表定义、代码地图）拖进每个热路。
    """
    import sys
    根目录 = str(Path(__file__).resolve().parents[2] / "构建装配" / "一键验证")
    if 根目录 not in sys.path:
        sys.path.insert(0, 根目录)
    from 一键验证.基础定义.判据取值常量 import 跳过目录, 临时目录前缀, 扫描后缀
    return 跳过目录, 临时目录前缀, 扫描后缀


def 算树指纹(仓根: Path) -> str:
    """一棵工作树的指纹（sha256 前 16 位）⇒ 十六进制文本。**口径与闸 0 的读件面一致**。

    逐件喂「相对路径 + 0 + 字节 + 0」（相对路径也进摘要 ⇒ 改名 / 移动同样算内容变），
    末了把两个库件按同一形状追加。读不动的件跳过（不让一个坏件把整条命令打死）。
    """
    跳过目录, 临时目录前缀, 扫描后缀 = _取扫描口径()
    指纹器 = hashlib.sha256()
    件表 = []
    for 根目录, 目录表, 文件表 in os.walk(仓根):
        目录表[:] = [目录名 for 目录名 in 目录表
                   if 目录名 not in 跳过目录 and not 目录名.startswith(临时目录前缀)]
        for 名称 in 文件表:
            if 名称.endswith(扫描后缀):
                件表.append(Path(根目录) / 名称)
    件表.sort(key=lambda 路径: str(路径.relative_to(仓根)))
    for 路径 in 件表:
        指纹器.update(str(路径.relative_to(仓根)).encode("utf-8"))
        指纹器.update(b"\0")
        try:
            指纹器.update(路径.read_bytes())
        except OSError:
            pass
        指纹器.update(b"\0")
    for 库件 in 库件相对路径表:
        路径 = Path(仓根) / 库件
        if not 路径.is_file():
            continue
        指纹器.update(库件.encode("utf-8"))
        指纹器.update(b"\0")
        try:
            指纹器.update(路径.read_bytes())
        except OSError:
            pass
        指纹器.update(b"\0")
    return 指纹器.hexdigest()[:16]


def 复用记录路径(仓根: Path):
    """本树复用记录的落点 ⇒ `Path` 或 `None`（不是版本库 / git 调不动 ⇒ `None`）。

    **问 git**（`--git-path`），不拼目录名：它天然按树分（主仓 `.git/` · 每条腿
    `.git/worktrees/<开工号>/`），且落点不在源码树里（不进扫描面、不进版本库）。
    """
    try:
        回执 = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-path", 复用记录件名],
                           cwd=str(仓根), capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    if 回执.returncode != 0 or not 回执.stdout.strip():
        return None
    return Path(回执.stdout.strip())


def 读复用记录(仓根: Path):
    """读本树复用记录 ⇒ 字典（`树指纹` / `全过` / `读数行表`）或 `None`（缺件 / 坏件一律 `None`）。"""
    记录路径 = 复用记录路径(仓根)
    if 记录路径 is None or not 记录路径.is_file():
        return None
    try:
        读取结果 = 记录路径.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        读到的记录 = json.loads(读取结果)
    except ValueError:
        return None
    return 读到的记录 if isinstance(读到的记录, dict) else None


def 写复用记录(仓根: Path, 树指纹: str, 读数行表: list) -> bool:
    """把「树指纹 → 本次读数」落盘 ⇒ 真假。**写不进就静默不复用**（绝不因它拦活）。"""
    记录路径 = 复用记录路径(仓根)
    if 记录路径 is None:
        return False
    写入内容 = json.dumps({"树指纹": 树指纹, "全过": True, "读数行表": list(读数行表)},
                        ensure_ascii=False, indent=2)
    try:
        记录路径.write_text(写入内容, encoding="utf-8")
    except OSError:
        return False
    return True


def 复用命中(复用记录, 树指纹: str) -> bool:
    """这份记录能不能给当前这棵树复用 ⇒ 真假。**只认指纹逐字相等、且记录是全过的**。"""
    if not isinstance(复用记录, dict):
        return False
    return 复用记录.get("树指纹") == 树指纹 and 复用记录.get("全过") is True


def 跑闸0或复用(仓根: Path, 硬顶毫秒: int, 外层起表秒: float, 跑两条闸) -> tuple:
    """同一棵树同一份内容只跑一遍 ⇒ `(是否全过, 明细表)`（签名与 `跑两条闸` 一致）。

    指纹命中 ⇒ **回放上次读数**（逐行原样打印，下游解析器照旧吃得下），不重跑；
    否则真跑，跑完**只在全过时**落记录。跑法由调用方以 `跑两条闸` 传入（避免与调度器互相 import）。
    """
    import contextlib
    import io

    新指纹 = 算树指纹(仓根)
    旧记录 = 读复用记录(仓根)
    if 复用命中(旧记录, 新指纹):
        print("闸 0：同一棵树、同一份内容 ⇒ 复用上次读数（树指纹 %s），不重跑" % 新指纹)
        for 文本行 in 旧记录.get("读数行表") or []:
            print(文本行)
        return True, []
    缓冲 = io.StringIO()
    with contextlib.redirect_stdout(缓冲):
        全过, 明细 = 跑两条闸(仓根, 硬顶毫秒, 外层起表秒)
    print(缓冲.getvalue(), end="")
    if 全过:
        写复用记录(仓根, 新指纹, 缓冲.getvalue().splitlines())
    return 全过, 明细


def 自检_闸0复用() -> list:
    """闸 0 复用口径的身份证（挂 `一键验证.py --自测` 的机制用例）：正 + 反四问。

    反样本是**承重的那一条**：内容一变，指纹必变 ⇒ 必须重跑（不能因复用把该跑的省掉）。
    """
    import tempfile

    with tempfile.TemporaryDirectory(prefix="闸0复用样本-") as 临时目录:
        探针根 = Path(临时目录)
        (探针根 / "样本件.py").write_text("内容一\n", encoding="utf-8")
        指纹前 = 算树指纹(探针根)
        (探针根 / "样本件.py").write_text("内容二\n", encoding="utf-8")
        指纹后 = 算树指纹(探针根)
        (探针根 / "新件.py").write_text("内容三\n", encoding="utf-8")
        指纹增件 = 算树指纹(探针根)
        指纹复算 = 算树指纹(探针根)

    好记录 = {"树指纹": 指纹增件, "全过": True, "读数行表": ["闸 0：两条闸都过（退出码 0）"]}
    红记录 = {"树指纹": 指纹增件, "全过": False, "读数行表": []}
    return [
        ("闸0 复用：同一份内容两次算出的树指纹逐字相等",
         指纹增件 == 指纹复算, "增件后 %s · 复算 %s" % (指纹增件, 指纹复算)),
        ("闸0 复用：改一个扫描面件的字节 ⇒ 指纹必变（必重跑）",
         指纹前 != 指纹后, "改前 %s · 改后 %s" % (指纹前, 指纹后)),
        ("闸0 复用：新增一个件 ⇒ 指纹必变（必重跑）",
         指纹后 != 指纹增件, "改后 %s · 增件 %s" % (指纹后, 指纹增件)),
        ("闸0 复用：指纹一致且记录全过 ⇒ 命中复用",
         复用命中(好记录, 指纹增件) is True, "%r" % (复用命中(好记录, 指纹增件),)),
        ("闸0 复用：指纹不一致 / 记录不是全过 ⇒ 不命中（必重跑）",
         复用命中(好记录, 指纹前) is False and 复用命中(红记录, 指纹增件) is False,
         "%r · %r" % (复用命中(好记录, 指纹前), 复用命中(红记录, 指纹增件))),
    ]
