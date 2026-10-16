# -*- coding: utf-8 -*-
"""恢复主目录编排 —— 主目录未提交漂移的**最小正式恢复口**（只复原 tracked 件，不碰未跟踪件）。

**给谁用**：主目录 tracked 工作区与主干提交不等时，`合并主干` 的「同步保护」按设计 fail-closed
拒 ⇒ 正常合并无法推进。本口在**明确授权范围**内，把**已完整保全**的 tracked 件从**固定提交的
Git 对象**复原，使主目录重回主干权威；未跟踪件与用户目录**原样保留**。

**四条硬边界**（全批先验；任一不过 ⇒ 一个字节都不写）：
  ① 主目录**只由公共 Git 元目录解析**（`合主干集成树.定位主仓`）——**不接任意路径输入**；
  ② `预期提交` 必须等于主目录当前 `主干` HEAD（HEAD 变了 ⇒ 拒）；
  ③ 主目录 index 必须 == `预期提交` 树，且盘上 tracked 漂移集**逐件等于** `拟恢复文件表`
     （多一件未知 tracked 差异 ⇒ 拒）；有并发写（忙锁）即拒；
  ④ 每件盘上当前 blob == `拟恢复文件表.当前指纹`、目标 blob == `预期提交:路径` 的 blob，
     `保全位置` 存在且逐件 sha256 与盘上现量一致（保全覆盖当前漂移态）。

**不做**：clean / reset / 删树 / 移走未知件 / 改 config / 改 hooks。源码与二进制一律从固定提交的
Git 对象读。写盘逐件**原子**（临时件 + `os.replace`）；中途失败**如实报**已恢复与未恢复，不假全成。
本口**仅此一次**受控操作，用于把已被工具带偏的主目录复原，不替代正常合并与各腿独立验收。
"""

import fcntl as 文件锁
import hashlib
import os
import subprocess
from pathlib import Path

from . import 仓操作
from . import 合主干集成树 as 集成
from .合主干有界跑 import 干净环境

锁定文件 = "合主干.lock"
超时秒数 = 5
记录目录 = "记录"
副本目录 = "原文件"
清单文件 = "manifest.tsv"
写盘后缀 = ".v1恢复-tmp"


def _前缀(主目录):
    """主目录若为 bare（`core.bare=true`）⇒ git 必须显式给 `--git-dir` / `--work-tree`；两形态走同一前缀。"""
    return ["git", "--git-dir", str(Path(主目录) / ".git"), "--work-tree", str(主目录)]


def 算指纹值(文件字节):
    """git blob 对象号：`sha1(blob头部 NUL 分隔 + 字节)`。"""
    return hashlib.sha1(b"blob %d\0" % len(文件字节) + 文件字节).hexdigest()


def 取对象字节(主目录, 指纹值):
    """从 Git 对象库读**原始字节**（二进制源库也走这里）⇒ 读不出给 `None`。"""
    try:
        回执 = subprocess.run(_前缀(主目录) + ["cat-file", "blob", 指纹值],
                          cwd=str(主目录), capture_output=True, env=干净环境(), timeout=超时秒数)
    except (subprocess.TimeoutExpired, OSError):
        return None
    return 回执.stdout if 回执.returncode == 0 else None


def 读提交记录(主目录, 提交, 相对路径):
    """`提交:相对路径` 的 `(指纹值, 模式)`；读不出给空串。"""
    退出码, 输出文本 = 仓操作.跑命令(_前缀(主目录) + ["ls-tree", 提交, "--", 相对路径], 主目录)
    片段 = 输出文本.split() if 退出码 == 0 else []
    指纹值 = 片段[2] if len(片段) >= 3 else ""
    模式 = 片段[0] if len(片段) >= 3 else ""
    return 指纹值, 模式


def 读差集(主目录):
    """全量工作差集 ⇒ `(变更表, 未跟踪表, 错误)`（含未跟踪；一处解析）。"""
    退出码, 输出文本 = 仓操作.跑命令(_前缀(主目录) + ["status", "--porcelain", "-uall"], 主目录)
    if 退出码 != 0:
        return [], [], "git status 失败：%s" % 输出文本.strip()[-200:]
    变更表, 未跟踪表 = [], []
    for 数据行 in 输出文本.splitlines():
        if not 数据行.strip():
            continue
        标记, 路径 = 数据行[:2], 数据行[3:].strip().strip('"')
        if " -> " in 路径:
            路径 = 路径.split(" -> ")[-1].strip().strip('"')
        (未跟踪表 if 标记 == "??" else 变更表).append(路径)
    return 变更表, 未跟踪表, ""


