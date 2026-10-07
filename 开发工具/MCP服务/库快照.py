# -*- coding: utf-8 -*-
"""库快照 —— `v1_db` 的实现：按 ref 抽 信息核心.db 到临时件后**按主键**比表差集（只读）。

**为什么要有它**（多路代理实测）：比两个 ref 的规则库差了什么，现在只能把 3.6MB 的二进制
拉出来手工比。本件按 ref 抽库到临时件、按主键逐表比出「新增 / 删除 / 变更」。

★ **条款正文含换行** ⇒ 一律**按主键取整行**（sqlite 行），不得把库 dump 成文本再拆行。
★ **临时件落 `<运行数据根>/临时件/`**（走 `口径.py`），绝不写真实源库；收尾即删。
"""
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))     # 开发工具/

from 运行数据根 import 无位置, 子目录路径, 解析当前环境            # noqa: E402
from .仓状态 import (参数错, 取记录条数, 拒未知, 收尾, 主干引用, 源件路径,  # noqa: E402
                 跑git, 建操作处理, 超时秒, git环境)

def _抽库(仓根, 引用, 临时件) -> tuple:
    """把某个 ref 下的源库抽到临时件 ⇒ `(件路径, 错误)`；`盘上` 就用盘上件（不落临时）。
    抽出来的临时件路径记进 `临时件` 表，调用方收尾时删。"""
    if 引用 in ("盘上", ""):
        件路径 = Path(仓根) / 源件路径
        return (件路径, "") if 件路径.is_file() else (None, "盘上源库不在：%s" % 件路径)
    try:
        回执 = subprocess.run(["git", "show", "%s:%s" % (引用, 源件路径)], cwd=str(仓根),
                          capture_output=True, timeout=超时秒, env=git环境(仓根))
    except subprocess.TimeoutExpired:
        return None, "抽 %s 的源库超时" % 引用
    except OSError as 错误:
        return None, "起不了 git：%r" % (错误,)
    if 回执.returncode != 0:
        return None, "该 ref 下没有源库（或读不出）：%s" % 回执.stderr.decode("utf-8", "replace")[:200]
    try:
        临时根 = 子目录路径(解析当前环境(), "临时件")
    except 无位置 as 错误:
        return None, "临时件落点解析不出：%s" % 错误
    临时根.mkdir(parents=True, exist_ok=True)
    句柄, 临时路径 = tempfile.mkstemp(prefix="v1_db_", suffix=".db", dir=str(临时根))
    os.close(句柄)
    Path(临时路径).write_bytes(回执.stdout)
    临时件.append(临时路径)
    return Path(临时路径), ""

def _表列(连接, 表名) -> list:
    return list(连接.execute('pragma table_info("%s")' % 表名.replace('"', '""')))

def _键名(连接, 表名) -> list:
    """表的主键列名（按 pk 序号排）；没声明主键 ⇒ 空表（调用方跳过并报出）。"""
    字段表 = [字段 for 字段 in _表列(连接, 表名) if 字段[5]]
    字段表.sort(key=lambda 字段: 字段[5])
    return [字段[1] for 字段 in 字段表]

def _读表(连接, 表名, 键名) -> dict:
    """按主键把整表读成 `{键元组: 整行元组}` —— **整行取**，条款正文里的换行原样保留。"""
    列名 = [字段[1] for 字段 in _表列(连接, 表名)]
    位表 = [列名.index(名称) for 名称 in 键名]
    结果表 = {}
    for 数据行 in 连接.execute('select * from "%s"' % 表名.replace('"', '""')):
        结果表[tuple(数据行[列号] for 列号 in 位表)] = tuple(数据行)
    return 结果表

def _读全库(件路径, 表名) -> tuple:
    """读一个库 ⇒ `({表名: (键名, {键元组: 整行元组})}, 错误)`；坏库如实报（不假空）。"""
    try:
        连接 = sqlite3.connect("file:%s?mode=ro" % 件路径, uri=True)
    except sqlite3.Error as 错误:
        return None, "库打不开：%s" % 错误
    try:
        全表 = [数据行[0] for 数据行 in 连接.execute(
            "select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name")]
        结果表 = {}
        for 名称 in 全表:
            if 表名 and 表名 not in 名称:
                continue
            键名 = _键名(连接, 名称)
            结果表[名称] = (键名, _读表(连接, 名称, 键名)) if 键名 else ([], None)
        return 结果表, ""
    except sqlite3.Error as 错误:
        return None, "库读不动（可能不是 sqlite 库）：%s" % 错误
    finally:
        连接.close()

def _键文(字段) -> str:
    return "、".join(str(值) for 值 in 字段)

