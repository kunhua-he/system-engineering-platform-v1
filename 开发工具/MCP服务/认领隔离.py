# -*- coding: utf-8 -*-
"""认领隔离：事务外核验真实 Git 副本，短事务内复核并登记。"""
from pathlib import Path

from . import 开工账本 as 账本
from .仓操作 import 跑命令, 读盘指纹
from .仓状态 import 跑git


def 读认领快照(连接, 开工号):
    return [tuple(快照行) for 快照行 in 连接.execute(
        "select 开工.开工号, 开工.工作树, 开工.分支名, 开工.状态, 认领.路径, 认领.指纹 "
        "from 开工 left join 认领 on 开工.开工号 = 认领.开工号 "
        "where 开工.开工号 <> ? order by 开工.开工号, 认领.路径", (开工号,))]


def 核验树身份(仓根, 工作树, 分支名):
    """只接受本仓已注册的完整工作树根和对应支线。

    仓根**可以是 bare**（`core.bare=true` 时它没有 toplevel）—— 与仓根只比**公共 Git 目录**；
    树身份仍由工作树自身的 toplevel 与 `git worktree list` 登记项把关，隔离强度不变。
    """
    工作树 = Path(工作树).resolve()
    if not 工作树.is_dir():
        return None
    退出码, 输出文本 = 跑git(工作树, ["rev-parse", "--path-format=absolute",
                              "--git-common-dir", "--show-toplevel"])
    输出行 = 输出文本.strip().splitlines()
    if 退出码 or len(输出行) != 2:
        return None
    公共Git目录, 树根 = (Path(路径).resolve() for 路径 in 输出行)
    if 树根 != 工作树:
        return None
    退出码, 输出文本 = 跑git(Path(仓根).resolve(), ["rev-parse", "--path-format=absolute", "--git-common-dir"])
    输出行 = 输出文本.strip().splitlines()
    if 退出码 or not 输出行 or Path(输出行[0]).resolve() != 公共Git目录:
        return None
    退出码, 输出文本 = 跑git(仓根, ["worktree", "list", "--porcelain", "-z"])
    if 退出码:
        return None
    for 工作树记录 in 输出文本.split("\0\0"):
        字段表 = dict(字段.partition(" ")[::2] for 字段 in 工作树记录.split("\0") if 字段)
        if (字段表.get("worktree") and Path(字段表["worktree"]).resolve() == 工作树
                and 字段表.get("branch") == "refs/heads/" + 分支名):
            退出码, 基线提交 = 跑git(工作树, ["rev-parse", "HEAD"])
            if not 退出码:
                return 工作树, 基线提交.strip()
    return None


def 判认领隔离(仓根, 开工记录, 指纹表, 快照表):
    本树身份 = 核验树身份(仓根, 开工记录["工作树"], 开工记录["分支名"])
    if not 本树身份:
        return 2, "无法核验本仓真实工作树根与支线 ⇒ 拒绝认领", []
    本树路径, 本树提交 = 本树身份
    for 路径 in 指纹表:
        if not (本树路径 / 路径).resolve().is_relative_to(本树路径):
            return 2, "认领文件指向树外公共物理落点 ⇒ 拒绝", []
    诊断表, 树身份表 = [], {}
    for 别的号, 树路径, 支线名, 状态值, 认领路径, 旧指纹 in 快照表:
        if not 认领路径 or not Path(树路径).is_dir():
            continue
        for 路径 in 指纹表:
            本件路径 = (本树路径 / 路径).resolve()
            别件路径 = (Path(树路径) / 认领路径).resolve()
            同物理件 = 本件路径 == 别件路径
            if 本件路径.is_file() and 别件路径.is_file():
                同物理件 = 同物理件 or 本件路径.samefile(别件路径)
            if 路径 != 认领路径 and not 同物理件:
                continue
            if 别的号 not in 树身份表:
                树身份表[别的号] = 核验树身份(仓根, 树路径, 支线名)
            别树身份 = 树身份表[别的号]
            if (not 别树身份 or 本树路径 == 别树身份[0] or 同物理件
                    or not 本件路径.is_relative_to(本树路径)
                    or not 别件路径.is_relative_to(别树身份[0])):
                return 2, ("重叠认领冲突：%s 与 %s（同树、公共物理落点或无法核验本仓隔离）"
                           " ⇒ 拒绝；确认重叠不能绕过隔离硬闸" % (路径, 别的号)), []
            诊断表.append((开工记录["开工号"], 路径, str(本树路径), 本树提交,
                          别的号, str(别树身份[0]), 别树身份[1]))
    return 0, "", 诊断表


