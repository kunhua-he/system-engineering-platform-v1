# -*- coding: utf-8 -*-
"""同源自检核心 —— 模板与真实扩展的必备件同源比对（不复制第二套判定）。

本件是**库件**（无主入口）：入口在同目录外的 `../同源自检.py`（薄壳，只转调 `入口函数`）。

口径：拿三套模板（支持库 / 组合模块 / 技能）与 `扩展根目录/` 下的真实扩展，
逐个按 `必备件.json` 的「哪几种要哪几件」比对 ⇒ 缺件即红。两端读同一份清单，
本件不另立一份「哪些件必需」。

用法（只看模板）：

    python 扩展装载/开发标准/同源自检.py

用法（连真实扩展一起看）：

    python 扩展装载/开发标准/同源自检.py 扩展根目录/原子支持库/示例扩展

零第三方依赖。退出码：0 = 全齐；1 = 有缺件；2 = 判不了（清单读不到 / 目录不在三类里）。
"""
from __future__ import annotations

import sys
from pathlib import Path

本件目录 = Path(__file__).resolve().parent
if str(本件目录) not in sys.path:
    sys.path.insert(0, str(本件目录))

from 必备件 import 仓根, 开发标准根, 取必备件表, 取种类表, 读必备件  # noqa: E402

模板目录名 = "模板"
# 模板子目录名：模板目录里那三个子目录的实际名。
# `模块` 是禁用泛名（判据 59）⇒ 它的模板子目录改叫 `组合模块`；其余同名。
模板子目录名 = {"支持库": "支持库", "模块": "组合模块", "技能": "技能"}


def 认种类(路径: Path, 种类表: list, 仓根: Path):
    """这个路径属三类里的哪一种 ⇒ 种类名 或 None。

    先按**默认目录**认（真实扩展住在 `扩展根目录/<层>/<扩展名>/`，扩展名不等于种类名）；
    认不出再按目录名认（模板目录名就是种类名）。
    """
    try:
        相对 = str(Path(路径).resolve().relative_to(仓根))
    except ValueError:
        相对 = ""
    for 种类名, 默认目录 in 种类表:
        if 相对 == 默认目录 or 相对.startswith(默认目录 + "/"):
            return 种类名
    for 种类名, 默认目录 in 种类表:
        if Path(路径).name == 种类名 or Path(路径).name == 模板子目录名.get(种类名):
            return 种类名
    return None


def 扫件名(件目录: Path):
    """⇒ 该目录下的相对件路径集（含子目录里的件；不带目录 ⇒ 空集）。"""
    件名集 = set()
    if not 件目录.is_dir():
        return 件名集
    for 件路径 in 件目录.rglob("*"):
        if 件路径.is_file():
            件名集.add(str(件路径.relative_to(件目录)).replace("\\", "/"))
    return 件名集


def 命中(要求件: str, 件名集: set) -> bool:
    """这件在不在件名集里 —— 支持 `<名>/` 前缀形、`<占位>` 通配形、`src/ + Cargo.toml` 双件形。"""
    if 要求件 == "src/ + Cargo.toml":
        return "Cargo.toml" in 件名集 and any(件名.startswith("src/") for 件名 in 件名集)
    规范 = 要求件
    while "<" in 规范 and ">" in 规范:
        开位 = 规范.index("<")
        闭位 = 规范.index(">", 开位)
        规范 = 规范[:开位] + "*" + 规范[闭位 + 1:]
    if 规范.endswith("/"):
        前缀段 = 规范[:-1]
        return any(件名 == 前缀段 or 件名.startswith(前缀段 + "/") for 件名 in 件名集)
    if "*" in 规范:
        目录段, _, 尾段 = 规范.partition("*")
        目录段 = 目录段.rstrip("/")
        return any(件名.startswith(目录段 + "/") and 件名.endswith(尾段) for 件名 in 件名集)
    return 规范 in 件名集


def 比对目录(件目录: Path, 种类名: str, 必备件表: list):
    """⇒ (缺件名表, 读数文本)。"""
    件名集 = 扫件名(件目录)
    缺件名 = []
    for 必备件条 in 必备件表:
        要求件 = 必备件条.get("文件")
        if not 要求件 or not 必备件条.get(种类名):
            continue
        if not 命中(要求件, 件名集):
            缺件名.append(要求件)
    读数 = f"{件目录.name}（{种类名}）：{len(件名集)} 件 · " + (
        "齐备" if not 缺件名 else "缺 " + " / ".join(缺件名))
    return 缺件名, 读数


def 出报告(目标表: list, 必备件表: list):
    """⇒ (退出码, 正文行表)。"""
    正文行 = ["同源自检：模板与真实扩展按同一份必备件清单比对（扩展装载/开发标准/必备件.json）"]
    失败 = 0
    for 件目录, 种类名 in 目标表:
        缺件名, 读数 = 比对目录(件目录, 种类名, 必备件表)
        正文行.append(("✗ " if 缺件名 else "✓ ") + 读数)
        if 缺件名:
            失败 += 1
    return (1 if 失败 else 0), 正文行


def 入口函数(参数表: list) -> int:
    必备件清单, 错误 = 读必备件()
    if 错误:
        print("判不了：" + 错误)
        return 2
    种类表 = 取种类表(必备件清单)
    必备件表 = 取必备件表(必备件清单)
    if 参数表:
        目标表 = []
        for 路径文本 in 参数表:
            种类名 = 认种类(Path(路径文本), 种类表, 仓根)
            if 种类名 is None:
                print(f"判不了：{路径文本} 不在三类（支持库 / 组合模块 / 技能）里")
                return 2
            目标表.append((Path(路径文本), 种类名))
    else:
        目标表 = []
        模板根 = 开发标准根 / 模板目录名
        for 种类名, 默认目录 in 种类表:
            子目录 = 模板根 / 模板子目录名.get(种类名, 种类名)
            if 子目录.is_dir():
                目标表.append((子目录, 种类名))
    退出码, 正文行 = 出报告(目标表, 必备件表)
    for 行项 in 正文行:
        print(行项)
    return 退出码
