# -*- coding: utf-8 -*-
"""只读缓存 —— 查询类 git 子命令的**按仓内容指纹失效**进程内缓存。

**为什么要有它**（实测 2026-10-08）：判据 ㊽ 跑 `开发工具/MCP服务.py --自检`，是闸 1 的
关键路径。自检里的隔离样本组与主线程样本反复用**同一组 ref** 查询（`rev-parse --verify` ·
`rev-parse <ref>:<路径>` · `rev-list --left-right` · `ls-tree`）—— 同一个问句在一条命令里
被问几十次，每次都 fork 一个 git（实测每次 spawn ≈ 20 ms；十条隔离组加起来 ≈ 250 次）。
五秒硬顶之下这是纯浪费，且负载一高就把 `--自检` 顶过 5 s（实测 load 14–21 时 5.17 s）。

**失效判据不是 mtime，也不跨树串**：缓存键 = `(目标树绝对路径, argv)`，值里带一个**仓状态
指纹**。指纹由**真内容**算出：`HEAD` · `packed-refs` · `config` · `commondir` · `info/grafts` ·
`shallow` 的正文，`refs/**` 逐件（名字＋正文），以及（仅索引类查询）`index` 的**正文**。
问句前重算指纹，不一致即未命中（重跑 git 并换新值）。⇒ 同一棵树里 ref 一动、索引正文一改，
旧值立刻作废；不同树各按各的指纹，绝不互相命中。

**只缓存「只读且只依赖对象库 / refs / index」的子命令**（白名单）：`rev-parse` · `rev-list` ·
`ls-tree` · `cat-file` · `show` · `merge-base` · `show-ref` · `for-each-ref` · `symbolic-ref` ·
`name-rev` · `describe` · `log` · `branch` · `ls-files --cached` · `diff --cached`。
**不缓存**依赖工作区文件正文的（`status` · `worktree` · 不带 `--cached` 的 `diff` ·
`ls-files --others`）—— 指纹到 index 一层为止，盘上正文变了它看不见。

**三条安全边界**：① **失败不缓存**（未出现的对象 / 引用后来出现要能立刻读到）；
② **只存读前读后指纹一致的结果**（查询期间仓被并发改过 ⇒ 丢弃本次，不写）；
③ **读不出仓库元目录**（无仓 / 形状不认识）⇒ 不缓存（一律现跑，绝不拿旧值冒充通过）。
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

# 只读白名单：这些子命令的答案只由对象库 / refs / index 决定（工作区正文无关）。
只读子命令 = frozenset({
    "rev-parse", "rev-list", "ls-tree", "cat-file", "show", "merge-base",
    "show-ref", "for-each-ref", "symbolic-ref", "name-rev", "describe",
    "log", "branch", "ls-files", "diff",
})

# 看索引的子命令：只有它们的指纹要连 index 正文一起算（其余读整份 index 反而比命令慢）。
看索引子命令 = frozenset({"ls-files", "diff"})

# ── 616 独立审计 F1–F4 收紧：**确切白名单**，只留「只依赖 refs / 对象库 / 纯索引」且对
#    配置与环境不敏感的问句；拿不准的一律现跑（正确性优先，宁慢不错）。──

# 影响 git 读取结果的环境键（含全局/系统配置、refs 命名空间、浅仓、外部 diff、替换基线）。
# 有任意一个在场 ⇒ 一律不缓存（fail-closed）：拿不准它怎么改答案，就不拿旧值冒充。
环境可疑键 = frozenset({
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_PREFIX",
    "GIT_NAMESPACE", "GIT_CONFIG", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM",
    "GIT_CONFIG_NOSYSTEM", "GIT_CONFIG_COUNT", "GIT_SHALLOW_FILE",
    "GIT_EXTERNAL_DIFF", "GIT_REPLACE_REF_BASE", "GIT_CEILING_DIRECTORIES",
    "GIT_DISCOVERY_ACROSS_FILESYSTEM", "GIT_ATTR_NOSYSTEM",
})

# 依赖**对象集合**的开关：`--short` 的长度取决于同前缀对象是否存在（新增一个同前缀 blob
# 会让真值变长，而缓存回旧值 —— 616 审计 F2）⇒ 带这些的一律不缓存。
对象集敏感开关 = frozenset({"--short", "--abbrev"})

# 依赖对象集合 / 配置的子命令：答案随**对象库**或**全局配置**（含 include.path）变，
# 而指纹只到 refs / 本地 config ⇒ 不缓存（616 审计 F2）。
对象集敏感子命令 = frozenset({"log", "describe", "name-rev"})

# 工作区敏感开关：带这些的 `ls-files` / `diff` 依赖盘上正文（未跟踪 / 改动 / 忽略），
# 而指纹只到 index 一层 ⇒ 不缓存（616 审计 F1/F4：`件头读数.py` 的
# `ls-files --cached --others --exclude-standard` 就是这一形）。
工作区敏感开关 = frozenset({
    "--others", "-o", "--modified", "-m", "--deleted", "-d", "--unmerged", "-u",
    "--ignored", "-i", "--exclude-standard", "--no-index", "--directory",
})

# 配置敏感开关：答案随**全局 / 系统配置**（或 core.bare）变，而指纹只含本地 config ⇒ 不缓存。
配置敏感开关 = frozenset({"--is-bare-repository"})

# 缓存条数上限：超过即整批清（问句键的基数很小，正常远达不到）。
缓存上限 = 4096

# (目标树, argv) ⇒ (状态指纹, 退出码, 输出文本)。模块级字典 = 进程内缓存。
问句缓存: dict = {}


def 读仓库元目录(树根) -> tuple:
    """⇒ `(元目录, 公共目录)`；读不出 ⇒ `(None, None)`。**纯文件读，不起子进程。**

    三种形状：① `树根/.git` 是目录（普通仓）；② `树根/.git` 是文件（工作树，内含
    `gitdir: …`，可能还有 `commondir` 指回公共目录）；③ `树根` 本身就是元目录（裸仓）。
    """
    树根 = Path(树根)
    指针件 = 树根 / ".git"
    if 指针件.is_dir():
        return 指针件, 指针件
    if 指针件.is_file():
        try:
            指针文本 = 指针件.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            return None, None
        if not 指针文本.startswith("gitdir:"):
            return None, None
        元目录 = Path(指针文本[len("gitdir:"):].strip())
        if not 元目录.is_absolute():
            元目录 = (树根 / 元目录).resolve()
        公共目录 = 元目录
        公共指针件 = 元目录 / "commondir"
        if 公共指针件.is_file():
            try:
                公共指针文本 = 公共指针件.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                公共指针文本 = ""
            if 公共指针文本:
                公共目录 = (元目录 / 公共指针文本).resolve()
        return 元目录, 公共目录
    if (树根 / "HEAD").is_file() and (树根 / "objects").is_dir():
        return 树根, 树根
    return None, None


def 仓状态指纹(树根) -> str:
    """该树 refs / HEAD / config 一层的**仓状态指纹**；读不出仓库元目录 ⇒ 空串。

    **不含 index** —— 对象 / 引用类查询（`rev-parse` · `ls-tree` · `show` …）的答案与索引
    无关，带上索引会让每次访问多读一整份索引（比被缓存的 git 命令还慢）。
    """
    元目录, 公共目录 = 读仓库元目录(树根)
    if 元目录 is None:
        return ""
    摘要值 = hashlib.sha256()
    for 件路径 in (元目录 / "HEAD", 公共目录 / "packed-refs", 元目录 / "config",
                公共目录 / "config", 元目录 / "commondir",
                公共目录 / "info" / "grafts", 公共目录 / "shallow"):
        try:
            摘要值.update(件路径.read_bytes())
        except OSError:
            摘要值.update(b"-")
    引用根 = 公共目录 / "refs"
    if 引用根.is_dir():
        for 件路径 in sorted(引用根.rglob("*")):
            if not 件路径.is_file():
                continue
            摘要值.update(str(件路径.relative_to(引用根)).encode("utf-8"))
            try:
                摘要值.update(件路径.read_bytes())
            except OSError:
                摘要值.update(b"-")
    return 摘要值.hexdigest()[:16]


def 索引指纹(树根) -> str:
    """该树**索引正文**的指纹（真内容，不是尺寸＋改时）；无索引 / 读不出 ⇒ 空串。"""
    元目录, 公共目录 = 读仓库元目录(树根)
    if 元目录 is None:
        return ""
    索引件 = 元目录 / "index"
    try:
        return hashlib.sha256(索引件.read_bytes()).hexdigest()[:16]
    except OSError:
        return ""


def 可缓存(参数表) -> bool:
    """该 git 子命令能不能进缓存：**确切白名单** —— 只留「只依赖 refs / 对象库 / 纯索引」
    且对配置与环境不敏感的问句；其余一律现跑（616 独立审计 F1–F4，正确性优先）。"""
    词表 = [str(词条) for 词条 in 参数表]
    if not 词表 or 词表[0] not in 只读子命令:
        return False
    首词 = 词表[0]
    if 首词 in 对象集敏感子命令:
        return False
    if any(词条 in 对象集敏感开关 or 词条.split("=", 1)[0] in 对象集敏感开关 for 词条 in 词表):
        return False
    if 首词 == "ls-files":
        return 词表 == ["ls-files", "--cached"]      # 纯索引；任何工作区开关都现跑（F1/F4）
    if 首词 == "diff":
        return "--cached" in 词表 and not (工作区敏感开关 & set(词表))
    if (工作区敏感开关 | 配置敏感开关) & set(词表):
        return False
    return True


def 跑只读命令(底层, 仓根, 参数表, 树根=None, 超时=5) -> tuple:
    """`底层(仓根, 参数表, 树根=…, 超时=…)` 的**可缓存**包装 ⇒ `(退出码, 输出文本)`。

    命中条件：可缓存 且 读得出仓状态指纹 且 键与指纹都与上次一致。
    写入条件：**只存成功**（失败不缓存 —— 未出现的对象 / 引用后来出现要能立刻读到），
    且**读前读后指纹一致**（查询期间仓没被并发改过，否则丢弃本次结果不写）。
    """
    目标树 = str(树根 or 仓根)
    if not 可缓存(参数表):
        return 底层(仓根, 参数表, 树根=树根, 超时=超时)
    if 环境可疑键 & set(os.environ):
        # 环境里带着会改 git 答案的键（全局/系统配置 · 命名空间 · 浅仓 …）⇒ 不缓存（F3）。
        return 底层(仓根, 参数表, 树根=树根, 超时=超时)
    看索引 = str(参数表[0]) in 看索引子命令
    状态指纹 = 仓状态指纹(目标树)
    if not 状态指纹:
        return 底层(仓根, 参数表, 树根=树根, 超时=超时)
    if 看索引:
        状态指纹 = 状态指纹 + ":" + 索引指纹(目标树)
    问句键 = (目标树, tuple(str(词条) for 词条 in 参数表))
    命中 = 问句缓存.get(问句键)
    if 命中 is not None and 命中[0] == 状态指纹:
        return 命中[1], 命中[2]
    查询结果 = 底层(仓根, 参数表, 树根=树根, 超时=超时)
    复读指纹 = 仓状态指纹(目标树)
    if 看索引:
        复读指纹 = 复读指纹 + ":" + 索引指纹(目标树)
    if 查询结果[0] == 0 and 复读指纹 == 状态指纹:
        if len(问句缓存) >= 缓存上限:
            问句缓存.clear()
        问句缓存[问句键] = (状态指纹, 查询结果[0], 查询结果[1])
    return 查询结果
