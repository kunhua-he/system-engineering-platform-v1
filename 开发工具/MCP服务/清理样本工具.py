# -*- coding: utf-8 -*-
"""清理样本工具 —— 清理样本共用的取数与造账（真仓夹具 · 临时账本 · 反馈行 · 环境切换）。

**为什么单开一件**（判据 ⑲ 单件 ≤400 行）：`清理样本.py` 装多组正反场景已近硬数；把「搭真仓 /
建腿 / 建账 / 造反馈行 / 切运行数据根」抽到一处，场景件读得完，也不成环（本件不 import 样本件）。
"""

import hashlib
import os
import sqlite3
import subprocess
from unittest import mock

from . import 开工账本, 反馈账本, 工具流水
from .合主干有界跑 import 干净环境
from .清理执行 import 快照列名


def 跑样本命令(仓根, *参数表):
    """在夹具仓里跑一条命令（断言成功）⇒ 去空白 stdout。"""
    回执 = subprocess.run(["git", *参数表], cwd=str(仓根), capture_output=True, text=True,
                       env=干净环境(), timeout=5)
    assert 回执.returncode == 0, (参数表, 回执.stdout, 回执.stderr)
    return 回执.stdout.strip()


def 搭样本基座(临时根):
    """一个最小真仓（主干 + 空 pre-commit 钩子）⇒ 主目录。"""
    主目录 = 临时根 / "主目录"
    主目录.mkdir(parents=True)
    for 参数表 in (("init", "-q", "-b", "主干"), ("config", "user.name", "样本"),
               ("config", "user.email", "样本@例")):
        跑样本命令(主目录, *参数表)
    (主目录 / "样本.txt").write_text("基线\n", encoding="utf-8")
    跑样本命令(主目录, "add", ".")
    跑样本命令(主目录, "commit", "-q", "-m", "基线")
    钩子件 = 主目录 / ".git/hooks/pre-commit"
    钩子件.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    钩子件.chmod(0o755)
    return 主目录


def 建样本腿(主目录, 开工号, 并入主干=True):
    """建工作树 + 提交；`并入主干`=真 时并回主干 ⇒ 支线成为主干祖先（合主干）。"""
    腿树 = 主目录.parent / ("腿目录-" + 开工号)
    跑样本命令(主目录, "worktree", "add", "-q", "-b", "腿/" + 开工号, str(腿树))
    (腿树 / ("成果-" + 开工号 + ".txt")).write_text("腿成果\n", encoding="utf-8")
    跑样本命令(腿树, "add", ".")
    跑样本命令(腿树, "commit", "-q", "-m", "腿成果")
    if 并入主干:
        跑样本命令(主目录, "merge", "--no-ff", "-q", "-m", "合腿", "腿/" + 开工号)
    return 腿树


