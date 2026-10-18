# -*- coding: utf-8 -*-
"""库快照 —— `v1_db` 的实现：按 ref 抽 信息核心.db 到**本次请求唯一临时目录**后**按主键**比表差集（只读）。

**为什么要有它**（多路代理实测）：比两个 ref 的规则库差了什么，现在只能把 3.6MB 的二进制
拉出来手工比。本件按 ref 抽库到临时件、按主键逐表比出「新增 / 删除 / 变更」。

★ **条款正文含换行** ⇒ 一律**按主键取整行**（sqlite 行），不得把库 dump 成文本再拆行。
★ **版本侧一律走 git 不可变 blob**（`git show <ref>:<路径>`）—— 盘上那一侧如实标「工作树可变件」，
  绝不用可变库冒充提交。
★ **每次请求一个唯一临时目录**（`tempfile.mkdtemp` 落 `<运行数据根>/临时件/`）：并发 / 重入两请求
  各写各的目录，**绝不交叉覆盖**（不复用固定名）。抽出的快照件落盘即 0444 只读。
★ **只读一致性**：源库读前 / 读后各算一次文件 sha256（版本侧另记 git blob 指纹与 ref 前后一致），
  回执如实报「一致 / 变了」；本工具**绝不写真实源库**。
★ **临时件用完即清**：清理走 `_清快照目录`（路径由 `shlex.quote` 引用 ⇒ 含空格 / 特殊字符也不
  漏清、不误删；只删**临时件根之下**本工具那个目录，越界一律不删）。
"""
import hashlib
import os
import shlex
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))     # 开发工具/

from 运行数据根 import 无位置, 子目录路径, 解析当前环境            # noqa: E402
from .仓状态 import (参数错, 取记录条数, 拒未知, 收尾, 主干引用, 源件路径,  # noqa: E402
                 跑git, 建操作处理, 超时秒, git环境, 声明键集)

盘上标记 = "盘上"
块大小 = 1 << 20


def _文件sha256(件路径) -> str:
    """件的 **sha256 文件指纹**（与 git 的 blob 指纹是两码事，回执里分开写）。"""
    哈希摘要 = hashlib.sha256()
    with open(件路径, "rb") as 读句柄:
        for 数据块 in iter(lambda: 读句柄.read(块大小), b""):
            哈希摘要.update(数据块)
    return 哈希摘要.hexdigest()


def _取临时根():
    """临时件根（`<运行数据根>/临时件`）⇒ 目录；解析不出 ⇒ 参数错。"""
    try:
        临时根 = 子目录路径(解析当前环境(), "临时件")
    except 无位置 as 错误:
        raise 参数错("临时件落点解析不出：%s" % 错误)
    临时根.mkdir(parents=True, exist_ok=True)
    return 临时根


def _开快照目录(临时根):
    """本次请求**唯一**的临时目录（落 临时根）⇒ 并发 / 重入各写各的，绝不交叉覆盖。"""
    return Path(tempfile.mkdtemp(prefix="v1_db快照-", dir=str(临时根)))


def _清快照目录(快照目录, 临时根) -> str:
    """删掉本次请求的唯一目录 ⇒ 返回**所用命令**（路径由 `shlex.quote` 引用）；越界 / 不在 ⇒ 空串不删。

    只删**临时件根之下**的目录：含空格 / 特殊字符的路径由 `shlex.quote` 正确引用，不误删、不漏清。
    命令与执行**同源**（`shlex.split` 拆回参数表跑）⇒ 回执给的命令就是真跑的那条。
    """
    目录路径 = Path(快照目录)
    根路径 = Path(临时根)
    if not 目录路径.is_dir():
        return ""
    try:
        规整目录, 规整根 = 目录路径.resolve(), 根路径.resolve()
    except OSError:
        return ""
    if 规整目录 == 规整根 or 规整根 not in 规整目录.parents:
        return ""        # 越界：绝不删临时件根自身，或根之外的任意路径
    命令 = "rm -rf -- %s" % shlex.quote(str(规整目录))
    try:
        回执 = subprocess.run(shlex.split(命令), capture_output=True, timeout=超时秒)
    except OSError:
        return ""
    return 命令 if 回执.returncode == 0 else ""


def _取提交(仓根, 引用) -> str:
    """`引用` 指向的 commit（原文）；`盘上` / 读不出 ⇒ 空串（盘上可变件不冒充提交）。"""
    if 引用 == 盘上标记:
        return ""
    退出码, 输出文本 = 跑git(仓根, ["rev-parse", "--verify", "--quiet", "%s^{commit}" % 引用])
    return 输出文本.strip() if 退出码 == 0 else ""


