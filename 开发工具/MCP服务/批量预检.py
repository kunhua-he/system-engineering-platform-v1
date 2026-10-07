# -*- coding: utf-8 -*-
"""批量预检：复用写口检查，在内存按顺序定位；回执不作为写入凭据。"""
import sqlite3
from pathlib import Path

from . import 开工账本 as 账本
from . import 修改
from .禁改面 import 禁改原因


def 检查候选文本(工作树: Path, 路径: str, 全文: str) -> list:
    """只报既有判据的局部预警；不复制基线比较或全仓验证。"""
    from 查文件行数 import 核心
    from 一键验证.判据_入口覆盖 import 主入口模式, 入口带壳, 读入口白名单
    from 一键验证.判据_十干 import 扫十干, 路径被排除
    from 一键验证.判据_禁译名 import 扫禁译名

    输出表 = []
    if 核心.是源码(路径):
        行数 = len(全文.splitlines())
        if 行数 > 核心.行数上限:
            输出表.append("行数 %d > %d" % (行数, 核心.行数上限))
        类别值 = 核心.入口类别(路径, 全文)
        if 类别值:
            if 行数 > 核心.入口行数上限:
                输出表.append("入口行数 %d > %d" % (行数, 核心.入口行数上限))
            if 核心.入口实现项(类别值, 路径, 全文):
                输出表.append("入口含实现")
    if 路径.endswith(".sh") or (路径.endswith(".py") and 主入口模式.search(全文)):
        名表, 错误 = 读入口白名单(工作树)
        if 错误:
            输出表.append("入口白名单未判：%s" % 错误)
        elif 路径 not in 名表 and not 入口带壳(路径, 全文):
            输出表.append("入口缺壳且未登记白名单")
    if not 路径被排除(路径):
        输出表.extend("字面禁字：行 %d · U+%04X" % (行数, 类别值)
                    for _, 行数, 类别值 in 扫十干({路径: 全文}))
        输出表.extend("字面禁译名：行 %d" % 行数 for _, 行数 in 扫禁译名({路径: 全文}))
    return 输出表


