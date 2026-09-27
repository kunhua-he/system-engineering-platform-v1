# -*- coding: utf-8 -*-
"""反解 —— 读文件 → 资源叶子分类 + 逐类解码（原 `界面反解.py::反解/反解数据`，纯搬家）。"""

from .加速键 import 解加速键
from .压缩 import 压缩判定
from .图标组 import 解图标组
from .字符串表 import 解字符串表
from .对话框 import 解对话框
from .形状 import PE, 解析错误
from .版本 import 解版本
from .菜单 import 解菜单
from .资源树 import 走资源树


def 反解(路径):
    with open(路径, "rb") as fh:
        数据 = fh.read()
    return 反解数据(数据, 路径)


def 反解数据(数据, 路径="<内存>"):
    pe = PE(数据, 路径)
    叶子 = 走资源树(pe)
    分类 = {}
    for 叶 in 叶子:
        分类.setdefault(叶["类型"], []).append(叶)
    r = {"路径": 路径, "字节数": len(数据), "pe": pe, "叶子": 叶子, "分类": 分类,
         "菜单": {}, "对话框": {}, "字符串": {}, "加速键": {}, "图标组": {}, "版本": {},
         "其它": [], "图形": []}
    for 叶 in 叶子:
        类, rid = 叶["类型"], 叶["id"]
        已见 = {4: r["菜单"], 5: r["对话框"], 6: r["字符串"], 9: r["加速键"],
                12: r["图标组"], 14: r["图标组"], 16: r["版本"]}.get(类)
        if 已见 is not None and rid in 已见:
            raise 解析错误("资源 (type=%s id=%s) 重复：目录不自洽" % (类, rid))
        b = 数据[叶["数据偏移"]:叶["数据偏移"] + 叶["大小"]]
        if 类 == 4:
            r["菜单"][rid] = (叶, 解菜单(b, rid))
        elif 类 == 5:
            r["对话框"][rid] = (叶, 解对话框(b, rid))
        elif 类 == 6:
            r["字符串"][rid] = (叶, 解字符串表(b, rid))
        elif 类 == 9:
            r["加速键"][rid] = (叶, 解加速键(b, rid))
        elif 类 in (12, 14):
            r["图标组"][rid] = (叶, 解图标组(b, rid, 类 == 12))
        elif 类 == 16:
            r["版本"][rid] = (叶, 解版本(b, rid))
        elif 类 in (10, 240, 23):
            r["其它"].append((叶, 压缩判定(b)))
        elif 类 in (2, 3, 1):
            r["图形"].append((叶, 压缩判定(b)))
    return r
