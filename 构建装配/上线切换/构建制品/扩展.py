"""扩展 —— 扫候选 · 编可装载库 · 读库名（本包**不认识任何扩展的名字**）。

**扫描面 = 全部 `种类[]`**：三个种类（支持库 · 模块 · 技能）都有制品，只是载入方式不同
（支持库取能力码段 · 模块/技能只解析段），所以没有哪一类该被排除在候选外。
候选资格由「该子目录里有没有本种类的制品」判（`扩展装载/后缀表.json`），不由声明里的开关判。
支持库的制品形态是「装配侧现场编 → 包成制品」⇒ 尚无制品但有 `Cargo.toml` 的支持库也算候选（现场编它）；
模块 / 技能只消费既有制品，装配侧不替它们编任何东西。
"""

import json
import os
import struct
from pathlib import Path

from .命令 import 跑子进程
from .常量 import 仓根, 构建缓存
from .输出 import 打印文本
from .产物回执 import 记扩展产物回执, 取扩展产物回执

# 后缀集的**唯一权威**（与运行期 `扫扩展根.rs::读后缀表` 读同一份）：候选资格与制品落点都按它判。
后缀表源 = 仓根 / "扩展装载" / "后缀表.json"


def 读后缀表() -> dict:
    """读唯一权威 `扩展装载/后缀表.json` → {种类名: 制品后缀}。

    与运行期 `扫扩展根.rs::读后缀表` **同一条规则**（两侧各一份实现、规则逐字相同，分界见
    `构建装配/上线切换/形状.md` §三「两侧分界」）。空表 / 缺键即 fail-closed ——
    空后缀集 ⇒ 没有候选可扫，不许静默当「扫到 0 个扩展」。
    """
    来源 = json.loads(后缀表源.read_text(encoding="utf-8"))
    分类 = {}
    for 种类项 in 来源.get("三类扩展", []):
        后缀项 = 种类项.get("制品后缀")
        if 后缀项:
            分类[种类项.get("种类", "")] = 后缀项
    if not 分类:
        raise SystemExit("后缀表的 `三类扩展[].制品后缀` 一个都没有（空后缀集 ⇒ 没有候选可扫）")
    return 分类


def 取制品路径(扩展: dict) -> Path:
    """取一个扩展的**已产出制品**（本函数不编任何东西 —— 模块 / 技能只消费既有制品）。

    落点按 `扩展装载/后缀表.json` 的 制品后缀 找（不按名字找）；要求**恰好一个**普通文件
    （与运行期 `扫扩展根.rs::取扩展声明` 的「恰好一个本平台制品」同口径）。
    """
    分类 = 读后缀表()
    if 扩展["种类"] not in 分类:
        raise SystemExit("未知扩展种类，拒绝取制品：{}".format(扩展["种类"]))
    制品列表 = sorted(路径 for 路径 in 扩展["落点"].glob("*{}".format(分类[扩展["种类"]])) if 路径.is_file() and not 路径.is_symlink())
    if len(制品列表) != 1:
        raise SystemExit("{}：{} 制品必须恰好一个普通文件，实际 {}".format(扩展["落点"], 扩展["种类"], len(制品列表)))
    return 制品列表[0]


def 扫扩展(声明: dict) -> list:
    """按 扩展根声明 的「怎么扫」扫候选：每个 种类[].扩展落点 下的直接子目录，**有本种类制品的**才算候选。

    返回 [{种类, 扩展落点, 名, 落点}]。**本函数不认任何扩展的名字** —— 名字从目录现取。
    候选资格按 `扩展装载/后缀表.json` 的 制品后缀 判（不按名字找）：支持库尚无制品但有
    `Cargo.toml` ⇒ 也算候选（制品形态 =「装配侧现场编」，此刻还没编出来）；其余不合格目录
    **跳过并报原因**（不崩、不静默当扩展）；同类制品 >1 / 未知种类 ⇒ fail-closed。
    """
    分类 = 读后缀表()
    输出缓冲 = []
    for 扩展类别 in 声明.get("种类", []):
        种类名 = 扩展类别.get("种类", "")
        if 种类名 not in 分类:
            raise SystemExit("未知扩展种类，拒绝装配：{}".format(种类名))
        扩展根目录 = 仓根 / 扩展类别.get("扩展落点", "")
        if not 扩展根目录.is_dir():
            continue
        for 子项 in sorted(扩展根目录.iterdir()):
            if not 子项.is_dir() or 子项.name.startswith("."):
                continue
            制品列表 = sorted(路径 for 路径 in 子项.glob("*{}".format(分类[种类名])) if 路径.is_file())
            if len(制品列表) > 1:
                raise SystemExit("{}：{} 制品不唯一（{} 个）".format(子项, 种类名, len(制品列表)))
            if not 制品列表 and not (种类名 == "支持库" and (子项 / "Cargo.toml").is_file()):
                打印文本("  跳过 {}（无 {} 制品）".format(子项.name, 种类名))
                continue
            输出缓冲.append({"种类": 种类名, "扩展落点": 扩展类别.get("扩展落点", ""), "名": 子项.name, "落点": 子项})
    return 输出缓冲


def 扩展产物(扩展: dict) -> Path:
    """把一个扩展编成**可装载库**（`GetPlatformInfo` 能被 dlopen 取到），返回库文件路径。

    Cargo直接接收cdylib目标，统一决定全部依赖的链接形态。
    不把crate-type放在参数分隔符后，不扫描缓存或人工指定某一份rlib。

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
    运行结果 = 跑子进程(
        ["cargo", "rustc", "--locked", "--offline", "--release", "--manifest-path", str(清单路径),
         "--message-format=json-render-diagnostics", "--crate-type", "cdylib"],
        cwd=仓根,
        env=子进程环境,
    )
    记扩展产物回执(运行结果.stdout, 清单路径, 读库名(清单路径), 缓存)
    # ★ 容器写：把编出的 cdylib 字节包成 `.支持库制品`（落点照 `扩展装载/后缀表.json`）。
    打包支持库制品(扩展)


def 找扩展产物(扩展: dict) -> Path:
    """**只找不编** —— 命令本体用。找不到（没预构建 / 缓存被清）即 fail-closed 指路。"""
    清单路径 = 扩展["落点"] / "Cargo.toml"
    缓存 = 构建缓存 / "扩展"
    return 取扩展产物回执(清单路径, 读库名(清单路径), 缓存)


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
