# -*- coding: utf-8 -*-
"""清理执行 —— 「清理已解决任务」的**落盘执行面**：路径硬化 · 待续清意图 · 文件删除 · 库行删除 · 作业行删除。

**为什么单开一件**（判据 ⑲ 单件 ≤400 行）：`任务清理.py` 只留编排与回执；执行面（含 TOCTOU 硬化）
单列一件，读得完也守得住行数。

**路径硬化（拒符号链接与越界软链）**：允许边界按**逻辑路径**判（`normpath`，**绝不 `resolve`**）——
`resolve` 会把界外软链映射成界内目标，让越界件冒充界内件。允许根**自身**的链不判（如 macOS
`/var → /private/var`），允许根**以下**的每一段都逐段 `is_symlink` 拒。报告件、作业日志、
反馈源正文快照只在下述各自的落点里被删，别处一律越界拒删。

**待续清意图（短生命周期，不备份整史）**：库行删除与「待删文件清单」在**同一条事务**里落
`清理待续` 表（开工号 · 路径 · 种类 · 期望内容哈希 · 时刻）⇒ 提交后逐个 `unlink`，删一件清一件。
`unlink` 失败（权限 / 非普通文件 / 内容已变 / 路径消失）⇒ 该行**留在待续表**，本次**不得回 0
宣称完整清**；下次同口调用**先续清**，清完即删行。不另建历史库、不复制原件、不留永久流水。

**TOCTOU 复核**：删除前重新核内容 sha256 与落意图时的 `期望内容哈希` 逐字相同 ⇒ 盘上换过内容即拒删。
"""

import hashlib
import os
import sqlite3
import stat
from pathlib import Path

from .. import 作业账本

待续表名 = "清理待续"
种类_报告件 = "报告件"
种类_作业日志 = "作业日志"
种类_反馈快照 = "反馈快照"
快照列名 = "快照路径"
内容哈希块字节 = 1 << 20
# 与 `任务清理.辅助表名` 同一集合（本件是它的取数口）——按开工号直删的那些表。
辅助表名 = ("开工检查点", "工具流水", "写盘意图", "已记账恢复", "认领重叠", "认领", "改动", "开工基线")


def 允许边界根表() -> list:
    """报告件 / 作业日志 / 临时快照的**允许边界根**（逻辑路径，不经 resolve）。

    边界根含：客户端 agents 根（报告件）· 运行数据根 `日志`（作业日志）· 运行数据根 `临时件`
    （报告件与反馈源正文快照）。别处一律越界。
    """
    import sys
    from pathlib import Path as _路径
    sys.path.insert(0, str(_路径(__file__).resolve().parents[2]))     # 开发工具/：取 运行数据根
    from 运行数据根 import 解析当前环境, 子目录路径
    from ..反馈治理.反馈源清点 import 客户端根
    边界根表 = []
    try:
        边界根表.append(客户端根())
    except OSError:
        pass
    for 子目录名 in ("日志", "临时件"):
        try:
            边界根表.append(子目录路径(解析当前环境(), 子目录名))
        except Exception:
            pass
    return [Path(os.path.normpath(str(边界根))) for 边界根 in 边界根表]


def 规范报告路径(路径) -> tuple:
    """原文 ⇒ `(逻辑绝对路径 或 None, 说明)`。只 `normpath`，**绝不 resolve**（理由见文件头）。"""
    原文 = str(路径 or "").strip()
    if not 原文:
        return None, "空路径"
    原路径 = Path(原文)
    if not 原路径.is_absolute():
        return None, "非绝对路径"
    逻辑路径 = Path(os.path.normpath(原文))
    if str(逻辑路径) != str(原路径):
        return None, "含 `..` 或冗余分隔（逻辑路径与原文不符）"
    return 逻辑路径, ""


def 在界内(逻辑路径) -> bool:
    """逻辑路径是否落在某个允许边界根之下（**按逻辑前缀**判，不经 resolve）。"""
    候选文本 = os.path.normpath(str(逻辑路径))
    for 边界根 in 允许边界根表():
        边界根文本 = str(边界根)
        if 候选文本 == 边界根文本 or 候选文本.startswith(边界根文本 + os.sep):
            return True
    return False


def 链接面异常(逻辑路径) -> str:
    """允许根**以下**逐段 `is_symlink` ⇒ 说明（空 = 正常；根自身链不判，见文件头）。"""
    件路径 = Path(str(逻辑路径))
    匹配边界根 = None
    for 边界根 in 允许边界根表():
        if str(件路径).startswith(str(边界根) + os.sep):
            匹配边界根 = 边界根
            break
    if 匹配边界根 is None:
        return "越界（不在允许根内）"
    当前路径 = 匹配边界根
    for 段名 in 件路径.relative_to(匹配边界根).parts:
        当前路径 = 当前路径 / 段名
        try:
            if 当前路径.is_symlink():
                return "含符号链接：%s" % 段名
        except OSError:
            return "链接面读不动：%s" % 段名
    return ""


