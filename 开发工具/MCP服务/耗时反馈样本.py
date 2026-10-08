# -*- coding: utf-8 -*-
"""耗时反馈样本 —— 「跨过效率阈值自动提交一次性能反馈」的正反样本（函数级 + 真并发）。

一片一测（前四片用临时运行数据根，一个字节都不碰真账本；末片起真两进程并发）：
  · 未跨阈 ⇒ 一个字节都不写（返回空回执）。
  · 跨阈 ⇒ 登记一条；重复调用 ⇒ 重放（零新行）。
  · 反馈口写失败 ⇒ 返回「未登记」（可发现）且**不上抛**（业务继续）。
  · 真两进程并发同键 ⇒ 只登记一条（幂等）。

释放路径「超 5 秒不杀 + 真红不提交」的**集成样本**住 `释放样本.释放样本`（真 Git 夹具）。
本件不带 `__main__` 块（带了就被判据 ⑲ 当入口件）。
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from 运行数据根.口径 import 覆盖变量名

from . import 耗时反馈

样本开工号 = "v1-900001"


def 建夹具(根路径: Path):
    """把运行数据根指向临时根并登记样本开工 ⇒ 旧覆盖值（用完 `清夹具` 还原）。"""
    from . import 开工账本
    旧根 = os.environ.get(覆盖变量名)
    os.environ[覆盖变量名] = str(根路径)
    连接 = 开工账本.连账本()
    开工账本.登记开工(连接, 样本开工号, "耗时反馈样本", "腿/" + 样本开工号, str(根路径 / 样本开工号))
    连接.close()
    return 旧根


def 清夹具(旧根):
    """还原运行数据根覆盖值（`None` ⇒ 真正删掉这个键，不留空串假覆盖）。"""
    if 旧根 is None:
        os.environ.pop(覆盖变量名, None)
    else:
        os.environ[覆盖变量名] = 旧根


def 反馈条数() -> int:
    """当前运行数据根下 `反馈条目` 的行数（跨表读数：判「只登记一条」）。"""
    from . import 反馈账本
    连接 = 反馈账本.连反馈库()
    try:
        return 连接.execute("select count(*) from 反馈条目").fetchone()[0]
    finally:
        连接.close()


def 样本列表(仓根, 工具表=None) -> list:
    """⇒ `[(说明, 通过)]`（`工具表` 不用；签名与其它样本组同形，便于挂长样本套件）。

    `仓根` 可能是 `str`（调用方传 POSIX 路径）⇒ 入口先归一为 `Path`（子进程脚本拼路径要用）。
    """
    from unittest import mock
    from . import 反馈提交
    仓根 = Path(仓根) if not isinstance(仓根, Path) else 仓根
    样本表 = []
    with tempfile.TemporaryDirectory(prefix="v1耗时反馈-") as 临时目录:
        旧根 = 建夹具(Path(临时目录) / "运行数据根")
        try:
            登记过, 回执行 = 耗时反馈.记耗时反馈(仓根, 样本开工号, 耗时反馈.阶段_释放验证,
                                            耗时反馈.阈值毫秒)
            样本表.append(("耗时反馈·未跨阈（已耗时 == 阈值）⇒ 不登记且回执为空：%r" % (回执行,),
                     登记过 is False and 回执行 == "" and 反馈条数() == 0))

            登记过, 回执行 = 耗时反馈.记耗时反馈(仓根, 样本开工号, 耗时反馈.阶段_释放验证,
                                            耗时反馈.阈值毫秒 + 1204)
            样本表.append(("耗时反馈·跨阈 ⇒ 登记一条（登记 %s · 条数 %d）" % (登记过, 反馈条数()),
                     登记过 is True and 反馈条数() == 1 and "已登记" in 回执行))

            再登记, 回执二 = 耗时反馈.记耗时反馈(仓根, 样本开工号, 耗时反馈.阶段_释放验证,
                                            耗时反馈.阈值毫秒 + 5000)
            样本表.append(("耗时反馈·重复调用 ⇒ 重放（零新行 · 条数仍 %d）" % 反馈条数(),
                     再登记 is True and 反馈条数() == 1))

            with mock.patch.object(反馈提交, "提交反馈", side_effect=RuntimeError("样本：反馈口坏了")):
                失败登记, 失败回执 = 耗时反馈.记耗时反馈(仓根, 样本开工号, "另一阶段", 9999)
            样本表.append(("耗时反馈·反馈口写失败 ⇒ 返回「未登记」可发现且不上抛：登记 %s · 含未登记 %s · 条数 %d"
                     % (失败登记, "未登记" in 失败回执, 反馈条数()),
                     失败登记 is False and "未登记" in 失败回执 and 反馈条数() == 1))
        finally:
            清夹具(旧根)

    with tempfile.TemporaryDirectory(prefix="v1耗时并发-") as 临时目录:
        旧根 = 建夹具(Path(临时目录) / "运行数据根")
        try:
            脚本 = ("import sys;"
                "sys.path.insert(0, %r);"
                "from MCP服务 import 耗时反馈;"
                "耗时反馈.记耗时反馈(%r, %r, 耗时反馈.阶段_释放验证, %d)"
                % (str(仓根 / "开发工具"), str(仓根), 样本开工号, 耗时反馈.阈值毫秒 + 3000))
            子进程表 = [subprocess.Popen([sys.executable, "-c", 脚本], cwd=str(仓根),
                               env=dict(os.environ), stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE) for _ in range(2)]
            for 子进程 in 子进程表:
                子进程.communicate()
            样本表.append(("耗时反馈·真两进程并发同键 ⇒ 只登记一条（条数 %d）" % 反馈条数(),
                     反馈条数() == 1))
        finally:
            清夹具(旧根)
    return 样本表
