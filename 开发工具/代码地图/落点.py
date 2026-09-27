# -*- coding: utf-8 -*-
"""代码地图 · 落点 —— 索引库在哪、在不在、多大、多新。

**一份产物**：`<仓根>/.codegraph/codegraph.db` —— 索引器 `codegraph` 自带的 sqlite 库。
它是**外部件的私有落点**（`codegraph init` 建、`codegraph index` 刷），本仓**只读不写** ——
换索引器就是换这个库，上层一行不改。

★ **它在源码树里**，这是换索引器**唯一付的代价**（codegraph 写死要落在工程目录下）：
  · 判据 ⑳ 的禁名表是 `("数据库", "缓存", "日志", "临时件")` ⇒ `.codegraph` 不在其中，判据照绿；
  · `.gitignore` 忽略它（本机产物，不进版本库）。
裁决与代价的实测数据见 `项目文档/决策记录/2026-09-27_代码地图换 codegraph.md`。
"""

from pathlib import Path

仓根 = Path(__file__).resolve().parents[2]      # 开发工具/代码地图/落点.py ⇒ 仓根
库目录名 = ".codegraph"
库文件名 = "codegraph.db"


def 库目录() -> Path:
    return 仓根 / 库目录名


def 库路径() -> Path:
    return 库目录() / 库文件名


def 索引状态() -> dict:
    """索引库在不在、多大、多新。**只读文件元数据，不连库**（连库归 `索引库`）。"""
    路径 = 库路径()
    if not 路径.is_file():
        return {"有": False, "路径": str(路径)}
    文件元数据 = 路径.stat()
    return {"有": True, "路径": str(路径),
            "字节": 文件元数据.st_size, "改于": 文件元数据.st_mtime}
