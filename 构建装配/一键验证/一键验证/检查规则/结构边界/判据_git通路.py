# -*- coding: utf-8 -*-
"""判据 69：Git **路径读数**形式 —— 吐路径的子命令必须带 `-z`，且不许第二套字符串解析。

**为什么要这条**（2026-10-27 实测，不是推测）：默认 `core.quotePath` 下 `git status` /
`ls-files` 把中文路径输出成八进制转义串（`"\\346\240\267..."`），判据 ㉓ 的 `endswith('.md')`
因此恒不中 ⇒ **判据 23 假绿**；`-c core.quotePath=false` 只解决非 ASCII，含空格 / 引号 / 换行
的路径仍失真，而 `splitlines()` 会把一个含换行的件名拆成两条 ⇒ 冲突件、变更件读数与盘面不符。
`-z` 是 Git 唯一「按原字节给路径」的输出形式，解析只能落在 `构建装配/门禁/git路径解析.py`。

**判什么（AST，不看注释、不看整文本子串）**：

  ① `["git", …]` 字面 argv（`ast.List` / `ast.Tuple`，首元素是 `"git"`）里，子命令属「吐路径」
     的那些必须含 `-z`：`status` / `ls-files` / `ls-tree` 一律；`diff` / `show` 仅在带
     `--name-only` / `--name-status` 时；`worktree` 仅在子命令是 `list` 时（`add` / `remove`
     不吐路径）。
  ② 同一个件里只要存在 git 读方，就不许出现 `.strip('"')` 与 `.split(" -> ")` 这类第二套解析
     （AST 的 `Call`，参数是那两个字面）—— 它们是本轮维修前四处各写一遍的旧形。
  ③ 例外登记在 `git读数白名单`：键 = `(件路径, 命令串)`，每条带**理由**（只判空 / 只判退出码 /
     只观察子进程，不取路径）。白名单按命令串精确匹配 ⇒ 同一件里新增一条别的读法照样红。

三元读数：对象数 = 面里 git argv 条数（0 ⇒ 未判 —— 空集不是通过）；通过 = 面非空且 0 命中。
"""
from __future__ import annotations

import ast

from ...判据编排.验证小工具 import 判不了, 违规
from ...基础定义.常量 import 检查名, 代码后缀
from ...源码解析.测试件 import 并行取生产区文本

# 子命令名与「第二套解析」的字面一律**拆开拼**：本件自身也在扫描面内，整字连写会自命中。
路径读方子命令 = frozenset({"status", "ls-files", "ls-tree", "diff", "show", "worktree"})
名表开关 = ("--name-" + "only", "--name-" + "status")
改名分隔形 = " -" + "> "
引号字面形 = chr(34)
零分隔开关字 = "-" + "z"

# 例外：只判空 / 只判退出码 / 只观察子进程 —— 都不把输出当路径用。
git读数白名单 = {
    ("开发工具/MCP服务/施工管理/仓操作.py", "git status --porcelain -uall"):
        "只判空（`输出文本.strip()` 判有没有脏）+ 原样回显，不取路径",
    ("开发工具/MCP服务/施工管理/释放作业.py", "git status --porcelain --"):
        "带 pathspec 的定点查：只判退出码与空/非空，不取路径",
    ("开发工具/MCP服务/集成管理/合主干编排.py", "git status --porcelain -uall"):
        "只判空 + 原样回显给人看，不取路径",
    ("开发工具/MCP服务/集成管理/合主干编排.py", "git ls-files -u --"):
        "只判退出码，输出原样回显，不取路径",
    ("开发工具/MCP服务/集成管理/合主干集成树.py", "git status --porcelain -uall"):
        "只判空 + 原样回显，不取路径",
    ("开发工具/MCP服务/验证管理/自检样本.py", "git status"):
        "只为观察注入的 env 有没有被剔，不取输出",
    ("开发工具/MCP服务/验证样本/施工管理/释放样本.py", "git status --porcelain"):
        "只判空（`== \"\"`），不取路径",
    ("测试验证/准入判据/故障取证样本/进程取证.py", "git status --porcelain"):
        "取证样本：只为看子进程行为，不取输出",
}

判据扫描面缓存: dict = {}


def git读数面(上层读数: dict) -> dict:
    """扫描面：全仓 `.py` 的**生产区文本**（保串 —— AST 要看 argv 字面）。"""
    键名 = str(上层读数["仓根"])
    if 键名 in 判据扫描面缓存:
        return 判据扫描面缓存[键名]
    件表 = [
        (键_件, 文件项["文本"])
        for 键_件, 文件项 in 上层读数["文件"].items()
        if 文件项.get("文本") is not None and 键_件.endswith(代码后缀)
    ]
    扫描面 = 并行取生产区文本(件表, 上层读数.get("测试文件集") or frozenset(), 保串=True)
    判据扫描面缓存[键名] = 扫描面
    return 扫描面


