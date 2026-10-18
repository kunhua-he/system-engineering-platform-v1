# -*- coding: utf-8 -*-
"""判据 60：样本在临时仓里跑 git 必须做环境隔离（541 / 545 同源缺陷的判据化）。

依据：541 腿实测 —— 裸仓根服务把 `GIT_DIR`/`GIT_WORK_TREE` 注入进程环境，样本再在临时仓里
跑 `git`，子进程**继承**了这几个键 ⇒ `git add` 落到**外层真仓索引**（`--git-dir` 指真仓、
`--show-toplevel` 仍是临时仓）。545 腿的 `库快照样本.py` 又因**漏用** `干净环境()` 把自建
临时仓的 `git add` 写进外层暂存索引、损坏 index。

**面**：名字含「样本」的 `.py` 件里、参数表出现 `"git"` 字面量的 `subprocess.run` /
`subprocess.Popen` 调用（只钉真跑 git 的那类调用，非 git 的 subprocess 调用不误伤）。
**规则**：这些调用必须带 `env=` 关键字（唯一权威 = `开发工具/MCP服务/集成管理/合主干有界跑.py::干净环境`，
它剔掉 `GIT_*` 定位键）。

**测哪一份**：被扫仓里有「名字含样本的 `.py`」就扫它（真仓 / 反向样本的注入仓）；一件都没有
（干净合成夹具）就退回**本验证器所在仓** —— 本条的对象是「本仓的样本 git 调用面」，与夹具无关
（同判据 ㊽ 的口径）。

**三元读数**：通过 = 面非空且无缺 `env=` 的调用；失败 = 逐条报出（件:行）；未判 = 面 0 件。
"""
from __future__ import annotations

import ast
import os
from pathlib import Path

from ...判据编排.验证小工具 import 判不了, 违规, 取相对路径
from ...基础定义.常量 import 仓根, 检查名, 跳过目录, 临时目录前缀

# 运行口：`subprocess` 上会起子进程的调用名
运行口名表 = ("run", "Popen", "check_call", "check_output")
# 只认「名字含样本」的 `.py` 件（口径写在名字里，不散落文档）
样本名含 = "样本"


def 是git调用(节点: ast.Call) -> bool:
    """调用的参数表里出现 `"git"` 字符串字面量 ⇒ 是真跑 git 的调用。"""
    for 实参 in 节点.args:
        if isinstance(实参, ast.Constant) and 实参.value == "git":
            return True
        if isinstance(实参, ast.List):
            for 表项 in 实参.elts:
                if isinstance(表项, ast.Constant) and 表项.value == "git":
                    return True
    return False


def 带环境关键字(节点: ast.Call) -> bool:
    """调用带了 `env=` 关键字 ⇒ 调用方另行指定了子进程环境（环境隔离已做）。"""
    return any(关键词.arg == "env" for 关键词 in 节点.keywords)


def 扫样本git隔离(扫根: Path) -> tuple:
    """走树 ⇒ `({相对路径: 首现行号}, 面调用数)`。面调用数 = 命中的 git 子进程调用总数。"""
    命中 = {}
    面数 = 0
    扫根 = Path(扫根)
    for 根目录, 子目录表, 文件表 in os.walk(扫根):
        子目录表[:] = [目录名 for 目录名 in 子目录表
                   if 目录名 not in 跳过目录
                   and not 目录名.startswith(临时目录前缀)
                   and not 目录名.startswith(".")]
        for 名称 in 文件表:
            if not 名称.endswith(".py") or 样本名含 not in 名称:
                continue
            件路径 = Path(根目录) / 名称
            try:
                源码 = 件路径.read_text(encoding="utf-8")
            except OSError:
                continue
            try:
                语法树 = ast.parse(源码)
            except SyntaxError:
                continue
            for 节点 in ast.walk(语法树):
                if not isinstance(节点, ast.Call):
                    continue
                if not (isinstance(节点.func, ast.Attribute) and 节点.func.attr in 运行口名表):
                    continue
                if not (isinstance(节点.func.value, ast.Name)
                        and 节点.func.value.id == "subprocess"):
                    continue
                if not 是git调用(节点):
                    continue
                面数 += 1
                if not 带环境关键字(节点):
                    相对路径 = 取相对路径(扫根, 件路径)
                    if 相对路径 not in 命中:
                        命中[相对路径] = 节点.lineno
    return 命中, 面数


def 取扫根(上层读数: dict) -> Path:
    """被扫仓里有「名字含样本的 `.py`」就扫它；一件都没有（合成夹具）就退回本验证器所在仓。"""
    被扫仓根 = Path(上层读数["仓根"])
    for 根目录, 子目录表, 文件表 in os.walk(被扫仓根):
        子目录表[:] = [目录名 for 目录名 in 子目录表
                   if 目录名 not in 跳过目录 and not 目录名.startswith(临时目录前缀)
                   and not 目录名.startswith(".")]
        if any(名称.endswith(".py") and 样本名含 in 名称 for 名称 in 文件表):
            return 被扫仓根
    return 仓根


def 检查60_样本git隔离(上层读数: dict) -> list:
    """样本跑 git 的子进程调用必须带 `env=`（否则继承外层 `GIT_*` ⇒ 污染真仓）。"""
    输出缓冲 = []
    命中, 面数 = 扫样本git隔离(取扫根(上层读数))
    if not 面数:
        判不了(
            检查名[41],
            "全仓",
            "样本面里没扫到任何「名字含样本的 .py 里跑 git」的 subprocess 调用（走树坏了，或面为空）",
            "判据的可信性.md 第二节：空集是**未判**，不是通过 ⇒ 只能由判据作者确认走树口径",
        )
        return 输出缓冲
    for 路径, 行号 in sorted(命中.items()):
        输出缓冲.append(违规(
            检查名[41], 路径,
            "第 %d 行的 subprocess 调用跑 git 却没带 `env=` ⇒ 会继承外层 `GIT_DIR` / "
            "`GIT_WORK_TREE` 等定位键（541 实测：git add 落到外层真仓索引；545 实测：损坏外层暂存索引）"
            % 行号,
            "修法：把该调用补上 `env=干净环境()`（唯一权威 = "
            "`开发工具/MCP服务/集成管理/合主干有界跑.py::干净环境`，它剔掉 `GIT_*` 定位键）⇒ 只能由该件作者改",
        ))
    return 输出缓冲


def 样本_样本git面(上层读数: dict) -> int:
    """对象数：样本面里跑 git 的子进程调用数（0 ⇒ 未判：面为空）。"""
    return 扫样本git隔离(取扫根(上层读数))[1]
