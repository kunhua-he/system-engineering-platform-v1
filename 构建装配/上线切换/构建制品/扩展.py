"""扩展 —— 扫候选 · 编可装载库 · 读库名（本包**不认识任何扩展的名字**）。"""

import os
from pathlib import Path

from .命令 import 跑
from .常量 import 仓根, 构建缓存, 底座依赖名


def 扫扩展(声明: dict) -> list:
    """按 扩展根声明 的「怎么扫」扫扩展：每个 种类[].目录 下的直接子目录各算一个候选。

    返回 [{种类, 目录, 名, 落点}]。**本函数不认任何扩展的名字** —— 名字从目录现取。
    """
    出 = []
    for 类 in 声明.get("种类", []):
        目录 = 仓根 / 类.get("目录", "")
        if not 目录.is_dir():
            continue
        for 子 in sorted(目录.iterdir()):
            if 子.is_dir() and not 子.name.startswith("."):
                出.append({"种类": 类.get("种类", ""), "目录": 类.get("目录", ""), "名": 子.name, "落点": 子})
    return 出


def 扩展产物(扩展: dict) -> Path:
    """把一个扩展编成**可装载库**（`GetPlatformInfo` 能被 dlopen 取到），返回库文件路径。

    为什么要有这一步：扩展仓自己声明的是 **rlib**（`[lib]` 没写 `crate-type`），
    静态库进不了 `dlopen`。装配侧把它按 `cdylib` 再编一遍 —— 这是**装配动作**，
    不改扩展一行源（`cargo rustc -- --crate-type cdylib`）。

    `--extern <底座依赖名>=<rlib 路径>` 是必须的：cargo 给依赖传的是**只含元数据**的
    `.rmeta`，而 `cdylib` 要的是可链接的 `.rlib`；不显式指路就报
    「crate `v1_contract` required to be available in rlib format」（实测）。

    **本函数 = 建 + 找**（公开行为逐字不变：`构建装配/演示/装配.py` 转调的就是它）。
    命令本体（装配档）**不许**用它 —— 它含构建段，会把命令顶上五秒硬顶（台账 #233）；
    装配档用 `找扩展产物`，二进制由环境步 `--预构建` 负责。
    """
    建扩展产物(扩展)
    return 找扩展产物(扩展)


def 建扩展产物(扩展: dict) -> None:
    """**只编不找** —— 环境步（`--预构建`）用。产物落 `构建缓存/扩展/release/deps`。"""
    清单 = 扩展["落点"] / "Cargo.toml"
    缓存 = 构建缓存 / "扩展"
    环境 = dict(os.environ, CARGO_TARGET_DIR=str(缓存))
    跑(["cargo", "build", "--locked", "--offline", "--release", "--manifest-path", str(清单)], cwd=仓根, env=环境)
    rlibs = sorted((缓存 / "release" / "deps").glob("lib{}*.rlib".format(底座依赖名)))
    if not rlibs:
        raise SystemExit("找不到底座依赖的 rlib：{}".format(缓存 / "release" / "deps"))
    跑(
        ["cargo", "rustc", "--locked", "--offline", "--release", "--manifest-path", str(清单), "--",
         "--crate-type", "cdylib", "--extern", "{}={}".format(底座依赖名, rlibs[0])],
        cwd=仓根,
        env=环境,
    )


def 找扩展产物(扩展: dict) -> Path:
    """**只找不编** —— 命令本体用。找不到（没预构建 / 缓存被清）即 fail-closed 指路。"""
    清单 = 扩展["落点"] / "Cargo.toml"
    缓存 = 构建缓存 / "扩展"
    库 = sorted((缓存 / "release" / "deps").glob("lib*.dylib")) + sorted((缓存 / "release" / "deps").glob("lib*.so"))
    # 只认**编出来的那一个**：按 Cargo.toml 的 `[lib] name` 找（`[package] name` 不是库名）。
    名 = 读库名(清单)
    命中 = [库文件 for 库文件 in 库 if 名 and 库文件.name.startswith("lib{}".format(名))]
    if len(命中) != 1:
        raise SystemExit(
            "找不到已编好的可装载库（按 [lib] name 找 {}，命中 {} 个）：{}\n"
            "  先跑环境步：python3 构建装配/上线切换/构建制品.py --预构建".format(
                名, len(命中), 缓存 / "release" / "deps"
            )
        )
    return 命中[0]


def 读库名(清单: Path) -> str:
    """从 Cargo.toml 取 `[lib]` 段的 `name`（`[package]` 段的 name 是包名，不是库名）。"""
    段 = None
    for 行 in 清单.read_text(encoding="utf-8").splitlines():
        文 = 行.split("#", 1)[0].strip()
        if 文.startswith("["):
            段 = 文
            continue
        if 段 == "[lib]" and 文.startswith("name"):
            return 文.split("=", 1)[1].strip().strip('"')
    raise SystemExit("Cargo.toml 里没有 [lib] name：{}".format(清单))
