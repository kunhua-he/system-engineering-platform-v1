# -*- coding: utf-8 -*-
"""合主干编排 —— 合并主干.py 的实现：五步把一条已释放/待合并的腿合进主干。

① 校验（入参 / 账本状态 / 腿树闸0绿）
② 建隔离集成树 + 合腿 + 源库按主键逻辑重放（解二进制冲突）
③ 集成树跑 闸0 + 判据自测 + 全案例（与 pre-commit 同口径，不降 5 秒硬顶）
④ 绿后推进主干（ff-only 优先，附 tree 相等核验 + 三方一致复核）
⑤ 显式同步主目录工作区/index 并复核三方一致；清集成树；推送（仅显式）

默认**不推远端**；远端动作须显式 `推送=真`。
"""

import fcntl as 文件锁
import json
import traceback
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from .合主干有界跑 import 干净环境, 跑有界命令, 命令记录
from .合主干源库重放 import 合并三方库, 重放动作表
from . import 合主干集成树 as 集成

开工号形状 = re.compile(r"v1-[0-9]{6}")
库相对路径 = "开发工具/信息核心/信息核心.db"
可合并状态 = ("已提交待合并", "已释放")
闸门说明 = "闸0 + 判据自测 + 全案例"
案例命令 = ". ./构建环境/进入.sh >/dev/null 2>&1 || exit 1; cargo run --quiet --locked -p v1-case-runner"


def _读开工记录(仓根, 开工号):
    sys.path.insert(0, str(Path(仓根) / "开发工具" / "MCP服务"))
    from 开工账本 import 连账本, 读开工
    连接 = 连账本()
    try:
        return 读开工(连接, 开工号)
    finally:
        连接.close()


def _钩子路径(工作树):
    _, 输出文本, _ = 跑有界命令(["git", "rev-parse", "--git-path", "hooks/pre-commit"], 工作目录=工作树)
    路径 = Path(输出文本.strip())
    if not 路径.is_absolute():
        路径 = Path(工作树) / 路径
    return 路径


def _临时库(名字前缀) -> str:
    句柄, 路径 = tempfile.mkstemp(prefix=名字前缀, suffix=".db")
    os.close(句柄)
    return 路径


def _导出库(仓根, 引用, 目标路径) -> int:
    """把某引用的源库导出成临时件（二进制，不经文本）⇒ 退出码。"""
    with open(目标路径, "wb") as 文件句柄, tempfile.TemporaryFile() as 标准错误件:
        try:
            回执 = subprocess.run(["git", "show", "%s:%s" % (引用, 库相对路径)],
                cwd=str(仓根), stdout=文件句柄, stderr=标准错误件,
                env=干净环境(), timeout=5)
            退出码 = 回执.returncode
        except subprocess.TimeoutExpired:
            退出码 = -1
        标准错误件.seek(0)
        输出文本 = 标准错误件.read().decode("utf-8", errors="replace")
    句柄, 日志路径 = tempfile.mkstemp(prefix="v1_合主干导库_", suffix=".log")
    with os.fdopen(句柄, "w", encoding="utf-8") as 日志件:
        日志件.write("② 导出源库 %s · 退出码 %d · 是否超时 %s\n%s" % (引用, 退出码, 退出码 == -1, 输出文本))
    if 命令记录.get() is not None:
        命令记录.get().append((退出码, 输出文本[:1500], 日志路径))
    return 退出码