def 建样本账(数据根, 开工号, 工作树, 状态="已释放"):
    """临时运行数据根里建一本真账本：开工行 + 各辅助表各一行（供计数 / 删除核对）。"""
    库件 = 数据根 / "数据库" / "开工账本.db"
    库件.parent.mkdir(parents=True, exist_ok=True)
    连接 = sqlite3.connect(str(库件))
    连接.row_factory = sqlite3.Row
    for 建表行 in 开工账本.建表语句 + 反馈账本.建表语句 + 工具流水.流水建表语句:
        连接.execute(建表行)
    连接.execute("create table if not exists 写盘意图 (开工号 text not null, 路径 text not null, "
             "功能 text not null, 写前指纹 text, 期望写后指纹 text, 时间 text not null, "
             "primary key (开工号, 路径))")
    连接.execute("create table if not exists 已记账恢复 (原改动编号 integer primary key, "
             "开工号 text, 路径 text, 写前指纹 text, 写后指纹 text, 候选SHA256 text, 时间 text)")
    连接.execute("create table if not exists 认领重叠 (开工号 text, 路径 text, 工作树 text, "
             "基线提交 text, 对方开工号 text, 对方工作树 text, 对方基线提交 text, "
             "primary key (开工号, 路径, 对方开工号))")
    连接.execute("create table if not exists 开工基线 (开工号 text primary key, 基线 text not null)")
    # 655 `反馈源快照` 的 `快照路径` 列由它那里的 `_补列` 加到老库；本件夹具就地补
    # （本件不改 `反馈账本.py` —— 那列归 655 的件；这里只让夹具能造出「有快照 / 无快照」两态）。
    来源列名集 = {文本行[1] for 文本行 in 连接.execute("pragma table_info(反馈来源)")}
    if 快照列名 not in 来源列名集:
        连接.execute("alter table 反馈来源 add column %s text" % 快照列名)
    时刻 = 开工账本.时刻串()
    连接.execute("insert into 开工 (开工号, 工作内容, 分支名, 工作树, 状态, 开工时间) "
             "values (?, ?, ?, ?, ?, ?)",
             (开工号, "样本任务", "腿/" + 开工号, str(工作树), 状态, 时刻))
    连接.execute("insert into 认领 (开工号, 路径, 指纹) values (?, ?, ?)", (开工号, "样本.txt", "指纹"))
    连接.execute("insert into 改动 (开工号, 路径, 功能, 写前指纹, 写后指纹, 时间) "
             "values (?, ?, ?, ?, ?, ?)", (开工号, "样本.txt", "修改", "旧", "新", 时刻))
    连接.execute("insert into 开工检查点 (开工号, 目标, 时刻) values (?, ?, ?)",
             (开工号, "样本目标", 时刻))
    连接.execute("insert into 工具流水 (工具名, 操作, 开工号, 时刻) values (?, ?, ?, ?)",
             ("v1_task", "单纯释放", 开工号, 时刻))
    连接.execute("insert into 写盘意图 (开工号, 路径, 功能, 时间) values (?, ?, ?, ?)",
             (开工号, "样本.txt", "修改", 时刻))
    连接.execute("insert into 已记账恢复 (开工号, 路径, 写前指纹, 写后指纹, 候选SHA256, 时间) "
             "values (?, ?, ?, ?, ?, ?)", (开工号, "样本.txt", "旧", "新", "候选", 时刻))
    连接.execute("insert into 认领重叠 (开工号, 路径, 对方开工号) values (?, ?, ?)",
             (开工号, "样本.txt", "v1-900000"))
    连接.execute("insert into 开工基线 (开工号, 基线) values (?, ?)", (开工号, "v1-900000"))
    连接.commit()
    连接.close()


def 连样本账(数据根):
    连接 = sqlite3.connect(str(数据根 / "数据库" / "开工账本.db"))
    连接.row_factory = sqlite3.Row
    return 连接


def 连作业库(数据根):
    """临时运行数据根里建 / 连作业账本 ⇒ 连接（建表同主干）。"""
    库件 = 数据根 / "数据库" / "作业账本.db"
    库件.parent.mkdir(parents=True, exist_ok=True)
    连接 = sqlite3.connect(str(库件))
    连接.row_factory = sqlite3.Row
    for 建表行 in 作业建表语句():
        连接.execute(建表行)
    连接.commit()
    return 连接


def 作业建表语句():
    from .作业账本 import 建表语句
    return 建表语句


def 加来源行(连接, 开工号, 来源标识, 报告路径, 读取状态="已读", 快照路径=None):
    列名表 = ["开工号", "来源标识", "内容指纹", "报告路径", "读取状态", "提取条数", "判词条数", "登记时刻"]
    值表 = [开工号, 来源标识, "指纹-" + 来源标识, 报告路径, 读取状态, 0, 0, 开工账本.时刻串()]
    if 快照路径 is not None:
        列名表.append(快照列名)
        值表.append(快照路径)
    连接.execute("insert into 反馈来源 (%s) values (%s)"
             % (", ".join(列名表), ", ".join("?" * len(列名表))), 值表)
    return 连接.execute("select last_insert_rowid()").fetchone()[0]


def 加审完(连接, 来源号表):
    """把来源行标「审完」（`审完时刻` 非空）—— 未审完来源会被 `清树门禁` 当**未蒸馏反馈**拒。"""
    有效表 = [号值 for 号值 in 来源号表 if 号值]
    if not 有效表:
        return
    占位符 = ",".join("?" * len(有效表))
    连接.execute("update 反馈来源 set 审完时刻 = ? where 来源号 in (%s)" % 占位符,
             [开工账本.时刻串()] + 有效表)


