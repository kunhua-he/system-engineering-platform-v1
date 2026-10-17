# -*- coding: utf-8 -*-
"""重跑指纹 · 收集与计算 —— 按固定范围收集文件 · sha256 · 算指纹表 · 读旧指纹表。"""
import hashlib
import json
import os

from .常量 import 扩展根路径, 指纹件


def 相对路径(路径):
    return os.path.relpath(路径, 扩展根路径).replace(os.sep, "/")


def 收集指纹文件():
    """按固定范围收集要指纹的文件（返回相对路径列表，已排序）。"""
    件路径表 = []
    顶层声明 = ("包声明.json",)
    for 名称 in 顶层声明:
        路径 = os.path.join(扩展根路径, 名称)
        if os.path.isfile(路径):
            件路径表.append(路径)
    实现 = os.path.join(扩展根路径, "Cargo.toml")
    if os.path.isfile(实现):
        件路径表.append(实现)
    for 子目录名 in ("能力声明", "错误码表", "类型声明"):
        根目录 = os.path.join(扩展根路径, 子目录名)
        if os.path.isdir(根目录):
            for 名称 in sorted(os.listdir(根目录)):
                if 名称.endswith(".json"):
                    件路径表.append(os.path.join(根目录, 名称))
    源码目录 = os.path.join(扩展根路径, "src")
    for 当前目录, _子目录s, 名s in os.walk(源码目录):
        for 名称 in 名s:
            if 名称.endswith(".rs"):
                件路径表.append(os.path.join(当前目录, 名称))
    return sorted(相对路径(路径) for 路径 in 件路径表)


def 算指纹(路径):
    摘要器 = hashlib.sha256()
    with open(路径, "rb") as 句柄:
        for 数据块 in iter(lambda: 句柄.read(1 << 20), b""):
            摘要器.update(数据块)
    return 摘要器.hexdigest()


def 算指纹表():
    return {相对路径: 算指纹(os.path.join(扩展根路径, 相对路径)) for 相对路径 in 收集指纹文件()}


def 读旧指纹表():
    if not os.path.isfile(指纹件):
        return None
    with open(指纹件, "r", encoding="utf-8") as 句柄:
        return json.load(句柄).get("指纹", {})
