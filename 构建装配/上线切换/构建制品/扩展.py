"""扩展 —— 扫候选 · 编可装载库 · 读库名（本包**不认识任何扩展的名字**）。

**扫描面 = 全部 `种类[]`**：三个种类（支持库 · 模块 · 技能）都有制品，只是载入方式不同
（支持库取能力码段 · 模块/技能只解析段），所以没有哪一类该被排除在候选外。
候选资格由「该子目录里有没有本种类的制品」判（`扩展装载/后缀表.json`），不由声明里的开关判。
"""

import json
import os
import struct
from pathlib import Path

from .命令 import 跑子进程
from .常量 import 仓根, 构建缓存, 底座依赖名


def 扫扩展(声明: dict) -> list:
    """按 扩展根声明 的「怎么扫」扫候选：每个 种类[].扩展落点 下的直接子目录各算一个候选。

    返回 [{种类, 扩展落点, 名, 落点}]。**本函数不认任何扩展的名字** —— 名字从目录现取。
    """
    输出缓冲 = []
    for 扩展类别 in 声明.get("种类", []):
        扩展根目录 = 仓根 / 扩展类别.get("扩展落点", "")
        if not 扩展根目录.is_dir():
            continue
        for 子项 in sorted(扩展根目录.iterdir()):
            if 子项.is_dir() and not 子项.name.startswith("."):
                输出缓冲.append({"种类": 扩展类别.get("种类", ""), "扩展落点": 扩展类别.get("扩展落点", ""), "名": 子项.name, "落点": 子项})
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
    清单路径 = 扩展["落点"] / "Cargo.toml"
    缓存 = 构建缓存 / "扩展"
    子进程环境 = dict(os.environ, CARGO_TARGET_DIR=str(缓存))
    跑子进程(["cargo", "build", "--locked", "--offline", "--release", "--manifest-path", str(清单路径)], cwd=仓根, env=子进程环境)
    rlibs = sorted((缓存 / "release" / "deps").glob("lib{}*.rlib".format(底座依赖名)))
    if not rlibs:
        raise SystemExit("找不到底座依赖的 rlib：{}".format(缓存 / "release" / "deps"))
    跑子进程(
        ["cargo", "rustc", "--locked", "--offline", "--release", "--manifest-path", str(清单路径), "--",
         "--crate-type", "cdylib", "--extern", "{}={}".format(底座依赖名, rlibs[0])],
        cwd=仓根,
        env=子进程环境,
    )
    # ★ 容器写：把编出的 cdylib 字节包成 `.支持库制品`（落点照 `扩展装载/后缀表.json`）。
    打包支持库制品(扩展)


def 找扩展产物(扩展: dict) -> Path:
    """**只找不编** —— 命令本体用。找不到（没预构建 / 缓存被清）即 fail-closed 指路。"""
    清单路径 = 扩展["落点"] / "Cargo.toml"
    缓存 = 构建缓存 / "扩展"
    动态库 = sorted((缓存 / "release" / "deps").glob("lib*.dylib")) + sorted((缓存 / "release" / "deps").glob("lib*.so"))
    # 只认**编出来的那一个**：按 Cargo.toml 的 `[lib] name` 找（`[package] name` 不是库名）。
    名称 = 读库名(清单路径)
    命中 = [库文件 for 库文件 in 动态库 if 名称 and 库文件.name.startswith("lib{}".format(名称))]
    if len(命中) != 1:
        raise SystemExit(
            "找不到已编好的可装载库（按 [lib] name 找 {}，命中 {} 个）：{}\n"
            "  先跑环境步：python3 构建装配/上线切换/构建制品.py --预构建".format(
                名称, len(命中), 缓存 / "release" / "deps"
            )
        )
    return 命中[0]


def 读库名(清单路径: Path) -> str:
    """从 Cargo.toml 取 `[lib]` 段的 `name`（`[package]` 段的 name 是包名，不是库名）。"""
    号段 = None
    for 源码行 in 清单路径.read_text(encoding="utf-8").splitlines():
        源文本 = 源码行.split("#", 1)[0].strip()
        if 源文本.startswith("["):
            号段 = 源文本
            continue
        if 号段 == "[lib]" and 源文本.startswith("name"):
            return 源文本.split("=", 1)[1].strip().strip('"')
    raise SystemExit("Cargo.toml 里没有 [lib] name：{}".format(清单路径))


# ── 容器写：把编出的 cdylib 包成 `.支持库制品` ─────────────────────────────────


def 打包支持库制品(扩展: dict) -> Path:
    """把编出的 cdylib 字节包成 `<扩展目录>/<扩展目录名>.支持库制品`（容器写）。

    容器 codec 的**唯一实现**在 `契约声明/src/契约声明/容器.rs`；本函数只转调构建期 bin
    `契约声明/examples/装支持库制品.rs`（它用那份 codec）。落点照 `扩展装载/后缀表.json`：
    `扩展根目录/原子支持库/<扩展名>/<扩展名>.支持库制品`。
    """
    动态库 = 找扩展产物(扩展)
    段文件 = 构建缓存 / "扩展" / "{}.接口说明段".format(扩展["名"])
    段文件.parent.mkdir(parents=True, exist_ok=True)
    段文件.write_bytes(编接口说明段(扩展["落点"]))
    制品路径 = 扩展["落点"] / "{}.支持库制品".format(扩展["名"])
    跑子进程(
        [str(装支持库制品入口()), "--能力码", str(动态库), "--接口说明", str(段文件), "--输出", str(制品路径)],
        cwd=仓根,
    )
    return 制品路径


