# -*- coding: utf-8 -*-
"""注入样本 · 行数硬数一类（判据 ⑲）：单文件超行数 · 存量还在长 · 基线陈旧 · 基线缩水。"""
from __future__ import annotations

import json
from pathlib import Path


def 注入_单文件超行数(临根: Path) -> str:
    """造一个**基线里没有**的 401 行新文件 ⇒ 判据 ⑲ 当场红（「新增即红」）。"""
    路径 = 临根 / "运行内核" / "实例状态" / "src" / "超限件.rs"
    路径.parent.mkdir(parents=True, exist_ok=True)
    路径.write_text("\n".join(f"// 第 {i} 行" for i in range(401)) + "\n", encoding="utf-8")
    return "运行内核/实例状态/src/超限件.rs"



def 注入_存量还在长(临根: Path) -> str:
    """把基线里某件的登记数**改小 1** ⇒ 实际 > 登记 ⇒ 判据 ⑲ 当场红（「存量还在长」）。

    这条反向样本专证「基线只许减不许增」不是空转：基线不是白名单，**缩小的登记也拦得住**。
    """
    路径 = 临根 / "构建装配" / "一键验证" / "行数基线.json"
    数据 = json.loads(路径.read_text(encoding="utf-8"))
    for 条 in 数据["债务"]["入口有实现"]:
        if 条["路径"] == "运行内核/资源网关口/src/lib.rs":
            条["处数"] = 2
    路径.write_text(json.dumps(数据, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return "构建装配/一键验证/行数基线.json"



def 注入_基线陈旧登记(临根: Path) -> str:
    """给基线**加一条已不超限的登记** ⇒ 判据 ⑲ 当场红（「陈旧登记」）。

    专证「基线只许减」的反面不是空的：留着一条不再欠债的登记，基线读数就不再是现状，
    而且它白占一格上限。
    """
    路径 = 临根 / "构建装配" / "一键验证" / "行数基线.json"
    数据 = json.loads(路径.read_text(encoding="utf-8"))
    数据["债务"]["入口有实现"].append({"路径": "运行内核/实例状态/src/lib.rs", "处数": 1})
    路径.write_text(json.dumps(数据, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return "运行内核/实例状态/src/lib.rs"



def 注入_基线缩水登记(临根: Path) -> str:
    """把基线里某件的登记数**改大 1** ⇒ 实测 < 登记 ⇒ 判据 ⑲ 当场红（「登记没跟着减」）。

    专证那个洞：登记比实测高，那一件就能一路长回登记值而不报红。
    """
    路径 = 临根 / "构建装配" / "一键验证" / "行数基线.json"
    数据 = json.loads(路径.read_text(encoding="utf-8"))
    for 条 in 数据["债务"]["入口有实现"]:
        if 条["路径"] == "运行内核/资源网关口/src/lib.rs":
            条["处数"] = 999   # 远高于实测 ⇒ 实测 < 登记
    路径.write_text(json.dumps(数据, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return "运行内核/资源网关口/src/lib.rs"
