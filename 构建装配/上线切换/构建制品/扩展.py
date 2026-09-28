"""扩展 —— 扫候选 · 编可装载库 · 读库名（本包**不认识任何扩展的名字**）。

**扫描面 = 全部 `种类[]`**：三个种类（支持库 · 模块 · 技能）都有制品，只是载入方式不同
（支持库取能力码段 · 模块/技能只解析段），所以没有哪一类该被排除在候选外。
候选资格由「该子目录里有没有本种类的制品」判（`扩展装载/后缀表.json`），不由声明里的开关判。
"""

import os
from pathlib import Path

from .命令 import 跑命令
from .常量 import 仓根, 构建缓存, 底座依赖名


def 扫扩展(声明: dict) -> list:
    """按 扩展根声明 的「怎么扫」扫候选：每个 种类[].目录 下的直接子目录各算一个候选。

    返回 [{种类, 目录, 名, 落点}]。**本函数不认任何扩展的名字** —— 名字从目录现取。
    """
    输出缓冲 = []
    for 类别 in 声明.get("种类", []):
        目录 = 仓根 / 类别.get("目录", "")
        if not 目录.is_dir():
            continue
        for 子项 in sorted(目录.iterdir()):
            if 子项.is_dir() and not 子项.name.startswith("."):
                输出缓冲.append({"种类": 类别.get("种类", ""), "目录": 类别.get("目录", ""), "名": 子项.name, "落点": 子项})
    return 输出缓冲


def 扩展产物(扩展: dict) -> Path:
    """把一个扩展编成**可装载库**（`GetPlatformInfo` 能被 dlopen 取到），返回库文件路径。

    为什么要有这一步：扩展仓自身声明的是 **rlib**（`[lib]` 没写 `crate-type`），
    静态库进不了 `dlopen`。装配侧把它按 `cdylib` 再编一遍 —— 这是**装配动作**，
    不改扩展一行源（`cargo rustc -- --crate-type cdylib`）。

    `--extern <底座依赖名>=<rlib 路径>` 是必须的：cargo 给依赖传的是**只含元数据**的
    `.rmeta`，而 `cdylib` 要的是可链接的 `.rlib`；不显式指路就报
    「crate `v1_contract` required to be available in rlib format」（实测）。

    **本函数 = 建 + 找**（公开行为逐字不变：`构建装配/演示/装配.py` 转调的就是它）。
    命令本体（装配档）**不许**用它 —— 它含构建段，会把命令顶上五秒硬顶；
    装配档用 `找扩展产物`，二进制由环境步 `--预构建` 负责。
    """
    建扩展产物(扩展)
    return 找扩展产物(扩展)


def 建扩展产物(扩展: dict) -> None:
    """**只编不找** —— 环境步（`--预构建`）用。产物落 `构建缓存/扩展/release/deps`。"""
    清单 = 扩展["落点"] / "Cargo.toml"
    缓存 = 构建缓存 / "扩展"
    环境 = dict(os.environ, CARGO_TARGET_DIR=str(缓存))
    跑命令(["cargo", "build", "--locked", "--offline", "--release", "--manifest-path", str(清单)], cwd=仓根, env=环境)
    rlibs = sorted((缓存 / "release" / "deps").glob("lib{}*.rlib".format(底座依赖名)))
    if not rlibs:
        raise SystemExit("找不到底座依赖的 rlib：{}".format(缓存 / "release" / "deps"))
    跑命令(
        ["cargo", "rustc", "--locked", "--offline", "--release", "--manifest-path", str(清单), "--",
         "--crate-type", "cdylib", "--extern", "{}={}".format(底座依赖名, rlibs[0])],
        cwd=仓根,
        env=环境,
    )


def 找扩展产物(扩展: dict) -> Path:
    """**只找不编** —— 命令本体用。找不到（没预构建 / 缓存被清）即 fail-closed 指路。"""
    清单 = 扩展["落点"] / "Cargo.toml"
    缓存 = 构建缓存 / "扩展"
    动态库 = sorted((缓存 / "release" / "deps").glob("lib*.dylib")) + sorted((缓存 / "release" / "deps").glob("lib*.so"))
    # 只认**编出来的那一个**：按 Cargo.toml 的 `[lib] name` 找（`[package] name` 不是库名）。
    名称 = 读库名(清单)
    命中 = [库文件 for 库文件 in 动态库 if 名称 and 库文件.name.startswith("lib{}".format(名称))]
    if len(命中) != 1:
        raise SystemExit(
            "找不到已编好的可装载库（按 [lib] name 找 {}，命中 {} 个）：{}\n"
            "  先跑环境步：python3 构建装配/上线切换/构建制品.py --预构建".format(
                名称, len(命中), 缓存 / "release" / "deps"
            )
        )
    return 命中[0]


def 读库名(清单: Path) -> str:
    """从 Cargo.toml 取 `[lib]` 段的 `name`（`[package]` 段的 name 是包名，不是库名）。"""
    号段 = None
    for 源码行 in 清单.read_text(encoding="utf-8").splitlines():
        文本 = 源码行.split("#", 1)[0].strip()
        if 文本.startswith("["):
            号段 = 文本
            continue
        if 号段 == "[lib]" and 文本.startswith("name"):
            return 文本.split("=", 1)[1].strip().strip('"')
    raise SystemExit("Cargo.toml 里没有 [lib] name：{}".format(清单))
