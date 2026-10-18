# -*- coding: utf-8 -*-
"""有界只读搜索 W3 声明；复用既有遍历实现。"""
import os
import re
import time
from pathlib import Path
from ..作业执行.shell import _取工作树

工具名 = "v1_search"
工具说明 = ("有界只读搜索；`关键词` 收一个词或一张词表（1..8，多词一次搜，按词分组回执）；"
        "操作留空发现，按最大深度、条数、时间预算提前返回。")

搜索排除目录 = (".git", "__pycache__", "node_modules", "target", "构建缓存", ".codegraph", "venv")
搜索文本后缀 = (".py", ".rs", ".js", ".ts", ".vue", ".json", ".md", ".toml", ".sh", ".txt",
           ".html", ".css", ".yml", ".yaml", ".c", ".h", ".go", ".java")
单件读上限 = 1024 * 1024     # 内容搜索时单个文件最多读这么多字节（防一个大件吃掉预算）

def _相对路径(仓根, 文件路径: Path) -> str:
    """尽量给仓内相对路径（仓外件给绝对路径）。"""
    try:
        return str(Path(文件路径).resolve().relative_to(Path(仓根).resolve()))
    except ValueError:
        return str(文件路径)


def _读文本行(文件路径: Path) -> list:
    """按行读文本（有界：单件最多 `单件读上限` 字节；坏字节不炸；读不动 ⇒ 空表）。"""
    try:
        with open(文件路径, "r", encoding="utf-8", errors="replace") as 句柄:
            return 句柄.read(单件读上限).splitlines()
    except OSError:
        return []


def 取搜索键集() -> tuple:
    """本件 `操作表` 里 `搜索` 那一档的 `必需` + `可选`（**唯一来源**）。

    与 `仓状态.py::声明键集` 同一修法（债务 2882 / 605）：键集不许手写第二份 ——
    `操作表` 是声明，本函数是它的派生口；`操作表` 定义在本件尾部 ⇒ 函数体内取
    （调用时才求值，不撞定义顺序）。
    """
    操作条 = 操作表["搜索"]
    return tuple(操作条.get("必需", ())) + tuple(操作条.get("可选", ()))


def _取范围整数(参数表: dict, 键名: str, 缺省值: int, 最小允许: int, 最大允许: int):
    """取一个带范围约束的整数（缺省给 `缺省值`）；非法 ⇒ `None`（调用方拒）。"""
    if 键名 not in 参数表:
        return 缺省值
    参数值 = 参数表[键名]
    if type(参数值) is not int or not 最小允许 <= 参数值 <= 最大允许:
        return None
    return 参数值


def _取关键词表(参数表: dict) -> tuple:
    """`关键词` 收单个字符串，也收字符串表（1..8）—— 多词一次搜，按词分组回执。"""
    原值 = 参数表.get("关键词")
    if isinstance(原值, str):
        原文表 = [原值]
    elif isinstance(原值, list) and all(isinstance(词条, str) for 词条 in 原值):
        原文表 = list(原值)
    else:
        return None, "参数拒绝：`关键词` 要是非空字符串，或 1..8 个非空字符串的表（收到 %r）" % (原值,)
    规范表 = [词条.strip() for 词条 in 原文表]
    if not 规范表 or len(规范表) > 8:
        return None, "参数拒绝：`关键词` 表要有 1..8 个词（收到 %d 个）" % len(规范表)
    if any(not 词条 for 词条 in 规范表):
        return None, "参数拒绝：`关键词` 表里不许有空串"
    return 规范表, ""


