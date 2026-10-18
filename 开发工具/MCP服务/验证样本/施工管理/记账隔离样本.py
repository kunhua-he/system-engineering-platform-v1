# -*- coding: utf-8 -*-
r"""记账隔离样本 —— `--自检` 的工具流水**不串写生产账本**的正反样本（独立进程各写临时库并回读）。

**为什么要有它**（2026-10-08 实测）：`--自检` 每跑一次会往**生产** `<运行数据根>/数据库/开工账本.db`
的 `工具流水` 落 6 行遥测（生产库 3148 行里约 76% 是自检遥测）—— 既污染生产时间线，又让多路自检
抢同一把 `begin immediate` 写锁。`工具流水.临时记账库()` 把域内记账改落**本进程私有**的临时库
（`记流水` 仍是同一份实现），生产默认路径与行为逐字不变。

四条口径：
  ① 两个**独立进程**各进临时记账域 ⇒ 各写各的临时库、各自**回读得到**所写的行；出域目的地回默认；
  ② 这两个进程跑完，**生产** `工具流水` 里自检专用开工号的行数**前后不变**（按唯一开工号追，不看
     总数 —— 生产允许真实外部调用并发增长）；
  ③ 域外（默认路径）记流水照旧落 `账本.连账本()` ⇒ **正常生产帧仍记流水**；
  ④ 域内抛异常 ⇒ 作用域**恢复默认**、临时目录**已清**（下一次记账仍走生产口）。

★ 真仓一个字节都不改：临时库在系统临时目录，跑完即删；生产库**只读**。
"""
import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

独立入口文本 = (
    "import sys; from pathlib import Path; "
    "sys.path.insert(0, str(Path.cwd() / '开发工具')); "
    "from MCP服务.验证样本.施工管理.记账隔离样本 import 独立记账进程; "
    "print(独立记账进程(sys.argv[1], Path.cwd()))"
)


def 独立记账进程(开工号: str, 仓根) -> str:
    """在**独立进程**里进临时记账域：跑一帧真工具调用 ⇒ 回读临时库行数（JSON 一行）。

    回执里的 `域外目的地` 必须是 `None` ⇒ 证「出域即恢复默认」（ContextVar 作用域**逐进程**成立）。
    """
    from ...服务协议.工具 import 工具表
    from ...施工管理.工具流水 import 临时记账库, 记账目的地
    with 临时记账库():
        工具表["v1_task"][0]({"开工ID": 开工号, "操作": "查询"}, 仓根)
        库路径 = 记账目的地.get()
        连接 = sqlite3.connect(str(库路径))
        try:
            行数 = 连接.execute("select count(*) from 工具流水").fetchone()[0]
        finally:
            连接.close()
    return json.dumps({"行数": 行数, "域外目的地": str(记账目的地.get())})