def _重放源库(仓根, 集成路径, 腿分支) -> tuple:
    """源库按主键三方**正式重放** ⇒ (退出码, 行表)。新建 / 恢复两路共用这一份 —— 恢复不再静默跳过。

    重放后逐条**核验**腿侧动作真落库（读库比对）；缺 ⇒ **显式拒**（不静默跳过丢动作）。
    """
    from . import 集成接管
    行表 = []
    _, 合并基, _ = 跑有界命令(["git", "merge-base", "主干", 腿分支], 工作目录=仓根)
    合并基 = 合并基.strip()
    基库, 腿库, 主干库 = _临时库("v1基库_"), _临时库("v1腿库_"), _临时库("v1主干库_")
    try:
        for 引用, 路径 in ((合并基, 基库), (腿分支, 腿库), ("主干", 主干库)):
            if _导出库(仓根, 引用, 路径) != 0:
                return 1, 行表 + ["   源库导出失败：%s" % 引用]
        动作表, 冲突表, 跳过表 = 合并三方库(基库, 腿库, 主干库, 集成路径)
        行表.append("   源库三方重放：动作 %d 条 · 冲突 %d 条 · 跳过 %d 条（合并基 %s）"
                  % (len(动作表), len(冲突表), len(跳过表), 合并基[:8]))
        if 冲突表:
            return 1, 行表 + _报冲突(冲突表)
        退出码, 重放行表 = 重放动作表(集成路径, 动作表, 主干库)
        for 重放行 in 重放行表:
            行表.append("   " + 重放行)
        if 退出码 != 0:
            return 1, 行表
        if 跳过表:
            行表.append("   （跳过 %d 条：源件权威，建库 重抽）" % len(跳过表))
        核验码, 核验行表 = 集成接管.核验重放(集成路径, 动作表)
        行表.extend(核验行表)
        if 核验码 != 0:
            return 1, 行表
        if 动作表:
            退出码, 输出文本, _ = 跑有界命令(["git", "add", 库相对路径], 工作目录=集成路径)
            if 退出码 != 0:
                return 1, 行表 + ["   源库 git add（标记已解决）失败：%s" % 输出文本.strip()[-300:]]
            行表.append("   源库已标为已解决（git add）")
        return 0, 行表
    finally:
        for 路径 in (基库, 腿库, 主干库):
            try:
                os.unlink(路径)
            except OSError:
                pass


def _跑集成门禁(集成树) -> tuple:
    """③ 在集成树跑闸0 + 判据自测 + 全案例（与 pre-commit 同口径）⇒ (退出码, 行表, 尾部输出)。"""
    钩子 = _钩子路径(集成树)
    if 钩子.is_file() and os.access(钩子, os.X_OK):
        退出码, 输出文本, 日志路径 = 跑有界命令(["git", "hook", "run", "pre-commit"], 工作目录=集成树,
                          超时秒数=None, 保留日志=True)
        return 退出码, ["③ 提交门禁（git hook run pre-commit · 与 pre-commit 同口径：%s）退出码 %d · 日志 %s"
                  % (闸门说明, 退出码, 日志路径)], 输出文本
    行表 = ["③ 提交门禁钩子不在 ⇒ 直接跑三条（%s）" % 闸门说明]
    退出码0, 输出0, 日志0 = 跑有界命令([sys.executable, "构建装配/一键验证/闸0.py"], 工作目录=集成树,
                         超时秒数=5, 保留日志=True)
    if 退出码0 != 0:
        return 退出码0, 行表 + ["闸0 不过（退出码 %d）· 日志 %s" % (退出码0, 日志0)], 输出0
    退出码1, 输出1, 日志1 = 跑有界命令([sys.executable, "构建装配/一键验证/一键验证.py", "--自测"],
                         工作目录=集成树, 超时秒数=None, 保留日志=True)
    if 退出码1 != 0:
        return 退出码1, 行表 + ["判据自测 不过（退出码 %d）· 日志 %s" % (退出码1, 日志1)], 输出1
    退出码2, 输出2, 日志2 = 跑有界命令(["sh", "-c", 案例命令], 工作目录=集成树, 超时秒数=None, 保留日志=True)
    return 退出码2, 行表 + ["闸0 绿 · 日志 %s；判据自测 绿 · 日志 %s；全案例 退出码 %d · 日志 %s"
                      % (日志0, 日志1, 退出码2, 日志2)], 输出2


def _报冲突(冲突表) -> list:
    行表 = ["② ★ 源库冲突（两腿各改同一主键且不同）⇒ 拒绝并留双方值交人裁："]
    for 冲突 in 冲突表:
        行表.append("   %s 主键 %r" % (冲突["表"], 冲突["键"]))
        行表.append("     合并基：%r" % (冲突["基值"],))
        行表.append("     腿：%r" % (冲突["腿值"],))
        行表.append("     主干：%r" % (冲突["主干值"],))
    return 行表


