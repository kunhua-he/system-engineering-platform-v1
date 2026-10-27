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
        # ① 列**顺序**变了（集合相同、顺序不同）⇒ 逐列比对会错位 ⇒ 必须拒并（列面冲突）。
        重排语句 = ("create table 未完成(号 integer primary key, 缺什么 text not null, "
                "验证命令 text, 备注 text, 落点 text)")
        with sqlite3.connect(库文件表[1]) as 连接:
            连接.execute("drop table 未完成")
            连接.execute(重排语句)
        动作表, 冲突表, 跳过表 = 重放.合并三方库(*库文件表, 临时根)
        assert not 动作表 and len(冲突表) == 1 and 冲突表[0]["键"] == ("列面",), 冲突表
        # ② 腿**只在末尾追加一栏**（带默认值）⇒ 合法演进、按腿列面放行
        #   （6125 给台账加「类别」栏正是这一形；一刀切拒并曾让任何加列改造都合不进主干）。
        with sqlite3.connect(库文件表[1]) as 连接:
            连接.execute("drop table 未完成")
            连接.execute(建表语句)
            连接.execute("alter table 未完成 add column 类别 text not null default '债务'")
        动作表, 冲突表, 跳过表 = 重放.合并三方库(*库文件表, 临时根)
        assert not 冲突表, 冲突表
        with sqlite3.connect(库文件表[0]) as 连接:
            连接.execute("drop table 未完成")
        with sqlite3.connect(库文件表[1]) as 连接:
            连接.execute("drop table 未完成")
            连接.execute(建表语句)
            连接.execute("alter table 未完成 add column 类别 text not null default '债务'")
            连接.execute("insert into 未完成(号, 缺什么, 落点, 验证命令) values(7,'腿新增','','验证内容')")
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
        验条款三态(仓根, 临时根)
        print("通过 源库边界：列漂移拒绝、基缺表不漏行、缺参保值、空串和空值分离")

def 验条款三态(仓根, 临时根):
    """物理复制依赖，真实CLI与具名重放均逐字段回读；不触碰正式库。"""
    import shutil
    import subprocess
    import sys
    from ... import 合主干源库重放 as 重放
    集成树 = 临时根 / "条款隔离"
    for 目录名 in ("开发工具", "构建装配", "测试验证", "契约声明"):
        shutil.copytree(Path(仓根) / 目录名, 集成树 / 目录名,
                        ignore=shutil.ignore_patterns("__pycache__", "*.db", "target"))
    库件 = 集成树 / "开发工具/信息核心/信息核心.db"
    文档路径 = "项目文档/条款三态验证.md"
    with sqlite3.connect(库件) as 连接:
        for 建表语句 in 重放.表定义.建表语句:
            连接.execute(建表语句)
        连接.execute("insert into 条款 values(?,?,?,?,?)", (文档路径, 0, "标题", "正文", "正式"))
    def 读权威档():
        with sqlite3.connect(库件) as 连接:
            return 连接.execute("select 权威档 from 条款 where 文档路径=? and 序号=0", (文档路径,)).fetchone()[0]
    def 跑条款(参数表):
        return subprocess.run([sys.executable, "开发工具/信息核心/信息核心.py", "记条款",
                               "--文档路径", 文档路径, "--序号", "0", "--标题", "标题", "--正文", "正文"] + 参数表,
                              cwd=集成树, capture_output=True, text=True, timeout=5)
    assert 跑条款(["--覆盖"]).returncode == 0 and 读权威档() == "正式"
    assert 跑条款(["--覆盖", "--权威档", ""]).returncode == 0 and 读权威档() == ""
    assert 跑条款(["--覆盖", "--权威档为空"]).returncode == 0 and 读权威档() is None
    assert 跑条款(["--覆盖"]).returncode == 0 and 读权威档() is None
    assert 跑条款(["--覆盖", "--权威档", "候选"]).returncode == 0 and 读权威档() == "候选"
    assert 跑条款(["--覆盖", "--权威档", "候选", "--权威档为空"]).returncode != 0 and 读权威档() == "候选"
    assert 跑条款(["--权威档", "拒写"]).returncode != 0 and 读权威档() == "候选"
    for 权威档 in ("", None, "正式"):
        动作 = {"表":"条款", "键":(文档路径, 0),
                "列名表":["文档路径", "序号", "标题", "正文", "权威档"],
                "腿值":(文档路径, 0, "标题", "正文", 权威档)}
        退出码, 说明 = 重放._重放一条(str(集成树), 动作)
        assert 退出码 == 0 and 读权威档() == 权威档, (退出码, 说明, 读权威档(), 权威档)
    print("通过 条款真实CLI7态与具名重放3态：缺参/空串/NULL/实值/冲突/覆盖保护逐字段一致")

