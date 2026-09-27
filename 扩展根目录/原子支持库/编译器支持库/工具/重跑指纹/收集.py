# -*- coding: utf-8 -*-
"""重跑指纹 · 收集与计算 —— 按固定范围收集文件 · sha256 · 算表 · 读旧表。"""
import hashlib
import json
import os

from .常量 import 扩展根, 指纹件


def 相对路径(路径):
    return os.path.relpath(路径, 扩展根).replace(os.sep, "/")


def 收集():
    """按固定范围收集要指纹的文件（返回相对路径列表，已排序）。"""
    文件 = []
    顶层声明 = ("包声明.json",)
    for 名 in 顶层声明:
        路 = os.path.join(扩展根, 名)
        if os.path.isfile(路):
            文件.append(路)
    实现 = os.path.join(扩展根, "Cargo.toml")
    if os.path.isfile(实现):
        文件.append(实现)
    for 目录 in ("能力声明", "错误码表", "类型声明"):
        根 = os.path.join(扩展根, 目录)
        if os.path.isdir(根):
            for 名 in sorted(os.listdir(根)):
                if 名.endswith(".json"):
                    文件.append(os.path.join(根, 名))
    src = os.path.join(扩展根, "src")
    for 当前, _子目录s, 名s in os.walk(src):
        for 名 in 名s:
            if 名.endswith(".rs"):
                文件.append(os.path.join(当前, 名))
    return sorted(相对路径(路) for 路 in 文件)


def sha256(路):
    摘要 = hashlib.sha256()
    with open(路, "rb") as 句柄:
        for 块 in iter(lambda: 句柄.read(1 << 20), b""):
            摘要.update(块)
    return 摘要.hexdigest()


def 算表():
    return {相: sha256(os.path.join(扩展根, 相)) for 相 in 收集()}


def 读旧表():
    if not os.path.isfile(指纹件):
        return None
    with open(指纹件, "r", encoding="utf-8") as 句柄:
        return json.load(句柄).get("指纹", {})
