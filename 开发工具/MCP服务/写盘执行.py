# -*- coding: utf-8 -*-
"""写盘执行 —— `v1_edit` 逐条写盘那一段（落意图 → 落盘 → 同事务记账），以及原子写盘原语。

**为什么单开一件**（判据 ⑲ 单源文件 ≤400 行）：`修改.py` 已 377 行 ⇒ 执行与沙箱原语搬到这里，
`修改.py` 只留闸序与调度。**实现只有这一份**：`批量改名` 的 `_写文件` 也从 `修改` 转口取。

**逐条为什么不是整批**（2026-10-08 隔离复现）：定位靠**内容**不靠行号 ⇒ 只能逐条；
故本工具从来不是整批回滚，回执必须如实报「本批写了几件、失败在第几件」。

**两步之间不再有裸窗口**（本件修的那个缺陷）：写盘之前的**每一项**都先落一行写盘意图；
落盘后走 `写盘账本.记一件写盘`：认领指纹 + 改动记录 + 销意图在**一条** sqlite 事务里。
盘已写、账未记的窗口只可能在「落盘成功、事务未提」之间，且此时意图行仍在账本 ⇒
`写盘恢复` 能按写前 / 期望写后指纹把它收敛。落盘本身失败 ⇒ 件没动（临时件加更换是原子的），
意图就地销掉，回执照实说「没写成」。
"""

import hashlib
import os
import sqlite3
from pathlib import Path

from 代码地图 import 文件指纹

from .写盘账本 import 记一件写盘, 记写盘意图, 销写盘意图

功能_新建 = 0
功能_修改 = 1
功能_删除 = 2
功能名表 = {功能_新建: "新建", 功能_修改: "修改", 功能_删除: "删除"}

写盘后缀 = ".v1edit-tmp"          # 不含 `_临时_`：源码树里禁那个前缀（判据 ⑰）


def 内容指纹(内容值: str) -> str:
    """一段文本按 utf-8 码的内容指纹（sha256 前 16 位）—— 与 `文件指纹` 同形，但吃内存文本。

    `写文件` 以 `newline="\n"` + utf-8 写盘 ⇒ 落盘字节就是 `文本.encode("utf-8")` ⇒
    两者得同一个值。写盘**之前**就能算出期望写后指纹，才能拿它当恢复的唯一凭据。
    """
    return hashlib.sha256(内容值.encode("utf-8")).hexdigest()[:16]


def 写文件(件路径: Path, 全文: str, 预期指纹=None) -> str:
    """**临时件 + rename**（同目录、同文件系统 ⇒ 原子的）⇒ 错误说明（空 = 成功）。

    为什么不 `write_text`：它是「截断 + 写」，中途崩了会留一个**半截文件** ——
    那是把「拒」变成了「毁」。

    ★ **保留既有件的模式位**（2026-10-08 实测）：`rename` 换的是**新 inode**，新 inode 的模式
    是「按 umask 新建」的那个（仓内 umask 022 ⇒ 644），**原件带不带执行位都不带过去** ——
    实测 0755 的件经本函数落盘后变 644。仓里有 5 个带执行位的 `.sh`（`git ls-files -s` 记
    `100755`，`合主干集成树.py` 合主干时也读这个位），原先的 `write_text`（原地截断）不丢模式位
    ⇒ 那是本件引入的**回归**。故写临时件后先把原模式位 `chmod` 回去、再 `replace`。
    新件（原件不存在）照旧吃 umask —— 与 `write_text` 建新件同一口径。模式位读 / 设不动
    ⇒ 同 `OSError` 一并走失败分支：临时件删掉，**原文件一个字节不动**。
    """
    import tempfile
    if 预期指纹 is None:
        预期指纹 = 文件指纹(str(件路径)) if 件路径.is_file() else ""
    临时路径 = None
    原父目录 = 件路径.parent.resolve()
    try:
        文件描述符, 临时文件名 = tempfile.mkstemp(prefix=件路径.name + ".", suffix=写盘后缀, dir=件路径.parent)
        os.close(文件描述符)
        临时路径 = Path(临时文件名)
        原模式 = 件路径.stat().st_mode & 0o7777 if 件路径.exists() else None
        临时路径.write_text(全文, encoding="utf-8", newline="\n")
        if 原模式 is not None:
            os.chmod(临时路径, 原模式)
        当前指纹 = 文件指纹(str(件路径)) if 件路径.is_file() else ""
        if 件路径.is_symlink() or 件路径.parent.resolve() != 原父目录 or 当前指纹 != 预期指纹:
            临时路径.unlink(missing_ok=True)
            return "替换前指纹漂移：未替换原件"
        os.replace(临时路径, 件路径)
    except OSError as 写不动的原因:
        if 临时路径 is not None:
            临时路径.unlink(missing_ok=True)
        return "写盘失败：%r" % (写不动的原因,)
    return ""


