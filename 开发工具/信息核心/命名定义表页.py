# -*- coding: utf-8 -*-
"""信息核心 · 命名定义表页 —— 把一份 md **原样渲染**成网页（简单阅读排版器）。

★ 不做重排、不改写：md 里写什么，页面就显示什么（标题 · 表格 · **可收可展的嵌套列表** · 段落 · 粗体 · 行内码）。
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
    表头行 = "".join(f'<th onclick="排序(this)">{行内(单元格值)}</th>' for 单元格值 in 数据行表[0])
    表体行 = "".join("<tr>" + "".join(f"<td>{行内(单元格值)}</td>" for 单元格值 in 单元格表)
                     + "</tr>" for 单元格表 in 数据行表[1:])
    return f"<table><tr>{表头行}</tr>{表体行}</table>"


def 列表块(块行表: list) -> str:
    """缩进嵌套的 `- ` 列表 ⇒ 树。**有子项的节点渲染成 `<details open>`**（可收可展、默认展开），
    叶子仍是 `<li>`。缩进按前导空格算，每 2 空格一层。"""
    项表 = [(len(列表行) - len(列表行.lstrip(" ")), 列表行.strip()[2:]) for 列表行 in 块行表]
    根节点表 = []
    祖先节点栈 = []
    for 缩进级, 节点文本 in 项表:
        while 祖先节点栈 and 祖先节点栈[-1][0] >= 缩进级:
            祖先节点栈.pop()
        节点 = {"文本": 节点文本, "子": []}
        (祖先节点栈[-1][1]["子"] if 祖先节点栈 else 根节点表).append(节点)
        祖先节点栈.append((缩进级, 节点))

    def 渲染节点(节点: dict) -> str:
        if not 节点["子"]:
            return f"<li>{行内(节点['文本'])}</li>"
        子节点表 = "".join(渲染节点(子节点) for 子节点 in 节点["子"])
        return (f"<details open><summary>{行内(节点['文本'])}</summary>"
                f"<ul>{子节点表}</ul></details>")

    return "<ul>" + "".join(渲染节点(节点) for 节点 in 根节点表) + "</ul>"


def 渲染(正文行表: list) -> str:
    """md 行表 ⇒ HTML（标题 / 表格 / 列表 / 段落）。**嵌套列表渲染成可收可展的树**。"""
    段落表 = []
    行位置 = 0
    while 行位置 < len(正文行表):
        原行 = 正文行表[行位置]
        当前行 = 原行.strip()
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
            块行表 = [原行]
            while 行位置 < len(正文行表) and 正文行表[行位置].strip().startswith(("- ", "* ")):
                块行表.append(正文行表[行位置])
                行位置 += 1
            段落表.append(列表块(块行表))
        else:
            段落表.append(f"<p>{行内(当前行)}</p>")
    return "".join(段落表)


排序脚本 = ("<script>function 排序(头){const 表=头.closest('table'),列=[...头.parentNode.children].indexOf(头);"
           "const 向=头.dataset.向==='升'?'降':'升';"
           "[...头.parentNode.children].forEach(x=>{delete x.dataset.向;x.textContent=x.textContent.replace(/[▲▼]$/,'')});"
           "头.dataset.向=向;头.textContent+=(向==='升'?'▲':'▼');"
           "const 行=[...表.rows].slice(1);"
           "行.sort((a,b)=>{const x=a.cells[列].textContent,y=b.cells[列].textContent;"
           "return (向==='升'?1:-1)*x.localeCompare(y,'zh');});"
           "行.forEach(r=>表.tBodies[0].appendChild(r));}</script>")


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
    return 页面壳("命名定义表", 渲染(正文行表) + 排序脚本)
