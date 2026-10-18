# -*- coding: utf-8 -*-
"""已记账恢复的真实隔离工作树正反样本。"""
import hashlib
import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch


def 样本列表(仓根):
    """真实Git登记树、临时账本、准确原记录，绝不操作在用开工。"""
    from ... import 开工账本 as 账本
    from ...文件编辑 import 写盘恢复, 写盘执行, 写盘账本
    from ...施工管理.仓操作 import 跑命令
    输出表 = []
    with tempfile.TemporaryDirectory(prefix="v1恢复样本-") as 临时目录:
        临时根 = Path(临时目录)
        公共仓 = 临时根 / "公共仓"
        公共仓.mkdir()
        def 执行命令(参数表, 目标树=公共仓):
            退出码, 说明 = 跑命令(["git"] + 参数表, cwd=目标树)
            if 退出码:
                raise RuntimeError(说明)
            return 说明
        执行命令(["init", "-q"])
        原全文, 候选全文 = "print(1)\n", "print(2)\n"
        (公共仓 / "目标.py").write_text(原全文)
        执行命令(["add", "目标.py"])
        执行命令(["-c", "user.name=隔离样本", "-c", "user.email=sample@localhost", "commit", "-qm", "夹具"])
        工作树 = 临时根 / "工作树"
        执行命令(["worktree", "add", "-qb", "腿/v1-900001", str(工作树)])
        件路径 = 工作树 / "目标.py"
        信息目录 = 工作树 / "开发工具/信息核心"
        信息目录.mkdir(parents=True)
        with sqlite3.connect(信息目录 / "信息核心.db") as 信息连接:
            信息连接.execute("create table 命名登记(名字 text, 状态 text)")
            信息连接.execute("create table 命名例外(名字 text)")
        账本路径 = 临时根 / "账本.db"
        def 连夹具():
            连接 = sqlite3.connect(账本路径)
            连接.row_factory = sqlite3.Row
            return 连接
        with 连夹具() as 连接:
            for 建表语句 in 账本.建表语句:
                连接.execute(建表语句)
        写前指纹 = 写盘执行.内容指纹(原全文)
        写后指纹 = 写盘执行.内容指纹(候选全文)
        def 重置夹具():
            if 件路径.is_symlink():
                件路径.unlink()
            件路径.write_text(原全文)
            with 连夹具() as 连接:
                for 表名 in ("开工", "认领", "改动"):
                    连接.execute("delete from " + 表名)
                写盘账本.补意图表(连接)
                连接.execute("delete from 写盘意图")
                连接.execute("insert into 开工(开工号,工作内容,分支名,工作树,状态,开工时间) values (?,?,?,?,?,?)", ("v1-900001", "夹具", "腿/v1-900001", str(工作树), "进行中", "夹具"))
                连接.execute("insert into 认领 values (?,?,?)", ("v1-900001", "目标.py", 写后指纹))
                连接.execute("insert into 改动(编号,开工号,路径,功能,写前指纹,写后指纹,时间) values (?,?,?,?,?,?,?)", (1, "v1-900001", "目标.py", "修改", 写前指纹, 写后指纹, "夹具"))
        参数表 = {"改动编号": 1, "路径": "目标.py", "候选全文": 候选全文}
        def 恢复(覆盖参数=None, 目标仓=公共仓):
            return 写盘恢复.恢复已记账写后(目标仓, "v1-900001", 参数表 | (覆盖参数 or {}))
        with patch.object(账本, "连账本", 连夹具), patch.object(账本, "开工账本路径", lambda: 账本路径):
            重置夹具()
            索引前 = 执行命令(["ls-files", "-s"], 工作树)
            原记录 = dict(连夹具().execute("select * from 改动 where 编号=1").fetchone())
            退出码, 说明 = 恢复()
            with 连夹具() as 连接:
                历史不变 = dict(连接.execute("select * from 改动 where 编号=1").fetchone()) == 原记录
                审计齐 = 连接.execute("select count(*) from 已记账恢复").fetchone()[0] == 1
                认领不变 = 账本.读认领(连接, "v1-900001")["目标.py"] == 写后指纹
            输出表.append(("精确恢复/原历史认领不变/正式审计/索引零污染", 退出码 == 0 and 件路径.read_text() == 候选全文 and 历史不变 and 审计齐 and 认领不变 and 索引前 == 执行命令(["ls-files", "-s"], 工作树)))
            修改时刻 = 件路径.stat().st_mtime_ns
            输出表.append(("同写后幂等零写", 恢复()[0] == 0 and 件路径.stat().st_mtime_ns == 修改时刻))
            for 测试名, 语句 in (
                ("无记录", "delete from 改动"),
                ("失败记录", "update 改动 set 功能='失败'"),
                ("不进行中", "update 开工 set 状态='已释放'"),
                ("未认领", "delete from 认领"),
                ("错认领指纹", "update 认领 set 指纹='不同'"),
                ("后续合法修改", "insert into 改动(开工号,路径,功能,写前指纹,写后指纹,时间) values ('v1-900001','目标.py','修改','不同','不同','夹具')"),
                ("原写前hash不同", "update 改动 set 写前指纹='不同'"),
                ("原写后hash不同", "update 改动 set 写后指纹='不同'")):
                重置夹具()
                with 连夹具() as 连接:
                    连接.execute(语句)
                输出表.append((测试名 + "拒且零写", 恢复()[0] != 0 and 件路径.read_text() == 原全文))
            for 测试名, 覆盖参数 in (("错路径", {"路径": "其他.py"}), ("候选hash错", {"候选全文": "print(3)\n"}), ("树外路径", {"路径": "../目标.py"}), ("无确切编号", {"改动编号": 99})):
                重置夹具()
                输出表.append((测试名 + "拒且零写", 恢复(覆盖参数)[0] != 0 and 件路径.read_text() == 原全文))
            重置夹具()
            件路径.write_text("print(3)\n")
            输出表.append(("盘第三版本拒", 恢复()[0] != 0 and 件路径.read_text() == "print(3)\n"))
            重置夹具()
            件路径.unlink()
            件路径.symlink_to(公共仓 / "目标.py")
            输出表.append(("链接拒", 恢复()[0] != 0 and (公共仓 / "目标.py").read_text() == 原全文))
            重置夹具()
            with 连夹具() as 连接:
                连接.execute("update 开工 set 工作树=?", (str(公共仓),))
            输出表.append(("外树登记不一致拒", 恢复()[0] != 0 and 件路径.read_text() == 原全文))
            重置夹具()
            外仓 = 临时根 / "外仓"
            外仓.mkdir()
            执行命令(["init", "-q"], 外仓)
            输出表.append(("外仓拒", 恢复(目标仓=外仓)[0] != 0 and 件路径.read_text() == 原全文))
            重置夹具()
            with 写盘执行.开工写盘锁("v1-900001"):
                输出表.append(("并发锁快速拒", 恢复()[0] == 3 and 件路径.read_text() == 原全文))
            重置夹具()
            原换模式 = 写盘执行.os.chmod
            def 并发漂移(目标路径, 模式值):
                原换模式(目标路径, 模式值)
                件路径.write_text("print(3)\n")
            with patch.object(写盘执行.os, "chmod", 并发漂移):
                退出码, 说明 = 恢复()
            输出表.append(("替换前漂移拒且成果不丢", 退出码 != 0 and 件路径.read_text() == "print(3)\n"))
            重置夹具()
            with patch.object(写盘执行.os, "replace", side_effect=OSError("注入失败")):
                退出码, 说明 = 恢复()
            输出表.append(("写中失败保原件/同参可重试", 退出码 == 4 and 件路径.read_text() == 原全文 and 恢复()[0] == 0))
            重置夹具()
            with patch.object(写盘账本, "记已记账恢复", side_effect=sqlite3.OperationalError("注入收尾失败")):
                退出码, 说明 = 恢复()
            with 连夹具() as 连接:
                未决齐 = bool(写盘账本.列写盘意图(连接, "v1-900001"))
            输出表.append(("记账失败保已写成果/意图/同参收敛", 退出码 != 0 and 件路径.read_text() == 候选全文 and 未决齐 and 恢复()[0] == 0))
            重置夹具()
            from ...文件编辑.修改 import 派发
            with patch("MCP服务.文件编辑.修改.同步索引", return_value=(0, "隔离")):
                with 连夹具() as 连接:
                    账本.写回指纹(连接, "v1-900001", "目标.py", 写前指纹)
                退出码, 说明 = 派发({"开工ID": "v1-900001", "改动表": [{"路径": "目标.py", "功能": 1, "旧内容": "print(1)", "新内容": "print(2)"}]}, 公共仓)
                输出表.append(("普通修改共锁行为正常", 退出码 == 0 and 件路径.read_text() == 候选全文))
    return 输出表