def _取提交(仓根, 引用) -> str:
    """`引用` 指向的 commit（原文）；`盘上` / 读不出 ⇒ 空串（盘上可变件不冒充提交）。"""
    if 引用 == "盘上":
        return ""
    退出码, 输出文本 = 跑git(仓根, ["rev-parse", "--verify", "--quiet", "%s^{commit}" % 引用])
    return 输出文本.strip() if 退出码 == 0 else ""

def _来源行(仓根, 侧名, 引用) -> str:
    """一侧的**来源**：git ref 给来源提交；`盘上` 如实标「工作树可变件（非提交）」。"""
    if 引用 == "盘上":
        return "  %s %s ⇒ 盘上工作树可变件（非提交，无 commit）" % (侧名, 引用)
    提交 = _取提交(仓根, 引用)
    return "  %s %s ⇒ 来源提交 %s" % (侧名, 引用, 提交 or "（读不出）")

def 快照差集(仓根, 参数表) -> tuple:
    """按 `基准`（默认主干）与 `对照`（默认盘上）两个 ref 抽库，按主键比出新增 / 删除 / 变更。

    **每表按同一完整主键差集**：全量 count 在**全量集**上算（显示前 `条数` 条不影响它）；
    另给每表 `展示` 条数与 `截断` 标记（展示截断 ≠ 全量统计变）。`目标` = `摘要` ⇒ 只出每表
    count、不出 `+ - ~` 行。**两端 diff**（两棵 ref 的库）与三方重放是两回事，不得混。
    """
    拒未知(参数表, ("基准", "对照", "表名", "条数", "目标"))
    记录条数 = 取记录条数(参数表)
    基准 = str(参数表.get("基准") or "").strip() or 主干引用(仓根)
    对照 = str(参数表.get("对照") or "").strip() or "盘上"
    表名 = str(参数表.get("表名") or "").strip()
    目标取值 = str(参数表.get("目标") or "").strip()
    if 目标取值 and 目标取值 != "摘要":
        raise 参数错("`目标` 只认 `摘要`（收到 %r）" % (目标取值,))
    只摘要 = 目标取值 == "摘要"
    临时件 = []
    try:
        行表 = ["基准 %s · 对照 %s（临时件落 运行数据根/临时件，只读不写源库）" % (基准, 对照)]
        行表.append("目标：%s" % ("摘要（每表只出 count，不出行）" if 只摘要 else "明细（每表出 count + 前 %d 条）" % 记录条数))
        库件, 错误 = _抽库(仓根, 基准, 临时件)
        if 错误:
            return 1, "基准侧（%s）：%s" % (基准, 错误)
        基准表, 错误 = _读全库(库件, 表名)
        if 错误:
            return 1, "基准侧（%s）：%s" % (基准, 错误)
        库件, 错误 = _抽库(仓根, 对照, 临时件)
        if 错误:
            return 1, "对照侧（%s）：%s" % (对照, 错误)
        对照表, 错误 = _读全库(库件, 表名)
        if 错误:
            return 1, "对照侧（%s）：%s" % (对照, 错误)
        行表.append("来源（两侧各一）：")
        行表.append(_来源行(仓根, "基准", 基准))
        行表.append(_来源行(仓根, "对照", 对照))
        行表.append("表数：基准 %d · 对照 %d" % (len(基准表), len(对照表)))
        for 名称 in sorted(set(基准表) | set(对照表)):
            键名, 基准行 = 基准表.get(名称, ([], None))
            _, 对照行 = 对照表.get(名称, ([], None))
            if 基准行 is None or 对照行 is None:
                if 基准行 is None and 对照行 is None:
                    行表.append("  %s：无声明主键 ⇒ 跳过（不按行比）· 截断 否" % 名称)
                else:
                    行表.append("  %s：%s" % (名称, "只在对照" if 基准行 is None else "只在基准"))
                continue
            新增 = sorted(set(对照行) - set(基准行))
            删除表 = sorted(set(基准行) - set(对照行))
            变更表 = sorted(字段 for 字段 in set(基准行) & set(对照行) if 对照行[字段] != 基准行[字段])
            展示新增 = 新增[:记录条数]
            展示删除 = 删除表[:记录条数]
            展示变更 = 变更表[:记录条数]
            截断标记 = "是" if (len(展示新增) < len(新增) or len(展示删除) < len(删除表)
                          or len(展示变更) < len(变更表)) else "否"
            行表.append("  %s（键 %s）：全量 新增 %d · 删除 %d · 变更 %d · 展示 +%d/-%d/~%d · 截断 %s"
                    % (名称, "+".join(键名) or "—", len(新增), len(删除表), len(变更表),
                       len(展示新增), len(展示删除), len(展示变更), 截断标记))
            if 只摘要:
                continue
            for 字段 in 展示新增:
                行表.append("    + %s" % _键文(字段))
            for 字段 in 展示删除:
                行表.append("    - %s" % _键文(字段))
            for 字段 in 展示变更:
                行表.append("    ~ %s" % _键文(字段))
        return 0, 收尾(行表)
    finally:
        for 件路径 in 临时件:
            try:
                Path(件路径).unlink()
            except OSError:
                pass

