#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建制品 —— 一次构建产出的、**可装载的整包**（形状与判据见 形状.md §一）。

    python3 构建装配/上线切换/构建制品.py [--变体 <名>] [--不含扩展]

落点：`构建装配/制品产物/<制品标识>/`。**制品标识不含时间戳、不含绝对路径**：

    制品标识 = <提交哈希 12 位>-<构建指纹 16 位>
    构建指纹 = sha256(规范文本)[:16]，规范文本 = profile + 变体 + 工具链 + 扩展根声明指纹
                                          + 逐行「相对路径 sha256(内容)」（按路径排序）

规范文本里**没有时间、没有绝对路径、没有机器名** ⇒ 同一份源在两台机器上产出同一个标识。
**制品不可变**：目标目录已存在即拒绝重建（不是覆盖）——判据见 `--检查`。

本件只做装配：读 `扩展装载/扩展根声明.json` + 编译底座网关 + 把扩展编成**可装载库**，
把结果拼成整包。它**不改任何源文件**，也不生成声明（声明由 `构建装配/形态装配/` 生成）。
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

仓根 = Path(__file__).resolve().parents[2]
制品落点 = 仓根 / "构建装配" / "制品产物"
扩展根声明 = 仓根 / "扩展装载" / "扩展根声明.json"
构建缓存 = 仓根 / "构建环境" / "构建缓存"

# 底座源码范围：影响制品内容的那些件（契约声明 的 .json 也进制品 —— 它编译进底座）。
底座目录 = ("契约声明", "运行内核", "跨语言适配", "对外接口面")
底座根文件 = ("Cargo.toml", "Cargo.lock", "rust-toolchain.toml", ".cargo/config.toml")
源后缀 = (".rs", ".toml", ".json", ".lock")
跳过目录 = {"target", "__pycache__", "构建缓存", "只读参考", ".git", "node_modules"}

# 装配要认识的**底座**名字：底座是装配的输入（装配认识底座是必然）。
# 反向不成立：装配**不认识任何扩展** —— 扩展的名字一律从扫描结果现取（见 扫扩展）。
底座依赖名 = "v1_contract"


def 走源文件(目录: Path):
    for 根, 目录表, 文件表 in os.walk(目录):
        目录表[:] = [d for d in 目录表 if d not in 跳过目录]
        for 名 in 文件表:
            if 名.endswith(源后缀):
                yield Path(根) / 名


def 相对(路: Path) -> str:
    return 路.relative_to(仓根).as_posix()


def 文件指纹(路: Path) -> str:
    return hashlib.sha256(路.read_bytes()).hexdigest()


def 跑(命令, **附加):
    """跑一条命令；失败即抛，**不吞输出**。"""
    成 = subprocess.run(命令, capture_output=True, text=True, **附加)
    if 成.returncode != 0:
        raise SystemExit(
            "命令失败（退出码 {}）：{}\n{}\n{}".format(
                成.returncode, " ".join(命令), 成.stdout[-2000:], 成.stderr[-2000:]
            )
        )
    return 成


def 工具链版本() -> str:
    return 跑(["rustc", "--version"], cwd=仓根).stdout.strip()


def 提交哈希() -> tuple:
    成 = 跑(["git", "rev-parse", "--short=12", "HEAD"], cwd=仓根).stdout.strip()
    脏 = bool(跑(["git", "status", "--porcelain"], cwd=仓根).stdout.strip())
    return 成, 脏


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
    """把一个扩展编成**可装载库**（`GetPlatformInfo` 能被 dlopen 取到）。

    为什么要有这一步：扩展仓自己声明的是 **rlib**（`[lib]` 没写 `crate-type`），
    静态库进不了 `dlopen`。装配侧把它按 `cdylib` 再编一遍 —— 这是**装配动作**，
    不改扩展一行源（`cargo rustc -- --crate-type cdylib`）。

    `--extern <底座依赖名>=<rlib 路径>` 是必须的：cargo 给依赖传的是**只含元数据**的
    `.rmeta`，而 `cdylib` 要的是可链接的 `.rlib`；不显式指路就报
    「crate `v1_contract` required to be available in rlib format」（实测）。
    """
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
    库 = sorted((缓存 / "release" / "deps").glob("lib*.dylib")) + sorted((缓存 / "release" / "deps").glob("lib*.so"))
    # 只认**刚编出来的那一个**：按 Cargo.toml 的 `[lib] name` 找（`[package] name` 不是库名）。
    名 = 读库名(清单)
    命中 = [库文件 for 库文件 in 库 if 名 and 库文件.name.startswith("lib{}".format(名))]
    if len(命中) != 1:
        raise SystemExit("可装载库不唯一（找 {}）：{}".format(名, 命中))
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


