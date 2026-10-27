# -*- coding: utf-8 -*-
"""判据 68：条款写口占用保护 —— 往 `条款` 表 `insert or replace` 的件必须先过占用检查。

**为何要有这一条**（实测，不是推测）：`条款` 表是**已删 md 的唯一存本**（`表定义.分片源件表`：
`文档路径` 是源件路径，源件不在 ⇒ 保住库里的行）。写口 `开发工具/信息核心/记条款.py::记条款`
收尾是直写 `insert or replace`（表 `条款`），主键 `(文档路径, 序号)` —— 它只读 `权威档`，从不检查该序号
是否已被占用。实测后果：往 `测试验证/测试案例/形状.md` §10 写新节，把库里原有整节正文静默替换
（正文 1824 字 → 681 字）；库行数不变、闸 1 / 闸 2 / 案例全绿 —— 因为判据 ㊴ 只核「节号在不在」，
10 一直在，三处 §10.x 引用于是落到新节编号下。原正文已由一次恢复提交还原，但机制当时未修。

修法是两件套：① 写口默认拒覆盖 + 占用检查与写入同一原子事务（`BEGIN IMMEDIATE`）；
② 本条判据守**它不许回潮**。

**判什么（AST，不看注释、不看整文本子串）**：生产区 `.py` 里凡解析出**真正执行的** SQL 调用
（`<任意>.execute("insert or replace into 条款 …")` 这一形，语句串从 `Constant` / 串拼接里取）
的件，必须在该**同一函数**里满足四件（缺一即红）：

  · `x = 检查占用(…)` —— 占用检查**被调用且结果被接住**（光有 `def 检查占用` 定义不算）；
  · 该调用的行号在写口调用**之前**（保护排在写后 = 拦不住覆盖）；
  · 写前存在一个 `if`：条件**用到占用结果** ∧ 条件里对**开关名取反**（`not 允许覆盖`）∧ 块里有
    `return` 非零常量 ⇒ 才是真拒写分支（读开关不用它拦、或断言被删，都判红）；
  · 开关名本身要**从 `"覆盖" in 字段表` 这一形赋值得到**（AST 的 `Compare` + `In`），
    且件里有 `--覆盖` 用法串（`Constant` 文本里）——否则开关不可达。

⇒ 注释里凑字面量、只定义不调用、开关读而不拒、保护写在写后、断言被删，全部判红
（五种反例的身份证住 `自检_条款占用.py`，挂 `--自测` 的机制断言）。

**不算写口的两类**：测试夹具（文件名以 `夹具` / `注入` / `自测` / `自检` 开头）是造夹具数据，
不是生产写口 —— 它们在 `条款` 里塞样本行，天然不持有占用保护；扫进来就是假红。

三元读数：通过 = 面非空且 0 命中；失败 = 逐件报出缺哪一件；未判 = 面里 0 件 `.py`（空集不算通过）。
"""
from __future__ import annotations

import ast

from ...判据编排.验证小工具 import 判不了, 违规
from ...基础定义.判据取值常量 import 检查名, 代码后缀
from ...源码解析.测试件 import 并行取生产区文本


# 语句与开关名一律**拆开拼**：本件自身也在扫描面内，整字连写会被自身当成写口命中。
条款表名 = "条" + "款"
写口语句 = "insert or replace into " + 条款表名
占用节点名 = "检查" + "占用"
开关字面 = "--" + "覆盖"
开关键名 = "覆盖"
# 执行方法名：`连接.execute(…)` / 游标同名形都收（只认 SQL 文本里带写口语句的那一条）。
执行方法名 = frozenset({"execute", "executemany", "executescript"})
# 测试夹具前缀：它们是造夹具数据的，不是生产写口（口径见件头）。
夹具前缀 = ("夹具", "注入", "自测", "自检")


def _常量文本(节点) -> str:
    """取节点里**静态**的串文本（`Constant` / `JoinedStr` 的常量段）；非静态 ⇒ 空串。"""
    if isinstance(节点, ast.Constant) and isinstance(节点.value, str):
        return 节点.value
    if isinstance(节点, ast.JoinedStr):
        return "".join(_常量文本(取值) for 取值 in 节点.values if not isinstance(取值, ast.FormattedValue))
    return ""


def _是写口调用(节点) -> bool:
    """是不是**真正执行**的条款写口调用（AST 节点，不是文本命中）。"""
    if not isinstance(节点, ast.Call) or not 节点.args:
        return False
    被调对象 = 节点.func
    if not (isinstance(被调对象, ast.Attribute) and 被调对象.attr in 执行方法名):
        return False
    语句 = " ".join(_常量文本(节点.args[0]).split()).lower()
    return 写口语句 in 语句


