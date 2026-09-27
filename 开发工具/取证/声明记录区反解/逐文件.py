# -*- coding: utf-8 -*-
"""逐文件 —— 单文件读数 + 逐文件结果缓存。

**为什么要拆出这一件**：全语料扫描的成本实测集中在**逐文件**的「取区」与「走记录」两段
（读数见报告，不在注释里复述数字 —— 注释里写死耗时必漂）。语料**只读**、mtime 稳定 ⇒
逐文件结果是**纯函数**，可缓存、可跨进程复用。

**缓存键 = `(路径, 大小, mtime_ns)`**：三者任一变了就是另一个输入，键不等即重算 —— 不猜、
不按时间戳排序、不按文件名。
**缓存落运行数据根**（`运行数据根.py`），**不落源码树**（判据 ⑳）。
**缓存是可选加速，不是正确性来源**：取不到 / 键不符 / 版本不符 / 文件坏了 ⇒ 一律**重算**，
故「缓存全丢」与「缓存全有」必须给出**同一份读数**（`自测` 里有一条反向样本钉这件事）。
"""

import hashlib
import json
import os
import time

from .公共 import 解析错误
from .段数据层 import 取声明记录区
from .记录层 import 走记录

# 读数的形状版本：字段增删 / 语义变化就 +1 ⇒ 旧缓存整批作废（否则旧形状静默冒充新读数）。
缓存版本 = 1

def 新读数() -> dict:
    """一份**全新的**空读数。★ 必须每次新造：`区长` / `计` 是可变容器，共享一份的话
    每件都往同一个列表里追加 ⇒ 逐件读数互相污染（实测撞到过：归并出的区长表长出一堆重复项）。"""
    return {"段数": 0, "区长": [], "首4零": 0, "全零": 0, "计": {}, "未解": 0, "字节": 0, "坏": None}


def 取缓存键(路径):
    """缓存键：`[路径, 大小, mtime_ns]`。取不到 stat 就返回 `None`（调用方据此不复用缓存）。"""
    try:
        st = os.stat(路径)
    except OSError:
        return None
    return [str(路径), int(st.st_size), int(st.st_mtime_ns)]


def 单件读数(路径) -> dict:
    """读一个文件 → 容器/段数据/记录三层反解 → 可归并的**逐件读数**。

    逐件读数只装「能加起来的量」+ 原始区长表（区长表用来在全语料层算 min/中位/max）。
    耗时也记进来：它是**实测值**，切分拿它做均衡（拿读数做均衡，不拿猜测）。
    """
    t0 = time.monotonic()
    读数 = 新读数()
    读数["键"] = 取缓存键(路径)
    try:
        with open(路径, "rb") as fh:
            数据 = fh.read()
        区表 = 取声明记录区(数据)
    except 解析错误 as ex:
        读数["坏"] = str(ex)
        读数["毫秒"] = int((time.monotonic() - t0) * 1000)
        return 读数
    except OSError as ex:
        读数["坏"] = "读盘失败：{}".format(ex)
        读数["毫秒"] = int((time.monotonic() - t0) * 1000)
        return 读数
    for _, _, _, 段体, _ in 区表:
        读数["段数"] += 1
        读数["区长"].append(len(段体))
        if len(段体) >= 4 and 段体[:4] == b"\x00\x00\x00\x00":
            读数["首4零"] += 1
        if not any(段体):
            读数["全零"] += 1
        记录, 未解 = 走记录(段体)
        for 一条 in 记录:
            读数["计"][一条["种类"]] = 读数["计"].get(一条["种类"], 0) + 1
        读数["未解"] += 未解
        读数["字节"] += len(段体)
    读数["毫秒"] = int((time.monotonic() - t0) * 1000)
    return 读数


def 缓存文件(缓存目录, 路径):
    """一个文件一个缓存件（按路径哈希命名）⇒ 多进程各写各的，**没有读改写争用**。"""
    摘要 = hashlib.sha256(str(路径).encode("utf-8")).hexdigest()[:24]
    return 缓存目录 / "{}.json".format(摘要)


def 取缓存(缓存目录, 路径):
    """命中给读数，任何一处不符给 `None`（不抛：缓存坏了不该让命令崩）。"""
    if 缓存目录 is None:
        return None
    try:
        缓存内容 = json.loads(缓存文件(缓存目录, 路径).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if 缓存内容.get("版本") != 缓存版本 or 缓存内容.get("键") != 取缓存键(路径):
        return None
    读数 = 缓存内容.get("读数")
    return 读数 if isinstance(读数, dict) and 读数.get("键") == 缓存内容.get("键") else None


def 存缓存(缓存目录, 路径, 读数) -> None:
    """原子写（临时件 + `os.replace`）：另一个进程读到的要么是旧整份、要么是新整份。"""
    if 缓存目录 is None:
        return
    try:
        缓存目录.mkdir(parents=True, exist_ok=True)
        路径 = 缓存文件(缓存目录, 路径)
        临时路径 = 路径.with_suffix(".json.临时")
        临时路径.write_text(
            json.dumps({"版本": 缓存版本, "键": 读数.get("键"), "读数": 读数}, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(临时路径, 路径)
    except OSError:
        return  # 缓存写不进不是命令的失败面（算得出来才是）


def 带缓存(缓存目录, 路径) -> dict:
    """缓存命中就用缓存，否则重算并回填。**两条路必须同读数**。"""
    读数 = 取缓存(缓存目录, 路径)
    if 读数 is not None:
        return 读数
    读数 = 单件读数(路径)
    存缓存(缓存目录, 路径, 读数)
    return 读数


def 缓存覆盖数(缓存目录, 文件表) -> int:
    """有多少件的缓存键与当前盘面相符（`--全部` 用它报「缓存命中/需算」）。"""
    return sum(1 for 节点件 in 文件表 if 取缓存(缓存目录, 节点件) is not None)
