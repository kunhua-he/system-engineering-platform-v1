# -*- coding: utf-8 -*-
"""合主干集成树 —— 从主干建隔离集成工作树、合腿、提交合并、推进主干、同步主工作区。

集成树落在**系统临时目录**（仓外）⇒ 全仓扫描看不见它（同并行工作树落仓外的理由），
且**不在仓内自建以「系统工程平台V1」开头的目录名**（那会踩判据 ㉕）。
"""

import shutil
import tempfile
from pathlib import Path

from 合主干有界跑 import 跑有界命令


def _跑(命令表, 工作目录, 超时秒数=None, 输入文本=None):
    return 跑有界命令(命令表, 工作目录=工作目录, 超时秒数=超时秒数, 输入文本=输入文本)


def 建集成树(仓根, 开工号) -> tuple:
    """从主干建隔离集成工作树 ⇒ (退出码, 路径 或 说明)。"""
    路径 = tempfile.mkdtemp(prefix="v1集成-")
    分支 = "集成/" + 开工号
    退出码, 输出文本, _ = _跑(["git", "worktree", "add", "-b", 分支, 路径, "主干"], 工作目录=仓根, 超时秒数=None)
    if 退出码 != 0:
        shutil.rmtree(路径, ignore_errors=True)
        return 退出码, "建集成树失败：%s" % 输出文本.strip()[-500:]
    return 0, 路径


def 合腿(集成树, 腿分支) -> tuple:
    """在集成树里合腿 ⇒ (退出码, 说明, 冲突文件表)。--no-ff 保证造合并提交（不走 ff）。"""
    退出码, 输出文本, _ = _跑(["git", "merge", "--no-commit", "--no-ff", 腿分支], 工作目录=集成树, 超时秒数=None)
    _, 输出2, _ = _跑(["git", "diff", "--name-only", "--diff-filter=U"], 工作目录=集成树)
    冲突表 = [数据行.strip() for 数据行 in 输出2.splitlines() if 数据行.strip()]
    if 冲突表:
        return 0, "合腿有冲突（源库交重放解；其余交人裁）", 冲突表
    if 退出码 != 0:
        return 退出码, "合腿失败：%s" % 输出文本.strip()[-500:], []
    return 0, "合腿干净（无冲突）", []


def 提交合并(集成树, 腿分支, 开工号) -> tuple:
    """提交集成树的合并 ⇒ (退出码, 说明)。--no-verify：闸已由编排以同一份钩子代码跑过，不重复。"""
    提交信息 = "合并 %s 进主干（隔离集成校验通过）\n\n开工号 %s\n" % (腿分支, 开工号)
    退出码, 输出文本, _ = _跑(["git", "commit", "--no-verify", "-F", "-"],
                 工作目录=集成树, 超时秒数=None, 输入文本=提交信息)
    if 退出码 != 0:
        return 退出码, "提交合并失败：%s" % 输出文本.strip()[-500:]
    return 0, "合并提交已造"


