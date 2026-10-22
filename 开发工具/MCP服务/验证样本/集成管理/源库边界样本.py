# -*- coding: utf-8 -*-
"""真实临时三库及台账写口的列面、缺表与空值反证。"""
import importlib.util
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch


def 验源库边界(仓根):
    from ... import 合主干源库重放 as 重放
    with tempfile.TemporaryDirectory() as 临时目录:
        临时根 = Path(临时目录)
        库文件表 = [临时根 / (名称 + ".db") for 名称 in ("基库", "腿库", "主干库")]
        建表语句 = "create table 未完成(号 integer primary key, 缺什么 text not null, 落点 text, 验证命令 text)"
        for 库件 in 库文件表:
            with sqlite3.connect(库件) as 连接:
                连接.execute(建表语句)
        with sqlite3.connect(库文件表[1]) as 连接:
            连接.execute("alter table 未完成 add column 备注 text")
        动作表, 冲突表, 跳过表 = 重放.合并三方库(*库文件表, 临时根)
        assert not 动作表 and len(冲突表) == 1 and 冲突表[0]["键"] == ("列面",)
        with sqlite3.connect(库文件表[0]) as 连接:
            连接.execute("drop table 未完成")
        with sqlite3.connect(库文件表[1]) as 连接:
            连接.execute("drop table 未完成")
            连接.execute(建表语句)
            连接.execute("insert into 未完成 values(7,'腿新增','','验证内容')")
        动作表, 冲突表, 跳过表 = 重放.合并三方库(*库文件表, 临时根)
        assert len(动作表) == 1 and not 冲突表 and not 跳过表
        加载规约 = importlib.util.spec_from_file_location("台账写口样本", Path(仓根)/"开发工具/信息核心/记未完成.py")
        写口模块 = importlib.util.module_from_spec(加载规约)
        加载规约.loader.exec_module(写口模块)
        with patch.object(写口模块.表定义, "库路径", lambda 根目录: 库文件表[1]):
            assert 写口模块.记未完成({"号":"7", "缺什么":"只改描述"}) == 0
            with sqlite3.connect(库文件表[1]) as 连接:
                assert 连接.execute("select 落点,验证命令 from 未完成 where 号=7").fetchone() == ("", "验证内容")
            assert 写口模块.记未完成({"号":"7", "缺什么":"显式空串", "验证命令":""}) == 0
            assert 写口模块.记未完成({"号":"7", "缺什么":"显式空值", "落点为空":""}) == 0
            with sqlite3.connect(库文件表[1]) as 连接:
                assert 连接.execute("select 落点,验证命令 from 未完成 where 号=7").fetchone() == (None, "")
        print("通过 源库边界：列漂移拒绝、基缺表不漏行、缺参保值、空串和空值分离")
