# -*- coding: utf-8 -*-
"""运行数据根 —— **Python 侧的唯一入口**（Rust 那份的镜像）。

**唯一解析器是 Rust crate `运行内核/运行数据根/`（`v1-dataroot`）**；本件是它在 Python 侧的
**镜像**，不是第二套规则。逐条对齐 `运行内核/运行数据根/src/解析.rs` 与 `子目录.rs`：

  · 覆盖：环境变量 `V1_RUN_DATA_ROOT`（**ASCII** 名），非空即**原样**用它（覆盖是完整根，
    不再拼 `默认目录名`）；
  · 默认：平台数据目录 + `默认目录名`（macOS `~/Library/Application Support` ·
    Linux `$XDG_DATA_HOME` 未设退回 `~/.local/share` · Windows `%APPDATA%`）；
  · 全缺 ⇒ **结构化失败（`无位置`），不编路径**；
  · 四类子目录：`数据库` · `缓存` · `日志` · `临时件`（封闭枚举的 Python 形态）。

**一致性判据**：本件带 `--检查`，逐项比对上面这些口径与 Rust 源码（默认目录名 · 覆盖变量名 ·
四类子目录名 · 三个平台基）；不一致 ⇒ 退出码非 0。`--反向样本` 逐项改坏一份副本，验证判据
**都抓得住**（改一处 ⇒ 必红）。依据：`项目文档/决策记录/2026-09-27_运行数据根.md` §二/§三。

**本件是叶子**：只 import 标准库。调用方（`构建装配/演示/常量.py` ·
`构建装配/上线切换/上线切换/常量.py` · `开发工具/认领机制/认领机制/账本.py`）**只引本件，
不许自己拼路径**（自己拼 = 第二个来源）。
"""

import os
import re
import sys
from pathlib import Path

# ── 与 Rust 逐项对齐的口径（下面每个常量都对应 `解析.rs` / `子目录.rs` 的一处）──────────────
# 覆盖变量名必须 **ASCII**（macOS 的 `/bin/sh` 是 bash 3.2，不认中文变量名；同 解析.rs 的理由）。
覆盖变量名 = "V1_RUN_DATA_ROOT"
默认目录名 = "系统工程平台V1"
子目录名 = ("数据库", "缓存", "日志", "临时件")
# 三个平台基（与 解析.rs::默认基 逐条对应）。
macOS基片段 = ("Library", "Application Support")
Linux退回片段 = (".local", "share")
XDG变量名 = "XDG_DATA_HOME"
应用数据变量名 = "APPDATA"
家目录变量名 = "HOME"


class 无位置(Exception):
    """既没有覆盖、也推不出默认位置（家目录 / XDG / APPDATA 全缺）—— 结构化失败，不编路径。"""


def 当前平台() -> str:
    """编译期不可知（本件是脚本）⇒ 运行期判一次；只用来选默认基，不参与任何语义。"""
    if sys.platform == "darwin":
        return "macos"
    if os.name == "nt":
        return "windows"
    return "linux"


def 默认基(家目录, xdg数据目录, 应用数据目录, 平台: str):
    """平台数据目录（**不含** `默认目录名` 那一层）。三条规则互不重叠，无一条落在当前目录。"""
    if 平台 == "macos":
        if 家目录:
            return Path(家目录).joinpath(*macOS基片段)
        return None
    if 平台 == "windows":
        if 应用数据目录:
            return Path(应用数据目录)
        return None
    if xdg数据目录:
        return Path(xdg数据目录)
    if 家目录:
        return Path(家目录).joinpath(*Linux退回片段)
    return None


def 解析(覆盖, 家目录, xdg数据目录, 应用数据目录, 平台: str) -> Path:
    """**唯一解析口**：`覆盖 > 平台默认`。外部事实全部注入（不从全局读），故每条分支都判得了。"""
    if 覆盖:
        return Path(覆盖)
    基 = 默认基(家目录, xdg数据目录, 应用数据目录, 平台)
    if 基 is None:
        raise 无位置(
            "运行数据根解析不出：既没有 %s，也推不出平台默认位置"
            "（家目录 / XDG_DATA_HOME / APPDATA 全缺）" % 覆盖变量名
        )
    return 基 / 默认目录名


def 解析当前() -> Path:
    """读真实环境那一层薄壳：只读四个环境变量 + 判平台，零判断。"""
    return 解析(
        os.environ.get(覆盖变量名),
        os.environ.get(家目录变量名),
        os.environ.get(XDG变量名),
        os.environ.get(应用数据变量名),
        当前平台(),
    )


def 子目录路径(根: Path, 类: str) -> Path:
    """某一类子目录的路径。**只拼路径，不建目录**；`类` 必须是四类之一（封闭枚举）。"""
    if 类 not in 子目录名:
        raise ValueError("不是四类运行数据子目录之一：%r（只许 %s）" % (类, " · ".join(子目录名)))
    return Path(根) / 类


def 确保子目录(根: Path, 类: str) -> Path:
    """建出某一类子目录并交出路径（父目录一并建）。"""
    路 = 子目录路径(根, 类)
    路.mkdir(parents=True, exist_ok=True)
    return 路


