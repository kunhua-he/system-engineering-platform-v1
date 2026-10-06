# -*- coding: utf-8 -*-
"""①类三判据的反向样本注入（#33）—— 单列一件，免把 `注入.py` 顶过 400 行。

⑪-1 对外监听 · ⑫-3 边界零业务判断 · ⑫-4 边界零状态：编译期断言不了
（构造口在实现侧 / 是否定存在性），故各留一条**能跑的读数**证明判据非空转。
"""

from pathlib import Path


def 注入_第二处对外监听(临根: Path) -> str:
    """在网关里再开一个监听点——对外监听多一处（判据 ⑪ 判据 1）。"""
    路径 = 临根 / "对外接口面" / "网关" / "src" / "lib.rs"
    路径.write_text(
        路径.read_text(encoding="utf-8")
        + '\npub fn 再起一个() { let _ = TcpListener::bind("127.0.0.1:0"); }\n',
        encoding="utf-8",
    )
    return "对外接口面/网关/src/lib.rs"


def 注入_边界里出现业务判断(临根: Path) -> str:
    """在边界层（`跨语言适配/`）塞一处按号分支——「边界 0 业务判断」被破（判据 ⑫ 判据 3）。"""
    路径 = 临根 / "跨语言适配" / "适配器实现" / "src" / "lib.rs"
    路径.write_text(
        路径.read_text(encoding="utf-8")
        + "\npub fn 按号分(能力号: u32) -> u32 { if 能力号 == 1 { 1 } else { 0 } }\n",
        encoding="utf-8",
    )
    return "跨语言适配/适配器实现/src/lib.rs"


def 注入_边界里出现状态(临根: Path) -> str:
    """在边界层（`跨语言适配/`）塞一处模块级 `static`——「边界 0 状态」被破（判据 ⑫ 判据 4）。"""
    路径 = 临根 / "跨语言适配" / "适配器实现" / "src" / "lib.rs"
    路径.write_text(
        路径.read_text(encoding="utf-8") + "\nstatic 缓存: u32 = 0;\n",
        encoding="utf-8",
    )
    return "跨语言适配/适配器实现/src/lib.rs"


def 注入_层间边括号可见性(临根: Path) -> str:
    """判据 ⑪-5 的反向样本：`pub(crate) use` 造成的**反向依赖**也必须进边表 ⇒ 当场红。

    审计（`2026-09-30_判据假绿审计落点.md` N6）：原正则只认行首 `use` / `pub use`，
    `pub(crate) use` / `pub(super) use` 整类漏判（实测全仓 11 处）。修完必须补反向样本
    （`判据元数据.py` 那条纪律：**给已有判据扩面必须同时补反向样本** —— 没有它，
    「面扩了却没人证它真走到了」）。
    `v1_gateway` 属 `对外接口面`（层序 3），本件在 `跨语言适配`（2）⇒ 目标序 > 源序 = 反向依赖。
    """
    路径 = 临根 / "跨语言适配" / "适配器实现" / "src" / "lib.rs"
    路径.write_text(
        路径.read_text(encoding="utf-8") + "\npub(crate) use v1_gateway::起;\n",
        encoding="utf-8",
    )
    return "跨语言适配/适配器实现/src/lib.rs"


def 注入_Python反向依赖(临根: Path) -> str:
    """判据 ⑪-5b 的反向样本：Python 侧 `from 构建装配… import` 造成的**反向依赖** ⇒ 当场红。

    B8 补面（判据 5 原先只认 Rust `use`）：`.py` 的跨层 import 此前不进边表 —— 实测
    `扩展根` 4 件 `from 构建装配.门禁 import 自门禁` 一路活到 2026-10-07 没人判。
    本件放**非豁免**位置（`样例支持库/src/`，不在 `常量.层序文件豁免` 里）：
    `扩展根`（层序 2）依赖 `构建装配`（3）⇒ 目标序 > 源序 = 反向依赖。
    """
    路径 = 临根 / "扩展根目录" / "原子支持库" / "样例支持库" / "src" / "工具脚本.py"
    路径.parent.mkdir(parents=True, exist_ok=True)
    路径.write_text(
        "# 反向样本：扩展根里的 Python 件反向 import 构建装配。\n"
        "from 构建装配.门禁 import 自门禁\n",
        encoding="utf-8",
    )
    return "扩展根目录/原子支持库/样例支持库/src/工具脚本.py"
