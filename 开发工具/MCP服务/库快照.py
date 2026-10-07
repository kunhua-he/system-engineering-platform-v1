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
                 骨架, 超时秒, git环境)

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

def 快照差集(仓根, 参数表) -> tuple:
    """按 `基准`（默认主干）与 `对照`（默认盘上）两个 ref 抽库，按主键比出新增 / 删除 / 变更。"""
    拒未知(参数表, ("基准", "对照", "表名", "条数"))
    记录条数 = 取记录条数(参数表)
    基准 = str(参数表.get("基准") or "").strip() or 主干引用(仓根)
    对照 = str(参数表.get("对照") or "").strip() or "盘上"
    表名 = str(参数表.get("表名") or "").strip()
    临时件 = []
    try:
        行表 = ["基准 %s · 对照 %s（临时件落 运行数据根/临时件，只读不写源库）" % (基准, 对照)]
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
        行表.append("表数：基准 %d · 对照 %d" % (len(基准表), len(对照表)))
        for 名称 in sorted(set(基准表) | set(对照表)):
            键名, 基准行 = 基准表.get(名称, ([], None))
            _, 对照行 = 对照表.get(名称, ([], None))
            if 基准行 is None or 对照行 is None:
                if 基准行 is None and 对照行 is None:
                    行表.append("  %s：无声明主键 ⇒ 跳过（不按行比）" % 名称)
                else:
                    行表.append("  %s：%s" % (名称, "只在对照" if 基准行 is None else "只在基准"))
                continue
            新增 = sorted(set(对照行) - set(基准行))
            删除表 = sorted(set(基准行) - set(对照行))
            变更表 = sorted(字段 for 字段 in set(基准行) & set(对照行) if 对照行[字段] != 基准行[字段])
            if not (新增 or 删除表 or 变更表):
                行表.append("  %s：无差异（%d 行）" % (名称, len(对照行)))
                continue
            行表.append("  %s（键 %s）：新增 %d · 删除 %d · 变更 %d"
                    % (名称, "+".join(键名) or "—", len(新增), len(删除表), len(变更表)))
            for 字段 in 新增[:记录条数]:
                行表.append("    + %s" % _键文(字段))
            for 字段 in 删除表[:记录条数]:
                行表.append("    - %s" % _键文(字段))
            for 字段 in 变更表[:记录条数]:
                行表.append("    ~ %s" % _键文(字段))
        return 0, 收尾(行表)
    finally:
        for 件路径 in 临时件:
            try:
                Path(件路径).unlink()
            except OSError:
                pass

工具名 = "v1_db"
工具说明 = ("规则库快照差集：按 `基准`（默认主干）与 `对照`（默认盘上源库）两个 ref 抽 "
        "`开发工具/信息核心/信息核心.db` 到运行数据根临时件，**按主键逐表**比出新增 / 删除 / 变更"
        "（条款正文含换行 ⇒ 按主键取整行，不拆行）。只读，绝不写真实源库；`表名` 可只看一张表。")
操作表 = {
    "快照差集": ((), ("基准", "对照", "表名", "条数"), '{"操作":"快照差集"}'),
}
分发表 = {"快照差集": 快照差集}
模式 = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "开工ID": {"type": "string", "description": "本工具按 ref 取库；留空即可（三字段同形）"},
        "操作": {"type": "string", "description": "要跑哪个只读操作；留空 = 只读发现调用，返回操作目录"},
        "参数": {"type": "object", "description": "该操作自有的参数（见 操作目录 里各操作的 必需/可选）"},
    },
}

def 派发(参数表, 仓根) -> tuple:
    return 骨架(工具名, 工具说明, 操作表, 分发表, 参数表, 仓根)