def 推进主干(仓根, 集成提交, 集成树) -> tuple:
    """优先 ff-only；附 tree 相等核验与三方一致复核 ⇒ (退出码, 说明)。"""
    _, 旧提交, _ = _跑(["git", "rev-parse", "主干"], 工作目录=仓根)
    旧提交 = 旧提交.strip()
    _, 提交树, _ = _跑(["git", "rev-parse", "%s^{tree}" % 集成提交], 工作目录=仓根)
    _, 索引树, _ = _跑(["git", "write-tree"], 工作目录=集成树)
    if 提交树.strip() != 索引树.strip():
        return 1, "集成树 index 与提交树不等（%s ≠ %s）⇒ 拒绝推进" % (索引树.strip(), 提交树.strip())
    _, 头提交, _ = _跑(["git", "rev-parse", "HEAD"], 工作目录=集成树)
    if 头提交.strip() != 集成提交:
        return 1, "集成树 HEAD %s ≠ 集成提交 %s ⇒ 拒绝推进" % (头提交.strip(), 集成提交)
    _, 脏输出, _ = _跑(["git", "status", "--porcelain", "-uall"], 工作目录=集成树)
    if 脏输出.strip():
        return 1, "集成树有未提交改动 ⇒ 拒绝推进：%s" % 脏输出.strip()[-300:]
    退出码, _, _ = _跑(["git", "merge-base", "--is-ancestor", 旧提交, 集成提交], 工作目录=仓根)
    if 退出码 != 0:
        return 1, "主干 %s 不是集成提交 %s 的祖先 ⇒ 非 ff，拒绝" % (旧提交, 集成提交)
    临时树 = tempfile.mkdtemp(prefix="v1主干-")
    shutil.rmtree(临时树, ignore_errors=True)
    退出码, 输出文本, _ = _跑(["git", "worktree", "add", 临时树, "主干"], 工作目录=仓根, 超时秒数=None)
    if 退出码 == 0:
        退出码2, 输出2, _ = _跑(["git", "merge", "--ff-only", 集成提交], 工作目录=临时树, 超时秒数=None)
        _跑(["git", "worktree", "remove", "--force", 临时树], 工作目录=仓根, 超时秒数=None)
        shutil.rmtree(临时树, ignore_errors=True)
        if 退出码2 != 0:
            return 退出码2, "ff-only 推进失败：%s" % 输出2.strip()[-400:]
        说明 = "ff-only（临时工作树 + merge --ff-only）"
    else:
        shutil.rmtree(临时树, ignore_errors=True)
        退出码3, 输出3, _ = _跑(["git", "update-ref", "refs/heads/主干", 集成提交, 旧提交], 工作目录=仓根)
        if 退出码3 != 0:
            return 退出码3, "update-ref 推进失败：%s" % 输出3.strip()[-400:]
        说明 = "update-ref（已附 tree 相等核验 + 三方一致复核 + 祖先核验）"
    _, 新提交, _ = _跑(["git", "rev-parse", "主干"], 工作目录=仓根)
    if 新提交.strip() != 集成提交:
        return 1, "推进后主干 %s ≠ 集成提交 %s ⇒ 异常" % (新提交.strip(), 集成提交)
    return 0, "主干 %s → %s（%s）" % (旧提交[:8], 集成提交[:8], 说明)


def 同步主工作区(主目录) -> tuple:
    """显式 --git-dir/--work-tree 把主目录工作区与 index 同步到主干 ⇒ (退出码, 说明)。"""
    元目录 = Path(主目录) / ".git"
    命令头 = ["git", "--git-dir", str(元目录), "--work-tree", str(主目录)]
    退出码, 输出文本, _ = _跑(命令头 + ["status", "--porcelain", "-uall"], 工作目录=主目录)
    if 退出码 != 0:
        return 退出码, "读主目录状态失败：%s" % 输出文本.strip()[-300:]
    已改 = [数据行 for 数据行 in 输出文本.splitlines() if 数据行.strip() and not 数据行.startswith("??")]
    if 已改:
        return 1, ("主目录有未提交的**已跟踪**改动 ⇒ 拒绝强制同步（不覆盖）：\n%s"
                 % "\n".join("    " + 数据行 for 数据行 in 已改[:20]))
    退出码, 输出文本, _ = _跑(命令头 + ["reset", "--hard", "主干"], 工作目录=主目录, 超时秒数=None)
    if 退出码 != 0:
        return 退出码, "同步主工作区失败：%s" % 输出文本.strip()[-400:]
    _, 头提交, _ = _跑(命令头 + ["rev-parse", "HEAD"], 工作目录=主目录)
    _, 索引, _ = _跑(命令头 + ["write-tree"], 工作目录=主目录)
    _, 提交树, _ = _跑(命令头 + ["rev-parse", "HEAD^{tree}"], 工作目录=主目录)
    _, 脏输出, _ = _跑(命令头 + ["status", "--porcelain", "-uall"], 工作目录=主目录)
    遗留 = [数据行 for 数据行 in 脏输出.splitlines() if 数据行.strip() and not 数据行.startswith("??")]
    if 遗留 or 索引.strip() != 提交树.strip():
        return 1, "同步后仍不一致（index %s ≠ HEAD 树 %s；遗留 %s）" % (
            索引.strip(), 提交树.strip(), 遗留[:5])
    return 0, "主目录 HEAD %s · index == HEAD 树 · 工作盘已跟踪件干净（三方一致）" % 头提交.strip()[:8]


def 清集成树(仓根, 集成树, 开工号) -> tuple:
    """移除集成工作树 + 删集成分支（幂等）⇒ (退出码, 说明)。"""
    if Path(集成树).is_dir():
        _跑(["git", "worktree", "remove", "--force", str(集成树)], 工作目录=仓根, 超时秒数=None)
        shutil.rmtree(集成树, ignore_errors=True)
    _跑(["git", "branch", "-D", "集成/" + 开工号], 工作目录=仓根)
    return 0, "集成树与集成分支已清"
