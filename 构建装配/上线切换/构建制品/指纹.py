"""指纹 —— 构建指纹：同一份源在两台机器上产出同一个标识。"""

import hashlib

from .常量 import 仓根, 底座目录, 底座根文件, 装配器入口
from .命令 import 工具链版本
from .源文件 import 相对, 走源文件, 文件指纹


def 源指纹(声明文本: str, 纳入的扩展: list, 变体: str) -> str:
    行 = [
        "profile=release",
        "变体={}".format(变体),
        "工具链={}".format(工具链版本()),
        "扩展根声明={}".format(hashlib.sha256(声明文本.encode("utf-8")).hexdigest()),
        # 装配器自己也是输入：本文件一改，同一个标识就不该再指同一份内容（否则标识在骗人）。
        "装配器=构建装配/上线切换/构建制品.py {}".format(文件指纹(装配器入口)),
    ]
    件 = {}
    for 名 in 底座根文件:
        路 = 仓根 / 名
        if 路.is_file():
            件[名] = 路
    for 目录 in 底座目录:
        for 路 in 走源文件(仓根 / 目录):
            件[相对(路)] = 路
    for 扩展 in 纳入的扩展:
        for 路 in 走源文件(扩展["落点"]):
            件[相对(路)] = 路
    for 键 in sorted(件):
        行.append("文件 {} {}".format(键, 文件指纹(件[键])))
    return hashlib.sha256("\n".join(行).encode("utf-8")).hexdigest()