def 扫一遍(工作树: Path, 认领表: dict, 改动表: list) -> tuple:
    """收集各条可判拒绝；同件前条无法模拟时，后续定位明确未判。"""
    输出行表, 项表, 结果表, 失败表 = [], [], {}, set()
    退出码 = 0
    for 序号, 改动项 in enumerate(改动表, 1):
        路径, 功能号, 旧内容, 新内容, 错误 = 修改._读一条改动(改动项)
        if not 错误:
            错误 = 修改._查改动字段(功能号, 旧内容, 新内容)
        if 错误:
            输出行表.append("第 %d 条 `%s` · 字段拒绝：%s" % (序号, 路径, 错误))
            退出码 = 2
            if 路径 and 功能号 is not None:
                失败表.add(路径)
            continue
        项表.append((序号, 路径, 功能号, 旧内容, 新内容))
    新建集 = {路径 for _, 路径, 功能号, _, _ in 项表
             if 功能号 == 修改.功能_新建 and not (工作树 / 路径).exists()}
    功能名表 = {路径 for _, 路径, 功能号, _, _ in 项表 if 功能号 == 修改.功能_新建}
    盘上表, 变过表 = {}, {}
    for 路径 in {路径 for _, 路径, _, _, _ in 项表 if 路径 in 认领表}:
        try:
            对得上表, 指纹表 = 修改.对账(工作树, {路径: 认领表[路径]})
            盘上表.update(对得上表)
            变过表.update(指纹表)
        except OSError as 错误:
            输出行表.append("`%s` · 指纹未判：%s" % (路径, 错误))
            退出码 = 退出码 or 3
    for 序号, 路径, 功能号, 旧内容, 新内容 in 项表:
        件路径 = 工作树 / 路径
        输出表 = []
        if 路径 not in 认领表 and 路径 not in 新建集:
            输出表.append("认领拒绝：未认领")
        if 路径 in 变过表 and 路径 not in 功能名表:
            输出表.append("指纹拒绝：账本 %s → 盘上 %s；Read不更新账本，查清漂移后恢复并经写口重做"
                        % 变过表[路径])
        if 功能号 == 修改.功能_新建 and 件路径.exists():
            输出表.append("新建拒绝：盘上已存在")
        if 功能号 != 修改.功能_新建 and not 件路径.is_file():
            输出表.append("真实写口前置拒绝：盘上不存在；先建后改需分批，内存模拟继续")
        try:
            未登记名表, 错误 = 修改._未登记绑定名(工作树, [(路径, 功能号, 旧内容, 新内容)])
        except (sqlite3.Error, OSError) as 失败原因:
            未登记名表, 错误 = [], str(失败原因)
        if 错误:
            输出表.append("命名未判：%s" % 错误)
            退出码 = 退出码 or 5
        if 未登记名表:
            输出表.append("命名拒绝：%s" % " · ".join(未登记名表))
            退出码 = 退出码 or 5
        try:
            全文 = 结果表[路径] if 路径 in 结果表 else (
                件路径.read_text(encoding="utf-8", newline="\n") if 件路径.is_file() else None)
            错误 = 禁改原因(路径, 新内容 if 功能号 == 修改.功能_新建 else (全文 or ""))
            if 错误:
                输出表.append("禁写拒绝：%s" % 错误)
            if 路径 in 失败表:
                输出表.append("顺序模拟未判：此前同件操作无法定位")
            elif 功能号 == 修改.功能_新建:
                if 全文 is not None:
                    输出表.append("顺序新建拒绝：候选件已存在")
                    失败表.add(路径)
                elif not 件路径.parent.is_dir():
                    输出表.append("新建拒绝：父目录不存在")
                    失败表.add(路径)
                else:
                    结果表[路径] = 新内容 if 新内容.endswith("\n") else 新内容 + "\n"
            elif 全文 is None:
                输出表.append("顺序模拟未判：候选件不存在")
                失败表.add(路径)
            else:
                位表 = 修改._定位旧内容(全文, 旧内容)
                if len(位表) != 1:
                    输出表.append("旧内容拒绝：出现 %d 次（须唯一）" % len(位表))
                    失败表.add(路径)
                elif 功能号 == 修改.功能_删除:
                    结果表[路径] = None
                else:
                    字节位置 = 位表[0]
                    结果表[路径] = 全文[:字节位置] + 新内容 + 全文[字节位置 + len(旧内容):]
        except (UnicodeDecodeError, OSError) as 错误:
            输出表.append("文本拒绝：%s；二进制源件走功能6" % 错误)
            失败表.add(路径)
        if 输出表:
            退出码 = 退出码 or 3
        输出行表.extend("第 %d 条 `%s` · %s" % (序号, 路径, 说明) for 说明 in 输出表)
        if 路径 not in 失败表:
            输出行表.append("第 %d 条 `%s` · 顺序内存模拟完成" % (序号, 路径))
    for 路径, 全文 in 结果表.items():
        if 全文 is None or 路径 in 失败表:
            continue
        try:
            输出行表.extend("`%s` · 正式闸预警：%s" % (路径, 说明)
                         for 说明 in 检查候选文本(工作树, 路径, 全文))
        except Exception as 错误:
            输出行表.append("`%s` · 正式闸预警未判：%s" % (路径, 错误))
    return 退出码, "\n".join(输出行表)


def 派发(参数表: dict, 仓根) -> tuple:
    """账本只读连接，不建目录、不建表、不迁移、不刷新指纹或索引。"""
    开工号 = str(参数表.get("开工ID") or "").strip()
    改动表 = 参数表.get("改动表")
    if not 开工号 or not isinstance(改动表, list) or not 改动表:
        return 2, "只读预检要开工ID及非空改动表"
    try:
        库件 = 账本.子目录路径(账本.解析当前环境(), 账本.子目录类别) / 账本.库文件名
        连接 = sqlite3.connect(库件.absolute().as_uri() + "?mode=ro", uri=True)
        连接.row_factory = sqlite3.Row
        try:
            一条开工 = 账本.读开工(连接, 开工号)
            if not 一条开工 or 一条开工["状态"] != 账本.状态_进行中:
                return 1, "只读预检拒绝：开工不存在或不在进行中"
            工作树 = Path(一条开工["工作树"])
            if not 工作树.is_dir():
                return 1, "只读预检拒绝：工作树不存在"
            认领表 = 账本.读认领(连接, 开工号)
        finally:
            连接.close()
    except (sqlite3.Error, OSError, ValueError, KeyError, 账本.无位置) as 错误:
        return 1, "只读预检账本未判：%s；未建库或迁移" % 错误
    退出码, 说明 = 扫一遍(工作树, 认领表, 改动表)
    return 退出码, ("只读预检 · 工作树 %s · %d 条 · 退出码 %d\n%s\n"
                  "零写：源码、规则库、账本、索引未改。命名面=形参+局部绑定；"
                  "定义面、基线及冻结形状须正式闸；预检不等放行，真实写入重新验闸。"
                  % (工作树, len(改动表), 退出码, 说明))
