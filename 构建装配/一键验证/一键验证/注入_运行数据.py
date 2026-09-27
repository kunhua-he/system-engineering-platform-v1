# -*- coding: utf-8 -*-
"""注入样本 · 判据 ㉕（运行数据自拼路径）。"""
from __future__ import annotations

from pathlib import Path


def 注入_自拼运行数据路径(临根: Path) -> str:
    """造一处**自身拼运行数据路径**的节点 ⇒ 判据 ㉕ 当场红（「新增即红」）。

    形状取形③（直读覆盖变量 `V1_RUN_DATA_ROOT`）：节点绕开唯一解析器
    `运行内核/运行数据根/`，自身读环境变量拼路径 —— 那正是「第二个来源」。
    """
    路径 = 临根 / "运行内核" / "实例状态" / "src" / "自拼路径.rs"
    路径.parent.mkdir(parents=True, exist_ok=True)
    路径.write_text(
        "//! 反向样本：绕开运行数据根，自身拼路径。\n"
        "pub fn 自身拼() -> std::path::PathBuf {\n"
        "    let 根 = std::env::var(\"V1_RUN_DATA_ROOT\").unwrap_or_default();\n"
        "    std::path::PathBuf::from(根).join(\"数据库\")\n"
        "}\n",
        encoding="utf-8",
    )
    return "运行内核/实例状态/src/自拼路径.rs"


def 注入_临时根自建运行数据(临根: Path) -> str:
    """造一处**拿临时根当运行数据根、又自建 `系统工程平台V1-*` 子目录名** ⇒ 判据 ㉕ 当场红。

    形状取现场实测的那一种（`构建装配/上线切换/上线切换/常量.py` 的 `运行根`、
    `构建装配/演示/常量.py` 的 `暂存根`）：`Path(tempfile.gettempdir()) / "系统工程平台V1-演示"`
    —— 它同时命中形④（临时根）与形②（**加后缀**的目录名）。证明形② 放宽成「以
    `系统工程平台V1` 开头」之后，**加后缀躲不过**。
    """
    路径 = 临根 / "构建装配" / "样例" / "常量.py"
    路径.parent.mkdir(parents=True, exist_ok=True)
    路径.write_text(
        "import tempfile\n"
        "from pathlib import Path\n\n"
        '暂存根 = Path(tempfile.gettempdir()) / "系统工程平台V1-演示"\n',
        encoding="utf-8",
    )
    return "构建装配/样例/常量.py"
