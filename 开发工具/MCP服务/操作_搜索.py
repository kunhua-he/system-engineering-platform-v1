# -*- coding: utf-8 -*-
"""有界只读搜索 W3 声明；复用既有遍历实现。"""
import os
import time
from pathlib import Path
from .shell import _取工作树

工具名 = "v1_search"
工具说明 = "有界只读搜索；操作留空发现，按最大深度、条数上限、时间预算提前返回。"

搜索有效键 = ("模式", "关键词", "起点", "最大深度", "条数上限", "时间预算秒")
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


def _取范围整数(参数表: dict, 键名: str, 缺省值: int, 最小允许: int, 最大允许: int):
    """取一个带范围约束的整数（缺省给 `缺省值`）；非法 ⇒ `None`（调用方拒）。"""
    if 键名 not in 参数表:
        return 缺省值
    参数值 = 参数表[键名]
    if type(参数值) is not int or not 最小允许 <= 参数值 <= 最大允许:
        return None
    return 参数值


def 搜索派发(参数表: dict, 仓根) -> tuple:
    """`v1_search`：**有界只读搜索** —— 替代「跨仓全树 find/grep 撞 5 秒硬顶」。
    `最大深度` + `条数上限` + `时间预算秒` 三重有界，缺省保守、到点即早返回。"""
    if not isinstance(参数表, dict):
        return 2, "参数拒绝：arguments 要是对象"
    未知键 = sorted(set(参数表) - set(搜索有效键))
    if 未知键:
        return 2, "参数拒绝：未知键 %s；只认 %s" % ("、".join(未知键), "、".join(搜索有效键))
    模式 = 参数表.get("模式")
    if 模式 not in ("文件", "内容"):
        return 2, "参数拒绝：`模式` 要是 文件 / 内容（收到 %r）" % (模式,)
    关键词 = 参数表.get("关键词")
    if not isinstance(关键词, str) or not 关键词.strip():
        return 2, "参数拒绝：`关键词` 要是非空字符串（收到 %r）" % (关键词,)
    关键词 = 关键词.strip()
    起点文本 = 参数表.get("起点") or ""
    if not isinstance(起点文本, str):
        return 2, "参数拒绝：`起点` 要是字符串（仓内相对目录，或绝对目录）"
    起点 = Path(起点文本).expanduser() if 起点文本.startswith("/") else Path(仓根) / 起点文本
    起点 = 起点.resolve()
    if not 起点.is_dir():
        return 2, "参数拒绝：`起点` 不是目录：%s" % 起点
    最大深度 = _取范围整数(参数表, "最大深度", 4, 1, 12)
    条数上限 = _取范围整数(参数表, "条数上限", 50, 1, 200)
    预算秒 = _取范围整数(参数表, "时间预算秒", 3, 1, 5)
    if 最大深度 is None or 条数上限 is None or 预算秒 is None:
        return 2, "参数拒绝：`最大深度` 1..12 · `条数上限` 1..200 · `时间预算秒` 1..5（都要整数）"
    截止时刻 = time.monotonic() + 预算秒
    起点深度 = len(起点.parts)
    结果表 = []
    早返回 = False
    for 根目录, 目录表, 文件表 in os.walk(起点):
        if len(结果表) >= 条数上限 or time.monotonic() > 截止时刻:
            早返回 = True
            break
        目录表[:] = sorted(子目录 for 子目录 in 目录表
                        if 子目录 not in 搜索排除目录 and not 子目录.startswith("."))
        if len(Path(根目录).parts) - 起点深度 >= 最大深度:
            目录表[:] = []
        for 文件名 in sorted(文件表):
            if len(结果表) >= 条数上限 or time.monotonic() > 截止时刻:
                早返回 = True
                break
            文件路径 = Path(根目录) / 文件名
            if 模式 == "文件":
                if 关键词 in 文件名:
                    结果表.append("%s  （文件）" % _相对路径(仓根, 文件路径))
                continue
            if not 文件名.endswith(搜索文本后缀):
                continue
            for 行号, 源码行 in enumerate(_读文本行(文件路径), 1):
                if 关键词 in 源码行:
                    结果表.append("%s:%d: %s" % (_相对路径(仓根, 文件路径), 行号,
                                            源码行.strip()[:200]))
                    if len(结果表) >= 条数上限 or time.monotonic() > 截止时刻:
                        早返回 = True
                        break
    输出行 = ["模式：%s" % 模式, "关键词：%s" % 关键词, "起点：%s" % 起点,
             "命中：%d 条（上限 %d）" % (len(结果表), 条数上限),
             "最大深度：%d · 时间预算：%d 秒（上限 5 秒）" % (最大深度, 预算秒)]
    if 早返回:
        输出行.append("★ 到条数上限 / 时间预算即早返回：结果可能不全（收窄起点或加大预算）")
    输出行.append("")
    输出行 += 结果表
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
    "说明": "只读文件名或内容子串搜索；起点可为仓内目录或外部只读目录。",
    "需开工ID": False, "必需": ["模式", "关键词"],
    "可选": ["起点", "最大深度", "条数上限", "时间预算秒"],
    "最短例": {"操作": "搜索", "参数": {"模式": "文件", "关键词": "作业"}},
    "处理": 搜索,
}}