def 事务认领(连接, 仓根, 开工号, 指纹表, 确认重叠=False):
    """快照失效即重新核验；功能2不能重置已认领件的漂移指纹。"""
    for 重试次数 in range(3):
        开工记录 = 账本.读开工(连接, 开工号)
        if not 开工记录 or 开工记录["状态"] != 账本.状态_进行中:
            return 1, "开工不存在或不在进行中 ⇒ 不能认领"
        快照表 = 读认领快照(连接, 开工号)
        退出码, 输出文本, 诊断表 = 判认领隔离(仓根, 开工记录, 指纹表, 快照表)
        if 退出码:
            return 退出码, 输出文本
        最新指纹, 读不出表 = 读盘指纹(Path(开工记录["工作树"]), list(指纹表))
        if 读不出表 or 最新指纹 != 指纹表:
            return 2, "本树文件在核验期间漂移 ⇒ 停止该件，查清后重试；不刷新账本指纹"
        连接.execute("begin immediate")
        try:
            if (账本.读开工(连接, 开工号) != 开工记录
                    or 读认领快照(连接, 开工号) != 快照表):
                continue
            旧认领表 = 账本.读认领(连接, 开工号)
            漂移表 = [路径 for 路径, 指纹 in 指纹表.items()
                     if 路径 in 旧认领表 and 旧认领表[路径] != 指纹]
            if 漂移表:
                return 2, "本树已认领件指纹漂移 ⇒ 停止这些件，不用功能2洗账：%s" % " · ".join(漂移表)
            连接.executemany("insert into 认领 (开工号, 路径, 指纹) values (?, ?, ?) "
                             # ★ 2026-10-10 修（腿 v1-100758 真实发作）：`do nothing` ⇒ 行已存在就
                             #   永不补指纹 ⇒ 认领那一刻没算上指纹的行（空串）会让 `v1_edit` 的
                             #   指纹闸恒拒（判「被绕过改过」）⇒ 该件永远改不动。改成**只补空指纹**：
                             #   已有指纹的行仍不刷（保隔离语义 —— 刷了等于放行漂移）。
                             "on conflict(开工号, 路径) do update set 指纹 = excluded.指纹 "
                             "where 认领.指纹 = '' or 认领.指纹 is null",
                             [(开工号, 路径, 指纹) for 路径, 指纹 in 指纹表.items()])
            if 诊断表:
                连接.execute("create table if not exists 认领重叠 (开工号 text, 路径 text, 工作树 text, "
                             "基线提交 text, 对方开工号 text, 对方工作树 text, 对方基线提交 text, "
                             "primary key (开工号, 路径, 对方开工号))")
                连接.executemany("insert into 认领重叠 values (?, ?, ?, ?, ?, ?, ?) "
                                 "on conflict do nothing", 诊断表)
            连接.commit()
            提示文本 = ""
            if 诊断表:
                提示文本 = "独立副本同文件认领已允许（%d 处）；合并时三方合并，重叠片段保留双方交裁决。" % len(诊断表)
                if any(诊断项[1].endswith(".db") for 诊断项 in 诊断表):
                    提示文本 += " 二进制规则源按主键增量重放，不作文本自动合并。"
            return 0, 提示文本
        finally:
            if 连接.in_transaction:
                连接.rollback()
    return 2, "并发认领快照连续变化 ⇒ 没登记认领，稍后重试"


def 预留开工(连接, 仓根, 工作内容):
    """占号事务只写账本，路径查询和建树均不持 SQLite 写锁。"""
    for 重试次数 in range(3):
        开工号 = 账本.新开工号(连接, 仓根)
        退出码, 输出文本 = 跑命令(["sh", str(Path(仓根) / "开发工具" / "并行工作树.sh"),
                                  "路径", 开工号], cwd=仓根)
        if 退出码 or not 输出文本.strip():
            return None, None
        工作树 = Path(输出文本.strip().splitlines()[0])
        连接.execute("begin immediate")
        try:
            if 账本.新开工号(连接, 仓根) != 开工号:
                continue
            账本.登记开工(连接, 开工号, 工作内容, "腿/" + 开工号, str(工作树))
            return 开工号, 工作树
        finally:
            if 连接.in_transaction:
                连接.rollback()
    return None, None
