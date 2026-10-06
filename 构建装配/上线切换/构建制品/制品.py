"""制品 —— 目录内文件清单 · 不可变判据（可机器数）。"""

import json
import os
from pathlib import Path

from .常量 import 跳过目录
from .源文件 import 文件指纹


def 制品内文件清单(目录: Path) -> dict:
    输出缓冲 = {}
    for 根目录, 目录表, 文件表 in os.walk(目录):
        目录表[:] = [目录名 for 目录名 in 目录表 if 目录名 not in 跳过目录]
        for 名称 in 文件表:
            路径 = Path(根目录) / 名称
            if 路径.name == "制品清单.json":
                continue  # 清单不把自身写进自身的清单（否则自指，哈希无解）
            输出缓冲[路径.relative_to(目录).as_posix()] = 文件指纹(路径)
    return dict(sorted(输出缓冲.items()))


def 检查制品(目录: Path) -> tuple:
    """制品不可变判据（可机器数）：① 清单里每个文件重算指纹都相符 ② 目录里没有清单外的文件。"""
    清单 = json.loads((目录 / "制品清单.json").read_text(encoding="utf-8"))
    记的 = 清单.get("文件清单", {})
    现在 = 制品内文件清单(目录)
    不符项 = sorted(键名 for 键名, 待处理值 in 记的.items() if 现在.get(键名) != 待处理值)
    多余项 = sorted(键名 for 键名 in 现在 if 键名 not in 记的)
    缺件清单 = sorted(键名 for 键名 in 记的 if 键名 not in 现在)
    return 不符项, 多余项, 缺件清单