# ── 一致性判据：本件（Python 镜像）与 Rust 那份逐项一致 ──────────────────────────────────
# 只读源文本抽口径，故判据能对**任意一份副本**跑（反向样本靠它）。
仓根 = Path(__file__).resolve().parents[1]
Rust解析 = 仓根 / "运行内核" / "运行数据根" / "src" / "解析.rs"
Rust子目录 = 仓根 / "运行内核" / "运行数据根" / "src" / "子目录.rs"
本件 = Path(__file__).resolve()

_抽 = lambda 文, 式, 旗=0: re.search(式, 文, 旗)


def 抽Rust(解析文: str, 子目录文: str) -> dict:
    """从 Rust 源文本抽出「与 Python 对齐」的七项口径。缺项 ⇒ `None`（判据当场报缺）。"""
    默认目录名 = _抽(解析文, r'pub const 默认目录名:\s*&str\s*=\s*"([^"]+)"')
    覆盖变量名 = _抽(解析文, r'pub const 覆盖变量名:\s*&str\s*=\s*"([^"]+)"')
    macOS = _抽(解析文, r'\.join\("(Library)"\)\.join\("(Application Support)"\)')
    Linux = _抽(解析文, r'\.join\("(\.local)"\)\.join\("(share)"\)')
    XDG = _抽(解析文, r'env::var\("(XDG_DATA_HOME)"\)')
    APPDATA = _抽(解析文, r'env::var\("(APPDATA)"\)')
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
        m = _抽(文, r'^%s\s*=\s*"([^"]+)"' % re.escape(名), re.M)
        return m.group(1) if m else None

    def 元组(名):
        m = _抽(文, r'^%s\s*=\s*\(([^)]*)\)' % re.escape(名), re.M)
        if not m:
            return None
        return tuple(x.strip().strip('"') for x in m.group(1).split(",") if x.strip())

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
    for 项 in ("默认目录名", "覆盖变量名", "四类子目录名", "macOS基片段", "Linux退回片段",
              "XDG变量名", "应用数据变量名"):
        if 真[项] is None:
            出.append("%s：Rust 源里抽不到（Rust 那边改了？）" % 项)
        elif 镜[项] is None:
            出.append("%s：Python 源里抽不到" % 项)
        elif tuple(真[项] if isinstance(真[项], tuple) else (真[项],)) != tuple(
            镜[项] if isinstance(镜[项], tuple) else (镜[项],)
        ):
            出.append("%s：Rust=%r ≠ Python=%r" % (项, 真[项], 镜[项]))
    return 出


def _改坏(文: str, 项: str, 假值) -> str:
    """把 Python 源文本里某一项改成假值（反向样本用）。"""
    元 = ("四类子目录名", "macOS基片段", "Linux退回片段")
    变量 = "子目录名" if 项 == "四类子目录名" else 项
    if 项 in 元:
        值 = "(%s)" % ", ".join('"%s"' % x for x in 假值)
    else:
        值 = '"%s"' % 假值
    return re.sub(r"^%s\s*=\s*.*$" % re.escape(变量), "%s = %s" % (变量, 值), 文, count=1, flags=re.M)


def _入口() -> int:
    import tempfile
    解析路, 子目录路, py = Rust解析, Rust子目录, 本件
    参 = sys.argv[1:]
    if "--python" in 参:
        py = Path(参[参.index("--python") + 1])
    if "--rust" in 参:
        解析路 = Path(参[参.index("--rust") + 1])
    if "--rust子目录" in 参:
        子目录路 = Path(参[参.index("--rust子目录") + 1])

    if "--反向样本" in 参:
        假 = {
            "默认目录名": "系统工程平台V1-坏",
            "覆盖变量名": "V1_RUN_DATA_ROOT_坏",
            "四类子目录名": ("数据库", "缓存", "日志", "临时件坏"),
            "macOS基片段": ("Library", "Application Support坏"),
            "Linux退回片段": (".local", "share坏"),
            "XDG变量名": "XDG_DATA_HOME_坏",
            "应用数据变量名": "APPDATA_坏",
        }
        原文 = 本件.read_text(encoding="utf-8")
        漏 = []
        with tempfile.TemporaryDirectory(prefix="运行数据根反向样本-") as 临时:
            for 项, 值 in 假.items():
                路 = Path(临时) / "坏.py"
                路.write_text(_改坏(原文, 项, 值), encoding="utf-8")
                if not 比对(解析路, 子目录路, 路):
                    漏.append(项)
        if 漏:
            print("反向样本失败：改坏这些项却没判红 ⇒ %s" % " · ".join(漏))
            return 1
        print("反向样本通过：%d 项逐项改坏 ⇒ 判据每次都判红" % len(假))
        return 0

    出 = 比对(解析路, 子目录路, py)
    if 出:
        print("一致性判据失败（%d 项不一致）：" % len(出))
        for 条 in 出:
            print("  ✗ " + 条)
        return 1
    print("一致性判据通过：Python 镜像与 Rust 那份逐项一致（%s）" % py)
    return 0


if __name__ == "__main__":
    sys.exit(_入口())