def _函数边界(语法树) -> list:
    """`[(函数节点, 起行, 止行)]` —— 按行区间判某个调用属于哪个函数。"""
    边界清单 = []
    for 节点 in ast.walk(语法树):
        if isinstance(节点, (ast.FunctionDef, ast.AsyncFunctionDef)):
            止行 = getattr(节点, "end_lineno", 节点.lineno) or 节点.lineno
            边界清单.append((节点, 节点.lineno, 止行))
    return 边界清单


def _所属函数(节点, 边界表: list):
    """取**最内层**包住该节点的函数；模块级 ⇒ None。"""
    命中 = None
    for 函数节点, 起行, 止行 in 边界表:
        if 起行 <= 节点.lineno <= 止行 and (命中 is None or 起行 >= 命中[1]):
            命中 = (函数节点, 起行)
    return 命中[0] if 命中 else None


def _赋值目标名(节点) -> list:
    目标 = 节点.targets if isinstance(节点, ast.Assign) else [节点.target]
    return [名节点.id for 单个目标 in 目标 for 名节点 in ast.walk(单个目标) if isinstance(名节点, ast.Name)]


def _末名(被调对象) -> str:
    return 被调对象.id if isinstance(被调对象, ast.Name) else getattr(被调对象, "attr", "")


def _占用调用(函数节点) -> tuple:
    """`(接住结果的名字集, 最早调用行)` —— 只认赋值形，裸调用（结果丢弃）不算。"""
    名集, 行表 = set(), []
    for 节点 in ast.walk(函数节点):
        if not isinstance(节点, (ast.Assign, ast.AnnAssign)):
            continue
        if isinstance(节点.value, ast.Call) and _末名(节点.value.func) == 占用节点名:
            名集.update(_赋值目标名(节点))
            行表.append(节点.lineno)
    return 名集, (min(行表) if 行表 else None)


def _开关名(函数节点) -> set:
    """`允许覆盖 = "覆盖" in 字段表` 这一形赋出的名字集（AST `Compare` + `In`）。"""
    名集 = set()
    for 节点 in ast.walk(函数节点):
        if not isinstance(节点, (ast.Assign, ast.AnnAssign)):
            continue
        取值 = 节点.value
        if not isinstance(取值, ast.Compare):
            continue
        有包含 = any(isinstance(操作, ast.In) for 操作 in 取值.ops)
        有开关字面 = any(_常量文本(比较边) == 开关键名 for 比较边 in [取值.left, *取值.comparators])
        有字段名 = any(isinstance(名节点, ast.Name) and 名节点.id == "字段表"
                      for 比较边 in 取值.comparators for 名节点 in ast.walk(比较边))
        if 有包含 and 有开关字面 and 有字段名:
            名集.update(_赋值目标名(节点))
    return 名集


def _名字集(节点) -> set:
    return {名节点.id for 名节点 in ast.walk(节点) if isinstance(名节点, ast.Name)}


def _拒写分支(函数节点, 占用名: set, 开关名: set) -> list:
    """写前是否真有「用占用结果 + 取反开关 ⇒ 非零 return」的分支 ⇒ `[(行, 是否在写前)]`。"""
    命中表 = []
    for 节点 in ast.walk(函数节点):
        if not isinstance(节点, ast.If):
            continue
        条件式 = 节点.test
        有占用 = bool(_名字集(条件式) & 占用名)
        有取反开关 = any(
            isinstance(子节点, ast.UnaryOp) and isinstance(子节点.op, ast.Not) and (_名字集(子节点.operand) & 开关名)
            for 子节点 in ast.walk(条件式)
        )
        有拒写 = any(
            isinstance(子节点, ast.Return) and isinstance(子节点.value, ast.Constant)
            and isinstance(子节点.value.value, int) and 子节点.value.value != 0
            for 子节点 in ast.walk(节点)
        )
        if 有占用 and 有取反开关 and 有拒写:
            命中表.append(节点.lineno)
    return 命中表


def _判一个写口(函数节点, 写口行: int, 有用法串: bool) -> list:
    缺失 = []
    占用名, 占用行 = _占用调用(函数节点)
    开关名 = _开关名(函数节点)
    if not 占用名:
        缺失.append("没有调用占用检查（`检查占用` 的返回值一处都没被接住 —— 只定义不调用不算）")
    elif 占用行 is not None and 占用行 > 写口行:
        缺失.append("占用检查排在 `insert or replace` 之后 ⇒ 拦不住覆盖")
    if not 开关名:
        缺失.append("没有读显式开关（`\"覆盖\" in 字段表` 这一形一处都没有）")
    elif not _拒写分支(函数节点, 占用名, 开关名):
        缺失.append("读了开关却没拿它拦（写前没有「占用结果 + `not 开关` ⇒ 非零 return」的分支）"
                    "⇒ 缺保护照样覆盖")
    elif min(_拒写分支(函数节点, 占用名, 开关名)) > 写口行:
        缺失.append("拒写分支排在 `insert or replace` 之后 ⇒ 写已经发生，拦不住覆盖")
    if not 有用法串:
        缺失.append("用法串里没有 `--覆盖`（开关存在但没人知道要加）")
    return 缺失


