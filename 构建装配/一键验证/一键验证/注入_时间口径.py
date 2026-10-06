# -*- coding: utf-8 -*-
"""注入样本 · 时间口径一类（判据 ㉑）：时间主人里塞墙钟 · 单位没进名字。"""
from __future__ import annotations

from pathlib import Path


def 注入_墙钟算耗时(临根: Path) -> str:
    """给时间主人塞一行墙钟 ⇒ 判据 ㉑ 当场红（墙钟会跳，不许用它算耗时/超时）。"""
    路径 = 临根 / "运行内核" / "调用调度" / "src" / "调度核心.rs"
    源文本 = 路径.read_text(encoding="utf-8")
    路径.write_text(
        "use std::time::SystemTime;\n" + 源文本, encoding="utf-8"
    )
    return "运行内核/调用调度/src/调度核心.rs"



def 注入_单位没进名字(临根: Path) -> str:
    """把超时量的名字改成不带单位的 ⇒ 判据 ㉑ 当场红（单位必须进名字）。"""
    路径 = 临根 / "运行内核" / "调用调度" / "src" / "调度核心.rs"
    源文本 = 路径.read_text(encoding="utf-8")
    assert "单项超时毫秒" in 源文本
    路径.write_text(源文本.replace("单项超时毫秒", "单项超时"), encoding="utf-8")
    return "运行内核/调用调度/src/调度核心.rs"
