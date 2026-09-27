# -*- coding: utf-8 -*-
"""运行数据根 —— 本脚本的**缓存落点**解析（Python 侧镜像 Rust 侧的口径）。

**为什么要有这一件**：逐文件缓存的键里有 `(路径, 大小, mtime)`，缓存必须落在**源码树之外**
（`README.md` §十 · 判据 ⑳「运行数据不落源码树」）。落点不是本脚本自己定的 —— 全平台唯一的
落点是「运行数据根」这一个唯一物，本件只把它的解析口径照抄一份（Python 侧），**不另造第二条规则**。

**口径来源**（逐条对齐，不另立）：`运行内核/运行数据根/src/解析.rs` ——
  · 覆盖：环境变量 `V1_RUN_DATA_ROOT`（ASCII 名），非空即**原样**用它（覆盖是完整根，不再拼目录名）
  · 默认：平台数据目录 + `默认目录名`（macOS `~/Library/Application Support` ·
    Linux `$XDG_DATA_HOME` 未设退回 `~/.local/share` · Windows `%APPDATA%`）
  · 全缺 ⇒ **结构化失败，不编路径**（编一个路径就是把「没有位置」藏起来）
  · 四类子目录名做成封闭枚举（`数据库` · `缓存` · `日志` · `临时件`），本件只用 `缓存` 那一类

**本件是叶子**：不 import 任何兄弟件，也不 import 任何第三方（零依赖）。
"""

import os
import sys
from pathlib import Path

# 覆盖变量名必须 **ASCII**（macOS 的 `/bin/sh` 是 bash 3.2，不认中文变量名；同 解析.rs 的理由）。
覆盖变量名 = "V1_RUN_DATA_ROOT"
默认目录名 = "系统工程平台V1"
子目录名 = ("数据库", "缓存", "日志", "临时件")
本件缓存子目录 = "声明记录区反解"


class 无位置(Exception):
    """既没有覆盖、也推不出默认位置（家目录 / XDG / APPDATA 全缺）—— 结构化失败，不编路径。"""


def 当前平台() -> str:
    """编译期不可知（本件是脚本）⇒ 运行期判一次；只用来选默认基，不参与任何语义。"""
    if sys.platform == "darwin":
        return "macos"
    if os.name == "nt":
        return "windows"
    return "linux"


def 解析(覆盖, 家目录, xdg数据目录, 应用数据目录, 平台: str) -> Path:
    """**唯一解析口**：`覆盖 > 平台默认`。四条外部事实全部注入（不从全局读），故每条分支都判得了。"""
    if 覆盖:
        return Path(覆盖)
    if 平台 == "macos":
        if 家目录:
            return Path(家目录) / "Library" / "Application Support" / 默认目录名
    elif 平台 == "windows":
        if 应用数据目录:
            return Path(应用数据目录) / 默认目录名
    else:
        if xdg数据目录:
            return Path(xdg数据目录) / 默认目录名
        if 家目录:
            return Path(家目录) / ".local" / "share" / 默认目录名
    raise 无位置(
        "运行数据根解析不出：既没有 %s，也推不出平台默认位置（家目录 / XDG_DATA_HOME / APPDATA 全缺）"
        % 覆盖变量名
    )


def 解析当前() -> Path:
    """读真实环境那一层薄壳：只读四个环境变量 + 判平台，零判断。"""
    return 解析(
        os.environ.get(覆盖变量名),
        os.environ.get("HOME"),
        os.environ.get("XDG_DATA_HOME"),
        os.environ.get("APPDATA"),
        当前平台(),
    )


def 缓存目录() -> "Path | None":
    """本脚本的缓存落点 = `<运行数据根>/缓存/声明记录区反解`。

    解析不出根 ⇒ 返回 `None`（**不是**退回源码树，也不是退回 `/tmp`）—— 调用方据此**关掉缓存**
    照常算，只是不复用。这样「没有位置」不会变成「偷偷落进源码树」。
    """
    try:
        根 = 解析当前()
    except 无位置:
        return None
    return 根 / "缓存" / 本件缓存子目录