def 核保全(保全位置, 盘上表):
    """保全证据目录必须**逐件**以 sha256 覆盖当前漂移态 ⇒ `(退出码, 说明)`。"""
    清单路径 = Path(保全位置) / 记录目录 / 清单文件
    if not 清单路径.is_file():
        return 3, "保全清单不在：%s" % 清单路径
    保全表 = {}
    for 数据行 in 清单路径.read_text(encoding="utf-8").splitlines():
        if not 数据行.strip():
            continue
        片段 = 数据行.split("\t")
        if len(片段) != 4:
            return 3, "保全清单形状不对：%r" % 数据行
        保全表[片段[3]] = 片段[0]
    for 路径, 校验值 in 盘上表.items():
        if 路径 not in 保全表:
            return 3, "保全清单里没有 `%s`" % 路径
        复制文件 = Path(保全位置) / 副本目录 / 路径
        if not 复制文件.is_file():
            return 3, "保全原件不在：%s" % 复制文件
        副本指纹 = hashlib.sha256(复制文件.read_bytes()).hexdigest()
        if 副本指纹 != 保全表[路径] or 副本指纹 != 校验值:
            return 3, "保全与盘上不一致：%s（保 %s · 档 %s · 盘 %s）" % (
                路径, 副本指纹[:12], 保全表[路径][:12], 校验值[:12])
    return 0, "保全 %d 件逐件 sha256 与盘上现量一致" % len(盘上表)


def 写件(件路径, 文件字节, 模式):
    """临时件 + `os.replace`（同目录原子）⇒ 错误说明（空 = 成功）。"""
    暂存文件 = 件路径.with_name(件路径.name + 写盘后缀)
    try:
        暂存文件.write_bytes(文件字节)
        os.chmod(暂存文件, 0o755 if 模式 == "100755" else 0o644)
        os.replace(暂存文件, 件路径)
    except OSError as 错误:
        暂存文件.unlink(missing_ok=True)
        return "写盘失败：%r" % (错误,)
    return ""


def 核验全批(主目录, 预期提交, 保全位置, 条目表):
    """全部前置核验 ⇒ `(0, 恢复计划)` 或 `(非0, 拒因文本)`；计划项 = `(路径, 目标指纹, 模式, 校验值)`。"""
    退出码, 输出文本 = 仓操作.跑命令(_前缀(主目录) + ["rev-parse", "主干"], 主目录)
    if 退出码 != 0:
        return 3, "读不出主干 HEAD：%s" % 输出文本.strip()[-200:]
    if 输出文本.strip() != 预期提交:
        return 3, "**拒**：主干 HEAD %s ≠ 预期提交 %s（HEAD 变了）" % (输出文本.strip()[:12], 预期提交[:12])
    退出码, 提交树 = 仓操作.跑命令(_前缀(主目录) + ["rev-parse", "%s^{tree}" % 预期提交], 主目录)
    if 退出码 != 0:
        return 3, "**拒**：预期提交读不出树：%s" % 提交树.strip()[-200:]
    退出码, 索引树 = 仓操作.跑命令(_前缀(主目录) + ["write-tree"], 主目录)
    if 退出码 != 0 or 索引树.strip() != 提交树.strip():
        return 3, "**拒**：主目录 index 与预期提交树不等（有并发写 / 暂存漂移）"
    变更表, _, 错误 = 读差集(主目录)
    if 错误:
        return 3, "**拒**：%s" % 错误
    恢复文件表 = {路径 for 路径, _, _ in 条目表}
    多余文件表 = sorted(路径 for 路径 in 变更表 if 路径 not in 恢复文件表)
    if 多余文件表:
        return 3, "**拒**：盘上还有未知 tracked 差异（不在拟恢复文件表里）：\n  %s" % " · ".join(多余文件表)
    缺件表 = sorted(路径 for 路径 in 恢复文件表 if 路径 not in 变更表)
    if 缺件表:
        return 3, "**拒**：拟恢复文件表里这些件盘上并没有漂移：\n  %s" % " · ".join(缺件表)
    恢复计划, 盘上表 = [], {}
    for 路径, 当前指纹, 目标指纹 in 条目表:
        件路径 = 主目录 / 路径
        if not 件路径.is_file():
            return 3, "**拒**：`%s` 盘上不是文件" % 路径
        盘上文件字节 = 件路径.read_bytes()
        实际指纹 = 算指纹值(盘上文件字节)
        if 实际指纹 != 当前指纹:
            return 3, "**拒**：`%s` 盘上 blob %s ≠ 拟定当前 %s" % (路径, 实际指纹, 当前指纹 or "（空）")
        提交指纹, 模式 = 读提交记录(主目录, 预期提交, 路径)
        if not 提交指纹 or 提交指纹 != 目标指纹:
            return 3, "**拒**：`%s` 提交里 blob %s ≠ 拟定目标 %s" % (
                路径, 提交指纹 or "（无）", 目标指纹 or "（空）")
        if 目标指纹 == 当前指纹:
            return 3, "**拒**：`%s` 目标与当前同 blob ⇒ 无需恢复" % 路径
        校验值 = hashlib.sha256(盘上文件字节).hexdigest()
        盘上表[路径] = 校验值
        恢复计划.append((路径, 目标指纹, 模式, 校验值))
    退出码, 说明 = 核保全(保全位置, 盘上表)
    if 退出码 != 0:
        return 退出码, "**拒**：%s" % 说明
    return 0, 恢复计划


