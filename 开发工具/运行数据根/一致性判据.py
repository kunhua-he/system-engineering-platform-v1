# -*- coding: utf-8 -*-
"""运行数据根 · 一致性判据 —— Python 镜像与 Rust 那份**逐项一致**（判据的身份证）。

只读**源文本**抽口径，故判据能对**任意一份副本**跑 —— `--反向样本` 靠这一点：逐项改坏一份
副本，验证判据**都抓得住**（改一处 ⇒ 必红）。依据：
`项目文档/决策记录/2026-09-27_运行数据根.md` §二/§三 · `判据的可信性.md` §三.5。

被比对的 Python 源是**本包的口径件**（`口径.py` —— 常量与解析都在那里），不是本件。
"""

import re
from pathlib import Path

本件 = Path(__file__).resolve()
仓根 = 本件.parents[2]
Rust解析 = 仓根 / "运行内核" / "运行数据根" / "src" / "解析.rs"
Rust子目录 = 仓根 / "运行内核" / "运行数据根" / "src" / "子目录.rs"
镜像源 = 本件.parent / "口径.py"

七项 = ("默认目录名", "覆盖变量名", "四类子目录名", "macOS基片段", "Linux退回片段",
        "XDG变量名", "应用数据变量名")


def 抽Rust(解析文: str, 子目录文: str) -> dict:
    """从 Rust 源文本抽出「与 Python 对齐」的七项口径。缺项 ⇒ `None`（判据当场报缺）。"""
    默认目录名 = re.search(r'pub const 默认目录名:\s*&str\s*=\s*"([^"]+)"', 解析文)
    覆盖变量名 = re.search(r'pub const 覆盖变量名:\s*&str\s*=\s*"([^"]+)"', 解析文)
    macOS = re.search(r'\.join\("(Library)"\)\.join\("(Application Support)"\)', 解析文)
    Linux = re.search(r'\.join\("(\.local)"\)\.join\("(share)"\)', 解析文)
    XDG = re.search(r'env::var\("(XDG_DATA_HOME)"\)', 解析文)
    APPDATA = re.search(r'env::var\("(APPDATA)"\)', 解析文)
    子 = re.findall(r'Self::[^\s=]+ => "([^"]+)"', 子目录文)
    return {
        "默认目录名": 默认目录名.group(1) if 默认目录名 else None,
        "覆盖变量名": 覆盖变量名.group(1) if 覆盖变量名 else None,
        "四类子目录名": tuple(子) if 子 else None,
        "macOS基片段": (macOS.group(1), macOS.group(2)) if macOS else None,
        "Linux退回片段": (Linux.group(1), Linux.group(2)) if Linux else None,
        "XDG变量名": XDG.group(1) if XDG else None,
        "应用数据变量名": APPDATA.group(1) if APPDATA else None,
    }


def 抽Python(文: str) -> dict:
    """从 Python 源文本抽出同一组口径（值本身就是实现用的常量，故改实现即改这里）。"""
    def 串(名):
        命中 = re.search(r'^%s\s*=\s*"([^"]+)"' % re.escape(名), 文, re.M)
        return 命中.group(1) if 命中 else None

    def 元组(名):
        命中 = re.search(r'^%s\s*=\s*\(([^)]*)\)' % re.escape(名), 文, re.M)
        if not 命中:
            return None
        return tuple(段.strip().strip('"') for 段 in 命中.group(1).split(",") if 段.strip())

    return {
        "默认目录名": 串("默认目录名"),
        "覆盖变量名": 串("覆盖变量名"),
        "四类子目录名": 元组("子目录名"),
        "macOS基片段": 元组("macOS基片段"),
        "Linux退回片段": 元组("Linux退回片段"),
        "XDG变量名": 串("XDG变量名"),
        "应用数据变量名": 串("应用数据变量名"),
    }


def 比对(解析路: Path, 子目录路: Path, python路: Path) -> list:
    """逐项比对 ⇒ 不一致项清单（空 = 一致）。"""
    真 = 抽Rust(解析路.read_text(encoding="utf-8"), 子目录路.read_text(encoding="utf-8"))
    镜 = 抽Python(python路.read_text(encoding="utf-8"))
    出 = []
    for 项 in 七项:
        if 真[项] is None:
            出.append("%s：Rust 源里抽不到（Rust 那边改了？）" % 项)
        elif 镜[项] is None:
            出.append("%s：Python 源里抽不到" % 项)
        elif tuple(真[项] if isinstance(真[项], tuple) else (真[项],)) != tuple(
            镜[项] if isinstance(镜[项], tuple) else (镜[项],)
        ):
            出.append("%s：Rust=%r ≠ Python=%r" % (项, 真[项], 镜[项]))
    return 出


def 改坏(文: str, 项: str, 假值) -> str:
    """把 Python 源文本里某一项改成假值（反向样本用）。"""
    元 = ("四类子目录名", "macOS基片段", "Linux退回片段")
    变量 = "子目录名" if 项 == "四类子目录名" else 项
    if 项 in 元:
        值 = "(%s)" % ", ".join('"%s"' % 段 for 段 in 假值)
    else:
        值 = '"%s"' % 假值
    return re.sub(r"^%s\s*=\s*.*$" % re.escape(变量), "%s = %s" % (变量, 值), 文, count=1, flags=re.M)


假值表 = {
    "默认目录名": "系统工程平台V1-坏",
    "覆盖变量名": "V1_RUN_DATA_ROOT_坏",
    "四类子目录名": ("数据库", "缓存", "日志", "临时件坏"),
    "macOS基片段": ("Library", "Application Support坏"),
    "Linux退回片段": (".local", "share坏"),
    "XDG变量名": "XDG_DATA_HOME_坏",
    "应用数据变量名": "APPDATA_坏",
}


def 反向样本(临时根: Path) -> int:
    """逐项改坏一份副本 ⇒ 每一项都必须被判红；有一项漏 ⇒ 退出码 1。"""
    原文 = 镜像源.read_text(encoding="utf-8")
    漏 = []
    for 项, 值 in 假值表.items():
        路 = 临时根 / "坏.py"
        路.write_text(改坏(原文, 项, 值), encoding="utf-8")
        if not 比对(Rust解析, Rust子目录, 路):
            漏.append(项)
    if 漏:
        print("反向样本失败：改坏这些项却没判红 ⇒ %s" % " · ".join(漏))
        return 1
    print("反向样本通过：%d 项逐项改坏 ⇒ 判据每次都判红" % len(假值表))
    return 0


def 跑(解析路: Path, 子目录路: Path, python路: Path) -> int:
    """正向检查：逐项比对 ⇒ 一致退 0，不一致逐条报出退 1。"""
    出 = 比对(解析路, 子目录路, python路)
    if 出:
        print("一致性判据失败（%d 项不一致）：" % len(出))
        for 条 in 出:
            print("  ✗ " + 条)
        return 1
    print("一致性判据通过：Python 镜像与 Rust 那份逐项一致（%s）" % python路)
    return 0
