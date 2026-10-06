# -*- coding: utf-8 -*-
"""建库 · 契约 —— `契约声明/` 三个子目录 → `能力` · `能力参数` · `类型` · `错误码` 四表。"""
from pathlib import Path

from .通用 import 读JSON件

# 「一次扫描 → 多张表」的中间结果缓存：四张表共用一次扫。
_契约缓存: dict = {}


def 装能力(根目录: Path) -> list:
    return _契约表(根目录)[0]


def 装能力参数(根目录: Path) -> list:
    return _契约表(根目录)[1]


def 装类型(根目录: Path) -> list:
    return _契约表(根目录)[2]


def 装错误码(根目录: Path) -> list:
    return _契约表(根目录)[3]


def _契约表(根目录: Path) -> tuple:
    """`契约声明/` 三个子目录 → `(能力行, 参行, 类型行, 错误码行)`。缓存住，四张表共用一次扫。"""
    if 根目录 in _契约缓存:
        return _契约缓存[根目录]
    契约 = 根目录 / "契约声明"
    能力行, 参行, 类型行, 错误行 = [], [], [], []
    for 声明件 in sorted((契约 / "能力声明").glob("*.json")):
        声明数据 = 读JSON件(声明件) or {}
        能力编号 = 声明数据.get("编号", 0)
        参数表 = 声明数据.get("参数表") or []
        能力行.append((能力编号, str(声明数据.get("名称", "")), len(参数表),
                      声明数据.get("返回类型", 0),
                      ",".join(str(码文) for 码文 in (声明数据.get("可抛错误码") or []))))
        for 参号, 入参 in enumerate(参数表, 1):
            参行.append((能力编号, 参号, str(入参.get("名称", "")), 入参.get("类型标签", 0), "入参"))
    for 声明件 in sorted((契约 / "类型声明").glob("*.json")):
        声明数据 = 读JSON件(声明件) or {}
        类型行.append((声明数据.get("类型标签", 0), str(声明数据.get("名称", "")),
                      str(声明数据.get("说明", ""))[:200]))
    for 声明件 in sorted((契约 / "错误码表").glob("*.json")):
        声明数据 = 读JSON件(声明件) or {}
        错误行.append((声明数据.get("码", 0), 声明数据.get("段位", 0),
                      str(声明数据.get("名称", "")),
                      1 if 声明数据.get("可重试") else 0,
                      1 if 声明数据.get("可自愈") else 0,
                      1 if 声明数据.get("需人工") else 0))
    _契约缓存[根目录] = (能力行, 参行, 类型行, 错误行)
    return _契约缓存[根目录]
