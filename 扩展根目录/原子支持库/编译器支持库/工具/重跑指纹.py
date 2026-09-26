#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重跑指纹 —— 刷新 `指纹.json`（本扩展的声明文件 + 实现文件的 sha256 快照）。

**为什么要有这一件**：`指纹.json` 原先的「生成命令」只写了一句散文
（「python（只读遍历本目录…）」）—— **不是一条可跑的命令**，所以它一漂就没人能刷新，
指纹形同虚设（台账 #31 / #157）。本脚本就是那条可跑的命令；重跑即刷新。

    python3 扩展根目录/原子支持库/编译器支持库/工具/重跑指纹.py           # 刷新 指纹.json
    python3 扩展根目录/原子支持库/编译器支持库/工具/重跑指纹.py --检查    # 只比对，不改盘（漂了即退出码 1）

**范围（与旧件逐字一致，本脚本不扩不缩）**：
  声明文件：`包声明.json` · `能力声明/*.json` · `错误码表/*.json` · `类型声明/*.json`
  实现文件：`Cargo.toml` · `src/**/*.rs`
  不含：`说明/`（散文）· `语料/`（取证语料）· `工具/`（本脚本自己）· `实现/` 与 `能力契约/`（空目录）
        · `编译器支持库.dylib`（构建产物，落源码树是待处置项，见台账 #209）· `Cargo.lock`

**判据**：`--检查` 把当前盘面重算一遍，与 `指纹.json` 的 `指纹` 表逐键比；
  多键 / 少键 / 值不同 ⇒ 报出并退出码 1（**fail-closed**：不静默）。`生成时刻` / `生成命令` 不参与比对。
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timezone, timedelta

# 本脚本自己所在目录 = <扩展根>/工具/；扩展根 = 上一级。
扩展根 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
指纹件 = os.path.join(扩展根, "指纹.json")

# 生成命令（写进 指纹.json 的那条，必须**可跑**：从仓库根执行）。
生成命令 = "python3 扩展根目录/原子支持库/编译器支持库/工具/重跑指纹.py"

说明 = (
    "生成物指纹 —— 每个**声明文件**（包声明.json · 能力声明/*.json · 错误码表/*.json · 类型声明/*.json）"
    "与**实现文件**（src/**/*.rs · Cargo.toml）的 sha256。供底座侧判「载入的是不是被改过的东西」"
    "——旁路校验：缺了不影响载入，但可追溯性没有落点。"
)
范围 = (
    "只含声明文件与实现文件；不含 说明/（散文）· 语料/（取证语料）· 工具/（生成脚本自己）· "
    "实现/ 与 能力契约/（空目录）· 编译器支持库.dylib（构建产物）。"
)
缺口 = (
    "本件是**快照**。任何声明文件或实现文件被改，这里就对不上——不符即「载入的东西被改过」，"
    "正是本件要报的；重跑生成命令即可刷新（`--检查` 只比对不改盘）。"
)


def 相对路径(路径):
    return os.path.relpath(路径, 扩展根).replace(os.sep, "/")


def 收集():
    """按固定范围收集要指纹的文件（返回相对路径列表，已排序）。"""
    文件 = []
    顶层声明 = ("包声明.json",)
    for 名 in 顶层声明:
        路 = os.path.join(扩展根, 名)
        if os.path.isfile(路):
            文件.append(路)
    实现 = os.path.join(扩展根, "Cargo.toml")
    if os.path.isfile(实现):
        文件.append(实现)
    for 目录 in ("能力声明", "错误码表", "类型声明"):
        根 = os.path.join(扩展根, 目录)
        if os.path.isdir(根):
            for 名 in sorted(os.listdir(根)):
                if 名.endswith(".json"):
                    文件.append(os.path.join(根, 名))
    src = os.path.join(扩展根, "src")
    for 当前, _子目录s, 名s in os.walk(src):
        for 名 in 名s:
            if 名.endswith(".rs"):
                文件.append(os.path.join(当前, 名))
    return sorted(相对路径(路) for 路 in 文件)


def sha256(路):
    摘要 = hashlib.sha256()
    with open(路, "rb") as 句柄:
        for 块 in iter(lambda: 句柄.read(1 << 20), b""):
            摘要.update(块)
    return 摘要.hexdigest()


def 算表():
    return {相: sha256(os.path.join(扩展根, 相)) for 相 in 收集()}


def 读旧表():
    if not os.path.isfile(指纹件):
        return None
    with open(指纹件, "r", encoding="utf-8") as 句柄:
        return json.load(句柄).get("指纹", {})


def 刷新():
    表 = 算表()
    时刻 = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S %z")
    件 = {
        "说明": 说明,
        "算法": "sha256",
        "生成时刻": 时刻,
        "生成命令": 生成命令,
        "范围": 范围,
        "缺口": 缺口,
        "指纹": 表,
    }
    with open(指纹件, "w", encoding="utf-8") as 句柄:
        json.dump(件, 句柄, ensure_ascii=False, indent=2)
        句柄.write("\n")
    print("已刷新 %s" % 相对路径(指纹件))
    print("生成时刻 %s · 文件 %d 个" % (时刻, len(表)))
    return 0


def 检查():
    新 = 算表()
    旧 = 读旧表()
    if 旧 is None:
        print("✗ 读不到 %s" % 相对路径(指纹件))
        return 1
    漂 = []
    for 相 in sorted(set(新) | set(旧)):
        if 相 not in 旧:
            漂.append("  新增未入指纹：%s" % 相)
        elif 相 not in 新:
            漂.append("  指纹里有、盘上没有：%s" % 相)
        elif 新[相] != 旧[相]:
            漂.append("  内容不符：%s（记录 %s / 实际 %s）" % (相, 旧[相][:8], 新[相][:8]))
    if 漂:
        print("✗ 指纹与盘面不符（%d 处）—— 重跑生成命令即可刷新：" % len(漂))
        for 行 in 漂:
            print(行)
        return 1
    print("✓ 指纹与盘面逐键一致（%d 个文件）" % len(新))
    return 0


def main():
    检查档 = "--检查" in sys.argv[1:]
    return 检查() if 检查档 else 刷新()


if __name__ == "__main__":
    sys.exit(main())
