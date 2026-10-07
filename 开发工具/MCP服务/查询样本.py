# -*- coding: utf-8 -*-
"""查询样本 —— `v1_task` 查询的**降噪正反样本**（临时账本 + 临时工作树，跑完即删）。

`自检样本.跑自检` 调它（判据 ㊽ 跑自检，退出码非 0 ⇒ 闸 0 当场红）。**仓一个字节都不改**：
账本连口与支线问口都走替身。

口径（与 `查询渲染` / `开工.查询开工` 同一份）：
  正向 —— 单号**只给本号**（不附「工作树仍在」全局段）；全局**保留诊断**但「工作树仍在」
  默认折成计数（`展开` 前不列号、`展开` = 真 才逐号列）；关键词命中仍有效；上限合法可调；
  查完**只读账本不翻状态**。
  反向 —— 关键词无命中**补一句**「查单号请用顶层 `开工ID`」；上限非法（非数 / 越界）⇒ 退出码 2。
"""
import re
from pathlib import Path


def 查询样本(仓根, 工具表) -> list:
    """跑查询正反样本 ⇒ 样本表。"""
    import shutil
    import sqlite3
    import tempfile

    from . import 开工, 开工账本

    临时根 = Path(tempfile.mkdtemp(prefix="v1查询自检-"))
    try:
        主树 = 临时根 / "主树"
        旁树 = 临时根 / "旁树"
        主树.mkdir()
        旁树.mkdir()
        账本路径 = 临时根 / "账本.db"
        连接 = sqlite3.connect(str(账本路径))
        连接.row_factory = sqlite3.Row
        for 建表行 in 开工账本.建表语句:
            连接.execute(建表行)
        开工账本.登记开工(连接, "v1-自检主", "查询样本主", "腿/v1-自检主", str(主树))
        开工账本.登记开工(连接, "v1-自检旁", "查询样本旁", "腿/v1-自检旁", str(旁树))
        开工账本.登记开工(连接, "v1-自检僵尸", "查询样本僵尸", "腿/v1-自检僵尸", str(临时根 / "不在"))
        连接.commit()
        连接.close()

        def 开账():
            新连接 = sqlite3.connect(str(账本路径))
            新连接.row_factory = sqlite3.Row
            return 新连接

        真连, 真支线 = 开工账本.连账本, 开工.支线在吗
        开工账本.连账本 = 开账
        开工.支线在吗 = lambda 忽略仓根, 忽略开工号: False
        出口 = 工具表["v1_task"][0]
        样本表 = []
        try:
            退出码, 回执 = 出口({"开工ID": "v1-自检主", "操作": "查询"}, 仓根)
            单号净 = ("v1-自检主" in 回执 and "v1-自检旁" not in 回执
                   and "工作树仍在" not in 回执 and "僵尸开工" not in 回执)
            样本表.append(("v1_task 查询 单号：退出码 %d · 只给本号%s · 不附全局诊断%s · 分支 HEAD 是 40 位哈希 %s"
                    % (退出码, "" if ("v1-自检主" in 回执 and "v1-自检旁" not in 回执) else "**没**",
                       "" if ("工作树仍在" not in 回执 and "僵尸开工" not in 回执) else "**仍附**",
                       "是" if re.search(r"分支 HEAD：\S+ [0-9a-f]{40}\b", 回执) else "否"),
                     退出码 == 0 and 单号净
                     and re.search(r"分支 HEAD：\S+ [0-9a-f]{40}\b", 回执) is not None
                     and "Traceback" not in 回执))
            退出码, 回执 = 出口({"操作": "查询", "参数": {"上限": 1}}, 仓根)
            折叠 = ("工作树仍在的开工 2 条" in 回执 and "默认折叠" in 回执
                  and "v1-自检主" not in 回执 and "僵尸开工 1 条" in 回执)
            样本表.append(("v1_task 查询 全局（上限=1 · 默认折叠）：退出码 %d · 计数%s · 折叠提示%s · "
                    "未列树在号%s · 僵尸计数%s"
                    % (退出码, "在" if "工作树仍在的开工 2 条" in 回执 else "**缺**",
                       "在" if "默认折叠" in 回执 else "**缺**",
                       "（对）" if "v1-自检主" not in 回执 else "**仍列**",
                       "在" if "僵尸开工 1 条" in 回执 else "**缺**"),
                     退出码 == 0 and 折叠 and "Traceback" not in 回执))
            退出码, 回执 = 出口({"操作": "查询", "参数": {"上限": 1, "展开": True}}, 仓根)
            展开齐 = ("默认折叠" not in 回执 and "v1-自检主" in 回执 and "v1-自检旁" in 回执)
            样本表.append(("v1_task 查询 全局（展开=真）：退出码 %d · 逐号列树在%s · 不再折叠%s"
                    % (退出码, "" if ("v1-自检主" in 回执 and "v1-自检旁" in 回执) else "**没**",
                       "" if "默认折叠" not in 回执 else "**仍折叠**"),
                     退出码 == 0 and 展开齐 and "Traceback" not in 回执))
            退出码, 回执 = 出口({"操作": "查询", "参数": {"关键词": "查询样本旁"}}, 仓根)
            样本表.append(("v1_task 查询 关键词命中：退出码 %d · 命中 v1-自检旁 %s"
                    % (退出码, "是" if "v1-自检旁" in 回执 else "否"),
                     退出码 == 0 and "命中 1 条" in 回执 and "v1-自检旁" in 回执
                     and "Traceback" not in 回执))
            退出码, 回执 = 出口({"操作": "查询", "参数": {"关键词": "绝无此词样本"}}, 仓根)
            样本表.append(("v1_task 查询 关键词无命中：退出码 %d · 补「查单号请用顶层 `开工ID`」%s"
                    % (退出码, "是" if "查单号请用顶层" in 回执 else "否"),
                     退出码 == 0 and "没有命中" in 回执 and "查单号请用顶层" in 回执
                     and "Traceback" not in 回执))
            for 坏上限 in ("abc", 0, 10 ** 9):
                退出码, 回执 = 出口({"操作": "查询", "参数": {"上限": 坏上限}}, 仓根)
                样本表.append(("v1_task 查询 上限非法（%r）：退出码 %d（期望 2 · 不崩）"
                        % (坏上限, 退出码),
                         退出码 == 2 and "Traceback" not in 回执))
            连接 = 开账()
            状态没翻 = 连接.execute("select 状态 from 开工 where 开工号 = ?",
                              ("v1-自检主",)).fetchone()[0] == 开工账本.状态_进行中
            连接.close()
            样本表.append(("v1_task 查询 只读账本：查完 v1-自检主 状态仍「进行中」%s"
                    % ("是" if 状态没翻 else "**否**"), 状态没翻))
        finally:
            开工账本.连账本, 开工.支线在吗 = 真连, 真支线
        return 样本表
    finally:
        shutil.rmtree(临时根, ignore_errors=True)
