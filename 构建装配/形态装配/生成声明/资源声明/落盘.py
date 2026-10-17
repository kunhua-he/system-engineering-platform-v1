# -*- coding: utf-8 -*-
"""资源声明 · 落盘 —— 生成并写 `<根>/src/资源声明.rs`，或只比对（闸 4 的口径）。

`检查资源声明` = 重新生成到内存、与落盘件逐字节比对（0 新鲜 / 1 不新鲜，**不落盘**）；
`生成资源声明` = 生成并落盘（0 成；`src/` 不存在即 fail-closed ⇒ 调用方回 2）。
"""

import hashlib
import os

from ..路径形状 import 仓根, 生成失败
from .路径与枚举 import 生成器相对路径, 落盘件
from .渲染 import 渲染资源声明


def 检查资源声明(根目录):
    """重新生成到内存，与落盘件逐字节比对。→ 0 新鲜 / 1 不新鲜（不落盘）。"""
    新字节 = 渲染资源声明(根目录).encode("utf-8")
    落盘 = os.path.join(仓根, 落盘件(根目录))
    if not os.path.isfile(落盘):
        print("生成物不存在：%s" % 落盘件(根目录))
        print("跑一次生成：python3 %s --声明根 %s" % (生成器相对路径, 根目录))
        return 1
    with open(落盘, "rb") as 句柄:
        旧字节 = 句柄.read()
    if 新字节 == 旧字节:
        print("生成物新鲜：%s（%d 字节 · sha256 %s）" % (落盘件(根目录), len(新字节), hashlib.sha256(新字节).hexdigest()))
        return 0
    print("生成物不新鲜：%s" % 落盘件(根目录))
    print("  落盘 %d 字节 · 重新生成 %d 字节" % (len(旧字节), len(新字节)))
    print("  处置：python3 %s --声明根 %s" % (生成器相对路径, 根目录))
    return 1


def 生成资源声明(根目录):
    """生成并落盘。→ 0（成）。`src/` 不存在即 fail-closed（生成失败 ⇒ 2）。"""
    落点目录 = os.path.dirname(os.path.join(仓根, 落盘件(根目录)))
    if not os.path.isdir(落点目录):
        raise 生成失败(
            "落点目录不存在：%s —— 生成物要落进实现 crate 的 src/（%s 下没有 src/）⇒ fail-closed"
            % (os.path.relpath(落点目录, 仓根).replace(os.sep, "/"), 根目录)
        )
    新字节 = 渲染资源声明(根目录).encode("utf-8")
    with open(os.path.join(仓根, 落盘件(根目录)), "wb") as 句柄:
        句柄.write(新字节)
    print("已生成 %s（%d 字节 · sha256 %s）" % (落盘件(根目录), len(新字节), hashlib.sha256(新字节).hexdigest()))
    print("  声明根：%s" % 根目录)
    return 0