def _有用法串(语法树) -> bool:
    return any(
        isinstance(节点, ast.Constant) and isinstance(节点.value, str) and 开关字面 in 节点.value
        for 节点 in ast.walk(语法树)
    )


def 扫写口(写口面: dict) -> list:
    """扫一遍 ⇒ `[(路径, 缺失表)]`；缺失表为空 = 该写口合规（不列入输出）。"""
    输出缓冲 = []
    for 路径 in sorted(写口面):
        if 路径.rsplit("/", 1)[-1].startswith(夹具前缀):
            continue
        源文本 = 写口面[路径] or ""
        if 写口语句 not in 源文本:  # 便宜的预筛（真相在 AST，不靠这行判）
            continue
        try:
            语法树 = ast.parse(源文本)
        except SyntaxError as 错误:
            输出缓冲.append((路径, [f"源码解析不了（第 {错误.lineno} 行语法错）—— 本条只认 AST，"
                                     f"解析失败即拒，不许当通过"]))
            continue
        边界表 = _函数边界(语法树)
        写口集 = [节点 for 节点 in ast.walk(语法树) if _是写口调用(节点)]
        if not 写口集:
            continue
        用法串 = _有用法串(语法树)
        缺失 = []
        for 写口 in sorted(写口集, key=lambda 节点: getattr(节点, "lineno", 0)):
            函数节点 = _所属函数(写口, 边界表)
            if 函数节点 is None:
                缺失.append(f"第 {getattr(写口, 'lineno', 0)} 行的条款写口在模块级 —— 占用保护必须在同一函数里、写之前")
                continue
            缺失.extend(_判一个写口(函数节点, getattr(写口, "lineno", 0), 用法串))
        if 缺失:
            输出缓冲.append((路径, 缺失))
    return 输出缓冲


# 面在一次运行里不变（判定与对象数各取一次）⇒ 按仓根缓存（同判据 61 / ㊳ 的先例）。
_写口面缓存: dict = {}


def 条款写口面(上层读数: dict) -> dict:
    """扫描面：全仓 `.py` 的**生产区文本**（**保串** —— AST 要解析 SQL 语句与开关字面）。"""
    键名 = str(上层读数["仓根"])
    if 键名 in _写口面缓存:
        return _写口面缓存[键名]
    件表 = [
        (键_件, 文件项["文本"])
        for 键_件, 文件项 in 上层读数["文件"].items()
        if 文件项.get("文本") is not None and 键_件.endswith(代码后缀)
    ]
    扫描面 = 并行取生产区文本(件表, 上层读数.get("测试文件集") or frozenset(), 保串=True)
    _写口面缓存[键名] = 扫描面
    return 扫描面


def 样本_条款写口(上层读数: dict) -> int:
    """对象数：面里的 `.py` 件数（0 ⇒ 未判）。"""
    return sum(1 for 键名 in 条款写口面(上层读数) if 键名.endswith(".py"))


def 检查68_条款写口占用(上层读数: dict) -> list:
    """全仓 `.py` 里每个条款写口都带占用保护。"""
    if 样本_条款写口(上层读数) == 0:
        判不了(检查名[61], "（全仓）",
              "扫描面 0 件 `.py` ⇒ 空集不算通过（空集不是「没问题」，是「这条判据这次没量到东西」）",
              "确认传进来的仓根是不是真的仓根（`上层读数[\"仓根\"]` 指到空目录时就会这样）")
        return []
    return [
        违规(检查名[61], 路径,
             "条款写口缺占用保护：" + "；".join(缺失表),
             "修法：写口照 `记条款.py::记条款` 的形状补四件 —— ① `当前标题, 当前正文 = 检查占用(…)` "
             "接住占用结果（同一 `BEGIN IMMEDIATE` 事务里）；② `允许覆盖 = \"覆盖\" in 字段表` 读开关；"
             "③ 写前 `if 当前正文.strip() and not 允许覆盖: return 1` 真拒写；④ 用法串写 `--覆盖`。"
             "`条款` 是已删 md 的唯一存本，一次静默覆盖即不可逆，而库行数不变、其它判据全绿 ⇒ "
             "只有本条能把它报出来")
        for 路径, 缺失表 in 扫写口(条款写口面(上层读数))
    ]