def 真清树(主目录, 开工号):
    """夹具里的「真清树」替身：真 `git worktree remove` + `git branch -D` ⇒ `(0, 说明)`。

    夹具仓里没有 `开发工具/并行工作树.sh` 定位仓根所需的标志件 ⇒ `仓操作.清工作树` 的真脚本在
    夹具里定位不到仓根；夹具用本替身做**真删**（验编排，不验那条脚本自身 —— 它由 `单纯释放` 管）。
    """
    腿树 = 主目录.parent / ("腿目录-" + 开工号)
    跑样本命令(主目录, "worktree", "remove", "--force", str(腿树))
    跑样本命令(主目录, "branch", "-D", "腿/" + 开工号)
    return 0, "工作树已移除 · 分支 `腿/%s` 已删" % 开工号


def 加条目行(连接, 来源号, 开工号, 现象):
    连接.execute("insert into 反馈条目 (来源号, 开工号, 现象, 条目指纹, 登记时刻) "
             "values (?, ?, ?, ?, ?)", (来源号, 开工号, 现象, "条目指纹", 开工账本.时刻串()))
    return 连接.execute("select last_insert_rowid()").fetchone()[0]


def 加判词行(连接, 条目号, 判词, 关联种类=None, 关联目标=None, 关联状态="现行"):
    连接.execute("insert into 反馈判词 (条目号, 判词, 理由, 关联种类, 关联目标, 关联状态, "
             "判定开工号, 判定时刻) values (?, ?, ?, ?, ?, ?, ?, ?)",
             (条目号, 判词, "样本理由", 关联种类, 关联目标, 关联状态, "v1-900001",
              开工账本.时刻串()))


def 加关闭行(连接, 条目号, 承接提交, 退出码=0, 关闭开工号="v1-900001", 验证命令="样本命令",
          日志指针=None):
    连接.execute("insert into 反馈关闭 (条目号, 验证证据, 验证命令, 退出码, 承接提交, "
             "关闭开工号, 日志指针, 关闭时刻) values (?, ?, ?, ?, ?, ?, ?, ?)",
             (条目号, "样本验证证据", 验证命令, 退出码, 承接提交, 关闭开工号, 日志指针,
              开工账本.时刻串()))


def 加反向认领重叠行(数据根, 别的开工号, 本开工号, 路径="样本.txt"):
    """别的开工的 `认领重叠` 行把 `本开工号` 当 `对方开工号` ⇒ 本开工快照被清会留孤儿。"""
    连接 = 连样本账(数据根)
    try:
        连接.execute("insert into 认领重叠 (开工号, 路径, 对方开工号) values (?, ?, ?)",
                 (别的开工号, 路径, 本开工号))
        连接.commit()
    finally:
        连接.close()


def 样本环境(数据根):
    """把运行数据根指到临时目录（开工账本 / 作业账本 / 日志 / 临时件 全落这里）。"""
    from 开发工具.运行数据根.口径 import 覆盖变量名
    return mock.patch.dict(os.environ, {覆盖变量名: str(数据根)})


def 数样本行(数据根, 语句, 查询参数=()):
    连接 = 连样本账(数据根)
    try:
        return 连接.execute(语句, 查询参数).fetchone()[0]
    finally:
        连接.close()


def 造报告件(数据根, 报告名):
    """在**允许边界内**（运行数据根临时件）造一份报告件 ⇒ 绝对路径。"""
    报告件 = 数据根 / "临时件" / 报告名
    报告件.parent.mkdir(parents=True, exist_ok=True)
    报告件.write_text("报告正文\n", encoding="utf-8")
    return str(报告件)


def 造快照件(数据根, 正文):
    """在**允许边界内**按内容寻址造一份快照件（`临时件/反馈源正文/<sha>.txt`）⇒ 绝对路径。"""
    内容字节 = 正文.encode("utf-8")
    快照件 = 数据根 / "临时件" / "反馈源正文" / (hashlib.sha256(内容字节).hexdigest() + ".txt")
    快照件.parent.mkdir(parents=True, exist_ok=True)
    快照件.write_bytes(内容字节)
    return str(快照件)


def 支线提交(仓根, 开工号):
    """该腿支线的 HEAD 提交（**该腿本支线的提交**，未必是主干祖先）⇒ sha。"""
    return 跑样本命令(仓根, "rev-parse", "腿/" + 开工号)


def 主干提交(仓根):
    return 跑样本命令(仓根, "rev-parse", "主干")
