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
    for 名称 in 顶层声明:
        路径 = os.path.join(扩展根, 名称)
        if os.path.isfile(路径):
            文件.append(路径)
    实现 = os.path.join(扩展根, "Cargo.toml")
    if os.path.isfile(实现):
        文件.append(实现)
    for 目录 in ("能力声明", "错误码表", "类型声明"):
        根目录 = os.path.join(扩展根, 目录)
        if os.path.isdir(根目录):
            for 名称 in sorted(os.listdir(根目录)):
                if 名称.endswith(".json"):
                    文件.append(os.path.join(根目录, 名称))
    src = os.path.join(扩展根, "src")
    for 当前, _子目录s, 名s in os.walk(src):
        for 名称 in 名s:
            if 名称.endswith(".rs"):
                文件.append(os.path.join(当前, 名称))
    return sorted(相对路径(路) for 路 in 文件)


def 算指纹(路径):
    摘要 = hashlib.sha256()
    with open(路径, "rb") as 句柄:
        for 数据块 in iter(lambda: 句柄.read(1 << 20), b""):
            摘要.update(数据块)
    return 摘要.hexdigest()


def 算表():
    return {相: 算指纹(os.path.join(扩展根, 相)) for 相 in 收集()}


def 读旧表():
    if not os.path.isfile(指纹件):
        return None
    with open(指纹件, "r", encoding="utf-8") as 句柄:
        return json.load(句柄).get("指纹", {})
