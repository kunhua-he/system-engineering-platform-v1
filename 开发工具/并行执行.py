# -*- coding: utf-8 -*-
"""并行执行 —— 把「互相独立的样本单元」摊到多核上（fork 进程池；工人不是 daemon）。

**为什么要有它**：`一键验证.py --自测` 的墙钟原先全压在**单核串行**上 —— 实测 121.7 s
（判据器自身机制 112.6 s + 77 个反向样本 2.66 s + 正向样本 0.32 s），而本机 32 核**只用一个核**。
本件是**唯一一份** fork 进程池口径，三处复用：`构建装配/一键验证/一键验证/自测.py`（反样本 +
机制断言）· `开发工具/MCP服务/长样本.py`（六套件）· `开发工具/MCP服务/合主干样本.py`（十二单元）。
★ 本件是**纯调度**：不判定、不打印、不碰盘 —— 判定与打印留在各自的父进程里，口径逐字不变。

**三条纪律**（破了就是踩过的坑）：

  · **fork 起步**：本仓 `开发工具/信息核心/` 等目录没有 `__init__.py`，`spawn` / `forkserver`
    起子进程会 ImportError（实测）；而 `fork` 的工人**继承**父进程已装载的模块与模块全局
    （判据批与自测的「阈值注入」依赖这条，见 `一键验证/验证.py::分片跑任务表`）。
  · **工人必须是模块级函数**（进程池按「模块名 + 函数名」反序列化；闭包 / lambda 不行），
    **任务**只许是可 pickle 的朴素值 —— 本仓一律传**下标**，函数表由工人按模块取。
  · **工人不是 daemon**：用 `concurrent.futures.ProcessPoolExecutor` 而不是
    `multiprocessing.Pool` —— `Pool` 的工人是 daemon，「daemon 不许有子进程」会把嵌套的
    判据进程池当场打红（`一键验证/验证.py` 已记过同一实测）。
"""
from __future__ import annotations

import os


def 并行执行(工人, 任务表: list, 进程数=None) -> list:
    """把 `任务表` 摊给 `工人` 跑完 ⇒ 结果表（**顺序与 `任务表` 逐位一致**）。

    `进程数` 缺省 = CPU 数与任务数取小；显式给 1 ⇒ 纯串行（给「这一批量墙钟，留单核」的档用）。
    进程池起不来（平台没有 fork）⇒ **退回串行**：判定口径不变，只是慢 —— 慢会被各命令的
    墙钟读数照实报出来，不静默降级。
    """
    if not 任务表:
        return []
    实际进程数 = max(1, min(int(进程数) if 进程数 else (os.cpu_count() or 1), len(任务表)))
    if 实际进程数 <= 1:
        return [工人(任务) for 任务 in 任务表]
    try:
        import multiprocessing
        from concurrent.futures import ProcessPoolExecutor

        if "fork" not in multiprocessing.get_all_start_methods():
            raise RuntimeError("本平台没有 fork 起步方式")
        进程池 = ProcessPoolExecutor(
            max_workers=实际进程数, mp_context=multiprocessing.get_context("fork"))
    except Exception:
        return [工人(任务) for 任务 in 任务表]
    with 进程池:
        return list(进程池.map(工人, 任务表, chunksize=1))
