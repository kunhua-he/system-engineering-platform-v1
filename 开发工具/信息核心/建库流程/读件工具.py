# -*- coding: utf-8 -*-
"""建库 · 通用 —— 读件与扫件：源件读器 · 全仓 md 扫描。

★ `读JSON件` / `读文本` 的错误策略是**有意的（吞 `OSError`/`ValueError` → `None` ·
吞 `OSError` → `""`）** —— 本包是**抽取器**，读器只做「读得到就读、读不到给空」：源件在不在、
坏不坏由上层处置（`装表` 先判「有源件」再决定要不要重抽；`读源件` 明写「读不动就炸，绝不
返回空」）。与别处同名读器（`形状检查/形状.py` 不吞原样抛 · `生成声明/生成小工具.py` 抛
`生成失败` · `查文件行数/核心.py` 不吞 `OSError` · `代码地图/形参面.py` `replace` 且吞
`OSError` 返空串）**不是同一事实，勿合并**。
"""
import json
import os
import subprocess
from pathlib import Path

from .路径 import 仓根  # noqa: F401,E402 —— 先挂 sys.path（须在下面那条 import 之前）
from 代码地图.落点 import 排除目录  # noqa: E402


def 读JSON件(路径: Path):
    try:
        return json.loads(路径.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def 读文本(路径: Path) -> str:
    try:
        return 路径.read_text(encoding="utf-8")
    except OSError:
        return ""


# 子进程不许继承的 Git 定位变量（会把 git 带到别的树 / 别的 index 上）—— 同 `开发工具/MCP服务/作业执行/命令执行.py`
继承定位变量 = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
              "GIT_COMMON_DIR", "GIT_ALTERNATE_OBJECT_DIRECTORIES")


def 版本库命令(根目录: Path, *子命令: str) -> list:
    """git 命令**显式定位**这条仓：`.git` 是目录（含 bare 主目录）⇒ 给 `--git-dir` / `--work-tree`；
    否则（工作树 `.git` 是文件）⇒ 退 `-C`。不改全局 Git 配置、不改 `core.bare`。
    """
    仓库元目录 = 根目录 / ".git"
    if 仓库元目录.is_dir():
        return ["git", "--git-dir", str(仓库元目录), "--work-tree", str(根目录), *子命令]
    return ["git", "-C", str(根目录), *子命令]


def 版本库环境() -> dict:
    """子进程环境：剔除继承的 Git 定位变量（避免读成被污染的仓）。"""
    环境表 = dict(os.environ)
    for 键名 in 继承定位变量:
        环境表.pop(键名, None)
    return 环境表


def 取已跟踪路径(根目录: Path) -> set:
    """`git ls-files` 的仓内相对路径集合。**读不动就炸**（fail-closed）—— 返回空集会把
    「已跟踪」判成「全未跟踪」，静默清空条款面（同 `读源件` 的「读不动就炸」）。
    """
    try:
        判定汇总 = subprocess.run(
            版本库命令(根目录, "ls-files"), capture_output=True, text=True,
            timeout=5, env=版本库环境())
    except (OSError, subprocess.SubprocessError) as 错误:
        raise ValueError(f"读不动 git ls-files（{type(错误).__name__}：{错误}）⇒ 判不了「已跟踪」")
    if 判定汇总.returncode != 0:
        raise ValueError(f"git ls-files 退出码 {判定汇总.returncode}：{判定汇总.stderr.strip()[:200]}")
    return set(判定汇总.stdout.splitlines()) - {""}


def 读账本定档(根目录: Path) -> tuple:
    """`项目文档/文档账本.json` ⇒ `(显式件集, 前缀表)`（口径同判据 ㊶：`件` 或 `按路径定档`）。"""
    账本 = 读JSON件(根目录 / "项目文档" / "文档账本.json") or {}
    显式 = {账本条目["路径"] for 账本条目 in (账本.get("件") or [])
            if isinstance(账本条目, dict) and isinstance(账本条目.get("路径"), str)}
    前缀表 = [账本条目["前缀"] for 账本条目 in (账本.get("按路径定档") or [])
              if isinstance(账本条目, dict) and isinstance(账本条目.get("前缀"), str)]
    return 显式, 前缀表


def 扫md(根目录: Path) -> list:
    """全仓 md 的**入库面**：账本已定义、且 git 已跟踪的那些（仓内相对路径，排序）。

    为何要这两道（不是只 `rglob("*.md")`）：
      · **账本已定义** —— 命中 `项目文档/文档账本.json` 的 `件` 或 `按路径定档`（口径同判据 ㊶）。
        未定档的 md 没有权威定义（随时可删）⇒ 不进 `条款`（它只装正文唯一存本）。
      · **git 已跟踪** —— `条款` 库受版本控制；把**机器局部**的未跟踪件（如 `.zcode/agents/`
        的客户端 / 代理配置）抽进库，会让库随本机文件漂、且克隆不到。
    只此一处收口「哪些 md 入库」—— 不在文档 / 命名 / 代码三面各写一份排除口径（它们职责不同，
    强行合一或各自 `startswith(".")` 都会让三面漂成不一致）。
    """
    显式, 前缀表 = 读账本定档(根目录)
    已跟踪路径集 = 取已跟踪路径(根目录)
    跳过 = set(排除目录) | {"__pycache__", "node_modules", "target"}  # 段形态主人（落点.排除目录）+ 本面增量
    查询读数 = []
    for 路径 in 根目录.rglob("*.md"):
        if any(路径段 in 跳过 for 路径段 in 路径.relative_to(根目录).parts):
            continue
        相对路径 = 路径.relative_to(根目录).as_posix()
        if 相对路径 not in 显式 and not any(map(相对路径.startswith, 前缀表)):
            continue
        if 相对路径 not in 已跟踪路径集:
            continue
        查询读数.append(相对路径)
    return sorted(查询读数)
