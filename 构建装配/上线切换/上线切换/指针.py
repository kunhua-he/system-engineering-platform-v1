"""运行态 —— 指针文件 · 原子写 · 回退账（有界）。"""

import json
import os

from .常量 import 回退账上限, 运行根


def 建运行子目录() -> None:
    for 子目录 in ("已装载", "日志"):
        (运行根 / 子目录).mkdir(parents=True, exist_ok=True)


def 读指针(名称: str) -> dict:
    路径 = 运行根 / "{}.json".format(名称)
    if not 路径.is_file():
        return {}
    try:
        return json.loads(路径.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def 写指针(名称: str, 待处理值: dict) -> None:
    """原子写：先写同目录临时件再 `os.replace`（换指针必须是**一步**，不许读到半个）。"""
    路径 = 运行根 / "{}.json".format(名称)
    临时路径 = 路径.with_suffix(".json.临时")
    临时路径.write_text(json.dumps(待处理值, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(临时路径, 路径)


def 清指针(名称: str) -> None:
    路径 = 运行根 / "{}.json".format(名称)
    if 路径.is_file():
        路径.unlink()


# ── 回退账（#81）：把「上一份」从**栈深 1** 变成**有界账**，账首即「上一份」──
#
# 存 `回退账.json`：`{ "账": [ {制品标识, 来源}, … ], "上限": 8 }`，**最近在前的有序表**。
# 只由 切换 / 回退 / 停 的成功路径调 `记账` 改写；装载不动账（形状.md §二）。
账文件 = "回退账"


def 读账() -> list:
    """回退账（最近在前）。文件不在 / 坏了 ⇒ 空账（不崩）。"""
    原文 = 读指针(账文件)
    台账 = 原文.get("账") if isinstance(原文, dict) else None
    return 台账 if isinstance(台账, list) else []


def 账首() -> dict:
    """账首 = 「上一份」= 刚才在流量口服务的那个。空账 ⇒ {}。"""
    台账 = 读账()
    return 台账[0] if 台账 else {}


def 记回退账(记录: dict) -> None:
    """把「刚才在服务的那个」压进账首：**去重**（同一制品先摘掉再压入）· **封顶**（丢最旧）。"""
    标识 = (记录 or {}).get("制品标识")
    if not 标识:
        return
    台账 = [台账项 for 台账项 in 读账() if 台账项.get("制品标识") != 标识]
    台账.insert(0, {"制品标识": 标识, "来源": 记录.get("来源", "")})
    写指针(账文件, {"账": 台账[:回退账上限], "上限": 回退账上限})
