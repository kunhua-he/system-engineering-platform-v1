# -*- coding: utf-8 -*-
r"""账本差集样本 —— `v1_db` 的 `账本差集` 正反样本（临时仓 + 临时账本，跑完即删）。

**为何要它**：schema 差集是「核对者别把漂移当主干事实」的那把尺 —— 必须可复跑地证明：

  · 盘上多一表 / 多一列 ⇒ 逐项列出，且**来源开工号**指到引入它的那条未合腿；
  · 盘上与主干一致 ⇒ **无漂移**（不虚报）；
  · 给不出来源 ⇒ 如实「未归因」（不许猜）；
  · 只读：跑前后盘上账本 sha256 不变。

★ 自建临时仓 + 临时运行数据根，跑完即删 ⇒ **真仓 / 真账本一个字节都不改**。
"""
from pathlib import Path

主干建表 = (
    '建表语句 = (\n'
    '    """create table if not exists 开工 (\n'
    '        开工号    text primary key,\n'
    '        工作内容  text not null\n'
    '    )""",\n'
    '    """create table if not exists 认领 (\n'
    '        开工号   text not null,\n'
    '        路径     text not null,\n'
    '        primary key (开工号, 路径)\n'
    '    )""",\n'
    ')\n'
)
腿建表 = (
    '建表语句 = (\n'
    '    """create table if not exists 开工 (\n'
    '        开工号    text primary key,\n'
    '        工作内容  text not null\n'
    '    )""",\n'
    '    """create table if not exists 认领 (\n'
    '        开工号   text not null,\n'
    '        路径     text not null,\n'
    '        primary key (开工号, 路径)\n'
    '    )""",\n'
    '    """create table if not exists 开工基线 (\n'
    '        开工号  text primary key,\n'
    '        基线    text not null\n'
    '    )""",\n'
    ')\n'
)
作业建表 = (
    '建表语句 = (\n'
    '    """create table if not exists 作业 (\n'
    '        任务ID  text primary key,\n'
    '        状态    text not null\n'
    '    )""",\n'
    ')\n'
)
# 盘上账本：一致（与主干同） vs 漂移（多 开工.基线 列 + 开工基线 / 认领重叠 两表）。
开工一致表 = (
    "create table 开工 (开工号 text primary key, 工作内容 text not null)",
    "create table 认领 (开工号 text not null, 路径 text not null, primary key (开工号, 路径))",
)
开工漂移表 = (
    "create table 开工 (开工号 text primary key, 工作内容 text not null, 基线 text)",
    "create table 认领 (开工号 text not null, 路径 text not null, primary key (开工号, 路径))",
    "create table 开工基线 (开工号 text primary key, 基线 text not null)",
    "create table 认领重叠 (开工号 text, 路径 text)",
)
作业表 = ("create table 作业 (任务ID text primary key, 状态 text not null)",)


def _写账本(库件, 建表表) -> None:
    """写一个最小 sqlite 账本（只建表，不插行）。"""
    import sqlite3
    连接 = sqlite3.connect(str(库件))
    try:
        for 语句 in 建表表:
            连接.execute(语句)
        连接.commit()
    finally:
        连接.close()


def 账本差集样本(仓根, 工具表) -> list:
    """⇒ 样本表（`(说明, 通过?)`）；临时仓 + 临时运行数据根，跑完即删。"""
    import hashlib
    import os
    import shutil
    import subprocess
    import tempfile
    from unittest.mock import patch

    from 开发工具.运行数据根.口径 import 覆盖变量名
    from .合主干有界跑 import 干净环境

    样本表 = []
    临时根 = Path(tempfile.mkdtemp(prefix="v1账本差集样本-"))
    try:
        环境表 = 干净环境()
        身份 = ["-c", "user.name=样本", "-c", "user.email=样本@例"]
        样本仓 = 临时根 / "样本仓"
        服务目录 = 样本仓 / "开发工具" / "MCP服务"
        服务目录.mkdir(parents=True)
        (服务目录 / "开工账本.py").write_text(主干建表, encoding="utf-8")
        (服务目录 / "作业账本.py").write_text(作业建表, encoding="utf-8")
        subprocess.run(["git", "init", "-q", "-b", "主干"], cwd=样本仓, check=True, env=环境表)
        subprocess.run(["git"] + 身份 + ["add", "."], cwd=样本仓, check=True, env=环境表)
        subprocess.run(["git"] + 身份 + ["commit", "-q", "-m", "主干"], cwd=样本仓,
                   check=True, env=环境表)
        subprocess.run(["git", "checkout", "-q", "-b", "腿/v1-100448"], cwd=样本仓,
                   check=True, env=环境表)
        (服务目录 / "开工账本.py").write_text(腿建表, encoding="utf-8")
        subprocess.run(["git"] + 身份 + ["commit", "-q", "-a", "-m", "腿加表"], cwd=样本仓,
                   check=True, env=环境表)
        for 带漂移, 漂移根 in ((True, 临时根 / "漂移数据根"), (False, 临时根 / "一致数据根")):
            库目录 = 漂移根 / "数据库"
            库目录.mkdir(parents=True)
            _写账本(库目录 / "开工账本.db", 开工漂移表 if 带漂移 else 开工一致表)
            _写账本(库目录 / "作业账本.db", 作业表)
        库件 = 临时根 / "漂移数据根" / "数据库" / "开工账本.db"
        读前 = hashlib.sha256(库件.read_bytes()).hexdigest()
        with patch.dict(os.environ, {覆盖变量名: str(临时根 / "漂移数据根")}):
            正读数 = 工具表["v1_db"][0]({"操作": "账本差集"}, 样本仓)
        with patch.dict(os.environ, {覆盖变量名: str(临时根 / "一致数据根")}):
            反读数 = 工具表["v1_db"][0]({"操作": "账本差集"}, 样本仓)
        读后 = hashlib.sha256(库件.read_bytes()).hexdigest()
        正退出码, 正输出 = 正读数
        反退出码, 反输出 = 反读数
        样本表.append(("盘上多表 + 多列 ⇒ 逐项列出（开工基线 / 认领重叠 / 开工.基线）：退出码 %d"
                 % 正退出码,
                 正退出码 == 0 and "多表 开工基线" in 正输出 and "多表 认领重叠" in 正输出
                 and "多列 开工.基线" in 正输出))
        样本表.append(("来源开工号指到引入它的未合腿（开工基线 ← v1-100448）：%s"
                 % ("是" if "多表 开工基线  ← v1-100448" in 正输出 else "否"),
                 "多表 开工基线  ← v1-100448" in 正输出))
        样本表.append(("给不出来源 ⇒ 如实「未归因」，不许猜：%s"
                 % ("是" if "多表 认领重叠  ← 未归因" in 正输出 else "否"),
                 "多表 认领重叠  ← 未归因" in 正输出))
        样本表.append(("盘上与主干一致 ⇒ 无漂移（不虚报）：退出码 %d" % 反退出码,
                 反退出码 == 0 and "无漂移" in 反输出 and "漂移项 0" in 反输出))
        样本表.append(("只读（跑前后盘上账本 sha256 不变）：%s" % ("是" if 读前 == 读后 else "否"),
                 读前 == 读后))
    finally:
        shutil.rmtree(临时根, ignore_errors=True)
    return 样本表
