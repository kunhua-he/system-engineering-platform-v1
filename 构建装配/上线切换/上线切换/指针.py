"""运行态 —— 指针文件 · 原子写。"""

import json
import os

from .常量 import 运行根


def 就绪() -> None:
    for 子 in ("已装载", "日志"):
        (运行根 / 子).mkdir(parents=True, exist_ok=True)


def 读指针(名: str) -> dict:
    路 = 运行根 / "{}.json".format(名)
    if not 路.is_file():
        return {}
    try:
        return json.loads(路.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def 写指针(名: str, 值: dict) -> None:
    """原子写：先写同目录临时件再 `os.replace`（换指针必须是**一步**，不许读到半个）。"""
    路 = 运行根 / "{}.json".format(名)
    临 = 路.with_suffix(".json.临时")
    临.write_text(json.dumps(值, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(临, 路)


def 清指针(名: str) -> None:
    路 = 运行根 / "{}.json".format(名)
    if 路.is_file():
        路.unlink()