def _回读合规(输出文本: str) -> bool:
    """独立进程回执合规：`行数 ≥ 1`（临时库真写了且回读得到）+ 出域目的地回默认。"""
    try:
        读数 = json.loads(输出文本.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return False
    return (isinstance(读数, dict) and int(读数.get("行数", 0)) >= 1
            and 读数.get("域外目的地") == "None")


def _全部合规(回读表) -> bool:
    """两个独立进程的回执**全**合规（退出码 0 + 临时库回读 ≥ 1 行 + 出域回默认）。"""
    for 开工号, 回执 in 回读表:
        if 回执.returncode != 0 or not _回读合规(回执.stdout):
            return False
    return bool(回读表)


def 样本列表(仓根, 工具表) -> list:
    """⇒ 样本表（`(说明, 通过?)`）；两个独立子进程 + 替身夹具，跑完删净，真仓与生产库**只读**。"""
    import shutil

    from ... import 开工账本
    from ...集成管理.合主干有界跑 import 干净环境
    from ...施工管理.工具流水 import 临时记账库, 记账目的地

    def 生产流水计数(开工号: str) -> int:
        """生产账本里该唯一开工号的流水行数（**只读**；库 / 表不在 ⇒ 0）。"""
        try:
            连接 = sqlite3.connect("file:%s?mode=ro" % 开工账本.开工账本路径(), uri=True)
            try:
                return 连接.execute("select count(*) from 工具流水 where 开工号 = ?",
                                (开工号,)).fetchone()[0]
            finally:
                连接.close()
        except sqlite3.Error:
            return 0

    键表 = ("v1-999631", "v1-999632")
    前计数表 = {开工号: 生产流水计数(开工号) for 开工号 in 键表}
    回读表 = []
    for 开工号 in 键表:
        回执 = subprocess.run([sys.executable, "-B", "-c", 独立入口文本, 开工号],
                          cwd=str(仓根), env=干净环境(), capture_output=True, text=True, timeout=5)
        回读表.append((开工号, 回执))
    后计数表 = {开工号: 生产流水计数(开工号) for 开工号 in 键表}
    样本表 = [
        ("① 两个独立进程各进临时记账域、各写临时库并**回读得到**所写的行：%s"
         % "；".join("%s → 退出码 %d · %s" % (开工号, 回执.returncode,
                                       回执.stdout.strip() or 回执.stderr[-120:])
                    for 开工号, 回执 in 回读表),
         _全部合规(回读表)),
        ("② 生产工具流水里自检专用开工号**前后无新增**（按唯一开工号追，不看总数）：%s"
         % "；".join("%s 前 %d → 后 %d" % (开工号, 前计数表[开工号], 后计数表[开工号])
                    for 开工号 in 键表),
         前计数表 == 后计数表),
    ]
    临时根 = Path(tempfile.mkdtemp(prefix="v1记账隔离样本-"))
    try:
        夹具库 = 临时根 / "账本.db"
        真连 = 开工账本.连账本

        def 开夹具():
            """替身账本：建表同 `开工账本.建表语句` **一份**（域外默认口落它）。"""
            夹具连接 = sqlite3.connect(str(夹具库))
            夹具连接.row_factory = sqlite3.Row
            for 建表语句行 in 开工账本.建表语句:
                夹具连接.execute(建表语句行)
            夹具连接.commit()
            return 夹具连接

        真目的地 = 记账目的地.set(None)
        开工账本.连账本 = 开夹具
        try:
            工具表["v1_task"][0]({"开工ID": 键表[0], "操作": "查询"}, 仓根)
        finally:
            开工账本.连账本 = 真连
            记账目的地.reset(真目的地)
        夹具连接 = sqlite3.connect(str(夹具库))
        try:
            夹具行数 = 夹具连接.execute("select count(*) from 工具流水").fetchone()[0]
        finally:
            夹具连接.close()
        样本表.append(("③ 域外（默认路径）记流水照旧落 `账本.连账本()`：替身账本行数 %d（期望 ≥ 1）"
                 % 夹具行数, 夹具行数 >= 1))
        真目的地 = 记账目的地.set(None)
        入域前 = 记账目的地.get()
        域内目录 = None
        出域后 = None
        try:
            with 临时记账库():
                域内目录 = 记账目的地.get().parent
                raise RuntimeError("样本：域内抛异常")
        except RuntimeError:
            pass
        finally:
            出域后 = 记账目的地.get()      # ★ 在自身 reset 之前取：域自身的 finally 应已回入域前值
            记账目的地.reset(真目的地)
        恢复默认 = 出域后 is 入域前
        样本表.append(("④ 域内抛异常 ⇒ 出域即回到入域前（%s，入域前 %s）· 临时目录已清（%s）"
                 % (恢复默认, 入域前,
                    "是" if (域内目录 is not None and not 域内目录.exists()) else "否"),
                 恢复默认 and 域内目录 is not None and not 域内目录.exists()))
    finally:
        shutil.rmtree(临时根, ignore_errors=True)
    return 样本表