def 装支持库制品入口() -> Path:
    """构建期 bin 的落点（由 `--预构建` 编出）。找不到即 fail-closed 指路。"""
    入口 = 构建缓存 / "release" / "examples" / "装支持库制品"
    if not 入口.is_file():
        raise SystemExit(
            "找不到构建期 bin 装支持库制品（没预构建 / 缓存被清）：{}\n"
            "  先跑环境步：python3 构建装配/上线切换/构建制品.py --预构建".format(入口)
        )
    return 入口


def 编接口说明段(扩展落点: Path) -> bytes:
    """`<扩展目录>/能力声明/*.json`（一个扩展的全部能力）→ 接口说明段字节。

    **六字段 = `GET /接口/能力/<编号>` 返回体，逐条同名同序**（字段表只在
    `项目文档/设计文档/接口面形状.md` §三 一处）。字节排布与扩展侧权威
    `src/能力包件/接口段编码.rs::编码` **逐字节同构**：小端 · 文本 `u32 字节长 + UTF-8` ·
    表 `u32 项数 + 逐项递归` · 槽 24 字节原样 · 逻辑型 `u8`。

    **一个扩展的全部能力 ⇒ 段里逐条串接**（每条字段全带长度前缀，故可顺序解析）。
    能力声明目录缺了 / 空了 ⇒ 空段（不是错）。
    """
    能力声明目录 = 扩展落点 / "能力声明"
    错误码目录 = 扩展落点 / "错误码表"
    段缓冲 = bytearray()
    for 声明路径 in sorted(能力声明目录.glob("*.json")):
        声明 = json.loads(声明路径.read_text(encoding="utf-8"))
        段缓冲 += _编一条接口说明(声明, 错误码目录)
    return bytes(段缓冲)


def _编一条接口说明(声明: dict, 错误码目录: Path) -> bytes:
    缓冲 = bytearray()
    缓冲 += struct.pack("<I", 声明["编号"])
    _写文本(缓冲, 声明["名称"])
    _写文本(缓冲, 声明["说明"])
    参数表 = 声明.get("参数表", [])
    缓冲 += struct.pack("<I", len(参数表))
    for 命令行参数 in 参数表:
        _写文本(缓冲, 命令行参数["名称"])
        缓冲 += struct.pack("<I", 命令行参数["类型标签"])
        缓冲 += struct.pack("<H", 命令行参数.get("状态位", 0))
        默认值 = 命令行参数.get("默认值") or {}
        # 定长槽 24 字节：u32 类型标签 · u16 标志 · u16 保留 · u64 长度 · u64 值
        # （标志 / 保留 / 长度 在能力声明里无源 ⇒ 写 0；非空槽需指针时另裁）。
        缓冲 += struct.pack("<IHHQQ", 默认值.get("类型标签", 0), 0, 0, 0, 默认值.get("值", 0))
    缓冲 += struct.pack("<I", 声明["返回类型"])
    可抛错误码表 = 声明.get("可抛错误码", [])
    缓冲 += struct.pack("<I", len(可抛错误码表))
    for 错误码号 in 可抛错误码表:
        缓冲 += _编错误项(错误码号, 错误码目录)
    return bytes(缓冲)


def _编错误项(错误码号: int, 错误码目录: Path) -> bytes:
    """一条可抛错误码 → 七字段（与 `错误形状.rs::到协议值` 逐条同序）。

    段位 / 名称 / 三项业务判断从扩展自身的 `错误码表/<码>.json` 查（查不到即用默认值 +
    `已登记 = 假`：**不是猜**，是如实登记「这个码没有源」）。
    """
    路径 = 错误码目录 / "{:04d}.json".format(错误码号)
    错误项 = json.loads(路径.read_text(encoding="utf-8")) if 路径.is_file() else None
    缓冲 = bytearray()
    缓冲 += struct.pack("<I", 错误码号)
    缓冲 += struct.pack("<I", 错误项.get("段位", 错误码号 // 1000) if 错误项 else 错误码号 // 1000)
    _写文本(缓冲, 错误项.get("名称", "") if 错误项 else "")
    缓冲 += bytes([
        1 if (错误项 and 错误项.get("可重试")) else 0,
        1 if (错误项 and 错误项.get("可自愈")) else 0,
        1 if (错误项 and 错误项.get("需人工")) else 0,
        1 if 错误项 else 0,
    ])
    return bytes(缓冲)


def _写文本(缓冲: bytearray, 源文本: str) -> None:
    字节 = 源文本.encode("utf-8")
    缓冲 += struct.pack("<I", len(字节))
    缓冲 += 字节
