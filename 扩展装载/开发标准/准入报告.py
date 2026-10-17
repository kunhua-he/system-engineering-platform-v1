# -*- coding: utf-8 -*-
"""准入报告 —— 产出「某扩展是否满足准入」的报告（读同一份必备件清单）。

用法：

    python 扩展装载/开发标准/准入报告.py 扩展根目录/原子支持库/示例扩展 [--json]

零第三方依赖。退出码：0 = 满足准入；1 = 不满足（有缺件）；2 = 判不了。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

起始时刻 = time.monotonic()  # 自量起表点（在导入本包之前）

本件目录 = Path(__file__).resolve().parent
同源自检目录 = 本件目录 / "同源自检"
if str(同源自检目录) not in sys.path:
    sys.path.insert(0, str(同源自检目录))

from 必备件 import 仓根, 取必备件表, 取种类表, 读必备件  # noqa: E402
from 自检 import 命中, 认种类, 扫件名  # noqa: E402


def 入口函数(参数表: list) -> int:
    json输出 = "--json" in 参数表
    路径表 = [参数项 for 参数项 in 参数表 if not 参数项.startswith("--")]
    if not 路径表:
        print("用法：python 扩展装载/开发标准/准入报告.py <扩展目录> [--json]")
        return 2
    必备件清单, 错误 = 读必备件()
    if 错误:
        print("判不了：" + 错误)
        return 2
    种类表 = 取种类表(必备件清单)
    必备件表 = 取必备件表(必备件清单)
    结果码 = 0
    for 路径文本 in 路径表:
        件目录 = Path(路径文本)
        种类名 = 认种类(件目录, 种类表, 仓根)
        if 种类名 is None:
            print(f"判不了：{路径文本} 不在三类（支持库 / 组合模块 / 技能）里")
            结果码 = 2
            continue
        件名集 = 扫件名(件目录)
        要求件表 = []
        缺件名 = []
        for 必备件条 in 必备件表:
            要求件 = 必备件条.get("文件")
            if not 要求件 or not 必备件条.get(种类名):
                continue
            具备 = 命中(要求件, 件名集)
            要求件表.append({"要求件": 要求件, "具备": 具备, "作用": 必备件条.get("作用", "")})
            if not 具备:
                缺件名.append(要求件)
        指纹件 = 件目录 / "指纹.json"
        结论 = "满足准入" if not 缺件名 else "不满足准入"
        报告表 = {
            "扩展": 件目录.name,
            "种类": 种类名,
            "件数": len(件名集),
            "要求件": 要求件表,
            "缺件": 缺件名,
            "结论": 结论,
            "指纹件": 指纹件.is_file(),
        }
        if json输出:
            print(json.dumps(报告表, ensure_ascii=False, indent=2))
        else:
            print(f"准入报告 · {件目录.name}（{种类名}）")
            print(f"  件数：{len(件名集)} · 结论：{结论}")
            for 要求件项 in 要求件表:
                print(("  ✓ " if 要求件项["具备"] else "  ✗ ") + 要求件项["要求件"])
            print(f"  指纹.json：{'在' if 指纹件.is_file() else '缺'}")
        if 缺件名:
            结果码 = 1
    return 结果码


if __name__ == "__main__":
    print(f"命令墙钟（自量）{int((time.monotonic() - 起始时刻) * 1000)} ms")
    sys.exit(入口函数(sys.argv[1:]))
