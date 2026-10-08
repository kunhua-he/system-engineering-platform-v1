# -*- coding: utf-8 -*-
"""验证超阈样本 —— 释放路径「跨阈即一次反馈（不等跑完） + 超 5 秒不杀 + 真红不提交」的集成样本。

一片一测（真临时工作树 + 真 pre-commit 钩子 + 独立样本账本；一个字节都不碰真账本 / 真远端）：
  · 跨阈即时反馈 —— 直测 `仓操作.跑验证带跨阈`：闸 0 真睡 1.2 秒、阈值压到 300 ms ⇒ 回调
    **在子进程结束之前**就被叫到，且**只叫一次**。这就是华哥 2026-10-08 那条线
    「超过 5 秒就自动的提交一个反馈而已」—— 不是等它跑完再补报。
  · 验证超阈自动反馈 —— 全栈：释放真跑（真提交），回执带「已登记」一条反馈。
  · 验证未超阈无反馈 —— 阈内 ⇒ 回执无反馈行、反馈表零行。
  · 反馈口坏仍继续 —— 反馈口抛异常 ⇒ 释放仍成功（真提交），回执**如实报「未登记」**（不吞、不阻塞）。

「真红不提交」由 `释放样本.释放样本` 的 `门禁失败 / 门禁真实超顶` 两档覆盖；「并发同键只报一次」
由 `耗时反馈样本.样本列表` 覆盖。本件不带 `__main__` 块。
"""

import sqlite3
import tempfile
import time
from pathlib import Path
from unittest import mock

from . import 仓操作, 开工账本, 写盘账本, 释放作业

开工号 = "v1-900421"
闸0睡秒 = 1.2
直测阈值毫秒 = 300


def 样本列表(仓根, 工具表=None) -> list:
    """⇒ `[(说明, 通过)]`（`工具表` 不用；签名与其它样本组同形）。"""
    from . import 耗时反馈, 反馈提交
    样本表 = [直测档()]
    for 名称 in ("验证超阈自动反馈", "验证未超阈无反馈", "反馈口坏仍继续"):
        with tempfile.TemporaryDirectory(prefix="v1验证超阈-") as 临时目录:
            样本表.append(跑一档(Path(临时目录), 名称, 耗时反馈, 反馈提交))
    return 样本表


def 直测档() -> tuple:
    """跨阈即一次反馈（**不等跑完**）：真起一个睡 1.2 秒的闸 0，阈值压到 300 ms。"""
    from . import 耗时反馈
    with tempfile.TemporaryDirectory(prefix="v1跨阈直测-") as 临时目录:
        工作树 = Path(临时目录) / "树"
        (工作树 / "构建装配/一键验证").mkdir(parents=True)
        (工作树 / "构建装配/一键验证/闸0.py").write_text(
            "import time\ntime.sleep(%s)\nprint('夹具门禁通过')\n" % 闸0睡秒, encoding="utf-8")
        观测表 = []

        def 回调(已耗时毫秒):
            观测表.append((time.monotonic(), 已耗时毫秒))

        with mock.patch.object(耗时反馈, "阈值毫秒", 直测阈值毫秒):
            起点 = time.monotonic()
            退出码, 输出文本, 复跑过 = 仓操作.跑验证带跨阈(工作树, 回调)
            总毫秒 = int((time.monotonic() - 起点) * 1000)
        提前毫秒 = int((观测表[0][0] - 起点) * 1000) if 观测表 else -1
        报的毫秒 = 观测表[0][1] if 观测表 else -1
        说明 = ("跨阈即时反馈：退出码 %d · 总墙钟 %d ms · 回调 %d 次 · 报的已耗时 %d ms · "
              "回调落在起点后 %d ms（阈值 %d ms）"
              % (退出码, 总毫秒, len(观测表), 报的毫秒, 提前毫秒, 直测阈值毫秒))
        通过 = (退出码 == 0 and len(观测表) == 1
                and 直测阈值毫秒 <= 报的毫秒 <= 直测阈值毫秒 + 500
                and 提前毫秒 <= 直测阈值毫秒 + 500
                and 总毫秒 >= int(闸0睡秒 * 1000))
        return (说明, 通过)


def 反馈行数(连接) -> int:
    """样本账本里 `反馈条目` 的行数（表不在 ⇒ 0）。"""
    表名集 = {表名行[0] for 表名行 in 连接.execute("select name from sqlite_master")}
    if "反馈条目" not in 表名集:
        return 0
    return 连接.execute("select count(*) from 反馈条目").fetchone()[0]


