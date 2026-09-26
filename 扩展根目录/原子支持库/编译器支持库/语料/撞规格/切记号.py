"""切记号 —— 按规格的 11 种记号切一段真文本。"""

import re

from .规格词表 import (
    DIGIT, ID_CHAR, SPEC_DELIM, SPEC_KEYWORD_BARE, SPEC_OP, _field_idx,
)

def tokenize(text):
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
        i = 0
        n = len(line)
        # 行首缩进
        while i < n and line[i] == " ":
            i += 1
        if i:
            toks.append(("空白", li, 0, line[:i], 0, "缩进"))
        line_start = i
        stripped = line.lstrip()
        line_kind = ("声明" if stripped.startswith(".") else
                     "注释" if stripped.startswith("'") else "语句")
        # 先定位注释起点（不在字面量内的第一个 `'`）
        cut = None
        j = i
        while j < n:
            c = line[j]
            if c in "“”\"":
                close = {"“": "”", "”": "”", '"': '"'}[c]
                j += 1
                while j < n and line[j] != close:
                    j += 1
                j += 1
                continue
            if c == "'":
                cut = j
                break
            j += 1
        code_end = cut if cut is not None else n
        while i < code_end:
            c = line[i]
            fi = _field_idx(line, i)
            if c == " ":
                k = i
                while k < code_end and line[k] == " ":
                    k += 1
                toks.append(("空白", li, i, line[i:k], fi, line_kind))
                i = k
                continue
            if c == "." and i == line_start:
                m = re.match(r"\.([0-9A-Za-z_\u4e00-\u9fff]+)", line[i:])
                if m:
                    toks.append(("关键字", li, i, m.group(0), fi, line_kind))
                    i += len(m.group(0))
                    continue
            if c == "#":
                m = re.match(r"#([0-9A-Za-z_\u4e00-\u9fff]+)", line[i:])
                if m:
                    toks.append(("常量引用", li, i, m.group(0), fi, line_kind))
                    i += len(m.group(0))
                    continue
                unknown.append((li, i, c, line, fi, line_kind))
                i += 1
                continue
            if c in "“”\"":
                close = "”" if c in "“”" else '"'
                k = i + 1
                while k < code_end and line[k] != close:
                    k += 1
                if k < code_end:
                    toks.append(("文本字面量", li, i, line[i:k + 1], fi, line_kind))
                    i = k + 1
                    continue
                unknown.append((li, i, c, line, fi, line_kind))
                i += 1
                continue
            if DIGIT.match(c) or (c == "-" and i + 1 < code_end and DIGIT.match(line[i + 1])
                                  and (i == line_start or not ID_CHAR.match(line[i - 1]))):
                m = re.match(r"-?(0[xX][0-9A-Fa-f]+|[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?)", line[i:])
                toks.append(("数值字面量", li, i, m.group(0), fi, line_kind))
                i += len(m.group(0))
                continue
            if c in SPEC_OP:
                toks.append(("运算符", li, i, c, fi, line_kind))
                i += 1
                continue
            if c in SPEC_DELIM:
                toks.append(("界符", li, i, c, fi, line_kind))
                i += 1
                continue
            if ID_CHAR.match(c):
                k = i
                while k < code_end and ID_CHAR.match(line[k]):
                    k += 1
                word = line[i:k]
                if i == line_start and word in SPEC_KEYWORD_BARE:
                    toks.append(("关键字", li, i, word, fi, line_kind))
                else:
                    toks.append(("标识符", li, i, word, fi, line_kind))
                i = k
                continue
            unknown.append((li, i, c, line, fi, line_kind))
            i += 1
        if cut is not None:
            toks.append(("注释", li, cut, line[cut:], _field_idx(line, cut), line_kind))
        if terminated:
            toks.append(("换行", li, n, "\r\n" if crlf else "\n", 0, line_kind))
    toks.append(("文件结束", nlines, 0, "", 0, ""))
    return toks, unknown
