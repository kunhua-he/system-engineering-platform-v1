# -*- coding: utf-8 -*-
"""记条款样本 —— `记条款` 的**孤儿行闸**正反样本（真跑 · 临时仓 · 不碰真库）。

**为什么要它**：`条款` 表是全部 md 正文的唯一存本。只过「仓内相对路径闸」时，一个拼错的新路径
（盘上没 md、库里也别处没有）也能写进去 ⇒ 一行无主正文（孤儿行）。本件验两态：
① 反向：全新文档路径 ⇒ 退 2 且库里不留行；② 正向：已入库文档路径 ⇒ 退 0（判据不误伤合法改节）。
"""
import contextlib
import io
import sqlite3
import sys
import tempfile
from pathlib import Path

仓根 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(仓根 / "开发工具" / "信息核心"))

import 记条款  # noqa: E402


def 记条款样本() -> list:
    """⇒ 样本表 `[(说明, 通过)]`。"""
    样本表 = []

    def 记样本(说明, 通过):
        样本表.append((说明, bool(通过)))

    with tempfile.TemporaryDirectory(prefix="v1记条款样本-") as 临时根文本:
        临时根 = Path(临时根文本)
        库目录 = 临时根 / "开发工具" / "信息核心"
        库目录.mkdir(parents=True, exist_ok=True)
        库件 = 库目录 / "信息核心.db"
        连接 = sqlite3.connect(str(库件))
        try:
            连接.execute("create table 条款 (文档路径 text, 序号 integer, 标题 text, 正文 text, 权威档 text)")
            连接.execute("insert into 条款 values ('样本文档.md', 1, '样本节', '样本正文', '落点与规范')")
            连接.commit()
        finally:
            连接.close()
        旧仓根 = 记条款.仓根
        记条款.仓根 = 临时根
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                反向码 = 记条款.记条款({"文档路径": "拼错的文档.md", "序号": "1", "正文": "样本"})
            连接 = sqlite3.connect(str(库件))
            try:
                落库 = 连接.execute(
                    "select count(*) from 条款 where 文档路径 = '拼错的文档.md'").fetchone()[0]
            finally:
                连接.close()
            记样本("记条款·反向：全新文档路径（盘上无 md · 库里无行）⇒ 拒且不留行",
                反向码 == 2 and 落库 == 0)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                正向码 = 记条款.记条款({"文档路径": "样本文档.md", "序号": "2", "正文": "第二节"})
            记样本("记条款·正向：已入库文档路径 ⇒ 放行（不误伤合法改节）", 正向码 == 0)
        finally:
            记条款.仓根 = 旧仓根
    return 样本表