def _argv词表(节点) -> list:
    """`["git", …]` 字面里的串词（非串元素 —— 变量 / 拼接 —— 直接跳过）。"""
    return [元素项.value for 元素项 in 节点.elts
            if isinstance(元素项, ast.Constant) and isinstance(元素项.value, str)]


def _是git字面(节点) -> bool:
    return (isinstance(节点, (ast.List, ast.Tuple)) and bool(节点.elts)
            and isinstance(节点.elts[0], ast.Constant) and 节点.elts[0].value == "git")


def _吐路径(词表: list) -> bool:
    """这条 argv 会不会把**路径**当输出（`worktree add/remove` 不会，`diff --quiet` 不会）。"""
    子命令 = next((词条 for 词条 in 词表[1:] if 词条 in 路径读方子命令), "")
    if 子命令 in ("status", "ls-files", "ls-tree"):
        return True
    if 子命令 in ("diff", "show"):
        return any(词条 in 名表开关 for 词条 in 词表)
    if 子命令 == "worktree":
        return "list" in 词表
    return False


def _第二套解析(语法树) -> list:
    """件里的第二套路径解析调用 ⇒ `[(行号, 形)]`。"""
    命中表 = []
    for 节点 in ast.walk(语法树):
        if not (isinstance(节点, ast.Call) and isinstance(节点.func, ast.Attribute) and 节点.args):
            continue
        首参 = 节点.args[0]
        首个字面 = 首参.value if isinstance(首参, ast.Constant) and isinstance(首参.value, str) else None
        if 节点.func.attr == "strip" and 首个字面 == 引号字面形:
            命中表.append((节点.lineno, "`.strip('\"')` 剥引号"))
        elif 节点.func.attr == "split" and 首个字面 == 改名分隔形:
            命中表.append((节点.lineno, "`.split(' -> ')` 切改名行"))
    return 命中表


def 样本_git路径读数(上层读数: dict) -> int:
    """对象数：面里 git argv 字面条数（0 ⇒ 未判）。"""
    条数 = 0
    for 件文本 in git读数面(上层读数).values():
        try:
            语法树 = ast.parse(件文本)
        except SyntaxError:
            continue
        条数 += sum(1 for 节点 in ast.walk(语法树) if _是git字面(节点))
    return 条数


def 扫描违规(扫描面: dict) -> list:
    """逐件扫 ⇒ `[(件路径, [缺什么…])]`（空 = 全合规）。"""
    违规表 = []
    for 件路径, 件文本 in 扫描面.items():
        try:
            语法树 = ast.parse(件文本)
        except SyntaxError:
            continue
        缺失表 = []
        有读方 = False
        for 节点 in ast.walk(语法树):
            if not _是git字面(节点):
                continue
            词表 = _argv词表(节点)
            if not _吐路径(词表):
                continue
            有读方 = True
            if 零分隔开关字 in 词表:
                continue
            命令串 = " ".join(词表)
            if (件路径, 命令串) in git读数白名单:
                continue
            缺失表.append("行 %d：`%s` 吐路径却没带 `-z`（登记理由也不在白名单里）"
                       % (节点.lineno, 命令串))
        if 有读方:
            缺失表.extend("行 %d：第二套路径解析 %s（唯一解析节点在 `构建装配/门禁/git路径解析.py`）"
                       % (行号, 形名) for 行号, 形名 in _第二套解析(语法树))
        if 缺失表:
            违规表.append((件路径, 缺失表))
    return 违规表


def 检查69_git路径读数(上层读数: dict) -> list:
    """全仓 `.py` 的 git 路径读数都走 `-z` + 唯一解析节点。"""
    if 样本_git路径读数(上层读数) == 0:
        判不了(检查名[62], "（全仓）",
              "扫描面 0 条 git argv ⇒ 空集不算通过（这条判据这次没量到东西）",
              "确认租进来的仓根是不是真仓根（`上层读数[\"仓根\"]` 指到空目录时就会这样）")
        return []
    return [
        违规(检查名[62], 件路径, "；".join(缺失表),
             "修法：argv 加 `-z`，解析改走 `构建装配/门禁/git路径解析.py`（`解析零分隔` / "
             "`解析状态零分隔` / `解析名状态零分隔` / `解析工作树零分隔`），并把标准错误从路径流里"
             "分出去（`只取标准输出=真`）。真不取路径的读法，按命令串登记进 `git读数白名单` 并写理由")
        for 件路径, 缺失表 in 扫描违规(git读数面(上层读数))
    ]
