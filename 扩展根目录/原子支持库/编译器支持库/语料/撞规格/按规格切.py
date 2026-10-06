"""按规格切 —— 按规格的 **12 种**记号切一段真文本（第 12 种 = `备注文本`：声明行末不加引号的自由文本，见 `程序文本格式.md` §二）。

（原名叫「切记号」，与产品公开面 `切记号` 同名 ⇒ 改名免得被读成「同一件事两套实现」）

★ 本件与产品词法**各算各的**：本件是**按规格文**独立切的第二实现，用来撞真语料。规格 §二 改名/加类后本件必须跟上。
"""

import re

from .规格词表 import (
    数字字符, 标识符字符, 规格界符, 规格裸关键字, 规格运算符, _字段序,
)

def 切记号(text):
    """按规格 12 种记号切。返回 (记号表, 未归类字符表)。

    记号表元素 = (种类, 行, 列, 文本, 字段序, 行类)
    行类 = '声明'（行首 `.`）/ '注释'（行首 `'`）/ '语句'
    """
    toks = []
    unknown = []
    lines = text.split("\n")
    nlines = len(lines)
    for li, 行文本 in enumerate(lines):
        last = (li == nlines - 1)
        if 行文本.endswith("\r"):
            行文本 = 行文本[:-1]
            crlf = True
        else:
            crlf = False
        terminated = (not last) or text.endswith("\n")
        if last and 行文本 == "" and not crlf:
            break                       # 末尾没有换行符 ⇒ 不产出幻影 换行 记号
        游标 = 0
        行长 = len(行文本)
        # 行首缩进
        while 游标 < 行长 and 行文本[游标] == " ":
            游标 += 1
        if 游标:
            toks.append(("空白", li, 0, 行文本[:游标], 0, "缩进"))
        line_start = 游标
        stripped = 行文本.lstrip()
        line_kind = ("声明" if stripped.startswith(".") else
                     "注释" if stripped.startswith("'") else "语句")
        # 先定位注释起点（不在字面量内的第一个 `'`）
        cut = None
        内游标 = 游标
        while 内游标 < 行长:
            字符 = 行文本[内游标]
            if 字符 in "“”\"":
                close = {"“": "”", "”": "”", '"': '"'}[字符]
                内游标 += 1
                while 内游标 < 行长 and 行文本[内游标] != close:
                    内游标 += 1
                内游标 += 1
                continue
            if 字符 == "'":
                cut = 内游标
                break
            内游标 += 1
        code_end = cut if cut is not None else 行长
        while 游标 < code_end:
            字符 = 行文本[游标]
            fi = _字段序(行文本, 游标)
            if 字符 == " ":
                列尾 = 游标
                while 列尾 < code_end and 行文本[列尾] == " ":
                    列尾 += 1
                toks.append(("空白", li, 游标, 行文本[游标:列尾], fi, line_kind))
                游标 = 列尾
                continue
            if 字符 == "." and 游标 == line_start:
                匹配 = re.match(r"\.([0-9A-Za-z_\u4e00-\u9fff]+)", 行文本[游标:])
                if 匹配:
                    toks.append(("关键字", li, 游标, 匹配.group(0), fi, line_kind))
                    游标 += len(匹配.group(0))
                    continue
            if 字符 == "#":
                匹配 = re.match(r"#([0-9A-Za-z_\u4e00-\u9fff]+)", 行文本[游标:])
                if 匹配:
                    toks.append(("常量引用", li, 游标, 匹配.group(0), fi, line_kind))
                    游标 += len(匹配.group(0))
                    continue
                unknown.append((li, 游标, 字符, 行文本, fi, line_kind))
                游标 += 1
                continue
            if 字符 in "“”\"":
                close = "”" if 字符 in "“”" else '"'
                列尾 = 游标 + 1
                while 列尾 < code_end and 行文本[列尾] != close:
                    列尾 += 1
                if 列尾 < code_end:
                    toks.append(("文本字面量", li, 游标, 行文本[游标:列尾 + 1], fi, line_kind))
                    游标 = 列尾 + 1
                    continue
                unknown.append((li, 游标, 字符, 行文本, fi, line_kind))
                游标 += 1
                continue
            if 数字字符.match(字符) or (字符 == "-" and 游标 + 1 < code_end and 数字字符.match(行文本[游标 + 1])
                                  and (游标 == line_start or not 标识符字符.match(行文本[游标 - 1]))):
                匹配 = re.match(r"-?(0[xX][0-9A-Fa-f]+|[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?)", 行文本[游标:])
                toks.append(("数值字面量", li, 游标, 匹配.group(0), fi, line_kind))
                游标 += len(匹配.group(0))
                continue
            if 字符 in 规格运算符:
                toks.append(("运算符", li, 游标, 字符, fi, line_kind))
                游标 += 1
                continue
            if 字符 in 规格界符:
                toks.append(("界符", li, 游标, 字符, fi, line_kind))
                游标 += 1
                continue
            if 标识符字符.match(字符):
                列尾 = 游标
                while 列尾 < code_end and 标识符字符.match(行文本[列尾]):
                    列尾 += 1
                词元 = 行文本[游标:列尾]
                if 游标 == line_start and 词元 in 规格裸关键字:
                    toks.append(("关键字", li, 游标, 词元, fi, line_kind))
                else:
                    toks.append(("标识符", li, 游标, 词元, fi, line_kind))
                游标 = 列尾
                continue
            unknown.append((li, 游标, 字符, 行文本, fi, line_kind))
            游标 += 1
        if cut is not None:
            toks.append(("注释", li, cut, 行文本[cut:], _字段序(行文本, cut), line_kind))
        if terminated:
            toks.append(("换行", li, 行长, "\r\n" if crlf else "\n", 0, line_kind))
    toks.append(("文件结束", nlines, 0, "", 0, ""))
    return toks, unknown
