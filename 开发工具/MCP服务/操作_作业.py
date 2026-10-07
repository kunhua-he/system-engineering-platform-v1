# -*- coding: utf-8 -*-
"""`v1_job` / `v1_search` 的**工具面** —— 导出 `操作表`（dict），供加载器 glob 合并进工具面。

**形状与 `工具.py::工具表` 逐项同形**：`名称 -> (实现, 标题, 说明, 模式)`；实现签名
`(参数表, 仓根) -> (退出码, 输出文本)`，与其余工具一致。本件**零业务逻辑**：作业四操作全在
`作业.py`，本件只声明 schema 与转发；**有界搜索**（`v1_search`）的实现也在本件 ——
它是只读的纯 Python 遍历，不落盘、不起子进程。

**有界搜索为什么要有**：跨仓大目录 `find`/`grep` 连续两次撞 5 秒硬顶（多路代理实测）⇒
`最大深度` + `条数上限` + `时间预算秒` **三重有界**，缺省保守、到点即早返回，替代同步硬顶。
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))     # 开发工具/
from .作业 import 派发 as 作业派发  # noqa: E402

搜索有效键 = ("模式", "关键词", "起点", "最大深度", "条数上限", "时间预算秒")
搜索排除目录 = (".git", "__pycache__", "node_modules", "target", "构建缓存", ".codegraph", "venv")
搜索文本后缀 = (".py", ".rs", ".js", ".ts", ".vue", ".json", ".md", ".toml", ".sh", ".txt",
           ".html", ".css", ".yml", ".yaml", ".c", ".h", ".go", ".java")
单件读上限 = 1024 * 1024     # 内容搜索时单个文件最多读这么多字节（防一个大件吃掉预算）

作业模式 = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "操作": {"type": "string", "enum": ["start", "status", "log", "cancel"], "description":
               "start=提交一个新后台作业（只启动不等待，秒级回任务ID）；status=只读查状态；"
               "log=读有界日志片段；cancel=只杀本作业进程组（终态幂等）。"},
        "命令": {"type": "string", "minLength": 1, "description":
               "start 用（与 `具名` 二选一）：要后台执行的 shell 命令，原样交 /bin/sh。"
               "**长活走这里**：跨仓 find/grep、gh/git ls-remote、cargo 一类。"},
        "具名": {"type": "string", "enum": ["闸0", "自测", "案例", "建库", "放行"], "description":
               "start 用（与 `命令` 二选一）：具名长活。`放行` = 闸0 + 判据自测 + 案例（与 "
               "pre-commit 钩子同一组命令）⇒ `v1_gate` 的放行档调它。"},
        "开工ID": {"type": "string", "maxLength": 32, "description":
                "start 可选：在这条开工的工作树里跑；留空=当前服务仓根。"},
        "超时秒": {"type": "integer", "minimum": 1, "maximum": 5, "default": 5, "description":
               "start 可选：**启动握手**等待秒数（≤5）。**不是**作业运行时预算 —— "
               "作业预算由规则库（类 安全边界）给，超顶压回硬顶。"},
        "任务ID": {"type": "string", "maxLength": 64, "description":
                "status/log/cancel 必填：start 返回的 32 位十六进制。"},
        "偏移": {"type": "integer", "minimum": 0, "description":
               "log 可选：从日志第几**字节**起读（默认 0；超出长度夹到末尾）。"},
        "流": {"type": "string", "enum": ["标准输出", "标准错误"], "default": "标准输出",
             "description": "log 可选：读哪条流的日志。"},
    },
    "required": ["操作"],
}

搜索模式 = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "模式": {"type": "string", "enum": ["文件", "内容"], "description":
               "文件=按文件名匹配；内容=按行内容匹配（普通子串，不是正则）。"},
        "关键词": {"type": "string", "minLength": 1, "description": "匹配词。"},
        "起点": {"type": "string", "description":
               "仓内相对目录（默认仓根），或绝对目录（如别的仓的根）—— 只读。"},
        "最大深度": {"type": "integer", "minimum": 1, "maximum": 12, "default": 4,
                 "description": "相对起点的最大层数（缺省 4，保守）。"},
        "条数上限": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50,
                 "description": "命中条数上限（缺省 50）。"},
        "时间预算秒": {"type": "integer", "minimum": 1, "maximum": 5, "default": 3,
                  "description": "本次搜索的墙钟预算（缺省 3、上限 5）—— 到点即早返回，"
                               "保证本工具进得了同步硬顶。"},
    },
    "required": ["模式", "关键词"],
}


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


操作表 = {
    "v1_job": (作业派发, "后台作业",
             "本地 shell 长活的**异步路**（提交 + 轮询 + 取消）。`操作`：start 提交（只启动不等待，"
             "秒级回 任务ID；`命令` 与 `具名` 二选一）、status 只读查状态、log 读有界日志片段、"
             "cancel 只杀本作业进程组（终态幂等）。作业**运行时上限从规则库读**（类 安全边界），"
             "`超时秒` 只用于 ≤5 秒**启动握手**；状态与日志都落盘（服务重载不丢，失联收敛成"
             "`崩溃失联`，不静默当成功）。副作用命令绝不自动重试。", 作业模式),
    "v1_search": (搜索派发, "有界搜索",
                "有界只读搜索（替代跨仓全树 find/grep 撞 5 秒硬顶）：`模式` 文件/内容 · `关键词` · "
                "`起点`（仓内相对或绝对目录）· `最大深度`（默认 4）· `条数上限`（默认 50）· "
                "`时间预算秒`（默认 3、上限 5）。到上限/预算即早返回，缺省保守。", 搜索模式),
}
