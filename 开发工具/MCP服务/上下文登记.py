# -*- coding: utf-8 -*-
"""上下文切片的新名重放：仅登记缺失名，经信息核心具名命令。"""
import sqlite3
import subprocess
import sys
from pathlib import Path

允许字段 = ("altchars", "patch", "return_value", "sort_keys", "validate", "上下文来源", "上下文读取", "新鲜度", "条件值", "错误种类")

名字表 = """__init__ 上下文失败 上下文样本 上下文模式 上下文派 上限值 下限值 下页位置 主题值 允许字段 写前内容 写前状态 冲突值 分支HEAD 分支值 包含表 取文档定档 取来源版本 取版本件表 变更来源 只读连接 台账内容 台账行 后缀名 命中定位集 命中来源表 响应表 失败样本 安全文档路径 完整条目 完整条目表 定档行 工具项 序号值 建上下文夹具 开工行 当前版本 打包游标 投影数量 投影条目 文档缓存 文档账本件 新鲜提示 旁件路径 旧服务提示 时间值 服务代码件表 服务代码版本 未完成件 条件文本 条数值 条款定位 条款行 来源值 来源指纹 来源版本 查询参数 查询指纹 查询键 标题值 树绝对路径 档位值 检查输入 模块版本 正文值 游标值 游标对象 版本件表 真读取 类别名 精确表 索引条目 索引读数 编码输出 解读游标 记样本 读上下文条目 读取上下文 读夹具 读指纹 读条款条目 读源JSON 读盘状态 账本内容 输出字节 输出对象 输出预算 返回条目 造条目 页位置 页数值 预算值 默认文档表 重放登记""".split()


def 重放登记(树根):
    树根 = Path(树根).resolve()
    from 开发工具.信息核心.表定义 import 库路径
    with sqlite3.connect(库路径(树根).as_uri() + "?mode=ro", uri=True) as 连接:
        命中定位集 = {条款行[0] for 条款行 in 连接.execute("select 名字 from 命名登记")}
    参数表 = sorted(set(名字表) - 命中定位集)
    for 名字 in 参数表:
        回执 = subprocess.run([sys.executable, "开发工具/信息核心/信息核心.py", "登记",
                            "--名字", 名字, "--语义", "项目上下文只读查询中的" + 名字,
                            "--模式", "对象+说明", "--来源", "新定义"], cwd=树根, capture_output=True, text=True, timeout=5)
        if 回执.returncode:
            raise RuntimeError(回执.stdout + 回执.stderr)
    if set(允许字段) - 命中定位集:
        回执 = subprocess.run([sys.executable, "开发工具/信息核心/信息核心.py", "落库"], cwd=树根, capture_output=True, text=True, timeout=5)
        if 回执.returncode:
            raise RuntimeError(回执.stdout + 回执.stderr)
    return len(参数表)
