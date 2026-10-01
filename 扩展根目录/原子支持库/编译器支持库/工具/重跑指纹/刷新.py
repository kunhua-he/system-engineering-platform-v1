# -*- coding: utf-8 -*-
"""重跑指纹 · 刷新与检查 —— 写 指纹.json（刷新指纹）· 与盘面逐键比对（检查，fail-closed）。"""
import json
import os
from datetime import datetime, timezone, timedelta

from .常量 import 扩展根, 指纹件, 重跑指纹命令, 说明, 指纹范围, 指纹缺口
from .收集 import 相对路径, 算指纹表, 读旧指纹表


def 刷新指纹():
    项表 = 算指纹表()
    时刻 = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S %z")
    指纹文档 = {
        "说明": 说明,
        "算法": "sha256",
        "生成时刻": 时刻,
        # 产物自称（判据 ⑩ 的产物头标）；JSON 装不下 `//` 注释 ⇒ 用 JSON 键承载同义声明。
        # **措辞与 `.rs` 生成物逐字一致**（`生成物，禁手改。`）—— 一处口径，不新造第二种写法。
        # 路径由**同一条** `重跑指纹命令` 派生，不新写第二处。
        "生成物声明": "生成物，禁手改。生成器：%s" % 重跑指纹命令.removeprefix("python3 "),
        "生成命令": 重跑指纹命令,
        "范围": 指纹范围,
        "缺口": 指纹缺口,
        "指纹": 项表,
    }
    with open(指纹件, "w", encoding="utf-8") as 句柄:
        json.dump(指纹文档, 句柄, ensure_ascii=False, indent=2)
        句柄.write("\n")
    print("已刷新 %s" % 相对路径(指纹件))
    print("生成时刻 %s · 文件 %d 个" % (时刻, len(项表)))
    return 0


def 检查():
    新指纹表 = 算指纹表()
    旧指纹表 = 读旧指纹表()
    if 旧指纹表 is None:
        print("✗ 读不到 %s" % 相对路径(指纹件))
        return 1
    漂移清单 = []
    for 路径键 in sorted(set(新指纹表) | set(旧指纹表)):
        if 路径键 not in 旧指纹表:
            漂移清单.append("  新增未入指纹：%s" % 路径键)
        elif 路径键 not in 新指纹表:
            漂移清单.append("  指纹里有、盘上没有：%s" % 路径键)
        elif 新指纹表[路径键] != 旧指纹表[路径键]:
            漂移清单.append("  内容不符：%s（记录 %s / 实际 %s）" % (路径键, 旧指纹表[路径键][:8], 新指纹表[路径键][:8]))
    if 漂移清单:
        print("✗ 指纹与盘面不符（%d 处）—— 重跑生成命令即可刷新：" % len(漂移清单))
        for 漂移说明 in 漂移清单:
            print(漂移说明)
        return 1
    print("✓ 指纹与盘面逐键一致（%d 个文件）" % len(新指纹表))
    return 0