def 跑一档(临时根, 名称, 耗时反馈, 反馈提交):
    仓根 = 临时根 / "主工作树"
    工作树 = 临时根 / "工作树"
    仓根.mkdir()
    原跑命令 = 仓操作.跑命令

    def 执行命令(参数表, cwd=仓根, **关键字参数):
        退出码, 输出文本 = 原跑命令(参数表, cwd=cwd, **关键字参数)
        assert 退出码 == 0, (参数表, 退出码, 输出文本)
        return 输出文本.strip()

    执行命令(["git", "init", "-b", "主干"])
    执行命令(["git", "config", "user.name", "验证超阈样本"])
    执行命令(["git", "config", "user.email", "gate@example.invalid"])
    (仓根 / "样本.txt").write_text("旧内容\n", encoding="utf-8")
    件路径 = 仓根 / "构建装配/一键验证/闸0.py"
    件路径.parent.mkdir(parents=True)
    件路径.write_text("import time\ntime.sleep(%s)\nprint('夹具门禁通过')\n" % 闸0睡秒, encoding="utf-8")
    执行命令(["git", "add", "--", "样本.txt", "构建装配/一键验证/闸0.py"])
    执行命令(["git", "commit", "-m", "夹具基线"])
    执行命令(["git", "worktree", "add", "-b", 仓操作.分支名(开工号), str(工作树)])
    钩子 = 仓根 / ".git/hooks/pre-commit"
    钩子.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    钩子.chmod(0o755)
    账本路径 = 临时根 / "账本.db"

    def 连样本账本():
        连接 = sqlite3.connect(账本路径)
        连接.row_factory = sqlite3.Row
        return 连接

    连接 = 连样本账本()
    for 建表行 in 开工账本.建表语句:
        连接.execute(建表行)
    写盘账本.补意图表(连接)
    开工账本.登记开工(连接, 开工号, "验证超阈样本", 仓操作.分支名(开工号), str(工作树))
    (工作树 / "样本.txt").write_text("新内容\n", encoding="utf-8")
    指纹 = 仓操作.文件指纹(str(工作树 / "样本.txt"))
    开工账本.认领文件(连接, 开工号, {"样本.txt": 指纹})
    开工账本.记改动(连接, 开工号, "样本.txt", "修改", "", 指纹)
    连接.close()
    样本起点 = 执行命令(["git", "rev-parse", "HEAD"], cwd=工作树)

    阈内 = 名称 == "验证未超阈无反馈"
    阈毫秒 = 5000 if 阈内 else 直测阈值毫秒
    with mock.patch.object(开工账本, "连账本", 连样本账本), \
            mock.patch.object(耗时反馈, "阈值毫秒", 阈毫秒):
        if 名称 == "反馈口坏仍继续":
            with mock.patch.object(反馈提交, "提交反馈", side_effect=RuntimeError("样本：反馈口坏了")):
                退出码, 输出文本 = 释放作业.释放主体(仓根, 开工号, 推送=False)
        else:
            退出码, 输出文本 = 释放作业.释放主体(仓根, 开工号, 推送=False)
    连接 = 连样本账本()
    状态 = 开工账本.读开工(连接, 开工号)["状态"]
    反馈计数 = 反馈行数(连接)
    连接.close()
    提交后头 = 执行命令(["git", "rev-parse", "HEAD"], cwd=工作树)
    真提交 = 提交后头 != 样本起点
    if 名称 == "验证超阈自动反馈":
        说明 = ("验证超阈自动反馈：退出码 %d · 状态 %s · 反馈 %d 条 · 真提交 %s · 回执含已登记 %s"
              % (退出码, 状态, 反馈计数, "是" if 真提交 else "否", "是" if "已登记" in 输出文本 else "否"))
        return (说明, 退出码 == 0 and 状态 == 开工账本.状态_已释放 and 反馈计数 == 1
                and "已登记" in 输出文本 and 真提交)
    if 名称 == "验证未超阈无反馈":
        说明 = ("验证未超阈无反馈：退出码 %d · 状态 %s · 反馈 %d 条 · 真提交 %s · 回执无反馈行 %s"
              % (退出码, 状态, 反馈计数, "是" if 真提交 else "否", "是" if "耗时反馈" not in 输出文本 else "否"))
        return (说明, 退出码 == 0 and 状态 == 开工账本.状态_已释放 and 反馈计数 == 0
                and "耗时反馈" not in 输出文本 and 真提交)
    说明 = ("反馈口坏仍继续：退出码 %d · 状态 %s · 真提交 %s · 回执含未登记 %s · 反馈 %d 条"
          % (退出码, 状态, "是" if 真提交 else "否", "是" if "未登记" in 输出文本 else "否", 反馈计数))
    return (说明, 退出码 == 0 and 状态 == 开工账本.状态_已释放 and 反馈计数 == 0
            and "未登记" in 输出文本 and 真提交)
