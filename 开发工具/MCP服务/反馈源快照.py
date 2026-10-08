# -*- coding: utf-8 -*-
"""反馈源快照 —— 未解决 source 的**可读真实报告版本**（内容寻址 · 落 临时件/反馈源正文）。

**一句话**：登记来源时把报告正文按 sha256 内容寻址存一份只读副本，只活到该来源被清理；
`提交反馈` 有路径且可读时**核真实完整 hash** 后原子存快照；缺路径显式**无快照**。

**并发安全**（用户 2026-10-08 纠正）：文件先写、DB 后提交**不自动并发安全** —— 先建 sha 件者
失败回滚若删，会毁掉后到者已成功引用的同 sha 件。故本件四道：全流程持**共锁**（`fcntl.flock`
独占）· 删前**引用复核**（`快照被引用`）· **不覆盖**已存在件（`O_EXCL`）· 路径走 `O_NOFOLLOW`
防 symlink 与 TOCTOU。**进程中断残留**（无来源行引用的孤儿件）**可清**（`清残留`），
**不冒充事务原子**。

**正文上限**：现真实最大报告实测 39500 字节（805 个 output.txt 全量），本件取 1 MiB 常量
（26x 余量），超限**拒**且**不截原文**；要调只改 `正文字节上限` 一处。
"""

import fcntl
import hashlib
import os
import stat
from contextlib import contextmanager
from pathlib import Path

from 运行数据根 import 子目录路径, 解析当前环境

快照子目录名 = "反馈源正文"
快照件后缀 = ".txt"
快照锁名 = ".快照锁"
快照列名 = "快照路径"
正文字节上限 = 1048576
分块字节 = 65536
快照状态_有 = "有快照"
快照状态_原路径 = "原路径可读且匹配"
快照状态_缺失 = "快照缺失待核"
快照状态_无 = "无快照待核"


class 快照写不动(Exception):
    """快照件写不动（临时件建不动 / 同名件内容与 sha 不符）—— 调用方整批零写。"""


def 快照目录(仓根) -> Path:
    """内容寻址快照的落点目录（`<运行数据根>/临时件/反馈源正文`）。"""
    return Path(子目录路径(解析当前环境(), "临时件")) / 快照子目录名


def 读正文上限(仓根) -> int:
    """报告正文上限字节（现取常量；真实最大 39500 ⇒ 1 MiB 余量充足）。"""
    return 正文字节上限


