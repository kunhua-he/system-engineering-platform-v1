# -*- coding: utf-8 -*-
"""运行数据根 · 一致性判据 —— Python 镜像与 Rust 那份**逐项一致**（判据的身份证）。

只读**源文本**抽口径，故判据能对**任意一份副本**跑 —— `--反向样本` 靠这一点：逐项改坏一份
副本，验证判据**都抓得住**（改一处 ⇒ 必红）。依据：
`项目文档/决策记录/2026-09-27_运行数据根.md` §二/§三 · `判据的可信性.md` §三.5。

被比对的 Python 源是**本包的口径件**（`口径.py` —— 常量与解析都在那里），不是本件。
"""

import re
from pathlib import Path

本件路径 = Path(__file__).resolve()
仓根 = 本件路径.parents[2]
# 真源 = Rust crate 的两件（判据的对比基准）；镜像侧 = 本包的 `口径.py`（见 `镜像源`）。
真源解析路径 = 仓根 / "运行内核" / "运行数据根" / "src" / "解析.rs"
真源子目录路径 = 仓根 / "运行内核" / "运行数据根" / "src" / "子目录.rs"
镜像源 = 本件路径.parent / "口径.py"

七项口径字段名 = ("默认目录名", "覆盖变量名", "四类子目录名", "苹果基片段", "利努克斯退回片段",
        "XDG变量名", "应用数据变量名")


def 抽真源口径(解析文: str, 子目录文: str) -> dict:
    """从 Rust 源文本抽出「与 Python 对齐」的七项口径字段名表。缺项 ⇒ `None`（判据当场报缺）。"""
    默认目录名 = re.search(r'pub const 默认目录名:\s*&str\s*=\s*"([^"]+)"', 解析文)
    覆盖变量名 = re.search(r'pub const 覆盖变量名:\s*&str\s*=\s*"([^"]+)"', 解析文)
    macOS = re.search(r'\.join\("(Library)"\)\.join\("(Application Support)"\)', 解析文)
    Linux = re.search(r'\.join\("(\.local)"\)\.join\("(share)"\)', 解析文)
    XDG = re.search(r'env::var\("(XDG_DATA_HOME)"\)', 解析文)
    APPDATA = re.search(r'env::var\("(APPDATA)"\)', 解析文)
    子目录名表 = re.findall(r'Self::[^\s=]+ => "([^"]+)"', 子目录文)
    return {
        "默认目录名": 默认目录名.group(1) if 默认目录名 else None,
        "覆盖变量名": 覆盖变量名.group(1) if 覆盖变量名 else None,
        "四类子目录名": tuple(子目录名表) if 子目录名表 else None,
        "苹果基片段": (macOS.group(1), macOS.group(2)) if macOS else None,
        "利努克斯退回片段": (Linux.group(1), Linux.group(2)) if Linux else None,
        "XDG变量名": XDG.group(1) if XDG else None,
        "应用数据变量名": APPDATA.group(1) if APPDATA else None,
    }


def 抽镜像口径(文本: str) -> dict:
    """从 Python 源文本抽出同一组口径（值本身就是实现用的常量，故改实现即改这里）。"""
    def 取字符串(名称):
        命中 = re.search(r'^%s\s*=\s*"([^"]+)"' % re.escape(名称), 文本, re.M)
        return 命中.group(1) if 命中 else None

    def 取元组常量(名称):
        命中 = re.search(r'^%s\s*=\s*\(([^)]*)\)' % re.escape(名称), 文本, re.M)
        if not 命中:
            return None
        return tuple(号段.strip().strip('"') for 号段 in 命中.group(1).split(",") if 号段.strip())

    return {
        "默认目录名": 取字符串("默认目录名"),
        "覆盖变量名": 取字符串("覆盖变量名"),
        "四类子目录名": 取元组常量("子目录名"),
        "苹果基片段": 取元组常量("苹果基片段"),
        "利努克斯退回片段": 取元组常量("利努克斯退回片段"),
        "XDG变量名": 取字符串("XDG变量名"),
        "应用数据变量名": 取字符串("应用数据变量名"),
    }


