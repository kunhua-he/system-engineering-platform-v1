# -*- coding: utf-8 -*-
"""隔离样本 —— 把动盘的重样本各放进独立子进程，**真并行**收敛（保判据 ㊽ 墙钟）。

**为何要它**：`自检主体` 原先串行跑「批量改名 / 上下文 / 跨树 / 账本差集 / 基线并入」这几个动盘
样本（各自搭临时仓、扫全树）—— 串行堆在一条 `--自检` 里，墙钟逼近五秒硬顶。改成每组一个子进程
（`concurrent.futures` 真并行）⇒ 墙钟 ≈ 最慢一组的长度，不是全部之和。口径同 `合主干` 提速。

**不弱化覆盖**：每组都跑**它那一组的全样本**（不抽子集）；子进程失败 / 超时 / 畸形输出 ⇒ 记一条
失败样本（不静默跳过、「未完整完成」不是通过）。
"""
import json
import subprocess
import sys

# 组名 → （模块名, 样本函数名）。模块住 `MCP服务/`；子进程里按模块名现导入。
隔离样本组 = {
    "改名样本": ("改名样本", "批量改名样本"),
    "上下文样本": ("上下文样本", "上下文样本"),
    "跨树样本": ("跨树样本", "跨树样本"),
    "账本差集样本": ("账本差集样本", "账本差集样本"),
    "基线并入样本": ("基线并入样本", "基线并入样本"),
}
# 子进程引导：从当前工作目录（= 被检仓）的 `开发工具` 里导入本件与入口。
隔离入口文本 = (
    "import json,sys; from pathlib import Path; "
    "sys.path.insert(0,str(Path.cwd()/'开发工具')); "
    "from MCP服务.隔离样本 import 隔离样本入口; "
    "print(json.dumps(隔离样本入口(sys.argv[1],Path.cwd()),ensure_ascii=False))"
)


def 隔离样本入口(样本组名, 仓根):
    """在独立进程里跑一组样本（真入口 + 取树快照 + 全样本）⇒ `{"组": …, "样本": […]}`。"""
    import importlib

    from MCP服务.工具 import 工具表
    from MCP服务.参数规范 import 开树快照, 关树快照

    模块名, 函数名 = 隔离样本组[样本组名]
    样本模块 = importlib.import_module("MCP服务." + 模块名)
    旧快照 = 开树快照()
    try:
        样本表 = getattr(样本模块, 函数名)(仓根, 工具表)
        return {"组": 样本组名, "样本": [(说明, bool(通过)) for 说明, 通过 in 样本表]}
    finally:
        关树快照(旧快照)


def 跑隔离样本(样本组名, 仓根) -> list:
    """一组样本在独立子进程里跑 ⇒ 样本表；失败 / 超时 / 畸形 ⇒ 记一条失败样本（不静默）。"""
    from .合主干有界跑 import 干净环境
    try:
        回执 = subprocess.run([sys.executable, "-B", "-c", 隔离入口文本, 样本组名],
                            cwd=str(仓根), env=干净环境(), capture_output=True, text=True, timeout=5)
        if 回执.returncode != 0:
            raise ValueError("退出码 %d：%s" % (回执.returncode, (回执.stderr or "")[-500:]))
        子组读数 = json.loads(回执.stdout)
        样本表 = 子组读数["样本"]
        if (子组读数["组"] != 样本组名 or not isinstance(样本表, list) or not 样本表
                or not all(isinstance(读数条, list) and len(读数条) == 2 and isinstance(读数条[0], str)
                           and type(读数条[1]) is bool for 读数条 in 样本表)):
            raise ValueError("样本组或样本表形状不齐")
        return [tuple(读数条) for 读数条 in 样本表]
    except Exception as 错误:
        return [("隔离样本 %s 未完整完成：%r" % (样本组名, 错误), False)]


def 并行样本结果(仓根) -> dict:
    """并发跑全部隔离样本组 ⇒ `{组名: 样本表}`（墙钟 ≈ 最慢一组的长度）。"""
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(隔离样本组)) as 执行池:
        作业表 = {组名: 执行池.submit(跑隔离样本, 组名, 仓根) for 组名 in 隔离样本组}
    return {组名: 作业.result() for 组名, 作业 in 作业表.items()}
