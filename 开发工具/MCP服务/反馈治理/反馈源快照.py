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


def 锚点根() -> str:
    """写侧安全开锚点 —— **运行数据根本体** 的真实路径（`realpath`；本机 `/var` 等系统链已消）。
    `临时件` 留在锚点**之下**逐段把守 ⇒ 它自身是 symlink 也会被 `O_NOFOLLOW` 拦。"""
    try:
        目标根 = 解析当前环境()
        return os.path.realpath(str(目标根))
    except OSError:
        return ""


def 读正文上限(仓根) -> int:
    """报告正文上限字节（现取常量；真实最大 39500 ⇒ 1 MiB 余量充足）。"""
    return 正文字节上限


def 开只读件(件路径) -> tuple:
    """**只读面**安全开件：`O_RDONLY|O_NOFOLLOW`（末段不跟）⇒ `(退出码, 描述符号, 件总字节)`。
    调用方**必**校回传字节 sha（与表内指纹比）⇒ 即使中段有链换也不信内容。"""
    try:
        件描述符号 = os.open(str(件路径 or ""), os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return 2, -1, 0
    件属性信息 = os.fstat(件描述符号)
    if not stat.S_ISREG(件属性信息.st_mode):
        os.close(件描述符号)
        return 2, -1, 0
    return 0, 件描述符号, 件属性信息.st_size


def 读全件(件路径, 上限字节数: int) -> tuple:
    """安全开件（末段不跟链）+ **同一描述符**读到尾 ⇒ `(退出码, 字节)`。
    超上限 / 读不动 ⇒ 码2（**不截**）。"""
    退出码, 件描述符号, 件总字节 = 开只读件(件路径)
    if 退出码 != 0:
        return 2, b""
    try:
        if 件总字节 > 上限字节数:
            return 2, b""
        读块表 = []
        剩余字节 = 件总字节
        while 剩余字节 > 0:
            读块字节 = os.read(件描述符号, min(分块字节, 剩余字节))
            if not 读块字节:
                break
            读块表.append(读块字节)
            剩余字节 -= len(读块字节)
        return 0, b"".join(读块表)
    finally:
        os.close(件描述符号)


def 读整件(件路径, 上限字节数: int) -> bytes:
    """有界读整件 ⇒ 字节；读不动 / 不安全 / 超上限 ⇒ `None`（拒，不截）。"""
    退出码, 字节值 = 读全件(件路径, 上限字节数)
    return 字节值 if 退出码 == 0 else None


def 核指纹(件路径, 期望内容指纹: str) -> bool:
    """安全开件 + **同一描述符**流式 sha256 与期望比；读不动 / 不安全 ⇒ 假（fail-closed）。"""
    退出码, 件描述符号, 件总字节 = 开只读件(件路径)
    if 退出码 != 0:
        return False
    try:
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
    """安全开件 + 有界读（可分段）⇒ `(退出码, 字节)`；越界 / 超上限 ⇒ 码2（不截）。"""
    退出码, 件描述符号, 件总字节 = 开只读件(件路径)
    if 退出码 != 0:
        return 2, b""
    try:
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
def 锁快照(仓根, 拒绝值=None):
    """快照库**跨进程共锁**（`fcntl.flock` 独占，阻塞等）：文件阶段与 DB 提交同锁。
    锁件也走 **dirfd 逐段**（不跟任何段 symlink）；目录不安全且有 `拒绝值` ⇒ 产出它并把
    `yield` 置假（调用方据此整批零写、库零写）；无 `拒绝值` ⇒ 抛 `快照写不动`。"""
    目录路径 = 快照目录(仓根)
    退出码, 目录描述符号 = 建目录链(目录路径)
    if 退出码 != 0:
        if 拒绝值 is not None:
            拒绝值.append((2, "**整批零写**：快照目录不安全（父目录链含 symlink / 非目录）⇒ 拒写：%s"
                       % 目录路径))
            yield False
            return
        raise 快照写不动("快照目录不安全（父目录链含 symlink / 非目录）⇒ 拒锁：%s" % 目录路径)
    try:
        锁描述符号 = os.open(快照锁名, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
                        0o644, dir_fd=目录描述符号)
    except OSError as 错误:
        os.close(目录描述符号)
        if 拒绝值 is not None:
            拒绝值.append((2, "**整批零写**：锁件开不出（%s）" % 错误))
            yield False
            return
        raise 快照写不动("锁件开不出：%s" % 错误) from 错误
    os.close(目录描述符号)
    try:
        fcntl.flock(锁描述符号, fcntl.LOCK_EX)
        try:
            yield True
        finally:
            fcntl.flock(锁描述符号, fcntl.LOCK_UN)
    finally:
        os.close(锁描述符号)


def 建目录链(目录路径) -> tuple:
    """从 `锚点根`（运行数据根本体真实路径）起**逐段** `O_NOFOLLOW|O_DIRECTORY` 打开目录链
    （缺段经父 dir_fd `mkdir` 补建，**锚点之下不跟任何段 symlink** —— 含 `临时件` 自身）
    ⇒ `(退出码, 目录描述符号)`；中段是 symlink / 非目录 / 越出锚点 ⇒ 码2。"""
    规范锚点 = os.path.realpath(锚点根())
    规范目录 = os.path.realpath(str(目录路径 or ""))
    if not 规范锚点 or not 规范目录:
        return 2, -1
    相对路径 = os.path.relpath(规范目录, 规范锚点)
    if 相对路径.startswith(".."):
        return 2, -1
    段表 = [段名 for 段名 in 相对路径.split("/") if 段名]
    if not 段表:
        return 2, -1
    当前描述符号 = os.open(规范锚点, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for 段名 in 段表:
            try:
                下一描述符号 = os.open(段名, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                  dir_fd=当前描述符号)
            except FileNotFoundError:
                try:
                    os.mkdir(段名, dir_fd=当前描述符号)
                except FileExistsError:
                    pass          # 并发建目录：另一进程先建好 ⇒ 直接开它（不是错）
                下一描述符号 = os.open(段名, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                  dir_fd=当前描述符号)
            os.close(当前描述符号)
            当前描述符号 = 下一描述符号
    except OSError:
        os.close(当前描述符号)
        return 2, -1
    return 0, 当前描述符号


def 存正文(仓根, 正文内容字节: bytes) -> tuple:
    """内容寻址存一份正文（**须持 `锁快照`**）⇒ `(件路径, 是否本次新建)`。
    **dirfd 逐段**建/开目录（不跟任何段 symlink ⇒ 防父目录写穿）；目标位 `O_EXCL` 建、已有核 sha 复用；
    同名件内容不符 ⇒ 拒（不覆盖）；临时名 + 同目录 `os.replace`（原子）。"""
    目录路径 = 快照目录(仓根)
    退出码, 目录描述符号 = 建目录链(目录路径)
    if 退出码 != 0:
        raise 快照写不动("快照目录不安全（父目录链含 symlink / 非目录）⇒ 拒写：%s" % 目录路径)
    try:
        实算内容指纹 = hashlib.sha256(正文内容字节).hexdigest()
        件基名 = 实算内容指纹 + 快照件后缀
        件路径 = 目录路径 / 件基名
        try:
            已有描述符号 = os.open(件基名, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=目录描述符号)
        except FileNotFoundError:
            已有描述符号 = -1
        except OSError as 错误:
            raise 快照写不动("同名位不可安全核（疑似 symlink）⇒ 拒：%s" % 错误) from 错误
        if 已有描述符号 >= 0:
            try:
                摘要器 = hashlib.sha256()
                while True:
                    读块字节 = os.read(已有描述符号, 分块字节)
                    if not 读块字节:
                        break
                    摘要器.update(读块字节)
            finally:
                os.close(已有描述符号)
            if 摘要器.hexdigest() == 实算内容指纹:
                return str(件路径), False
            raise 快照写不动("同名件内容与 sha 不符（疑似篡改）⇒ 拒覆盖：%s" % 件路径)
        临时基名 = 实算内容指纹 + ".临时"
        try:
            件描述符号 = os.open(临时基名,
                            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                            0o644, dir_fd=目录描述符号)
        except FileExistsError:
            # 持全局共锁写 ⇒ 同处遇旧 `.临时` = 上游中断残留 ⇒ 清掉重试一次（不冒充事务原子）
            try:
                os.unlink(临时基名, dir_fd=目录描述符号)
            except OSError:
                pass
            件描述符号 = os.open(临时基名,
                            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                            0o644, dir_fd=目录描述符号)
        except OSError as 错误:
            raise 快照写不动("临时件建不动：%s" % 错误) from 错误
        try:
            os.write(件描述符号, 正文内容字节)
            os.fsync(件描述符号)
        finally:
            os.close(件描述符号)
        os.replace(临时基名, 件基名, src_dir_fd=目录描述符号, dst_dir_fd=目录描述符号)
        return str(件路径), True
    finally:
        os.close(目录描述符号)


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
    **dirfd 逐段**开目录（不跟任何段 symlink ⇒ 不越根删）；**不冒充事务原子**：只收孤儿。"""
    目录路径 = 快照目录(仓根)
    退出码, 目录描述符号 = 建目录链(目录路径)
    if 退出码 != 0:
        return []
    已引用件集 = {数据行[0] for 数据行 in 连接.execute(
        "select distinct 快照路径 from 反馈来源 where 快照路径 is not null")}
    已删件表 = []
    try:
        for 基名 in sorted(os.listdir(目录描述符号)):
            if 基名 == 快照锁名:
                continue
            if 基名.endswith(".临时") or str(目录路径 / 基名) not in 已引用件集:
                try:
                    os.unlink(基名, dir_fd=目录描述符号)
                    已删件表.append(str(目录路径 / 基名))
                except OSError:
                    pass
    finally:
        os.close(目录描述符号)
    return 已删件表


def 读快照(连接, 来源号: int) -> tuple:
    """来源号 ⇒ `(状态, 报告文本)`：优先内容寻址快照（**同一描述符读 + 回传字节 sha 校验**，
    无「先核后开」TOCTOU）；缺失 / 不符 ⇒ 显式待核；再回退原 `报告路径`（同法）。**有界**，超上限 ⇒ 待核。"""
    来源行 = 连接.execute("select 快照路径, 报告路径, 内容指纹 "
                     "from 反馈来源 where 来源号 = ?", (来源号,)).fetchone()
    if not 来源行:
        return 快照状态_缺失, ""
    期望内容指纹 = 来源行["内容指纹"]
    快照件路径 = 来源行["快照路径"]
    for 候选路径, 命中状态 in ((快照件路径, 快照状态_有),
                          (来源行["报告路径"], 快照状态_原路径)):
        if not 候选路径:
            continue
        退出码, 字节值 = 读全件(候选路径, 正文字节上限)
        if 退出码 != 0:
            continue
        if hashlib.sha256(字节值).hexdigest() != 期望内容指纹:
            continue
        return 命中状态, 字节值.decode("utf-8", "replace")
    return (快照状态_缺失 if 快照件路径 else 快照状态_无), ""