def 删除文件(件路径: Path) -> str:
    """删除件 ⇒ 错误说明（空 = 成功）。

    ★ 原先直接 `件路径.unlink()` 裸抛：删不动（权限 / 目录不可写）时异常冒到协议层，
    变成 `-32603 内部错误`，而**前面已写成功的件已经落盘、账也记了** —— 回执拿不到，
    调用方无从判断。本函数把它收成可读的返回（与 `写文件` 同形），失败原样进回执。
    """
    try:
        件路径.unlink()
    except OSError as 删不动的原因:
        return "删除失败：%r" % (删不动的原因,)
    return ""


def 定位旧内容(全文: str, 旧内容: str) -> list:
    """`旧内容` 在全文里的**全部出现位置** ⇒ `[位置…]`（空表 = 找不到）。"""
    位表, 区间起点 = [], 0
    while True:
        字节位置 = 全文.find(旧内容, 区间起点)
        if 字节位置 < 0:
            return 位表
        位表.append(字节位置)
        区间起点 = 字节位置 + 1


def _记意图(连接, 开工号: str, 路径: str, 功能名: str, 写前指纹: str, 期望写后: str) -> str:
    """落盘前记一行意图 ⇒ 错误说明（空 = 成功）。落不动意图 ⇒ **不写盘**（fail-closed）。"""
    try:
        记写盘意图(连接, 开工号, 路径, 功能名, 写前指纹, 期望写后)
    except sqlite3.Error as 意图错:
        return "%s" % (意图错,)
    return ""


def _平意图(连接, 开工号: str, 路径: str) -> str:
    """落盘**失败**后就地销意图（件没动，意图无害）⇒ 残留提示（空 = 已销 / 销不动）。"""
    try:
        销写盘意图(连接, 开工号, 路径)
    except sqlite3.Error:
        return "（写盘意图未销掉，可跑 `v1_edit` 操作 `恢复` 收敛）"
    return ""