def 搜索派发(参数表: dict, 仓根) -> tuple:
    """`v1_search`：**有界只读搜索** —— 替代「跨仓全树 find/grep 撞 5 秒硬顶」。
    `最大深度` + `条数` + `时间预算秒` 三重有界，缺省保守、到点即早返回。"""
    if not isinstance(参数表, dict):
        return 2, "参数拒绝：arguments 要是对象"
    有效键表 = 取搜索键集()
    未知键 = sorted(set(参数表) - set(有效键表))
    if 未知键:
        return 2, "参数拒绝：未知键 %s；只认 %s" % ("、".join(未知键), "、".join(有效键表))
    模式 = 参数表.get("模式")
    if 模式 not in ("文件", "内容"):
        return 2, "参数拒绝：`模式` 要是 文件 / 内容（收到 %r）" % (模式,)
    关键词表, 词表错误 = _取关键词表(参数表)
    if 词表错误:
        return 2, 词表错误
    起点文本 = 参数表.get("路径前缀") or ""
    if not isinstance(起点文本, str):
        return 2, "参数拒绝：`路径前缀` 要是字符串（仓内相对目录，或绝对目录）"
    起点 = Path(起点文本).expanduser() if 起点文本.startswith("/") else Path(仓根) / 起点文本
    起点 = 起点.resolve()
    if not 起点.is_dir():
        return 2, "参数拒绝：`路径前缀` 不是目录：%s" % 起点
    最大深度 = _取范围整数(参数表, "最大深度", 4, 1, 12)
    条数上限 = _取范围整数(参数表, "条数", 50, 1, 200)
    预算秒 = _取范围整数(参数表, "时间预算秒", 3, 1, 5)
    # 字节预算口径与 `v1_context` 对齐（默认 8192 / 上限 16384）—— 光有条数上限挡不住「一条巨长行」。
    字节预算 = _取范围整数(参数表, "字节预算", 8192, 1024, 16384)
    if 最大深度 is None or 条数上限 is None or 预算秒 is None or 字节预算 is None:
        return 2, ("参数拒绝：`最大深度` 1..12 · `条数` 1..200 · `时间预算秒` 1..5 · "
                "`字节预算` 1024..16384（都要整数）")
    正则开 = bool(参数表.get("正则"))
    上下文行数 = _取范围整数(参数表, "上下文", 0, 0, 5)
    if 上下文行数 is None:
        return 2, "参数拒绝：`上下文` 0..5（整数，命中行前后各展示几行）"
    匹配器表 = []
    for 单词 in 关键词表:
        if not 正则开:
            匹配器表.append(None)
            continue
        try:
            匹配器表.append(re.compile(单词))
        except re.error as 失败因由:
            return 2, "参数拒绝：`关键词` %r 不是合法正则：%s" % (单词, 失败因由)
    截止时刻 = time.monotonic() + 预算秒
    起点深度 = len(起点.parts)
    分组表 = [[] for _ in 关键词表]
    命中数 = 0
    早返回 = False
    for 根目录, 目录表, 文件表 in os.walk(起点):
        if 命中数 >= 条数上限 or time.monotonic() > 截止时刻:
            早返回 = True
            break
        目录表[:] = sorted(子目录 for 子目录 in 目录表
                        if 子目录 not in 搜索排除目录 and not 子目录.startswith("."))
        if len(Path(根目录).parts) - 起点深度 >= 最大深度:
            目录表[:] = []
        for 文件名 in sorted(文件表):
            if 命中数 >= 条数上限 or time.monotonic() > 截止时刻:
                早返回 = True
                break
            文件路径 = Path(根目录) / 文件名
            if 模式 == "文件":
                for 序号, 单词 in enumerate(关键词表):
                    命中 = bool(匹配器表[序号].search(文件名)) if 正则开 else (单词 in 文件名)
                    if 命中 and 命中数 < 条数上限:
                        分组表[序号].append("%s  （文件）" % _相对路径(仓根, 文件路径))
                        命中数 += 1
                continue
            if not 文件名.endswith(搜索文本后缀):
                continue
            全行表 = _读文本行(文件路径)
            for 行号, 源码行 in enumerate(全行表, 1):
                for 序号, 单词 in enumerate(关键词表):
                    if 命中数 >= 条数上限:
                        break
                    命中 = bool(匹配器表[序号].search(源码行)) if 正则开 else (单词 in 源码行)
                    if not 命中:
                        continue
                    分组表[序号].append("%s:%d: %s" % (_相对路径(仓根, 文件路径), 行号,
                                                源码行.strip()[:200]))
                    命中数 += 1
                    if 上下文行数:
                        for 邻行号 in range(max(1, 行号 - 上下文行数),
                                        min(len(全行表), 行号 + 上下文行数) + 1):
                            if 邻行号 != 行号:
                                分组表[序号].append("%s:%d- %s" % (_相对路径(仓根, 文件路径), 邻行号,
                                                             全行表[邻行号 - 1].strip()[:200]))
                if 命中数 >= 条数上限 or time.monotonic() > 截止时刻:
                    早返回 = True
                    break
    # 条数过了还要过**字节预算**（一条巨长命中行就能吃掉整屏）⇒ 按预算收束（逐词各自收束，总量仍守预算）。
    累计字节 = 0
    for 序号 in range(len(分组表)):
        留存表 = []
        for 结果行 in 分组表[序号]:
            本行字节 = len(结果行.encode("utf-8")) + 1
            if 累计字节 + 本行字节 > 字节预算:
                早返回 = True
                break
            留存表.append(结果行)
            累计字节 += 本行字节
        分组表[序号] = 留存表
    输出行 = ["模式：%s%s" % (模式, "（正则）" if 正则开 else ""),
             "关键词：%s" % "、".join(关键词表), "路径前缀：%s" % 起点,
             "命中：%d 条（上限 %d）· 词数 %d" % (sum(len(分组表[序号]) for 序号 in range(len(分组表))),
                                          条数上限, len(关键词表)),
             "最大深度：%d · 时间预算：%d 秒（上限 5 秒）" % (最大深度, 预算秒),
             "字节预算：%d 字节（上限 16384）· 上下文：±%d 行" % (字节预算, 上下文行数)]
    if 早返回:
        输出行.append("★ 到条数上限 / 时间预算 / 字节预算即早返回：结果可能不全（收窄起点或加大预算）")
    for 序号, 单词 in enumerate(关键词表):
        输出行.append("")
        输出行.append("【%s】%d 条" % (单词, len(分组表[序号])))
        输出行 += 分组表[序号]
    return 0, "\n".join(输出行)



def 搜索(开工号, 参数表, 仓根):
    """按开工树复用既有搜索。"""
    if 开工号:
        工作树路径 = _取工作树(仓根, 开工号)
        if 工作树路径 is None or not 工作树路径.is_dir():
            return 2, "开工工作树不在 ⇒ 不搜索"
        仓根 = 工作树路径
    return 搜索派发(参数表, 仓根)


操作表 = {"搜索": {
    "说明": "只读文件名或内容搜索（可 `正则`）；`关键词` 收一个词或一张词表（1..8，多词一次搜）；`上下文` 给命中行前后各展示几行；起点可为仓内目录或外部只读目录。",
    "需开工ID": False, "必需": ["模式", "关键词"],
    "可选": ["路径前缀", "最大深度", "条数", "时间预算秒", "字节预算", "正则", "上下文"],
    "最短例": {"操作": "搜索", "参数": {"模式": "文件", "关键词": "作业"}},
    "处理": 搜索,
}}
