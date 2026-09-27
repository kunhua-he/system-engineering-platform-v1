# -*- coding: utf-8 -*-
"""路径归一化 —— 两条腿写同一个文件的不同拼法，必须判成同一条路径。"""

import os

from .仓根 import ROOT


def norm_paths(raw, root=ROOT):
    """→ (归一化后的路径集, 仓外路径)。相对路径按仓根解析，统一 `/` 分隔。"""
    good, outside = [], []
    for 原路径 in raw:
        ap = os.path.normpath(原路径 if os.path.isabs(原路径) else os.path.join(root, 原路径))
        rel = os.path.relpath(ap, root).replace(os.sep, "/")
        if rel == ".." or rel.startswith("../"):
            outside.append(原路径)
        else:
            good.append(rel)
    return sorted(set(good)), outside
