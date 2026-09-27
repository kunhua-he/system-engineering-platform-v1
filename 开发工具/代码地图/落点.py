# -*- coding: utf-8 -*-
"""代码地图 · 落点 —— 索引文件放哪、在不在、多大、多新。

四份产物（都在 `<运行数据根>/缓存/代码地图/`，判据 ⑳：不落源码树）：
  · `rs.scip` / `py.scip` / `js.scip` —— 三条腿索引器的**原始**产出（SCIP，protobuf）。
                     留着是给「符号级批量替换」用的：它带 **UTF-16 列**的精确位置。
  · `定义.jsonl`  —— **统一形状**：一行一个定义（跨三种语言同一套字段）。
  · `出现.jsonl`  —— **统一形状**：一行一次出现（定义处也算一次）。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # 开发工具/：取 运行数据根
from 运行数据根 import 解析当前, 子目录路径  # noqa: E402

缓存类 = "缓存"
缓存子目录 = "代码地图"
定义名 = "定义.jsonl"
出现名 = "出现.jsonl"
原始名 = {"rs": "rs.scip", "py": "py.scip", "js": "js.scip"}


def _缓存目录() -> Path:
    return 子目录路径(解析当前(), 缓存类) / 缓存子目录


def 原始路径(语言键: str) -> Path:
    """某条腿索引器的原始 `.scip` 落点。"""
    return _缓存目录() / 原始名[语言键]


def 定义路径() -> Path:
    return _缓存目录() / 定义名


def 出现路径() -> Path:
    return _缓存目录() / 出现名


def 确保目录() -> Path:
    缓存目录 = _缓存目录()
    缓存目录.mkdir(parents=True, exist_ok=True)
    return 缓存目录


def _一份状态(落点路径: Path) -> dict:
    if not 落点路径.is_file():
        return {"有": False, "路径": str(落点路径)}
    文件元数据 = 落点路径.stat()
    return {"有": True, "路径": str(落点路径),
            "字节": 文件元数据.st_size, "改于": 文件元数据.st_mtime}


def 原始状态() -> dict:
    """三条腿的原始 `.scip` 在不在、多大（**哪条腿跑了**就靠它如实报）。"""
    return {语言键: _一份状态(原始路径(语言键)) for 语言键 in 原始名}


def 索引状态() -> dict:
    """统一索引（`定义.jsonl` + `出现.jsonl`）在不在、多大、多新。**只读文件元数据，不解析。**"""
    定义状态, 出现状态 = _一份状态(定义路径()), _一份状态(出现路径())
    return {
        "有": 定义状态["有"] and 出现状态["有"],
        "路径": str(_缓存目录()),
        "定义": 定义状态,
        "出现": 出现状态,
        "原始": 原始状态(),
        "字节": (定义状态.get("字节") or 0) + (出现状态.get("字节") or 0),
        "改于": max(定义状态.get("改于") or 0, 出现状态.get("改于") or 0),
    }