def _派发(开工号, 推送, 仓根, 恢复, 阶段记录) -> tuple:
    """`合并主干.py` 的入口 ⇒ (退出码, 报告文本)。"""
    仓根 = Path(仓根).resolve()
    开工号 = (开工号 or "").strip()
    if not isinstance(推送, bool):
        return 2, "入参：推送 要是逻辑型（真/假）"
    if not 开工号形状.fullmatch(开工号):
        return 2, "入参：开工ID 必填，形状 `v1-` 加六位数字；收到 %r" % 开工号
    行表 = ["合并主干 —— 开工号 %s" % 开工号]
    集成路径 = ""
    临时库表 = []          # 源库临时件已挪进 `_重放源库` 自管自清 ⇒ 这里保持空表（finally 结构不动）
    try:
        开工记录 = _读开工记录(仓根, 开工号)
        if not 开工记录:
            return 1, "\n".join(行表 + ["① 校验：账本里没有这条开工：%s" % 开工号])
        状态 = 开工记录["状态"]
        if 状态 not in 可合并状态:
            return 1, "\n".join(行表 + ["① 校验：状态是「%s」⇒ 只合并「%s」"
                                     % (状态, " / ".join(可合并状态))])
        腿树 = Path(开工记录["工作树"])
        if not 腿树.is_dir():
            return 1, "\n".join(行表 + ["① 校验：腿树不在：%s" % 腿树])
        腿分支 = 开工记录["分支名"]
        退出码, 定位 = 集成.定位主仓(腿树)
        if 退出码 != 0 or 定位 != 仓根:
            return 1, "① 腿树不属于目标主仓：%s（%s）" % (腿树, 定位)
        退出码, 输出文本, 日志路径 = 跑有界命令([sys.executable, "构建装配/一键验证/闸0.py"], 工作目录=腿树,
                         超时秒数=5, 保留日志=True)
        if 退出码 != 0:
            return 1, "\n".join(行表 + ["① 校验：腿树闸0 不过（退出码 %d）· 日志 %s" % (退出码, 日志路径),
                                     输出文本[:1500]])
        行表.append("① 校验：状态「%s」· 腿树 %s · 腿树闸0 绿 · 日志 %s" % (状态, 腿树, 日志路径))

        阶段记录[0] = "② 集成合腿与源库重放"
        if 恢复:
            集成路径 = str(集成.找集成树(仓根, 开工号) or "")
            if not 集成路径:
                return 1, "② 恢复：没有已知集成现场"
            from . import 集成接管
            暂存码, 暂存行表 = 集成接管.暂存接管成果(仓根, 集成路径)
            行表.extend(暂存行表)
            if 暂存码 != 0:
                return 1, "\n".join(行表)
            退出码, 输出文本, 日志路径 = 跑有界命令(["git", "diff", "--name-only", "--diff-filter=U"], 集成路径, 超时秒数=5)
            if 退出码 != 0 or 输出文本.strip():
                return 1, "② 恢复：仍有未解决冲突，不自动解冲突 · 日志 %s\n%s" % (日志路径, 输出文本)
            行表.append("② 恢复已知现场 %s（分支 集成/%s）；冲突已按接管开工的改动暂存" % (集成路径, 开工号))
        else:
            退出码, 集成路径 = 集成.建集成树(仓根, 开工号)
            if 退出码 != 0:
                行表.append("② 建集成树失败：%s" % 集成路径)
                集成路径 = ""
                return 1, "\n".join(行表)
            行表.append("② 集成树 %s（分支 集成/%s，从主干建）" % (集成路径, 开工号))
            退出码, 说明, 冲突文件表 = 集成.合腿(集成路径, 腿分支)
            行表.append("   合腿 %s：%s" % (腿分支, 说明))
            if 退出码 != 0:
                return 1, "\n".join(行表)
        # 源库按主键逻辑三方**正式重放**：两路（新建 / 恢复）**共用同一份实现** —— 恢复不再静默跳过、
        # 不丢腿侧动作；重放后逐条核验真落库（缺 ⇒ 显式拒，见 `集成接管.核验重放`）。
        重放码, 重放行表 = _重放源库(仓根, 集成路径, 腿分支)
        行表.extend(重放行表)
        别处冲突 = [] if 恢复 else [路径 for 路径 in 冲突文件表 if 路径 != 库相对路径]
        if 别处冲突:
            return 1, "\n".join(行表 + [
                "   ★ 代码冲突（非源库）⇒ 交人裁：%s" % " · ".join(别处冲突),
                "   入口：`v1_task 操作=接管集成 开工ID=%s` 正式接管集成树后用 `v1_edit` 解冲突，"
                "再 `合并主干.py %s --恢复现场`。" % (开工号, 开工号)])
        if 重放码 != 0:
            return 1, "\n".join(行表)
    
        阶段记录[0] = "③ 集成验证"
        退出码, 门禁行表, 尾部 = _跑集成门禁(集成路径)
        行表.extend(门禁行表)
        if 退出码 != 0:
            return 1, "\n".join(行表 + [尾部[:1500]])
        退出码, _, _ = 跑有界命令(["git", "rev-parse", "--verify", "MERGE_HEAD"], 集成路径, 超时秒数=5)
        if 退出码 == 0:
            退出码, 说明 = 集成.提交合并(集成路径, 腿分支, 开工号)
        elif 恢复:
            退出码, _, _ = 跑有界命令(["git", "merge-base", "--is-ancestor", 腿分支, "HEAD"], 集成路径, 超时秒数=5)
            说明 = "恢复现场已有提交；腿分支祖先核验退出码 %d" % 退出码
        else:
            说明 = "集成现场无 MERGE_HEAD，拒绝提交"
        if 退出码 != 0:
            return 1, "\n".join(行表 + ["   " + 说明])
        _, 集成提交, _ = 跑有界命令(["git", "rev-parse", "HEAD"], 工作目录=集成路径)
        集成提交 = 集成提交.strip()
        行表.append("   合并提交 %s" % 集成提交[:12])

        阶段记录[0] = "④ 推进主干"
        _, 同步前提交, _ = 跑有界命令(["git", "rev-parse", "主干"], 仓根, 超时秒数=5)
        同步前提交 = 同步前提交.strip()
        _, 元目录, _ = 跑有界命令(["git", "rev-parse", "--absolute-git-dir"], 集成路径, 超时秒数=5)
        同步记录件 = Path(元目录.strip()) / "同步前提交"
        已推进 = 恢复 and 同步前提交 == 集成提交
        if 已推进:
            if not 同步记录件.is_file():
                return 1, "④ 恢复：同步旧基准未记录，拒绝猜测或覆盖"
            同步前提交 = 同步记录件.read_text(encoding="utf-8").strip()
        退出码, 说明 = 集成.核工作文件(仓根, 同步前提交)
        if 退出码 != 0:
            return 1, "④ 推进前同步保护拒绝：" + 说明
        退出码, 说明 = 集成.核主索引(仓根, 同步前提交)
        if 退出码 != 0:
            return 1, "④ 推进前同步保护拒绝：" + 说明
        if 已推进:
            行表.append("④ 已推进到此集成提交，按记录的旧基准恢复同步")
        else:
            同步记录件.write_text(同步前提交, encoding="utf-8")
            退出码, 说明 = 集成.推进主干(仓根, 集成提交, 集成路径)
            行表.append("④ 推进主干：%s" % 说明)
            if 退出码 != 0:
                return 1, "\n".join(行表)
        阶段记录[0] = "⑤ 同步主目录"
        退出码, 说明 = 集成.同步主工作区(仓根, 同步前提交)
        行表.append("⑤ 同步主工作区：%s" % 说明)
        if 退出码 != 0:
            return 1, "\n".join(行表)

        if 推送:
            退出码, 输出文本, _ = 跑有界命令(["git", "push", "origin", "主干"], 工作目录=仓根, 超时秒数=None)
            if 退出码 != 0:
                return 1, "\n".join(行表 + ["⑤ 推送 origin/主干 失败：%s" % 输出文本.strip()[-400:]])
            行表.append("⑤ 已推 origin/主干")
        else:
            行表.append("⑤ 未推远端（推送=false；远端动作须显式）")
        行表.append("结果：成功 —— 主干 %s" % 集成提交[:12])
        return 0, "\n".join(行表)
    finally:
        for 路径 in 临时库表:
            try:
                os.unlink(路径)
            except OSError:
                pass



