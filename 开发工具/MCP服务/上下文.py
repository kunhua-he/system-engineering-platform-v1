# -*- coding: utf-8 -*-
"""MCP 上下文工具：正式树解析与信息核心只读读取。"""
import re
import sqlite3
from pathlib import Path
from .仓操作 import 找工作树, 跑命令
from .开工账本 import 子目录路径, 解析当前环境, 子目录类别, 库文件名
from .服务指纹 import 启动指纹, 算服务指纹
from 开发工具.信息核心.上下文来源 import 上下文失败, 只读连接
from 开发工具.信息核心.上下文读取 import 检查输入, 读取上下文, 编码输出, 模块版本


def 派发(命令行参数, 仓根):
    try:
        查询参数 = 检查输入(命令行参数)
        开工号, 账本路径 = 查询参数["开工ID"], None
        if 开工号 or "开工" in 查询参数["包含"]:
            账本路径 = 子目录路径(解析当前环境(), 子目录类别) / 库文件名
        树根 = Path(仓根).resolve()
        if 开工号:
            if not re.fullmatch(r"v1-[0-9]{6}", 开工号):
                raise 上下文失败("参数错误", "开工ID格式错误")
            with 只读连接(账本路径) as 连接:
                开工行 = 连接.execute("select * from 开工 where 开工号=?", (开工号,)).fetchone()
                if 开工行 is None:
                    raise 上下文失败("missing", "未登记开工ID")
            工作树 = 找工作树(仓根, 开工号)
            if 工作树 is None or not 工作树.is_dir() or 工作树.resolve() != Path(开工行["工作树"]).resolve():
                raise 上下文失败("missing", "正式工作树不存在或与账本冲突")
            树根 = 工作树.resolve()
        退出码, 分支HEAD = 跑命令(["git", "rev-parse", "HEAD"], cwd=树根)
        if 退出码:
            raise 上下文失败("missing", "无法读取工作树HEAD")
        退出码, 分支值 = 跑命令(["git", "branch", "--show-current"], cwd=树根)
        if 退出码:
            raise 上下文失败("missing", "无法读取分支")
        输出文本 = 读取上下文(树根, 查询参数, 分支值.strip(), 分支HEAD.strip(), 账本路径,
                         {"加载指纹": 启动指纹, "盘上指纹": 算服务指纹(), "新鲜度": "新鲜" if 启动指纹 == 算服务指纹() else "陈旧"})
        退出码, 当前版本 = 跑命令(["git", "rev-parse", "HEAD"], cwd=树根)
        if 退出码 or 当前版本 != 分支HEAD:
            raise 上下文失败("不一致", "读取期间工作树HEAD发生变化")
        return 0, 输出文本
    except 上下文失败 as 失败原因:
        错误对象 = {"版本": 模块版本, "错误": {"种类": 失败原因.错误种类, "说明": str(失败原因)[:200]}, "条目": [], "截断": False, "游标": None}
        return (2 if 失败原因.错误种类 == "参数错误" else 1), 编码输出(错误对象)
    except (OSError, sqlite3.Error, ValueError, KeyError, TypeError) as 失败原因:
        return 1, 编码输出({"版本": 模块版本, "错误": {"种类": "corrupt", "说明": str(失败原因)[:200]}, "条目": []})
