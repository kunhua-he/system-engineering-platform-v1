"""按规格切 —— 按规格的 11 种记号切一段真文本。（原名叫「切记号」，与产品公开面 `切记号` 同名 ⇒ 改名免得被读成「同一件事两套实现」）"""

import re

from .规格词表 import (
    数字字符, 标识符字符, SPEC_DELIM, SPEC_KEYWORD_BARE, SPEC_OP, _字段序,
)

def 切记号(text):
    """按规格 11 种记号切。返回 (记号表, 未归类字符表)。

    记号表元素 = (种类, 行, 列, 文本, 字段序, 行类)
    行类 = '声明'（行首 `.`）/ '注释'（行首 `'`）/ '语句'
    """
    toks = []
    unknown = []
    lines = text.split("\n")
    nlines = len(lines)
    for li, line in enumerate(lines):
        last = (li == nlines - 1)
        if line.endswith("\r"):
            line = line[:-1]
            crlf = True
        else:
            crlf = False
        terminated = (not last) or text.endswith("\n")
        if last and line == "" and not crlf:
            break                       # 末尾没有换行符 ⇒ 不产出幻影 换行 记号
        游标 = 0
        行长 = len(line)
        # 行首缩进
        while 游标 < 行长 and line[游标] == " ":
            游标 += 1
        if 游标:
            toks.append(("空白", li, 0, line[:游标], 0, "缩进"))
        line_start = 游标
        stripped = line.lstrip()
        line_kind = ("声明" if stripped.startswith(".") else
                     "注释" if stripped.startswith("'") else "语句")
        # 先定位注释起点（不在字面量内的第一个 `'`）
        cut = None
        内游标 = 游标
        while 内游标 < 行长:
            字符 = line[内游标]
            if 字符 in "“”\"":
                close = {"“": "”", "”": "”", '"': '"'}[字符]
                内游标 += 1
                while 内游标 < 行长 and line[内游标] != close:
                    内游标 += 1
                内游标 += 1
                continue
            if 字符 == "'":
                cut = 内游标
                break
            内游标 += 1
        code_end = cut if cut is not None else 行长
        while 游标 < code_end:
            字符 = line[游标]
            fi = _字段序(line, 游标)
            if 字符 == " ":
                列尾 = 游标
                while 列尾 < code_end and line[列尾] == " ":
                    列尾 += 1
                toks.append(("空白", li, 游标, line[游标:列尾], fi, line_kind))
                游标 = 列尾
                continue
            if 字符 == "." and 游标 == line_start:
                匹配 = re.match(r"\.([0-9A-Za-z_\u4e00-\u9fff]+)", line[游标:])
                if 匹配:
                    toks.append(("关键字", li, 游标, 匹配.group(0), fi, line_kind))
                    游标 += len(匹配.group(0))
                    continue
            if 字符 == "#":
                匹配 = re.match(r"#([0-9A-Za-z_\u4e00-\u9fff]+)", line[游标:])
                if 匹配:
                    toks.append(("常量引用", li, 游标, 匹配.group(0), fi, line_kind))
                    游标 += len(匹配.group(0))
                    continue
                unknown.append((li, 游标, 字符, line, fi, line_kind))
                游标 += 1
                continue
            if 字符 in "“”\"":
                close = "”" if 字符 in "“”" else '"'
                列尾 = 游标 + 1
                while 列尾 < code_end and line[列尾] != close:
                    列尾 += 1
                if 列尾 < code_end:
                    toks.append(("文本字面量", li, 游标, line[游标:列尾 + 1], fi, line_kind))
                    游标 = 列尾 + 1
                    continue
                unknown.append((li, 游标, 字符, line, fi, line_kind))
                游标 += 1
                continue
            if 数字字符.match(字符) or (字符 == "-" and 游标 + 1 < code_end and 数字字符.match(line[游标 + 1])
                                  and (游标 == line_start or not 标识符字符.match(line[游标 - 1]))):
                匹配 = re.match(r"-?(0[xX][0-9A-Fa-f]+|[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?)", line[游标:])
                toks.append(("数值字面量", li, 游标, 匹配.group(0), fi, line_kind))
                游标 += len(匹配.group(0))
                continue
            if 字符 in SPEC_OP:
                toks.append(("运算符", li, 游标, 字符, fi, line_kind))
                游标 += 1
                continue
            if 字符 in SPEC_DELIM:
                toks.append(("界符", li, 游标, 字符, fi, line_kind))
                游标 += 1
                continue
            if 标识符字符.match(字符):
                列尾 = 游标
                while 列尾 < code_end and 标识符字符.match(line[列尾]):
                    列尾 += 1
                word = line[游标:列尾]
                if 游标 == line_start and word in SPEC_KEYWORD_BARE:
                    toks.append(("关键字", li, 游标, word, fi, line_kind))
                else:
                    toks.append(("标识符", li, 游标, word, fi, line_kind))
                游标 = 列尾
                continue
            unknown.append((li, 游标, 字符, line, fi, line_kind))
            游标 += 1
        if cut is not None:
            toks.append(("注释", li, cut, line[cut:], _字段序(line, cut), line_kind))
        if terminated:
            toks.append(("换行", li, 行长, "\r\n" if crlf else "\n", 0, line_kind))
    toks.append(("文件结束", nlines, 0, "", 0, ""))
    return toks, unknown