def 读整件(件路径, 上限字节数: int) -> bytes:
    """有界读整件（普通件 · `O_NOFOLLOW`）⇒ 字节；读不动 / 非普通件 / 超上限 ⇒ `None`（拒，不截）。"""
    try:
        件描述符号 = os.open(件路径, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return None
    try:
        件属性信息 = os.fstat(件描述符号)
        if not stat.S_ISREG(件属性信息.st_mode) or 件属性信息.st_size > 上限字节数:
            return None
        读块表 = []
        剩余字节 = 件属性信息.st_size
        while 剩余字节 > 0:
            读块字节 = os.read(件描述符号, min(分块字节, 剩余字节))
            if not 读块字节:
                break
            读块表.append(读块字节)
            剩余字节 -= len(读块字节)
        return b"".join(读块表)
    finally:
        os.close(件描述符号)


def 核指纹(件路径, 期望内容指纹: str) -> bool:
    """流式算件 sha256 与期望指纹比；读不动 / 非普通件 ⇒ 假（fail-closed）。"""
    try:
        件描述符号 = os.open(件路径, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return False
    try:
        if not stat.S_ISREG(os.fstat(件描述符号).st_mode):
            return False
        摘要器 = hashlib.sha256()
        while True:
            读块字节 = os.read(件描述符号, 分块字节)
            if not 读块字节:
                break
            摘要器.update(读块字节)
        return 摘要器.hexdigest() == 期望内容指纹
    finally:
        os.close(件描述符号)


def 读有界(件路径, 起始偏移: int = 0, 本页字节数: int = 0) -> tuple:
    """有界读普通件（**可分段**）⇒ `(退出码, 字节)`；`本页字节数` ≤0 ⇒ 读到上限为止；
    越界 / 超 `正文字节上限` ⇒ 码2（不截）。"""
    try:
        件描述符号 = os.open(件路径, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return 2, b""
    try:
        件属性信息 = os.fstat(件描述符号)
        if not stat.S_ISREG(件属性信息.st_mode):
            return 2, b""
        件总字节 = 件属性信息.st_size
        if 起始偏移 < 0 or 起始偏移 > 件总字节:
            return 2, b""
        取字节数 = 本页字节数 if 本页字节数 > 0 else 件总字节 - 起始偏移
        if 取字节数 > 正文字节上限:
            return 2, b""
        os.lseek(件描述符号, 起始偏移, os.SEEK_SET)
        return 0, os.read(件描述符号, 取字节数)
    finally:
        os.close(件描述符号)


@contextmanager
def 锁快照(仓根):
    """快照库**跨进程共锁**（`fcntl.flock` 独占，阻塞等）：文件阶段与 DB 提交同锁。"""
    目录路径 = 快照目录(仓根)
    目录路径.mkdir(parents=True, exist_ok=True)
    锁句柄 = open(目录路径 / 快照锁名, "a+")
    try:
        fcntl.flock(锁句柄, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(锁句柄, fcntl.LOCK_UN)
    finally:
        锁句柄.close()


def 存正文(仓根, 正文内容字节: bytes) -> tuple:
    """内容寻址存一份正文（**须持 `锁快照`**）⇒ `(件路径, 是否本次新建)`。
    已存在且 sha 相符 ⇒ 复用（**不覆盖**）；同名件内容不符 ⇒ 拒（疑似篡改）；
    新建走 `O_CREAT|O_EXCL|O_NOFOLLOW` 临时名 + `os.replace`（同目录原子改名）。"""
    目录路径 = 快照目录(仓根)
    目录路径.mkdir(parents=True, exist_ok=True)
    实算内容指纹 = hashlib.sha256(正文内容字节).hexdigest()
    目标件 = 目录路径 / (实算内容指纹 + 快照件后缀)
    if 目标件.exists():
        if 核指纹(目标件, 实算内容指纹):
            return str(目标件), False
        raise 快照写不动("同名件内容与 sha 不符（疑似篡改）⇒ 拒覆盖：%s" % 目标件)
    临时件路径 = 目录路径 / (实算内容指纹 + ".临时")
    try:
        件描述符号 = os.open(临时件路径,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    except OSError as 错误:
        raise 快照写不动("临时件建不动：%s" % 错误) from 错误
    try:
        os.write(件描述符号, 正文内容字节)
        os.fsync(件描述符号)
    finally:
        os.close(件描述符号)
    os.replace(临时件路径, 目标件)
    return str(目标件), True


def 删件(件路径) -> None:
    """删一个快照件（**只删本次新建且复核无引用者**；调用方负责复核）。"""
    try:
        os.unlink(件路径)
    except OSError:
        pass


def 快照被引用(连接, 快照件路径: str, 排除号表=()) -> bool:
    """该快照件路径是否仍被**别的**来源行引用（`排除号表` 内的来源号不算）。"""
    排除值表 = [int(号值) for 号值 in 排除号表 if 号值 is not None]
    条件 = ""
    if 排除值表:
        问号串 = ",".join("?" * len(排除值表))
        条件 = " and 来源号 not in (%s)" % 问号串
    快照计数行 = 连接.execute("select count(*) from 反馈来源 where 快照路径 = ?" + 条件,
                        (快照件路径, *排除值表)).fetchone()
    return bool(快照计数行 and 快照计数行[0])


def 可清快照(连接, 仓根, 待清来源号表) -> list:
    """待清来源的快照件里**无别的来源行引用**者 ⇒ 可删件路径表（按**剩余实际 source 引用**）。
    **不**要求整个开工未蒸馏为空 —— 单一已解决任务也能清（用户 2026-10-08 纠正）。"""
    排除值表 = [int(号值) for 号值 in 待清来源号表 if 号值 is not None]
    if not 排除值表:
        return []
    问号串 = ",".join("?" * len(排除值表))
    数据行表 = 连接.execute("select distinct 快照路径 from 反馈来源 where 来源号 in (%s) "
                       "and 快照路径 is not null" % 问号串, 排除值表).fetchall()
    可删件表 = []
    for 数据行 in 数据行表:
        候选路径 = 数据行[0]
        if 候选路径 and not 快照被引用(连接, 候选路径, 排除值表):
            可删件表.append(候选路径)
    return 可删件表


def 清残留(连接, 仓根) -> list:
    """清**孤儿**快照件（无任何来源行引用）+ 半写 `.临时` 件 ⇒ 已删件表。
    **不冒充事务原子**：只收孤儿，不动有引用的件。"""
    目录路径 = 快照目录(仓根)
    if not 目录路径.is_dir():
        return []
    已引用件集 = {数据行[0] for 数据行 in 连接.execute(
        "select distinct 快照路径 from 反馈来源 where 快照路径 is not null")}
    已删件表 = []
    for 快照件 in sorted(目录路径.iterdir()):
        if 快照件.name == 快照锁名:
            continue
        if 快照件.suffix == ".临时" or str(快照件) not in 已引用件集:
            删件(str(快照件))
            已删件表.append(str(快照件))
    return 已删件表


def 读快照(连接, 来源号: int) -> tuple:
    """来源号 ⇒ `(状态, 报告文本)`：优先内容寻址快照（**先校 sha**）；缺失 / 不符 ⇒ 显式待核；
    再回退原 `报告路径`（**可读且 sha 相符**才算）。**有界**，超上限 ⇒ 待核。"""
    来源行 = 连接.execute("select 快照路径, 报告路径, 内容指纹 "
                     "from 反馈来源 where 来源号 = ?", (来源号,)).fetchone()
    if not 来源行:
        return 快照状态_缺失, ""
    期望内容指纹 = 来源行["内容指纹"]
    快照件路径 = 来源行["快照路径"]
    for 候选路径, 命中状态 in ((快照件路径, 快照状态_有),
                          (来源行["报告路径"], 快照状态_原路径)):
        if not 候选路径 or not Path(候选路径).is_file():
            continue
        if not 核指纹(候选路径, 期望内容指纹):
            continue
        退出码, 字节值 = 读有界(候选路径)
        if 退出码 == 0:
            return 命中状态, 字节值.decode("utf-8", "replace")
    return (快照状态_缺失 if 快照件路径 else 快照状态_无), ""
