# -*- coding: utf-8 -*-
"""运行数据根 · 口径 —— **Python 侧唯一解析实现**（Rust 那份的镜像）。

**唯一解析器是 Rust crate `运行内核/运行数据根/`（`v1-dataroot`）**；本件是它在 Python 侧的
**镜像**，不是第二套规则。逐条对齐 `运行内核/运行数据根/src/解析.rs` 与 `子目录.rs`：

  · 覆盖：环境变量 `V1_RUN_DATA_ROOT`（**ASCII** 名），非空即**原样**用它（覆盖是完整根，
    不再拼 `默认目录名`）；
  · 默认：平台数据目录 + `默认目录名`（macOS `~/Library/Application Support` ·
    Linux `$XDG_DATA_HOME` 未设退回 `~/.local/share` · Windows `%APPDATA`）；
  · 全缺 ⇒ **结构化失败（`无位置`），不编路径**；
  · 四类子目录：`数据库` · `缓存` · `日志` · `临时件`（封闭枚举的 Python 形态）。

**漂移由判据盯**：`一致性判据.py` 带 `--检查`（逐项比对上面这些口径与 Rust 源码）与
`--反向样本`（逐项改坏一份副本，验证判据都抓得住）。依据：
`项目文档/决策记录/2026-09-27_运行数据根.md` §二/§三。

**本件是叶子**：只 import 标准库。调用方（`构建装配/演示/常量.py` ·
`构建装配/上线切换/上线切换/常量.py` · `开发工具/认领机制/认领机制/账本.py`）**只引本包，
不许自己拼路径**（自己拼 = 第二个来源）。
"""

import os
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