def 派发(参数表, 仓根):
    """`恢复主目录` 的入口 ⇒ `(退出码, 输出文本)`。

    参数：`预期提交`（必填）· `保全位置`（必填）· `拟恢复文件表`（必填，逐件 `{路径, 当前指纹, 目标指纹}`）。
    """
    if not isinstance(参数表, dict):
        return 2, "`参数` 要是对象"
    预期提交 = str(参数表.get("预期提交") or "").strip()
    保全位置 = str(参数表.get("保全位置") or "").strip()
    拟恢复文件表 = 参数表.get("拟恢复文件表")
    if not 预期提交:
        return 2, "缺 `预期提交`（要复原到的固定提交）"
    if not 保全位置:
        return 2, "缺 `保全位置`（保全证据目录绝对路径）"
    if not isinstance(拟恢复文件表, list) or not 拟恢复文件表:
        return 2, "缺 `拟恢复文件表`（逐件 {路径, 当前指纹, 目标指纹}）"
    条目表 = []
    for 序号, 条目项 in enumerate(拟恢复文件表, 1):
        if not isinstance(条目项, dict):
            return 2, "拟恢复文件表第 %d 条要是对象" % 序号
        路径 = str(条目项.get("路径") or "").strip()
        if not 路径 or 路径.startswith("/") or ".." in Path(路径).parts:
            return 2, "拟恢复文件表第 %d 条 `路径` 只认仓内相对路径" % 序号
        条目表.append((路径, str(条目项.get("当前指纹") or "").strip(),
                   str(条目项.get("目标指纹") or "").strip()))
    退出码, 主目录 = 集成.定位主仓(仓根)
    if 退出码 != 0:
        return 退出码, "主目录定位失败：%s" % 主目录
    主目录 = Path(主目录)
    with open(主目录 / ".git" / 锁定文件, "a+") as 锁句柄:
        try:
            文件锁.flock(锁句柄, 文件锁.LOCK_EX | 文件锁.LOCK_NB)
        except BlockingIOError:
            return 1, "主仓恢复忙，快速拒绝：%s（已有并发写）" % 主目录
        try:
            return _核与恢复(主目录, 预期提交, 保全位置, 条目表)
        finally:
            文件锁.flock(锁句柄, 文件锁.LOCK_UN)


def _核与恢复(主目录, 预期提交, 保全位置, 条目表):
    """核验通过后逐件写盘；失败如实报「已恢复 / 未恢复」，不假全成。"""
    退出码, 恢复计划 = 核验全批(主目录, 预期提交, 保全位置, 条目表)
    if 退出码 != 0:
        return 退出码, "%s ⇒ 一个字节都没写" % 恢复计划
    _, 未跟踪表, _ = 读差集(主目录)
    完成表, 失败说明 = [], ""
    for 路径, 目标指纹, 模式, _ in 恢复计划:
        文件字节 = 取对象字节(主目录, 目标指纹)
        if 文件字节 is None:
            失败说明 = "`%s`：提交对象读不出 ⇒ 停" % 路径
            break
        错误 = 写件(主目录 / 路径, 文件字节, 模式)
        if 错误:
            失败说明 = "`%s`：%s" % (路径, 错误)
            break
        完成表.append(路径)
    退出码, 输出文本 = 仓操作.跑命令(_前缀(主目录) + ["status", "--porcelain", "-uall"], 主目录)
    未恢复文件表 = [数据行 for 数据行 in 输出文本.splitlines()
             if 数据行.strip() and not 数据行.startswith("??")]
    行表 = ["主目录 %s · 预期提交 %s" % (主目录, 预期提交[:12]),
          "已恢复 %d/%d 件：%s" % (len(完成表), len(恢复计划), " · ".join(完成表) or "（无）"),
          "未跟踪件保留 %d 件（原样不动）：%s" % (len(未跟踪表), " · ".join(未跟踪表) or "（无）")]
    if 失败说明:
        行表.append("**%s**；未恢复：%s" % (失败说明,
                 " · ".join(路径 for 路径, _, _, _ in 恢复计划[len(完成表):])))
    if 未恢复文件表:
        行表.append("恢复后表主目录仍有 tracked 差异（异常，勿当成功）：\n  " + "\n  ".join(未恢复文件表))
    else:
        行表.append("恢复后表主目录 tracked 工作区与 index/提交一致（未跟踪件保留）")
    return (4 if 失败说明 else (1 if 未恢复文件表 else 0)), "\n".join(行表)
