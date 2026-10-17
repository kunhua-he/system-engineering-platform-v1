"""读基线 —— 读基线 ref 与当前盘上的冻结登记，以及「这件最近谁改的」。"""

import json
import subprocess
from pathlib import Path

from .常量 import 仓根, 冻结登记相对路径, git命令路径


def _跑(命令行参数: list) -> tuple:
    运行结果 = subprocess.run(
        命令行参数, cwd=str(仓根), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return 运行结果.returncode, 运行结果.stdout or "", 运行结果.stderr or ""


def 取基线引用(文件相对路径: str) -> str:
    """上一次改动这个文件的提交（`git log -1 --format=%H`）—— 基线 = 这份文件的上一版。"""
    退出码, 标准输出, _ = _跑([git命令路径, "log", "-1", "--format=%H", "--", 文件相对路径])
    return 标准输出.strip() if 退出码 == 0 else ""


def 读基线登记(基线引用: str) -> tuple:
    """`git show <基线引用>:<冻结登记>` → `(登记, 说明)`；读不动给 `(None, 原因)`。"""
    退出码, 标准输出, 标准错误 = _跑([git命令路径, "show", f"{基线引用}:{冻结登记相对路径}"])
    if 退出码 != 0:
        return None, f"基线 {基线引用[:12]} 里读不到 {冻结登记相对路径}（{标准错误.strip()[:200]}）"
    try:
        return json.loads(标准输出), ""
    except json.JSONDecodeError as 解析错误:
        return None, f"基线那份解不开（{解析错误}）"


def 读当前登记() -> tuple:
    登记路径 = 仓根 / 冻结登记相对路径
    try:
        return json.loads(登记路径.read_text(encoding="utf-8")), ""
    except (OSError, json.JSONDecodeError) as 解析错误:
        return None, f"当前 {冻结登记相对路径} 读不动（{解析错误}）"


def 取责任归属(件相对路径: str) -> str:
    """该件最近一次提交的「作者 短哈希」；无件或无提交给空串。"""
    if not 件相对路径:
        return ""
    退出码, 标准输出, _ = _跑([git命令路径, "log", "-1", "--format=%an %h", "--", 件相对路径])
    return 标准输出.strip() if 退出码 == 0 else ""
