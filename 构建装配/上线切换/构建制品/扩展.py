"""扩展 —— 扫候选 · 编可装载库 · 读库名（本包**不认识任何扩展的名字**）。

**候选面已收窄**（`2026-09-27_待裁九项按老仓设计哲学裁决.md` 裁决 9）：只有 `可装载件 = true`
的种类（支持库）的直接子目录才是**可装载件候选**；模块（组装件）与技能（声明/工作流）
**不编 cdylib、不 dlopen**，不进候选 —— 那正是老仓 7.1④ 要撤的旁路（装配面 + 声明面一起撤）。
"""

import os
from pathlib import Path

from .命令 import 跑
from .常量 import 仓根, 构建缓存, 底座依赖名


def 可装载种类(声明: dict) -> list:
    """声明里 `可装载件 = true` 的那些 种类（**装配只认识这个布尔，不认识任何种类名**）。

    依据 `2026-09-27_待裁九项按老仓设计哲学裁决.md` 裁决 9：**模块 / 技能都不编 cdylib、都不 dlopen**
    —— 模块 = 组装件（声明 + 成员引用，与 `.ec` 同义）· 技能 = 声明 / 工作流定义（本体是 md）。
    谁 dlopen：都不 dlopen（底座按声明组装，走唯一调用口）。所以它们**不是可装载件候选**。
    `可装载件` 缺了 / 不是布尔 ⇒ fail-closed 指路（旧声明没有这个键；不给默认值，
    默认 true 就把旁路放回来了，默认 false 就把支持库静默漏掉）。
    """
    出 = []
    for 类 in 声明.get("种类", []):
        标 = 类.get("可装载件")
        if not isinstance(标, bool):
            raise SystemExit(
                "扩展根声明的 种类[{}] 缺 `可装载件`（或不是布尔）：{}\n"
                "  这个键决定「这一类的直接子目录要不要当可装载件候选」（裁决 9："
                "支持库 true · 模块/技能 false）。不给默认值——默认 true 会把旁路放回来，"
                "默认 false 会把支持库静默漏掉。见 扩展装载/扩展根声明.json".format(
                    类.get("种类", "?"), 类
                )
            )
        if 标:
            出.append(类)
    return 出


def 扫扩展(声明: dict) -> list:
    """按 扩展根声明 的「怎么扫」扫**可装载件候选**：每个 `可装载件 = true` 种类[].目录
    下的直接子目录各算一个候选。

    返回 [{种类, 目录, 名, 落点}]。**本函数不认任何扩展的名字** —— 名字从目录现取。
    也**不认任何种类名**：哪些种类是可装载件，由声明里的 `可装载件` 说了算（见 `可装载种类`）。
    `可装载件 = false` 的种类（模块 = 组装件 · 技能 = 声明/工作流）**不进候选** ——
    它们不编 cdylib、不 dlopen（裁决 9），交给它们编 cdylib 正是 7.1④ 要撤的旁路。
    """
    出 = []
    for 类 in 可装载种类(声明):
        目录 = 仓根 / 类.get("目录", "")
        if not 目录.is_dir():
            continue
        for 子 in sorted(目录.iterdir()):
            if 子.is_dir() and not 子.name.startswith("."):
                出.append({"种类": 类.get("种类", ""), "目录": 类.get("目录", ""), "名": 子.name, "落点": 子})
    return 出


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
