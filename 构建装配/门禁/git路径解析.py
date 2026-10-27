# -*- coding: utf-8 -*-
"""Git **路径读数**的唯一解析节点（NUL 协议；全仓只此一处把 `-z` 输出变成路径）。

**为什么必须是 `-z`**：`core.quotePath=false` 只关「非 ASCII 加引号」，含**空格 / 引号 / 换行**
的路径照样失真；而 `splitlines()` 会把一个含换行的件名拆成两条 ⇒ 冲突件、变更件、忽略件
的读数与真实盘面不符。`-z` 是 Git 唯一「按原字节给路径」的输出形式，别处不许再手动切字符串。

**各子命令的协议**（2026-10-27 用真仓 `中文 名.txt` / 含换行件 / 改名件实测，不是照文档抄）：

    status --porcelain -z -uall      `XY␠路径\0`；改名 / 复制是 `XY␠新名\0旧名\0`（只回新名）
    diff --name-status -z            `码\0路径\0`；改名 / 复制是 `R100\0旧名\0新名\0`（回新名）
    diff --name-only -z              `路径\0` 流（改名只出现新名）
    ls-files … -z / ls-tree -r --name-only -z / show --name-only --format= -z   同上，`路径\0` 流
    worktree list --porcelain -z    字段以 `\0` 分、**记录以 `\0\0` 收尾**

**本件为什么住在 `构建装配/门禁/`**：`判据_拓扑` 的层序里 `开发工具/` 与 `测试验证/` 不在层序
⇒ 它们可以 import `构建装配`，反向不行 ⇒ 双侧共用的解析只能住在 `构建装配/` 下（同 `硬顶硬顶常量.py`）。
"""


def 解析零分隔(标准输出: str) -> list:
    """`路径\0` 流（`--name-only` / `ls-files` / `ls-tree` / `show --name-only`）。"""
    return [路径 for 路径 in (标准输出 or "").split("\0") if 路径]


def 解析状态零分隔(标准输出: str) -> list:
    """`status --porcelain -z` ⇒ `[(两字码, 路径)]`；改名 / 复制回**新名**（= 旧口径 `[-1]`）。"""
    条目表 = 解析零分隔(标准输出)
    结果表 = []
    序次 = 0
    while 序次 < len(条目表):
        条目 = 条目表[序次]
        状态码 = 条目[:2]
        路径 = 条目[3:] if len(条目) > 3 else ""
        是否改名 = "R" in 状态码 or "C" in 状态码
        if 是否改名:
            序次 += 1  # 紧跟的一条是**旧名**：改名只回新名，旧名不进结果（与旧 split 口径一致）
        if 路径:
            结果表.append((状态码, 路径))
        序次 += 1
    return 结果表


def 解析名状态零分隔(标准输出: str) -> list:
    """`diff --name-status -z` ⇒ `[(码, 路径)]`；改名 / 复制回**新名**。"""
    条目表 = 解析零分隔(标准输出)
    结果表 = []
    序次 = 0
    while 序次 < len(条目表):
        状态码 = 条目表[序次]
        路径 = 条目表[序次 + 1] if 序次 + 1 < len(条目表) else ""
        if 状态码[:1] in ("R", "C") and 序次 + 2 < len(条目表):
            序次 += 2  # `R100\0旧\0新\0`：新名是**后**一条
            路径 = 条目表[序次]
        if 路径:
            结果表.append((状态码, 路径))
        序次 += 2
    return 结果表


def 解析工作树零分隔(标准输出: str) -> list:
    """`worktree list --porcelain -z` ⇒ `[{"worktree": 路径, "HEAD": …, "branch": …, …}]`。"""
    记录表 = []
    for 记录文本 in (标准输出 or "").split("\0\0"):
        字段表 = {}
        for 字段 in 记录文本.split("\0"):
            if not 字段.strip():
                continue
            字段名, _, 值 = 字段.partition(" ")
            字段表[字段名] = 值
        if 字段表.get("worktree"):
            记录表.append(字段表)
    return 记录表