def 源指纹(声明文本: str, 纳入的扩展: list, 变体: str) -> str:
    行 = [
        "profile=release",
        "变体={}".format(变体),
        "工具链={}".format(工具链版本()),
        "扩展根声明={}".format(hashlib.sha256(声明文本.encode("utf-8")).hexdigest()),
        # 装配器自己也是输入：本文件一改，同一个标识就不该再指同一份内容（否则标识在骗人）。
        "装配器=构建装配/上线切换/构建制品.py {}".format(文件指纹(Path(__file__).resolve())),
    ]
    件 = {}
    for 名 in 底座根文件:
        路 = 仓根 / 名
        if 路.is_file():
            件[名] = 路
    for 目录 in 底座目录:
        for 路 in 走源文件(仓根 / 目录):
            件[相对(路)] = 路
    for 扩展 in 纳入的扩展:
        for 路 in 走源文件(扩展["落点"]):
            件[相对(路)] = 路
    for 键 in sorted(件):
        行.append("文件 {} {}".format(键, 文件指纹(件[键])))
    return hashlib.sha256("\n".join(行).encode("utf-8")).hexdigest()


def 制品内文件清单(目录: Path) -> dict:
    出 = {}
    for 根, 目录表, 文件表 in os.walk(目录):
        目录表[:] = [d for d in 目录表 if d not in 跳过目录]
        for 名 in 文件表:
            路 = Path(根) / 名
            if 路.name == "制品清单.json":
                continue  # 清单不把自己写进自己的清单（否则自指，哈希无解）
            出[路.relative_to(目录).as_posix()] = 文件指纹(路)
    return dict(sorted(出.items()))


def 检查制品(目录: Path) -> tuple:
    """制品不可变判据（可机器数）：① 清单里每个文件重算指纹都相符 ② 目录里没有清单外的文件。"""
    清单 = json.loads((目录 / "制品清单.json").read_text(encoding="utf-8"))
    记的 = 清单.get("文件清单", {})
    现在 = 制品内文件清单(目录)
    不符 = sorted(键 for 键, 值 in 记的.items() if 现在.get(键) != 值)
    多余 = sorted(键 for 键 in 现在 if 键 not in 记的)
    缺件 = sorted(键 for 键 in 记的 if 键 not in 现在)
    return 不符, 多余, 缺件


