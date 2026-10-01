# -*- coding: utf-8 -*-
"""建库 · 条款 —— 全部 md 的正文入库：一行一节（以 `# ` / `## ` 为界）。"""
from pathlib import Path

from .通用 import 读文本


def 装条款(根目录: Path, 文档行: list) -> list:
    """全部 md 的正文入库：一行一节（以 `# ` / `## ` 为界）。

    这是「md 只留索引」的**载荷步骤**：正文进了库，原件才可删。所以它跑在 `装文档` 之后 ——
    档位从 `文档` 表继承（账本定档），不另判一次。
    """
    输出行 = []
    for 文档路径, 档位, _表达 in 文档行:
        for 节号, (节标题, 节正文) in enumerate(拆节(读文本(根目录 / 文档路径))):
            输出行.append((文档路径, 节号, 节标题, 节正文, 档位))
    return 输出行


def 拆节(文本: str) -> list:
    """md → `[(节标题, 节正文)]`。`# ` 与 `## ` 都是界（`###` 及以下归上一节）。"""
    节表, 节标题, 缓冲 = [], "", []
    for 一行 in 文本.splitlines():
        if 一行.startswith("# ") or 一行.startswith("## "):
            节表.append((节标题, "\n".join(缓冲).strip()))
            节标题, 缓冲 = 一行.lstrip("#").strip(), []
        else:
            缓冲.append(一行)
    节表.append((节标题, "\n".join(缓冲).strip()))
    return [(节题, 节体) for 节题, 节体 in 节表 if 节题 or 节体]