def 执行写盘(连接, 工作树: Path, 开工号: str, 项表: list, 盘上表: dict) -> tuple:
    """逐条：落意图 → 定位 → 写盘 / 删除 → 同事务记账 ⇒ `(完成表, 失败说明, 失败阶段)`。

    返回的 `失败阶段` ∈ 空串（全成）/「落意图」/「读件」/「定位」/「落盘」/「记账」——
    回执靠它说清「盘到哪一步了」，不洒一个笼统的失败。
    """
    完成表, 失败说明, 失败阶段 = [], "", ""
    for 序号, (路径, 功能号, 旧内容, 新内容) in enumerate(项表, 1):
        件路径 = 工作树 / 路径
        写前指纹 = 盘上表.get(路径) or (文件指纹(str(件路径)) if 件路径.is_file() else "")
        功能名 = 功能名表[功能号]
        if 功能号 == 功能_新建:
            新全文 = 新内容 if 新内容.endswith("\n") else 新内容 + "\n"
            期望写后 = 内容指纹(新全文)
        else:
            try:
                全文 = 件路径.read_text(encoding="utf-8", newline="\n")
            except UnicodeDecodeError:
                失败说明 = ("第 %d 条 `%s`：不是 utf-8 文本（二进制件）⇒ 拒（`v1_edit` 只改"
                        "文本件；二进制源件走 `v1_task` 操作 源件记账）" % (序号, 路径))
                失败阶段 = "读件"
                break
            位表 = 定位旧内容(全文, 旧内容)
            if not 位表:
                失败说明 = ("第 %d 条 `%s`：**找不到** `旧内容` ⇒ 拒（文件已变，"
                        "请重新读一次这个件再发起修改）" % (序号, 路径))
                失败阶段 = "定位"
                break
            if len(位表) > 1:
                行号表 = [全文[:字节位置].count("\n") + 1 for 字节位置 in 位表]
                失败说明 = ("第 %d 条 `%s`：`旧内容` 在文件里出现 **%d 次**（行 %s）⇒ 拒。"
                        "多给几行上下文，让它唯一" % (序号, 路径, len(位表),
                                          " · ".join(str(行序号) for 行序号 in 行号表[:8])))
                失败阶段 = "定位"
                break
            字节位置 = 位表[0]
            if 功能号 == 功能_删除:
                新全文, 期望写后 = "", ""
            else:
                新全文 = 全文[:字节位置] + 新内容 + 全文[字节位置 + len(旧内容):]
                期望写后 = 内容指纹(新全文)
        意图错 = _记意图(连接, 开工号, 路径, 功能名, 写前指纹, 期望写后)
        if 意图错:
            失败说明 = ("第 %d 条 `%s`：落写盘意图失败 ⇒ **没写盘**（fail-closed）：%s"
                    % (序号, 路径, 意图错.strip()))
            失败阶段 = "落意图"
            break
        if 功能号 == 功能_删除:
            错误 = 删除文件(件路径)
        else:
            当前指纹 = 文件指纹(str(件路径)) if 件路径.is_file() else ""
            错误 = "落盘前指纹漂移" if 当前指纹 != 写前指纹 else 写文件(件路径, 新全文)
        if 错误:
            残留 = _平意图(连接, 开工号, 路径)
            失败说明 = "第 %d 条 `%s`：%s（盘上未改）%s" % (序号, 路径, 错误, 残留)
            失败阶段 = "落盘"
            break
        写后指纹 = 文件指纹(str(件路径)) if 件路径.is_file() else ""
        try:
            记一件写盘(连接, 开工号, 路径, 功能名, 写前指纹, 写后指纹)
        except sqlite3.Error as 收尾错:
            失败说明 = ("第 %d 条 `%s`：**盘已写（写后 %s），但记账没提上去**（%s）⇒ "
                    "盘账不一致，写盘意图仍在账本 —— 下一条没动，先跑 `v1_edit` 操作 `恢复` 收敛"
                    % (序号, 路径, 写后指纹 or "（件没了）", 收尾错))
            失败阶段 = "记账"
            break
        盘上表[路径] = 写后指纹
        完成表.append("%s（%s）" % (路径, 功能名))
    return 完成表, 失败说明, 失败阶段


class 写盘占用(Exception):
    """已有写入者时立即拒绝。"""


from contextlib import contextmanager


@contextmanager
def 开工写盘锁(开工号):
    """同一账本、同一开工共享非阻塞进程锁。"""
    import fcntl
    from .开工账本 import 连账本
    if not isinstance(开工号, str) or not 开工号.startswith("v1-") or "/" in 开工号 or ".." in 开工号 or "\\" in 开工号:
        raise 写盘占用("开工号形状错误")
    锁连接 = 连账本()
    try:
        树记录 = 锁连接.execute("select 工作树 from 开工 where 开工号 = ?", (开工号,)).fetchone()
    finally:
        锁连接.close()
    if not 树记录 or not Path(树记录[0]).is_dir():
        raise 写盘占用("没有这条开工工作树")
    锁描述符 = os.open(Path(树记录[0]), os.O_RDONLY)
    try:
        try:
            fcntl.flock(锁描述符, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise 写盘占用("开工写盘锁已占用，未写盘")
        try:
            yield
        finally:
            fcntl.flock(锁描述符, fcntl.LOCK_UN)
    finally:
        os.close(锁描述符)