def _抽库(仓根, 引用, 快照目录, 侧名) -> tuple:
    """把 `引用` 下的源库抽到 `快照目录` ⇒ `(件路径, 读数表, 错误)`。

    `盘上` ⇒ 直接用盘上件（**不落临时**，读数表如实标「工作树可变件」，绝不冒充提交）；
    其余 ⇒ 验引用存在（不存在 / 非本库 ⇒ 拒）＋取 blob 指纹与来源提交，再 `git show` 取不可变
    字节写进唯一件、置 0444 只读；blob 指纹读前读后各取一次（**ref 前后一致**）。
    """
    if 引用 in (盘上标记, ""):
        件路径 = Path(仓根) / 源件路径
        if not 件路径.is_file():
            return None, {}, "盘上源库不在：%s" % 件路径
        return 件路径, {"种类": "盘上", "件": str(件路径), "提交": "", "对象指纹": "",
                        "指纹一致": True, "文件sha256": _文件sha256(件路径)}, ""
    提交 = _取提交(仓根, 引用)
    if not 提交:
        return None, {}, "不是本库的合法引用（不存在 / 非本库路径）：%s" % 引用
    退出码, 输出文本 = 跑git(仓根, ["rev-parse", "%s:%s" % (引用, 源件路径)])
    指纹前 = 输出文本.strip() if 退出码 == 0 else ""
    if not 指纹前:
        return None, {}, "该 ref 下没有源库（读不出 blob）：%s" % 引用
    try:
        回执 = subprocess.run(["git", "show", "%s:%s" % (引用, 源件路径)], cwd=str(仓根),
                          capture_output=True, timeout=超时秒, env=git环境(仓根))
    except subprocess.TimeoutExpired:
        return None, {}, "抽 %s 的源库超时" % 引用
    except OSError as 错误:
        return None, {}, "起不了 git：%r" % (错误,)
    if 回执.returncode != 0:
        return None, {}, "该 ref 下没有源库（或读不出）：%s" % 回执.stderr.decode("utf-8", "replace")[:200]
    退出码, 输出文本 = 跑git(仓根, ["rev-parse", "%s:%s" % (引用, 源件路径)])
    指纹后 = 输出文本.strip() if 退出码 == 0 else ""
    件路径 = 快照目录 / ("快照_%s.db" % 侧名)
    件路径.write_bytes(回执.stdout)
    os.chmod(件路径, 0o444)          # 落盘即只读件：快照不许再被改
    return 件路径, {"种类": "git", "件": str(件路径), "提交": 提交, "对象指纹": 指纹前,
                    "指纹一致": 指纹前 == 指纹后, "文件sha256": _文件sha256(件路径)}, ""


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


def _来源行(侧名, 引用, 读数表) -> str:
    """一侧的**来源 + 指纹**：git ref 给来源提交与 blob；`盘上` 如实标「工作树可变件（非提交）」。"""
    if 读数表.get("种类") == "盘上":
        return ("  %s %s ⇒ 盘上工作树可变件（非提交，无 commit）· 文件 sha256 %s"
                % (侧名, 引用, 读数表.get("文件sha256") or "—"))
    return ("  %s %s ⇒ 来源提交 %s · 文件 sha256 %s · git blob %s · ref 前后一致 %s"
            % (侧名, 引用, 读数表.get("提交") or "（读不出）", 读数表.get("文件sha256") or "—",
               读数表.get("对象指纹") or "—", "是" if 读数表.get("指纹一致") else "否"))


