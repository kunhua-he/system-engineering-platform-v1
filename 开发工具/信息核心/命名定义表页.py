# -*- coding: utf-8 -*-
"""信息核心 · 命名定义表页 —— 读运行数据根下 `临时件/命名定义_表结构设计.md`（类目草案），
渲染成可搜索的表。

★ 本页**只读那份 md**，不查库 —— 类目四栏还没进库，先拿草案给人看。
★ 单拆一件的原因：`查看.py` 有 400 行硬限（判据 ⑲），本页塞进去会超 ⇒ 拆件。
"""
import html


def 命名定义表页(连接) -> bytes:
    """渲染命名定义类目草案表（`连接` 只为与路由表里其余页同形）。"""
    from 查看 import 页面壳
    from 运行数据根 import 口径 as 运行数据根口径
    草稿件 = (运行数据根口径.子目录路径(运行数据根口径.解析当前环境(), "临时件")
              / "命名定义_表结构设计.md")
    if not 草稿件.exists():
        return 页面壳("命名定义表",
                      f"<p class=\"红\">找不到草案件：<code>{html.escape(str(草稿件))}</code></p>")
    表格行清单 = []
    for 正文行 in 草稿件.read_text(encoding="utf-8").splitlines():
        if not 正文行.startswith("|"):
            continue
        单元格表 = [单元格.strip() for 单元格 in 正文行.strip("|").split("|")]
        if len(单元格表) != 7 or 单元格表[0] == "用途" or 单元格表[0].startswith("---"):
            continue
        表格行清单.append(单元格表)
    列标题表 = ("用途", "一级类目", "二级类目", "三级类目", "四级类目", "命名", "语义")
    表体 = "".join("<tr>" + "".join(f"<td>{html.escape(单元格值)}</td>" for 单元格值 in 单元格表) + "</tr>"
                   for 单元格表 in 表格行清单)
    正文 = (f"<h2>命名定义 · 类目草案（{len(表格行清单)} 行）</h2>"
            "<p><input id=\"筛选框\" class=\"输入\" placeholder=\"输入关键词筛（命名 / 语义 / 类目都行）\"></p>"
            f"<p class=\"灰\">来源：<code>{html.escape(str(草稿件))}</code></p>"
            "<table id=\"表\"><tr>"
            + "".join(f"<th>{html.escape(列标题)}</th>" for 列标题 in 列标题表)
            + f"</tr>{表体}</table>"
            "<script>const 筛=document.getElementById('筛选框'),表=document.getElementById('表');"
            "筛.oninput=()=>{const q=筛.value.trim();"
            "for(const r of 表.rows){if(r.rowIndex===0)continue;"
            "r.style.display=(!q||r.textContent.includes(q))?'':'none';}};</script>")
    return 页面壳("命名定义表", 正文)