def 名册读数(仓根, 参数表) -> tuple:
    """`命名登记` 名册读数（只读盘上源库）：总数 · 出现次数为零的行 · 按名查出现次数。

    **为什么要有它**（名册卫生腿实测）：核一个名的出现次数、列零出现行，现在只能手动
    `sqlite3` 直查、每次新拼 SQL。本操作给一处口径。**全 0 回「未判」**：整表出现次数全是 0
    ⇒ 那一列没在维护 ⇒ 读数不可信，如实说「未判」，不当「全是僵尸」。
    """
    拒未知(参数表, ("名字", "条数"))
    记录条数 = 取记录条数(参数表)
    名字 = str(参数表.get("名字") or "").strip()
    库件 = Path(仓根) / 源件路径
    if not 库件.is_file():
        return 1, "盘上源库不在：%s" % 库件
    try:
        连接 = sqlite3.connect("file:%s?mode=ro" % 库件, uri=True)
    except sqlite3.Error as 错误:
        return 1, "库打不开：%s" % 错误
    try:
        总数 = 连接.execute("select count(*) from 命名登记").fetchone()[0]
        零次行数 = 连接.execute("select count(*) from 命名登记 where 出现次数=0").fetchone()[0]
        行表 = ["命名登记（盘上源库，只读）：总数 %d · 出现次数为零 %d" % (总数, 零次行数)]
        if 名字:
            数据行 = 连接.execute(
                "select 名字, 出现次数, 状态, 语义 from 命名登记 where 名字=?", (名字,)).fetchone()
            if 数据行 is None:
                行表.append("按名查「%s」：**名册无此名**（先确认拼写，或走 `v1_edit` 命名闸的登记提示）" % 名字)
            else:
                行表.append("按名查「%s」：出现次数 %d · 状态 %s · 语义 %s"
                        % (数据行[0], 数据行[1], 数据行[2], 数据行[3]))
        elif 总数 and 零次行数 == 总数:
            行表.append("★ **未判**：整表出现次数全是 0 ⇒ 那一列没在维护（不是「全是僵尸行」）。"
                     "先跑 `python3 开发工具/信息核心/信息核心.py 落库` 再读。")
        else:
            行表.append("出现次数为零的行（僵尸行，前 %d 条）：" % 记录条数)
            for 数据行 in 连接.execute(
                    "select 名字, 状态 from 命名登记 where 出现次数=0 order by 名字 limit ?",
                    (记录条数,)):
                行表.append("  零次  %s（状态 %s）" % (数据行[0], 数据行[1]))
            if 零次行数 > 记录条数:
                行表.append("  …（还有 %d 条，调 `条数`）" % (零次行数 - 记录条数))
        return 0, 收尾(行表)
    except sqlite3.Error as 错误:
        return 1, "名册读不动：%s" % 错误
    finally:
        连接.close()


工具名 = "v1_db"
工具说明 = ("规则库快照差集：按 `基准`（默认主干）与 `对照`（默认盘上源库）两个 ref 抽 "
        "`开发工具/信息核心/信息核心.db` 到运行数据根临时件，**按同一完整主键逐表**比出全量 "
        "新增 / 删除 / 变更 count（条款正文含换行 ⇒ 按主键取整行，不拆行）。回执另给每表"
        "**展示条数与截断标记**（显示前 `条数` 条不改全量统计）与**两侧来源提交**（盘上侧如实标"
        "工作树可变件·非提交）；`目标=摘要` ⇒ 每表只出 count、不出行。只读，绝不写真实源库；"
        "`表名` 可只看一张表。两端 diff 与三方重放是两回事，不得混。")
操作表 = {
    '快照差集': {"说明": '快照差集：每表全量 新增/删除/变更 count + 展示条数/截断 + 两侧来源提交', "需开工ID": False, "必需": [],
        "可选": ['基准', '对照', '表名', '条数', '目标'], "最短例": {'操作': '快照差集'},
        "处理": 建操作处理(快照差集, 并入开工=False)},
    '名册读数': {"说明": '名册读数：命名登记总数 / 出现次数为零的行 / 按名查出现次数（只读盘上源库）',
        "需开工ID": False, "必需": [], "可选": ['名字', '条数'],
        "最短例": {'操作': '名册读数'},
        "处理": 建操作处理(名册读数, 并入开工=False)},
}