def main() -> int:
    解 = argparse.ArgumentParser(description="构建制品（可装载的整包）")
    解.add_argument("--变体", default=None, help="装配变体名（进构建指纹）")
    解.add_argument("--不含扩展", action="store_true", help="只装底座（形态裁剪：同一套源出另一种整包）")
    解.add_argument("--检查", default=None, help="只查一份已产出制品的不可变判据，不构建")
    参 = 解.parse_args()

    if 参.检查:
        目录 = 制品落点 / 参.检查
        if not (目录 / "制品清单.json").is_file():
            打印("制品不存在或没有清单：{}".format(目录))
            return 1
        不符, 多余, 缺件 = 检查制品(目录)
        打印("制品 {} ｜ 指纹不符 {} ｜ 清单外文件 {} ｜ 缺件 {}".format(参.检查, len(不符), len(多余), len(缺件)))
        for 项 in 不符:
            打印("  不符 {}".format(项))
        for 项 in 多余:
            打印("  清单外 {}".format(项))
        for 项 in 缺件:
            打印("  缺件 {}".format(项))
        return 0 if not (不符 or 多余 or 缺件) else 1

    声明文本 = 扩展根声明.read_text(encoding="utf-8")
    声明 = json.loads(声明文本)
    变体 = 参.变体 or ("仅底座" if 参.不含扩展 else "全量")

    扫到的 = 扫扩展(声明)
    纳入的 = [] if 参.不含扩展 else 扫到的
    指纹 = 源指纹(声明文本, 纳入的, 变体)
    提交, 脏 = 提交哈希()
    标识 = "{}-{}".format(提交, 指纹[:16])
    目录 = 制品落点 / 标识

    if 目录.exists():
        打印("制品已存在，拒绝重建（制品不可变）：{}".format(目录))
        打印("  要重出请换变体名，或先删掉这一份（删 = 显式动作，不许覆盖）")
        return 1

    目录.mkdir(parents=True)
    打印("制品标识 {}（提交 {} · 工作区{}）".format(标识, 提交, "脏" if 脏 else "干净"))

    # ── 1 底座网关：唯一对外门的可执行件 ─────────────────────────────────────
    跑(["cargo", "build", "--locked", "--offline", "--release", "-p", "v1-gateway", "--example", "启动网关"], cwd=仓根)
    入口 = 构建缓存 / "release" / "examples" / "启动网关"
    if not 入口.is_file():
        raise SystemExit("找不到启动入口：{}".format(入口))
    shutil.copy2(入口, 目录 / "网关")
    (目录 / "网关").chmod(0o755)

    # ── 2 扩展：编成可装载库，按种类摆进制品自己的扩展树 ─────────────────────
    装入 = []
    for 扩展 in 纳入的:
        库 = 扩展产物(扩展)
        # 制品内的种类目录名 = 扩展根声明里那个 目录 的**末段**（原子支持库 / 组合模块库 / 技能封装库）。
        # 与下面改写声明时用的是同一个名字 —— 两处不一致就是「制品自己找不到自己的扩展」（实测撞到过）。
        目标 = 目录 / "扩展" / Path(扩展["目录"]).name / 扩展["名"] / "{}{}".format(扩展["名"], 库.suffix)
        目标.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(库, 目标)
        装入.append({"种类": 扩展["种类"], "扩展目录": 扩展["名"], "制品内落点": 目标.relative_to(目录).as_posix()})
        打印("  装入扩展 {} → {}".format(扩展["落点"].relative_to(仓根).as_posix(), 装入[-1]["制品内落点"]))

    # ── 3 制品自己的扩展根声明：目录改指制品内，**形状不变** ─────────────────
    制品声明 = dict(声明)
    制品声明["说明"] = "制品内副本（生成物，禁手改）：目录已改指本制品内的 扩展/。源：扩展装载/扩展根声明.json"
    制品声明["路径基准"] = "工作目录"
    制品声明["种类"] = [
        dict(类, 目录="扩展/{}".format(Path(类.get("目录", "")).name)) for 类 in 声明.get("种类", [])
    ]
    (目录 / "扩展根声明.json").write_text(
        json.dumps(制品声明, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # ── 4 制品清单 ───────────────────────────────────────────────────────────
    常量表 = json.loads((仓根 / "契约声明" / "常量表.json").read_text(encoding="utf-8"))
    端口 = next(条["值"] for 条 in 常量表["常量"] if 条["名"] == "接口端口")
    清单 = {
        "生成物": True,
        "禁手改": True,
        "说明": "制品清单 —— 一次构建产出的可装载整包的身份与内容。改它请改 构建装配/上线切换/构建制品.py（源）。",
        "制品标识": 标识,
        "提交哈希": 提交,
        "工作区脏": 脏,
        "装配变体": 变体,
        "构建指纹": 指纹,
        "构建指纹算法": "sha256(规范文本)[:16]；规范文本 = profile + 变体 + 工具链 + 扩展根声明指纹 + 装配器指纹 + 逐行「相对路径 sha256(内容)」（按路径排序）。不含时间、不含绝对路径、不含机器名。",
        "构建指纹范围": {"底座根文件": list(底座根文件), "底座目录": list(底座目录), "扩展": [项["扩展目录"] for 项 in 装入], "后缀": list(源后缀)},
        "构建工具链": 工具链版本(),
        "构建 profile": "release",
        "流量端口": 端口,
        "流量端口来源": "契约声明/常量表.json 的 常量[名=接口端口]（唯一定义处）",
        "启动入口": "网关",
        "启动命令": ["./网关", "--声明根", "扩展根声明.json", "--端口", "<N>"],
        "启动入口读数约定": "启动入口把实际端口打在 `监听 127.0.0.1:<端口>` 这一行上（上线切换靠它拿端口）。",
        "扫到的扩展": [
            {"种类": 项["种类"], "扩展目录": 项["名"], "源落点": 项["落点"].relative_to(仓根).as_posix()} for 项 in 扫到的
        ],
        "装入的扩展": 装入,
        "文件清单": 制品内文件清单(目录),
        "不可变判据": "① 文件清单里每个文件重算 sha256 都相符（0 处不符）② 制品目录里没有清单之外的文件（除 制品清单.json 本身）③ 标识 = 提交哈希 + 构建指纹，且不含时间戳 / 绝对路径。检查：python3 构建装配/上线切换/构建制品.py --检查 <制品标识>",
    }
    (目录 / "制品清单.json").write_text(json.dumps(清单, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    打印("制品落点 {}".format(目录.relative_to(仓根).as_posix()))
    打印("  文件 {} 个 · 装入扩展 {} 个 · 流量端口 {}".format(len(清单["文件清单"]), len(装入), 端口))
    return 0


def 打印(文: str) -> None:
    print(文, flush=True)


if __name__ == "__main__":
    sys.exit(main())
