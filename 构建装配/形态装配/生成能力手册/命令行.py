# -*- coding: utf-8 -*-
"""命令行 —— 本命令的入口函数：按库名过滤，逐库生成，打一行读数。

退出码：0 = 全部生成完 · 1 = 指定的库一个都没匹配上。
"""

from .基座常量 import 支持库根
from .手册编写 import 生成一库


def 入口函数(参数):
    库名关键词 = 参数[0] if 参数 else ''
    库们 = sorted(d for d in 支持库根.iterdir() if d.is_dir() and not d.name.startswith('.'))
    if 库名关键词:
        库们 = [d for d in 库们 if d.name == 库名关键词 or 库名关键词 in d.name]
        if not 库们:
            print('没找到支持库：%s' % 库名关键词)
            return 1

    总库 = 总能力 = 0
    for 库目录 in 库们:
        生成结果 = 生成一库(库目录)
        if not 生成结果:
            continue
        产出, 接口数, 行数 = 生成结果
        print('%-26s %2d 个接口 / %4d 行' % (库目录.name, 接口数, 行数))
        总库 += 1
        总能力 += 接口数

    print('\n共 %d 个支持库 / %d 个接口' % (总库, 总能力))
    return 0
