# -*- coding: utf-8 -*-
"""上下文冻结落点：冻结登记与落点清单的只读读取。

从 `上下文来源.py` 拆出（单件 ≤400 行硬顶）；只读零写，不建库、不刷索引。
"""
import hashlib
from pathlib import Path
from .上下文来源 import 上下文失败, 读源JSON, 读指纹, 造条目, 冻结登记件

落点子目录名 = "落点"


def 取落点目录():
    from 运行数据根.口径 import 解析当前环境, 子目录路径
    try:
        return 子目录路径(解析当前环境(), "临时件") / 落点子目录名
    except Exception:
        return None


def 读冻结落点条目(树根, 查询参数):
    路径值 = 查询参数["路径"]
    冻结件 = 树根 / 冻结登记件
    落点目录 = 取落点目录()
    if 路径值:
        if 冻结件.is_file():
            冻结内容 = 读源JSON(冻结件)
            冻结命中 = [冻结行 for 冻结行 in 冻结内容.get("冻结项", []) if 冻结行.get("名称") == 路径值] if isinstance(冻结内容, dict) else []
            if 冻结命中:
                yield 造条目("冻结件", {"文件": 冻结登记件, "主键": 路径值}, "冻结登记", 冻结命中[0], 读指纹(冻结件))
                return
        if 落点目录 is not None:
            落点候选 = 落点目录 / Path(路径值).name
            if 落点候选.is_file():
                yield 造条目("落点", {"文件": str(落点候选)}, "临时档",
                            {"文本": 落点候选.read_text(encoding="utf-8", errors="replace")}, 读指纹(落点候选))
                return
        raise 上下文失败("missing", "冻结项或落点件未找到：" + 路径值)
    if 冻结件.is_file():
        冻结内容 = 读源JSON(冻结件)
        if not isinstance(冻结内容, dict):
            raise 上下文失败("corrupt", "冻结登记格式错误")
        yield 造条目("冻结件", {"文件": 冻结登记件}, "冻结登记",
                    {"冻结项数": len(冻结内容.get("冻结项", [])),
                     "冻结项": [冻结行.get("名称") for 冻结行 in 冻结内容.get("冻结项", [])],
                     "例外数": len(冻结内容.get("冻结例外", [])),
                     "待裁冻结例外数": len(冻结内容.get("待裁冻结例外", []))},
                    读指纹(冻结件))
    else:
        yield 造条目("冻结件", {"文件": 冻结登记件}, "冻结登记", {"状态": "缺失"}, "missing")
    if 落点目录 is not None and 落点目录.is_dir():
        件表 = sorted(落点项.name for 落点项 in 落点目录.iterdir() if 落点项.is_file())
        指纹值 = hashlib.sha256("\n".join(件表).encode()).hexdigest()
        yield 造条目("落点", {"目录": str(落点目录)}, "临时档", {"件数": len(件表), "件": 件表[:50]}, 指纹值)
    else:
        yield 造条目("落点", {"目录": str(落点目录) if 落点目录 else "（运行数据根不可解析）"}, "临时档", {"状态": "缺失"}, "missing")
