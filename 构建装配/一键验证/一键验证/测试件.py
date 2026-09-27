# -*- coding: utf-8 -*-
"""测试件与生产区：建测试文件集 · 生产区文本 · 并行生产区 · 收集导出。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
import re

from .剥字面量 import _剥, cfg测试区, 去字面量
from .常量 import 导出名模式, 并发度
from .构造点 import _cfg属性, _夹具挂载形, _属性窗口起


def 建测试文件集(文件: dict) -> set:
    """整文件都是测试的 .rs（父模块用 `#[cfg(test)] … mod X;` 把它挂进来）。

    为什么要它：夹具常被拆成单独文件（`#[cfg(test)] #[path = "测试夹具.rs"] mod 测试夹具;`），
    文件**自身**没有 `#[cfg(test)]` 属性 ⇒ 只看文件内会把它当生产代码（实测撞到过）。

    口径（与 `测试验证/契约一致性/扫实现.py` 的 `建夹具集` 同）：
      · 父文件可以是**任意一个 .rs**——实测撞到过 `装载测试.rs` 由同目录兄弟 `装载.rs`
        挂进来，不是 lib.rs/mod.rs/main.rs 挂的；
      · `#[path = "…"]` 与 `mod 名;` 都**相对父文件所在目录**解析 ⇒ 目标可以在子目录里、
        名字也可以与 mod 名不同——实测撞到过 `容器.rs` 用 `#[path = "容器/测试.rs"] mod 测试;`
        把 `容器/测试.rs` 挂进来（只按「同目录 + 同名」找会把这一份当生产代码 ⇒ 假红）；
      · `#[path]` 写在 `#[cfg(test)]` 之前也合法；cfg 条件里可以嵌括号
        （`#[cfg(any(test, feature = "x"))]`）——两种形状都要认。
    """
    出 = set()
    # 一遍预扫：把每份 .rs 的挂载声明解析成「相对父文件目录的目标路径」。
    # 注意 `#[path = "…"]` 的值写在字符串里 ⇒ 去字面量会把它抹成空白，必须回**原文**取引号内内容。
    挂载 = []
    for 父键, 项 in 文件.items():
        if not 父键.endswith(".rs") or 项["文本"] is None:
            continue
        净 = 去字面量(项["文本"])
        原 = 项["文本"]
        父目录 = 父键.rsplit("/", 1)[0] if "/" in 父键 else ""
        for 命 in _夹具挂载形.finditer(净):
            属 = _cfg属性(净, 命.start())
            if 属 is None:
                continue
            属性文本, 属止 = 属
            if not re.search(r"\btest\b", 属性文本):
                continue
            # 项头：从 cfg 属性之后扫到第一个 `{` 或 `;`
            终 = 属止
            while 终 < len(净) and 净[终] not in "{;":
                终 += 1
            if 终 >= len(净) or 净[终] != ";":
                continue  # 内联 `mod 名 { … }`：同一个文件里的测试块，不是外部夹具文件
            名配 = re.search(r"\bmod\s+([^\s;{]+)", 净[属止:终])
            if not 名配:
                continue
            路 = None
            # `#[path = "…"]` 可以写在 cfg 之前，也可以写在 cfg 之后（属性顺序不影响语义）
            窗起 = _属性窗口起(净, 命.start())
            for 路命 in re.finditer(r"#\[\s*path\b", 净[窗起:终]):
                引 = 原.find('"', 窗起 + 路命.end(), 终)
                if 引 >= 0:
                    终引 = 原.find('"', 引 + 1)
                    if 终引 > 引:
                        路 = 原[引 + 1 : 终引]
                        break
            if 路 is None:
                路 = 名配.group(1) + ".rs"
            挂载.append((父目录, 路))
    for 父目录, 路 in 挂载:
        候选 = f"{父目录}/{路}" if 父目录 else 路
        候选 = os.path.normpath(候选).replace("\\", "/")
        目标 = None
        if 候选 in 文件:
            目标 = 候选
        elif 候选.endswith(".rs") and (候选[:-3] + "/mod.rs") in 文件:
            目标 = 候选[:-3] + "/mod.rs"
        if 目标 is None or not 目标.endswith(".rs"):
            continue
        if 目标.rsplit("/", 1)[-1][:-3] in ("lib", "mod", "main"):
            continue  # 包根不是夹具（`mod lib;` 不是 Rust 能编的形状）
        出.add(目标)
    return 出


def 生产区文本(文本: str, 保串: bool = False) -> str:
    """去注释 + 抹掉 `#[cfg(test)]` 区 ⇒ 只剩生产代码。

    `保串=真` 时**保留字符串字面量**——数导出符号名必须保串（符号名就写在字符串里；
    实测撞到过：先去字面量会把 `export_name = "平台_调用"` 的名字抹成空白 ⇒ 数出 0 组）。

    ★ **按 `(保串, 文本)` 记忆化**（2026-09-27 · #224「共享一份扫描结果」）：本函数是**纯函数**
      —— 输出只由 `文本` 与 `保串` 决定（`去字面量` / `去注释保串` / `cfg测试区` 全是纯的）。
      而底下的 `_剥` 是**纯 Python 字符循环**，好几条判据各自把同一份文本重算一遍
      （实测 `--自测` 里 `并行生产区` 共 380 次、累计 6346 件、4616 ms）。键里放**文本本身**
      （不是它的哈希）⇒ 没有碰撞风险，不会因为「哈希撞了」而假绿；同文本必然同输出。
      跨夹具：文本相同则结果本就该相同 ⇒ 复用是**逐字正确**的，不是近似。
    """
    键 = (保串, 文本)
    记住 = _生产区缓存.get(键)
    if 记住 is not None:
        return 记住
    净 = 去字面量(文本) if not 保串 else 去注释保串(文本)
    出区 = list(净)
    for 起, 止 in cfg测试区(文本):
        for 游标 in range(起, min(止 + 1, len(出区))):
            出区[游标] = " "
    结果 = "".join(出区)
    _生产区缓存[键] = 结果
    return 结果


# 生产区文本的记忆化表（纯函数 ⇒ 可缓存；见 `生产区文本`）。
# 键含**文本本身**：上一轮自测夹具的文本留在表里只会占内存、不会串（同文本必然同输出）。
_生产区缓存: dict = {}


def 去注释保串(文本: str) -> str:
    """去注释（长度不变），**字符串字面量原样保留**。

    与 `去字面量` 共用同一个单次扫描器（`_剥`）——不许在这里另写一遍正则：
    早先这里也是「先 `/* */` 再 `//`」两遍，字符串里含 `//` 时会把收尾引号当注释剥掉
    （同 去字面量 的实测缺陷）⇒ 两条腿必须走同一个解析器。
    """
    return _剥(文本, 保串=True)


def 并行生产区(件表: list, 测试文件集=frozenset(), 保串: bool = False) -> dict:
    件表 = [(键, 文本) for 键, 文本 in 件表 if 文本 is not None]
    with ThreadPoolExecutor(max_workers=并发度) as 池:
        return dict(
            池.map(
                lambda 项: (
                    项[0],
                    "" if 项[0] in 测试文件集 else 生产区文本(项[1], 保串),
                ),
                件表,
            )
        )


def 收集导出(代码件: dict) -> dict:
    """导出符号名 → 出现处。`export_name` 取属性里的名字；`no_mangle` 取紧跟的 fn 名。"""
    出 = {}
    for 键, 文本 in 代码件.items():
        for 命 in 导出名模式.finditer(文本):
            行号 = 文本[: 命.start()].count("\n") + 1
            出.setdefault(命.group(1), []).append(f"{键}:{行号}")
        for 命 in re.finditer(r"#\[no_mangle\]", 文本):
            尾 = 文本[命.end() : 命.end() + 400]
            名配 = re.search(r"\bfn[ \t]+([A-Za-z_]\w*)", 尾)
            名 = 名配.group(1) if 名配 else "（未标名）"
            行号 = 文本[: 命.start()].count("\n") + 1
            出.setdefault(名, []).append(f"{键}:{行号}")
    return 出
