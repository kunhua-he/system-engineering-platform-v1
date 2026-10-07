# -*- coding: utf-8 -*-
r"""名册僵尸样本 —— `v1_repo 环境体检 · 名册僵尸行` 的**正反样本**（临时夹具，跑完即删，仓不改）。

正向：库里 `出现次数 > 0` 的名（现量代码里在用）⇒ **不进**僵尸清单。
反向：库里 `出现次数 = 0` 的名（仅库里有、代码已无）⇒ **报为**僵尸。
另加一条整合读数：真仓 `v1_repo 环境体检` 回执里必须带「名册僵尸行」这一段。
"""
import sqlite3
import tempfile
from pathlib import Path

from .名册僵尸 import 读僵尸行


def 名册僵尸样本(仓根, 工具表) -> list:
    """⇒ 样本表（`(说明, 是否通过)`）—— 建临时夹具库验证正反两向，跑完即删。"""
    样本表 = []
    with tempfile.TemporaryDirectory(prefix="名册僵尸样本") as 临时根:
        夹具库件 = Path(临时根) / "夹具规则库.db"
        连接 = sqlite3.connect(str(夹具库件))
        try:
            连接.execute("create table 命名登记(名字 text primary key, 出现次数 integer default 0)")
            连接.executemany("insert into 命名登记(名字, 出现次数) values(?,?)",
                        [("在用样本名", 3), ("僵尸样本名", 0)])
            连接.commit()
        finally:
            连接.close()
        # 夹具只用**两列**的 `命名登记` ⇒ 本口对真表多出的语义/模式/来源/状态列零依赖。
        正文 = "\n".join(读僵尸行(夹具库件, 50))
    样本表.append(("名册僵尸：在用名（出现次数=3）不进僵尸清单", "在用样本名" not in 正文))
    样本表.append(("名册僵尸：仅库里有（出现次数=0）报为僵尸", "僵尸样本名" in 正文))
    退出码, 输出文本 = 工具表["v1_repo"][0]({"操作": "环境体检"}, 仓根)
    样本表.append(("v1_repo 环境体检 回执带「名册僵尸行」一段（退出码 %d）" % 退出码,
             退出码 == 0 and "名册僵尸行" in 输出文本))
    return 样本表
