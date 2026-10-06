# -*- coding: utf-8 -*-
"""判据 ㉓：散文不落被忽略目录（被 `.gitignore` 忽略的目录里 0 处 `.md`）。

依据：`README.md` §十（本树明确不含什么）· `项目文档/开发规范/开发规范.md` §八.8
（「散文不许住进被忽略的目录」）· `项目文档/决策记录/2026-09-27_判据口径十一条.md` §十四
「落法」末段（那份 `构建装配/制品产物/说明.md` 就是这么永久丢的）。

**口径（读数已定，不许再发明）**：

    git ls-files --others --ignored --exclude-standard | grep '\\.md$' | grep -v '^构建环境/构建缓存/'

**空即通过**。要排掉 `构建环境/构建缓存/`：那里唯一命中的 `.md` 是 rustdoc 生成的字体
LICENSE（不是我们的散文）。

**为什么要有它**：被 `.gitignore` 忽略的目录会被 `git clean -xdf` 一次清掉，而散文（`.md`）
**不可复得**（实测已丢过一份 `构建装配/制品产物/说明.md`：它从未进版本库、别处无副本）。
纪律写在 `开发规范.md` §八.8 里，但**没有判据** —— 于是它只是一条能手跑的命令，会随仓长大而失效。
本条把它变成常驻判据：读数不为空即红，并逐条指名那份散文。

**非 git 仓**（读不出被忽略面）⇒ 报**判不了**（未判），不是通过 —— 空集不算通过。
故正向样本的合成仓自身 `git init`（见 `合成仓.py`），这样本条在夹具上也有对象。
"""
from __future__ import annotations

import subprocess

from .小工具 import 判不了, 违规
from .常量 import 检查名


# 被忽略面里**按设计允许**的 `.md` 前缀（rustdoc 生成的字体 LICENSE，不是我们的散文）。
被忽略散文排除前缀 = "构建环境/构建缓存/"

# 读数命令是定死的（文件头）；git 的读数在一次运行里不变 ⇒ 缓存住，避免对象数与判定各跑一遍。
_忽略条目缓存: dict = {}


def 忽略条目(仓根) -> tuple:
    """跑一次 `git ls-files --others --ignored --exclude-standard` ⇒ `(条目表, 错误或 None)`。

    返回的是**全部**被忽略条目（未过滤 `.md`）—— 它同时是「对象数」（0 ⇒ 未判）。
    """
    键名 = str(仓根)
    if 键名 in _忽略条目缓存:
        return _忽略条目缓存[键名]
    try:
        判定汇总 = subprocess.run(
            ["git", "-C", 键名, "ls-files", "--others", "--ignored", "--exclude-standard"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as 错误:
        待处理值 = ([], f"跑不动 git（{type(错误).__name__}：{错误}）")
        _忽略条目缓存[键名] = 待处理值
        return 待处理值
    if 判定汇总.returncode != 0:
        待处理值 = ([], f"git ls-files 退出码 {判定汇总.returncode}：{判定汇总.stderr.strip()[:200]}")
        _忽略条目缓存[键名] = 待处理值
        return 待处理值
    待处理值 = ([源码行 for 源码行 in 判定汇总.stdout.splitlines() if 源码行], None)
    _忽略条目缓存[键名] = 待处理值
    return 待处理值


def 样本_忽略条目(上层读数: dict) -> int:
    """对象数：被 git 忽略的条目数（0 ⇒ 未判：读不出被忽略面，这条判据什么都没验）。"""
    忽略条目表, _错误 = 忽略条目(上层读数["仓根"])
    return len(忽略条目表)


def 检查23_散文不落被忽略目录(上层读数: dict) -> list:
    """被忽略目录里的散文必须为空（`git ls-files --others --ignored` 里的 `.md`）。

    三元读数：**通过** = 被忽略面非空且其中 0 个（非排除前缀的）`.md`；
    **失败** = 逐条报出那份散文；**未判** = 读不出被忽略面（非 git 仓 / git 不可用）。
    """
    输出缓冲 = []
    忽略条目表, 错误 = 忽略条目(上层读数["仓根"])
    if 错误:
        判不了(
            检查名[22],
            "git ls-files --others --ignored --exclude-standard",
            f"判不了：{错误}",
            "被忽略目录里的散文只有 git 看得见（`.gitignore` 的语义不许自身重写一份——"
            "那是第二个事实源）⇒ 读不出就判不了。读数命令是定死的（见文件头）⇒ "
            "只能由环境（git 可用）或判据作者确认",
        )
        return 输出缓冲
    if not 忽略条目表:
        判不了(
            检查名[22],
            "git ls-files --others --ignored --exclude-standard",
            "被 git 忽略的条目 0 个（读不出被忽略面）",
            "判据的可信性.md 第二节：空集是**未判**，不是通过 —— 一条被忽略条目都没有的仓，"
            "本条判据什么都没验，算成通过就是假绿 ⇒ 只能由判据作者确认读数命令与仓状态",
        )
        return 输出缓冲

    命中 = [
        键名 for 键名 in 忽略条目表
        if 键名.endswith(".md") and not 键名.startswith(被忽略散文排除前缀)
    ]
    for 键名 in sorted(命中):
        输出缓冲.append(
            违规(
                检查名[22],
                键名,
                f"散文 `{键名}` 落在被 git 忽略的目录里 ⇒ 一次 `git clean -xdf` 就永久丢",
                "`开发规范.md` §八.8：**散文不许住进被忽略的目录**。落点目录要被忽略时，"
                "忽略必须写成「忽略内容 + 例外散文」（`构建装配/制品产物/*` + "
                "`!构建装配/制品产物/说明.md`），否则任何一次 `git clean -xdf` 都会把文档清掉，"
                "而散文不可复得（实测已丢过一份）⇒ 只能由把这份散文放进该目录的人挪出/加例外",
            )
        )
    return 输出缓冲