def 比对口径(解析路: Path, 子目录路: Path, python路: Path) -> list:
    """逐项比对 ⇒ 不一致项清单（空 = 一致）。"""
    真源口径 = 抽真源口径(解析路.read_text(encoding="utf-8"), 子目录路.read_text(encoding="utf-8"))
    镜像口径 = 抽镜像口径(python路.read_text(encoding="utf-8"))
    输出缓冲 = []
    for 口径字段名 in 七项口径字段名:
        if 真源口径[口径字段名] is None:
            输出缓冲.append("%s：Rust 源里抽不到（Rust 那边改了？）" % 口径字段名)
        elif 镜像口径[口径字段名] is None:
            输出缓冲.append("%s：Python 源里抽不到" % 口径字段名)
        elif tuple(真源口径[口径字段名] if isinstance(真源口径[口径字段名], tuple) else (真源口径[口径字段名],)) != tuple(
            镜像口径[口径字段名] if isinstance(镜像口径[口径字段名], tuple) else (镜像口径[口径字段名],)
        ):
            输出缓冲.append("%s：Rust=%r ≠ Python=%r" % (口径字段名, 真源口径[口径字段名], 镜像口径[口径字段名]))
    return 输出缓冲


def 改坏口径项(文本: str, 口径字段名: str, 假值) -> str:
    """把 Python 源文本里某一项改成假值（反向样本用）。"""
    元组项 = ("四类子目录名", "苹果基片段", "利努克斯退回片段")
    变量 = "子目录名" if 口径字段名 == "四类子目录名" else 口径字段名
    if 口径字段名 in 元组项:
        待处理值 = "(%s)" % ", ".join('"%s"' % 号段 for 号段 in 假值)
    else:
        待处理值 = '"%s"' % 假值
    return re.sub(r"^%s\s*=\s*.*$" % re.escape(变量), "%s = %s" % (变量, 待处理值), 文本, count=1, flags=re.M)


假值表 = {
    "默认目录名": "系统工程平台V1-坏",
    "覆盖变量名": "V1_RUN_DATA_ROOT_坏",
    "四类子目录名": ("数据库", "缓存", "日志", "临时件坏"),
    "苹果基片段": ("Library", "Application Support坏"),
    "利努克斯退回片段": (".local", "share坏"),
    "XDG变量名": "XDG_DATA_HOME_坏",
    "应用数据变量名": "APPDATA_坏",
}


def 跑反向样本(临时样本根: Path) -> int:
    """逐项改坏一份副本 ⇒ 每一项都必须被判红；有一项漏 ⇒ 退出码 1。"""
    原文 = 镜像源.read_text(encoding="utf-8")
    漏判项表 = []
    for 口径字段名, 待处理值 in 假值表.items():
        路径 = 临时样本根 / "坏.py"
        路径.write_text(改坏口径项(原文, 口径字段名, 待处理值), encoding="utf-8")
        if not 比对口径(真源解析路径, 真源子目录路径, 路径):
            漏判项表.append(口径字段名)
    if 漏判项表:
        print("反向样本失败：改坏这些项却没判红 ⇒ %s" % " · ".join(漏判项表))
        return 1
    print("反向样本通过：%d 项逐项改坏 ⇒ 判据每次都判红" % len(假值表))
    return 0


def 跑一遍(解析路: Path, 子目录路: Path, python路: Path) -> int:
    """正向检查：逐项比对 ⇒ 一致退 0，不一致逐条报出退 1。"""
    输出缓冲 = 比对口径(解析路, 子目录路, python路)
    if 输出缓冲:
        print("一致性判据失败（%d 项不一致）：" % len(输出缓冲))
        for 缓冲行 in 输出缓冲:
            print("  ✗ " + 缓冲行)
        return 1
    print("一致性判据通过：Python 镜像与 Rust 那份逐项一致（%s）" % python路)
    return 0
