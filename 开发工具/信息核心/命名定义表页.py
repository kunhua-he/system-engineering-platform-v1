# -*- coding: utf-8 -*-
"""信息核心 · 命名定义表页 —— 把一份 md **原样渲染**成网页（简单阅读排版器）。

★ 不做重排、不改写：md 里写什么，页面就显示什么（标题 · 表格 · 列表 · 段落 · 粗体 · 行内码）。
★ 单拆一件的原因：`查看.py` 有 400 行硬限（判据 ⑲），塞进去会超。
"""
import html
import re


def 行内(文本: str) -> str:
    """行内标记：先转义，再放 `**粗**` 与反引号码。"""
    文本 = html.escape(文本)
    文本 = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", 文本)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", 文本)


def 表格块(块行表: list) -> str:
    """md 表格块 ⇒ `<table>`（第二行是 `|---|` 分隔行 ⇒ 跳过）。"""
    数据行表 = []
    for 块序号, 正文行 in enumerate(块行表):
        单元格表 = [单元格.strip() for 单元格 in 正文行.strip("|").split("|")]
        if 块序号 == 1 and all(set(单元格) <= set("-: ") for 单元格 in 单元格表):
            continue
        数据行表.append(单元格表)
    if not 数据行表:
        return ""
    表头行 = "".join(f"<th>{行内(单元格值)}</th>" for 单元格值 in 数据行表[0])
    表体行 = "".join("<tr>" + "".join(f"<td>{行内(单元格值)}</td>" for 单元格值 in 单元格表)
                     + "</tr>" for 单元格表 in 数据行表[1:])
    return f"<table><tr>{表头行}</tr>{表体行}</table>"


def 渲染(正文行表: list) -> str:
    """md 行表 ⇒ HTML（只认标题 / 表格 / 列表 / 段落）。"""
    段落表 = []
    行位置 = 0
    while 行位置 < len(正文行表):
        当前行 = 正文行表[行位置].strip()
        行位置 += 1
        if not 当前行:
            continue
        if 当前行.startswith("#"):
            标题级 = len(当前行) - len(当前行.lstrip("#"))
            段落表.append(f"<h{标题级}>{行内(当前行[标题级:].strip())}</h{标题级}>")
        elif 当前行.startswith("|"):
            块行表 = [当前行]
            while 行位置 < len(正文行表) and 正文行表[行位置].strip().startswith("|"):
                块行表.append(正文行表[行位置].strip())
                行位置 += 1
            段落表.append(表格块(块行表))
        elif 当前行.startswith(("- ", "* ")):
            列表项表 = [f"<li>{行内(当前行[2:])}</li>"]
            while 行位置 < len(正文行表) and 正文行表[行位置].strip().startswith(("- ", "* ")):
                列表项表.append(f"<li>{行内(正文行表[行位置].strip()[2:])}</li>")
                行位置 += 1
            段落表.append("<ul>" + "".join(列表项表) + "</ul>")
        else:
            段落表.append(f"<p>{行内(当前行)}</p>")
    return "".join(段落表)


def 命名定义表页(连接) -> bytes:
    """读运行数据根 `临时件/命名定义_表结构设计.md`，**原样渲染**成网页。"""
    from 查看 import 页面壳
    from 运行数据根 import 口径 as 运行数据根口径
    草稿件 = (运行数据根口径.子目录路径(运行数据根口径.解析当前环境(), "临时件")
              / "命名定义_表结构设计.md")
    if not 草稿件.exists():
        return 页面壳("命名定义表",
                      f"<p class=\"红\">找不到草案件：<code>{html.escape(str(草稿件))}</code></p>")
    正文行表 = 草稿件.read_text(encoding="utf-8").splitlines()
    return 页面壳("命名定义表", 渲染(正文行表))