def 派发(开工号, 推送, 仓根, 操作="合并"):
    """唯一编排入口：公共主仓定位、非阻塞跨进程互斥、原始读数与现场。"""
    退出码, 定位 = 集成.定位主仓(仓根)
    if 退出码 != 0:
        return 退出码, str(定位)
    仓根 = 定位
    if not 开工号形状.fullmatch(开工号 or "") or 操作 not in ("合并", "查看现场", "恢复现场", "清理现场"):
        return 2, "开工号或现场操作不合法"
    with open(仓根 / ".git" / "合主干.lock", "a+") as 文件句柄:
        try:
            文件锁.flock(文件句柄, 文件锁.LOCK_EX | 文件锁.LOCK_NB)
        except BlockingIOError:
            return 1, "主仓合并忙，快速拒绝：%s（未等待互斥锁）" % 仓根
        记录表 = []
        记录令牌 = 命令记录.set(记录表)
        阶段记录 = ["① 校验"]
        try:
            已有树 = 集成.找集成树(仓根, 开工号)
            if 操作 == "查看现场":
                if not 已有树:
                    return 1, "主仓 %s · 没有已知现场：%s" % (仓根, 开工号)
                退出码, 输出文本, 日志路径 = 跑有界命令(["git", "status", "--porcelain", "-uall"], 已有树, 超时秒数=5)
                _, 元目录, _ = 跑有界命令(["git", "rev-parse", "--absolute-git-dir"], 已有树, 超时秒数=5)
                报告定位 = Path(元目录.strip()) / "合并报告路径"
                说明 = 报告定位.read_text(encoding="utf-8") if 报告定位.is_file() else "原报告未登记"
                return 退出码, "主仓 %s · 现场 %s · 日志 %s · 原完整报告 %s\n%s" % (仓根, 已有树, 日志路径, 说明, 输出文本)
            if 操作 == "清理现场":
                if not 已有树:
                    return 1, "没有已知现场，不清未知目录"
                return 集成.清集成树(仓根, 已有树, 开工号)
            try:
                退出码, 输出文本 = _派发(开工号, 推送, 仓根, 操作 == "恢复现场", 阶段记录)
            except Exception:
                退出码, 输出文本 = 1, traceback.format_exc()
            行表 = ["主仓目标 %s · 阶段 %s · 编排退出码 %d" % (仓根, 阶段记录[0], 退出码), 输出文本]
            if 退出码 != 0:
                for 回执码, 首部, 日志路径 in [读数 for 读数 in 记录表 if 读数[0] != 0][:20]:
                    行表.append("原始命令退出码 %d · 是否超时 %s · 完整日志 %s\n%s" % (回执码, 回执码 == -1, 日志路径, 首部))
            已有树 = 集成.找集成树(仓根, 开工号)
            if 已有树 and 退出码 == 0:
                清理码, 说明 = 集成.清集成树(仓根, 已有树, 开工号)
                行表.append(说明)
                if 清理码 != 0:
                    退出码 = 1
                else:
                    from . import 集成接管
                    解除码, 解除说明 = 集成接管.解除接管(已有树)
                    行表.append(解除说明)
                    if 解除码 != 0:
                        退出码 = 1
            if 已有树 and 退出码 != 0:
                行表.append("失败现场保留：%s（同开工只留这一棵，不自动覆盖）" % 已有树)
                行表.append("入口：合并主干.py %s --查看现场 / --恢复现场 / --清理现场；清理仅接受干净且已入主干的现场" % 开工号)
            句柄, 日志路径 = tempfile.mkstemp(prefix="v1_合主干报告_", suffix=".log")
            with os.fdopen(句柄, "w", encoding="utf-8") as 报告件:
                报告件.write("\n".join(行表))
                报告件.write("\n全部命令原始记录\n" + json.dumps(记录表, ensure_ascii=False, indent=2))
            if 已有树 and 退出码 != 0:
                _, 元目录, _ = 跑有界命令(["git", "rev-parse", "--absolute-git-dir"], 已有树, 超时秒数=5)
                (Path(元目录.strip()) / "合并报告路径").write_text(日志路径, encoding="utf-8")
            return 退出码, "\n".join(行表 + ["完整报告日志 %s" % 日志路径])
        finally:
            命令记录.reset(记录令牌)
            文件锁.flock(文件句柄, 文件锁.LOCK_UN)
