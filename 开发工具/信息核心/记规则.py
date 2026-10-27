# -*- coding: utf-8 -*-
"""记规则 —— 往规则库的 `规则` 表记一条**规则 / 裁决**（一次裁决一条的仓内写路径）。

用法：
    python3 开发工具/信息核心/信息核心.py 记规则 --类 <类名> --名 <一句话> --内容 <散文> [--依据 <落点>]
    python3 开发工具/信息核心/信息核心.py 记规则 --删 --编号 <既有编号>     （删一条已废规则）

**为何要它**：`规则` 表是「全项目规则的唯一落点」（宪法 · 层序 · 开发规范 · 判据口径 …），
但 md 删净之后它**没有写入路径** —— 手写 SQL 会绕过 `v1_edit` 的账本，那是已关掉的坏路。
本命令就是那条正路：写库 + 记账走 `v1_task` 功能 = 6（库是二进制**源件**，`v1_edit` 改不了它）。

`编号` 由本命令按类自动给：`<类>-<序号>`，序号 = 该类现有的最大序号 + 1（同类的旧编号不复用）。
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

仓根 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import 表定义  # noqa: E402


def 解析参数(参数表: list) -> dict:
    """`--类 X --名 Y --内容 Z` ⇒ `{"类": "X", "名": "Y", "内容": "Z"}`（值可以带空格）。"""
    字段表 = {}
    字段键 = ""
    for 参数片 in 参数表:
        if 参数片.startswith("--") and 参数片[2:] in ("类", "名", "名字", "内容", "依据", "编号", "删", "文档路径", "序号", "标题", "正文", "正文文件", "权威档", "权威档为空", "允许空正文", "覆盖", "确认", "号", "缺什么", "落点", "验证命令", "落点为空", "验证命令为空", "列", "类别", "语义", "模式", "来源", "状态", "分组", "说明", "例外", "泛名", "理由", "批", "干跑", "不落库"):
            字段键 = 参数片[2:]
            字段表[字段键] = ""
        elif 字段键:
            字段表[字段键] = (字段表[字段键] + " " + 参数片).strip()
    return 字段表


def 取新编号(连接, 类名: str) -> str:
    """`<类>-<序号>` —— 序号 = 该类现有的最大 + 1（按编号尾段取整数）。"""
    编号表 = 连接.execute(
        "select 编号 from 规则 where 类 = ?", (类名,)).fetchall()
    最大序号 = 0
    for (编号,) in 编号表:
        尾巴 = 编号.rsplit("-", 1)[-1]
        if 尾巴.isdigit():
            最大序号 = max(最大序号, int(尾巴))
    return f"{类名}-{最大序号 + 1}"


def 删规则(编号: str) -> int:
    """把一行从 `规则` 表**删掉**（`编号` 是主键）⇒ 退出码。

    用途：一条规则**已被后续裁决取代**（`决策记录/2026-09-28_文档账本.md` §4：已被取代的条目即删，
    留痕归 `git log`）⇒ 用本口清出。只认既有编号：编号不存在 ⇒ 拒，不静默当成功。
    """
    编号 = (编号 or "").strip()
    if not 编号:
        print("拒：`--删` 要给 `--编号 <既有编号>`。", file=sys.stderr)
        return 2
    连接 = sqlite3.connect(表定义.库路径(仓根))
    try:
        行数 = 连接.execute("delete from 规则 where 编号 = ?", (编号,)).rowcount
        连接.commit()
    finally:
        连接.close()
    if not 行数:
        print(f"拒：`规则` 表里没有编号 `{编号}`（没删到东西）。", file=sys.stderr)
        return 1
    print(f"记规则：删 {编号}（{行数} 行）")
    print("★ 库变了 ⇒ 收口前记得 `v1_task` 功能=6 记账"
          "（`源件` = `开发工具/信息核心/信息核心.db`），否则释放的越界检测会拒")
    return 0


def 记规则(字段表: dict) -> int:
    """写一条规则进 `规则` 表 ⇒ 退出码。

    给了 `--编号` ⇒ **就地改写那一行**（编号不变）；不给 ⇒ 自动编号（追加新号，撞号重取、
    不静默覆盖）。
    """
    类名 = (字段表.get("类") or "").strip()
    规则名 = (字段表.get("名") or "").strip()
    内容值 = (字段表.get("内容") or "").strip()
    规则依据 = (字段表.get("依据") or "").strip()
    编号 = (字段表.get("编号") or "").strip()
    if "删" in 字段表:
        return 删规则(编号)
    if not 类名 or not 规则名 or not 内容值:
        print("用法：信息核心.py 记规则 --类 <类名> --名 <一句话> --内容 <散文> "
              "[--依据 <落点>] [--编号 <既有编号>]", file=sys.stderr)
        return 2
    if 编号 and not 编号.startswith(类名 + "-"):
        print(f"记规则：`--编号 {编号}` 与 `--类 {类名}` 对不上 —— "
              f"编号必须带 `<类>-` 前缀（就地改写不许把一行挪到别的类）。", file=sys.stderr)
        return 2
    连接 = sqlite3.connect(表定义.库路径(仓根))
    try:
        if 编号:
            连接.execute("insert or replace into 规则 values(?,?,?,?,?)",
                       (编号, 类名, 规则名, 内容值, 规则依据))
            连接.commit()
        else:
            # 自动编号 + 写入：用 `insert`（不是 `or replace`）⇒ 撞号抛 `IntegrityError`、
            # 回滚重取，绝不静默覆盖别条腿刚写的同号行（旧实现用 `or replace`，并发下盖掉）。
            for 重试次数 in range(5):
                编号 = 取新编号(连接, 类名)
                try:
                    连接.execute("insert into 规则 values(?,?,?,?,?)",
                               (编号, 类名, 规则名, 内容值, 规则依据))
                    连接.commit()
                    break
                except sqlite3.IntegrityError:
                    连接.rollback()
            else:
                print("拒：并发撞号 5 次仍拿不到新号 —— 稍后重试", file=sys.stderr)
                return 1
    finally:
        连接.close()
    print(f"记规则：{编号} · {类名} · {规则名}")
    print("★ 库变了 ⇒ 收口前记得 `v1_task` 功能=6 记账"
          "（`源件` = `开发工具/信息核心/信息核心.db`），否则释放的越界检测会拒")
    return 0