def 规范同身份(逻辑路径) -> str:
    """同一物理文件的**身份串**（`realpath` 规范化）—— 共享判定与去重都走它（不由逻辑路径拼）。"""
    try:
        return os.path.normpath(os.path.realpath(str(逻辑路径))).rstrip(os.sep) or os.sep
    except OSError:
        return os.path.normpath(str(逻辑路径))


def 文件内容哈希(路径) -> str:
    """内容 sha256（`O_NOFOLLOW` 打开 ⇒ **符号链接直接失败**）⇒ 十六进制串；读不动 ⇒ 空串。"""
    try:
        文件号 = os.open(str(路径), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        return ""
    try:
        哈希摘要 = hashlib.sha256()
        while True:
            数据块 = os.read(文件号, 内容哈希块字节)
            if not 数据块:
                break
            哈希摘要.update(数据块)
        return 哈希摘要.hexdigest()
    except OSError:
        return ""
    finally:
        os.close(文件号)


# ── 待续清意图（短生命周期）───────────────────────────────────────────────────────────────

def 补待续表(连接) -> None:
    """建 `清理待续` 表（幂等，**不提交**）。库行与待删文件同事务落定 ⇒ 崩溃 / unlink 失败后能续清。

    **绝不在此 `commit`**：它会在「`begin immediate` → 删库行 → 记待续」之间插入一次提交，把
    「库行已删、待删文件清单未落」的中间态**永久固化**（正是本能力要杜绝的半删）。
    调用方须在**事务之外**先建表（`任务清理._连库`）。
    """
    连接.execute(
        "create table if not exists %s ("
        " 开工号 text not null, 路径 text not null, 种类 text not null,"
        " 期望内容哈希 text, 时刻 text not null, primary key (开工号, 路径))" % 待续表名)


def 记待续(连接, 开工号: str, 待续项表: list, 时刻: str) -> int:
    """把待删文件清单落进待续表（**与库行删除同一事务**）⇒ 落定条数。"""
    补待续表(连接)
    落定数 = 0
    for 待续项 in 待续项表:
        连接.execute("insert or replace into %s (开工号, 路径, 种类, 期望内容哈希, 时刻) "
                 "values (?, ?, ?, ?, ?)" % 待续表名,
                 (开工号, 待续项["路径"], 待续项["种类"], 待续项.get("期望内容哈希") or "", 时刻))
        落定数 += 1
    return 落定数


def 读待续(连接, 开工号: str) -> list:
    """本开工待续清的剩余文件 ⇒ 行表（按路径序）。"""
    补待续表(连接)
    return [dict(数据行) for 数据行 in 连接.execute(
        "select * from %s where 开工号 = ? order by 路径" % 待续表名, (开工号,))]


def 清待续(连接, 开工号: str, 路径表) -> int:
    """清掉**已真删**那些路径的待续行 ⇒ 删掉行数（清完 ⇒ 待续表里本开工为空）。"""
    if not 路径表:
        return 0
    占位符 = ",".join("?" * len(路径表))
    return 连接.execute("delete from %s where 开工号 = ? and 路径 in (%s)"
                    % (待续表名, 占位符), [开工号] + list(路径表)).rowcount


# ── 文件删除（硬化）─────────────────────────────────────────────────────────────────────

def 删一个文件(待续项: dict) -> tuple:
    """硬化删一件 ⇒ `(是否已删, 残留说明)`。

    四道：① 早删过（`lstat` 报不存在）⇒ **已完成**（幂等）；② 非普通文件（含符号链接）⇒ 拒；
    ③ 路径仍须**在允许界内且链接面正常**（计划期到删除期之间盘上可能变过）；④ 内容 sha256 与
    落意图时的 `期望内容哈希` 逐字相同（TOCTOU 复核）⇒ 不符即拒，绝不误删别人的件。
    """
    路径 = str(待续项.get("路径") or "")
    if not 路径:
        return True, ""
    try:
        状态 = os.lstat(路径)
    except FileNotFoundError:
        return True, ""
    except OSError as 错误:
        return False, "%s（lstat 读不动：%s）" % (路径, 错误)
    if stat.S_ISLNK(状态.st_mode) or not stat.S_ISREG(状态.st_mode):
        return False, "%s（不是普通文件 ⇒ 拒删）" % 路径
    逻辑路径, 路径说明 = 规范报告路径(路径)
    if 逻辑路径 is None:
        return False, "%s（%s ⇒ 拒删）" % (路径, 路径说明)
    if not 在界内(逻辑路径):
        return False, "%s（越界 ⇒ 拒删）" % 路径
    链接说明 = 链接面异常(逻辑路径)
    if 链接说明:
        return False, "%s（%s ⇒ 拒删）" % (路径, 链接说明)
    期望内容哈希 = str(待续项.get("期望内容哈希") or "")
    if 期望内容哈希:
        现内容哈希 = 文件内容哈希(路径)
        if 现内容哈希 != 期望内容哈希:
            return False, "%s（内容已变：期望 %s · 现 %s ⇒ 拒删）" % (
                路径, 期望内容哈希[:12], (现内容哈希 or "读不动")[:12])
    try:
        os.unlink(路径)
    except OSError as 错误:
        return False, "%s（%s）" % (路径, 错误)
    return True, ""


def 删文件(待续项表: list) -> tuple:
    """逐件硬化删 ⇒ `(已删路径表, 残留说明表)`。"""
    已删路径表, 残留表 = [], []
    for 待续项 in 待续项表:
        删掉, 说明 = 删一个文件(待续项)
        if 删掉:
            已删路径表.append(str(待续项.get("路径") or ""))
        elif 说明:
            残留表.append(说明)
    return 已删路径表, 残留表


# ── 库行删除（调用方负责事务边界）─────────────────────────────────────────────────────────

def 数表行(连接, 表名: str, 开工号: str) -> int:
    """本开工在一张辅助表里的行数（表不在 / 读不动 ⇒ 0，不阻断）。"""
    try:
        return 连接.execute("select count(*) from %s where 开工号 = ?" % 表名,
                        (开工号,)).fetchone()[0]
    except sqlite3.Error:
        return 0


def 删表行(连接, 表名: str, 开工号: str) -> int:
    """按开工号删一张表里的本开工行 ⇒ 行数（表不在 / 读不动 ⇒ 0，不阻断）。"""
    try:
        return 连接.execute("delete from %s where 开工号 = ?" % 表名, (开工号,)).rowcount
    except sqlite3.Error:
        return 0


def 删条目行(连接, 条目号表: list) -> dict:
    """删一批条目的从属行（关闭 / 判词 / 证据）与条目行本身 ⇒ 删除计数表。"""
    删除计数 = {}
    if not 条目号表:
        return 删除计数
    占位符 = ",".join("?" * len(条目号表))
    for 表名 in ("反馈关闭", "反馈判词", "反馈证据", "反馈条目"):
        删除计数[表名] = 连接.execute(
            "delete from %s where 条目号 in (%s)" % (表名, 占位符), 条目号表).rowcount
    return 删除计数


def 删来源行(连接, 来源号表: list) -> int:
    """删一批来源行 ⇒ 行数。"""
    if not 来源号表:
        return 0
    占位符 = ",".join("?" * len(来源号表))
    return 连接.execute("delete from 反馈来源 where 来源号 in (%s)" % 占位符, 来源号表).rowcount


def 删认领重叠行(连接, 行表: list) -> int:
    """真删**孤儿**反向 `认领重叠` 行（引用方已清 / 已释放 ⇒ 无主）⇒ 删掉条数。

    只删调用方点名的行（三列定位）—— 不按开工号粗删，也不动活开工的行。
    """
    删掉 = 0
    for 数据行 in 行表:
        游标 = 连接.execute(
            "delete from 认领重叠 where 开工号 = ? and 路径 = ? and 对方开工号 = ?",
            (数据行["开工号"], 数据行["路径"], 数据行["对方开工号"]))
        删掉 += 游标.rowcount or 0
    return 删掉


def 回写混合来源(连接, 混合来源: dict) -> None:
    """混合来源：只删已解决条目 ⇒ 提取 / 判词条数按**保留**口径回写（不伪造）。"""
    留条目表 = 混合来源["留条目"]
    占位符 = ",".join("?" * len(留条目表))
    判词条数 = 连接.execute("select count(*) from 反馈判词 where 条目号 in (%s)"
                      % 占位符, 留条目表).fetchone()[0]
    连接.execute("update 反馈来源 set 提取条数 = ?, 判词条数 = ? where 来源号 = ?",
              (len(留条目表), 判词条数, 混合来源["来源号"]))


def 删任务库行(连接, 计划: dict, 开工号: str) -> dict:
    """任务模式：**一条事务内**删全部库行（反馈 + 辅助表 + **开工行本体**）⇒ 删除计数表。

    开工行**本体删除**（2026-10-08 用户纠偏）：不留「已清理」墓碑 —— 墓碑是「以关闭替代删」，
    与本能力「做完即清」的口径相悖。
    """
    删除计数 = 删条目行(连接, 计划["可删条目"])
    删来源数 = 删来源行(连接, 计划["删来源"])
    if 删来源数:
        删除计数["反馈来源"] = 删来源数
    for 混合来源 in 计划["混合来源"]:
        回写混合来源(连接, 混合来源)
    if 计划["可清开工行"]:
        批次行数 = 删表行(连接, "反馈批次", 开工号)
        if 批次行数:
            删除计数["反馈批次"] = 批次行数
    for 表名 in 辅助表名:
        行数 = 删表行(连接, 表名, 开工号)
        if 行数:
            删除计数[表名] = 行数
    if 计划["可清开工行"]:
        行数 = 连接.execute("delete from 开工 where 开工号 = ?", (开工号,)).rowcount
        if 行数:
            删除计数["开工"] = 行数
    return 删除计数


def 删条目库行(连接, 计划: dict) -> dict:
    """条目模式：只删**标定的条目**及其变空的来源行；**不动**任何开工 / 认领 / 改动行。"""
    删除计数 = 删条目行(连接, 计划["可删条目"])
    删来源数 = 删来源行(连接, 计划["删来源"])
    if 删来源数:
        删除计数["反馈来源"] = 删来源数
    for 混合来源 in 计划["混合来源"]:
        回写混合来源(连接, 混合来源)
    return 删除计数


def 删作业行(任务ID表: list) -> tuple:
    """删归属作业行 ⇒ `(删掉数, 残留说明表)`。**另一本库、单独事务**；失败只报残留。"""
    if not 任务ID表:
        return 0, []
    连接 = sqlite3.connect(str(作业账本.作业账本路径()), timeout=5)
    try:
        占位符 = ",".join("?" * len(任务ID表))
        连接.execute("begin immediate")
        行数 = 连接.execute("delete from 作业 where 任务ID in (%s)" % 占位符, 任务ID表).rowcount
        连接.commit()
        return 行数, []
    except sqlite3.Error as 错误:
        连接.rollback()
        return 0, ["作业账本删行失败：%r" % (错误,)]
    finally:
        连接.close()


# ── 临时快照消费（655 `反馈源快照` 交本能力清）───────────────────────────────────────

def 候选快照路径(连接, 待清来源号表) -> list:
    """待清来源行引用的**全部**快照件路径（去重，按路径序）—— 计划期候选，**不代表可删**。

    全清来源的快照可能仍被**别的**来源行引用（共享快照）⇒ 计划期只取候选，真删与否由
    `复核快照待续` 在**事务内**按剩余实际 source 引用定。未并入 655 / 老库无 `快照路径`列 ⇒ 空。
    """
    if not 待清来源号表:
        return []
    try:
        列名集 = {文本行[1] for 文本行 in 连接.execute("pragma table_info(反馈来源)")}
    except sqlite3.Error:
        return []
    if 快照列名 not in 列名集:
        return []
    占位符 = ",".join("?" * len(待清来源号表))
    try:
        return sorted({数据行[0] for 数据行 in 连接.execute(
            "select distinct %s from 反馈来源 where 来源号 in (%s) and %s is not null"
            % (快照列名, 占位符, 快照列名), 待清来源号表) if 数据行[0]})
    except sqlite3.Error:
        return []


def 复核快照待续(连接, 候选路径表) -> list:
    """**事务内**复核：候选快照件里**已无任何来源行引用**者 ⇒ 待续项表（TOCTOU 安全）。

    口径**消费** 655 `反馈源快照.快照被引用`（按**剩余实际 source 引用**）；计划期到提交期之间
    若有别的来源行新引用了同一快照，这里会读到并**保留**它。读不动 ⇒ 保留（fail-closed）。
    """
    if not 候选路径表:
        return []
    待续项表 = []
    for 件路径 in 候选路径表:
        try:
            from ..反馈治理 import 反馈源快照
            被引用 = 反馈源快照.快照被引用(连接, 件路径)
        except Exception:
            try:
                被引用 = bool(连接.execute(
                    "select count(*) from 反馈来源 where %s = ?" % 快照列名,
                    (件路径,)).fetchone()[0])
            except sqlite3.Error:
                被引用 = True
        if 被引用:
            continue
        逻辑路径, _说明 = 规范报告路径(件路径)
        if 逻辑路径 is None or not 在界内(逻辑路径) or 链接面异常(逻辑路径):
            continue
        内容哈希 = 文件内容哈希(逻辑路径)
        if not 内容哈希:
            continue
        待续项表.append({"路径": str(逻辑路径), "种类": 种类_反馈快照,
                    "期望内容哈希": 内容哈希})
    return 待续项表