def 快照差集(仓根, 参数表) -> tuple:
    """按 `基准`（默认主干）与 `对照`（默认盘上）两个 ref 抽库，按主键比出新增 / 删除 / 变更。

    **每表按同一完整主键差集**：全量 count 在**全量集**上算（显示前 `条数` 条不影响它）；
    另给每表 `展示` 条数与 `截断` 标记（展示截断 ≠ 全量统计变）。`目标` = `摘要` ⇒ 只出每表
    count、不出 `+ - ~` 行。**每次请求一个唯一临时目录**（并发 / 重入不交叉覆盖），抽库只读源库
    （读前读后 sha256 对照），临时件**用完即清**（清理命令见回执末）。两端 diff 与三方重放是两回事。
    """
    拒未知(参数表, 声明键集(操作表, "快照差集"))
    记录条数 = 取记录条数(参数表)
    基准 = str(参数表.get("基准") or "").strip() or 主干引用(仓根)
    对照 = str(参数表.get("对照") or "").strip() or 盘上标记
    表名 = str(参数表.get("表名") or "").strip()
    目标取值 = str(参数表.get("目标") or "").strip()
    if 目标取值 and 目标取值 != "摘要":
        raise 参数错("`目标` 只认 `摘要`（收到 %r）" % (目标取值,))
    只摘要 = 目标取值 == "摘要"
    源库件 = Path(仓根) / 源件路径
    源库前 = _文件sha256(源库件) if 源库件.is_file() else ""
    临时根 = _取临时根()
    快照目录 = _开快照目录(临时根)
    try:
        行表 = ["基准 %s · 对照 %s（唯一临时目录落 运行数据根/临时件，只读不写源库）" % (基准, 对照)]
        行表.append("目标：%s" % ("摘要（每表只出 count，不出行）" if 只摘要 else "明细（每表出 count + 前 %d 条）" % 记录条数))
        库件, 基准读数, 错误 = _抽库(仓根, 基准, 快照目录, "基准")
        if 错误:
            return 1, "基准侧（%s）：%s" % (基准, 错误)
        基准表, 错误 = _读全库(库件, 表名)
        if 错误:
            return 1, "基准侧（%s）：%s" % (基准, 错误)
        库件, 对照读数, 错误 = _抽库(仓根, 对照, 快照目录, "对照")
        if 错误:
            return 1, "对照侧（%s）：%s" % (对照, 错误)
        对照表, 错误 = _读全库(库件, 表名)
        if 错误:
            return 1, "对照侧（%s）：%s" % (对照, 错误)
        源库后 = _文件sha256(源库件) if 源库件.is_file() else ""
        行表.append("快照落点（本次请求唯一目录 · 落盘即 0444 只读）：%s" % 快照目录)
        行表.append("来源（两侧各一 · 含文件 sha256 / git blob）：")
        行表.append(_来源行("基准", 基准, 基准读数))
        行表.append(_来源行("对照", 对照, 对照读数))
        行表.append("源库只读一致性：读前 sha256 %s · 读后 sha256 %s ⇒ %s"
                 % (源库前 or "（源库不在）", 源库后 or "（源库不在）",
                    "一致（未写源库）" if 源库前 == 源库后 else "★ 源库变了"))
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
        清理命令 = _清快照目录(快照目录, 临时根)
        行表.append("临时件用完即清：%s" % (清理命令 or "（快照目录不在 / 越界拒删）"))
        return 0, 收尾(行表)
    finally:
        _清快照目录(快照目录, 临时根)      # 幂等：成功路径已清则 no-op；错误路径在此兜底清


def 名册读数(仓根, 参数表) -> tuple:
    """`命名登记` 名册读数（只读盘上源库）：总数 · 出现次数为零的行 · 按名查出现次数。

    **为什么要有它**（名册卫生腿实测）：核一个名的出现次数、列零出现行，现在只能手动
    `sqlite3` 直查、每次新拼 SQL。本操作给一处口径。**全 0 回「未判」**：整表出现次数全是 0
    ⇒ 那一列没在维护 ⇒ 读数不可信，如实说「未判」，不当「全是僵尸」。
    """
    拒未知(参数表, 声明键集(操作表, "名册读数"))
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
        "`开发工具/信息核心/信息核心.db` 到**运行数据根/临时件的本次请求唯一目录**（并发 / 重入不"
        "交叉覆盖；不复用固定名），**按同一完整主键逐表**比出全量 新增 / 删除 / 变更 count（条款"
        "正文含换行 ⇒ 按主键取整行，不拆行）。回执另给每表**展示条数与截断标记**（显示前 `条数` 条"
        "不改全量统计）与**两侧来源 + 文件 sha256 + git blob 指纹 + ref 前后一致**；版本侧一律走 git "
        "不可变 blob，绝不拿盘上可变库冒充提交。源库**只读**（读前读后 sha256 对照）；临时件**用完即清**"
        "（清理命令由 `shlex.quote` 引用路径，含空格 / 特殊字符不漏清、不误删，越界拒删）。`目标=摘要` "
        "⇒ 每表只出 count、不出行；`表名` 可只看一张表。两端 diff 与三方重放是两回事，不得混。")
操作表 = {
    '快照差集': {"说明": '快照差集：每表全量 新增/删除/变更 count + 展示条数/截断 + 两侧来源与指纹', "需开工ID": False, "必需": [],
        "可选": ['基准', '对照', '表名', '条数', '目标'], "最短例": {'操作': '快照差集'},
        "处理": 建操作处理(快照差集, 并入开工=False)},
    '名册读数': {"说明": '名册读数：命名登记总数 / 出现次数为零的行 / 按名查出现次数（只读盘上源库）',
        "需开工ID": False, "必需": [], "可选": ['名字', '条数'],
        "最短例": {'操作': '名册读数'},
        "处理": 建操作处理(名册读数, 并入开工=False)},
}
