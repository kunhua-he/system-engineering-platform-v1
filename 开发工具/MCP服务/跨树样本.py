# -*- coding: utf-8 -*-
"""跨树样本 —— 跨树读文件正反样本：分页（起始行/行数）· 版本指纹 · 越界拒 · 符号链接逃逸拒。

`自检样本.跑自检` 调它（永久样本接入口）—— 搭一棵迷你仓 + 一条腿的工作树，跑完即删，
仓一个字节都不改。覆盖：ref 模式与工作树模式分页 · 三页无丢重 · 末页 / 空件 / 多字节 ·
起始越界 / 负值 / 超限 ⇒ 退出码 2 · 非本仓 path / `..` / 符号链接逃逸 ⇒ 拒。
"""
import os
import subprocess
import tempfile
from pathlib import Path

from . import 跨树

长行数 = 450


def _跑Git(仓根, 参数表):
    """在 `仓根` 里跑一条 git 子命令 ⇒ `CompletedProcess`。

    ★ **必须净化环境**：MCP 服务在裸仓根跑时把 `GIT_DIR` / `GIT_WORK_TREE` 注进进程环境（同
    `仓状态.git环境` 口径）；子进程若照继承，夹具的 `git init/add/commit` 会打到**真腿**的
    `.git`（实测：一套夹具样本把 `长件.txt/空件.txt/多字节.txt` 提交进真腿、并造出 `腿/v1-999999`
    杂支线，连累 `v1_task 释放` 报「工作树仍有改动」）。故**剔干净**再跑：夹具 git 只认 `cwd`。
    """
    净化环境 = {键名: 值 for 键名, 值 in os.environ.items()
             if 键名 not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                          "GIT_COMMON_DIR", "GIT_ALTERNATE_OBJECT_DIRECTORIES")}
    return subprocess.run(["git", *参数表], cwd=str(仓根), capture_output=True, text=True,
                        env=净化环境)


def 建跨树夹具(临时根):
    """⇒ `(仓根, 工作树)`：主干有长件 / 空件 / 多字节件；腿的工作树有未提交件与逃逸链。"""
    仓根 = 临时根 / "仓库"
    仓根.mkdir()
    _跑Git(仓根, ["init", "-b", "主干"])
    _跑Git(仓根, ["config", "user.name", "本地样本"])
    _跑Git(仓根, ["config", "user.email", "local@example.invalid"])
    (仓根 / "长件.txt").write_text("".join("行%03d\n" % 序号 for 序号 in range(1, 长行数 + 1)), encoding="utf-8")
    (仓根 / "空件.txt").write_text("", encoding="utf-8")
    (仓根 / "多字节.txt").write_text("中文行\n第二行·🙂\n第三行\n", encoding="utf-8")
    _跑Git(仓根, ["add", "长件.txt", "空件.txt", "多字节.txt"])
    _跑Git(仓根, ["commit", "-m", "样本基线"])
    _跑Git(仓根, ["branch", "腿/v1-999999"])
    工作树 = 临时根 / "工作树"
    _跑Git(仓根, ["worktree", "add", str(工作树), "腿/v1-999999"])
    (工作树 / "长件.txt").write_text("".join("未提交%03d\n" % 序号 for 序号 in range(1, 长行数 + 1)), encoding="utf-8")
    树外件 = 临时根 / "树外.txt"
    树外件.write_text("树外内容\n", encoding="utf-8")
    (工作树 / "逃逸链.txt").symlink_to(树外件)
    return 仓根, 工作树


def 跨树样本(仓根=None, 工具表=None) -> list:
    """⇒ `[(名称, 是否好)]`（本件不改仓：全在临时夹具里跑）。

    ★ **整个样本体在「净化后的环境」里跑**：裸仓根的服务把 `GIT_DIR` 注进进程环境，
    而读路（`跨树.读文件` → `仓状态.跑git`/`跑命令`）会把 `os.environ` 重新并进子进程 ⇒ 夹具的
    `git` 会误认**真腿**为仓（实测：`--自检` 把夹具的 txt 提交进真腿、还造出 `腿/v1-999999`）。
    摘掉 GIT_* 后读 / 写都只认夹具目录（`cwd`）；退出时**还原**原值（不留副作用）。
    """
    _GIT键 = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
            "GIT_COMMON_DIR", "GIT_ALTERNATE_OBJECT_DIRECTORIES")
    旧环境 = {键名: os.environ.pop(键名) for 键名 in _GIT键 if 键名 in os.environ}
    try:
        return _样本主体()
    finally:
        os.environ.update(旧环境)


def _样本主体() -> list:
    """样本体（净化环境作用域由 `跨树样本` 管）。"""
    样本表 = []

    def 记样本(名称, 条件值):
        样本表.append((名称, bool(条件值)))

    with tempfile.TemporaryDirectory(prefix="v1跨树-") as 临时目录:
        临时根 = Path(临时目录)
        夹具仓根, 腿工作树 = 建跨树夹具(临时根)

        def 读页(参数表, 开工号=""):
            return 跨树.操作表["读文件"]["处理"](开工号, dict(参数表), 夹具仓根)

        页读数表 = [读页({"路径": "长件.txt", "引用": "主干", "起始行": 起始值, "行数": 200})
                for 起始值 in (1, 201, 401)]
        首页文本, 次页文本, 末页文本 = (读数[1] for 读数 in 页读数表)
        记样本("ref 分页三页都成功（%d/%d/%d）" % tuple(读数[0] for 读数 in 页读数表),
            all(读数[0] == 0 for 读数 in 页读数表))
        记样本("首页第 1 行 / 总行数 450 / 下一页 201",
           "行001" in 首页文本 and "总行数 450" in 首页文本 and "下一页 起始行=201" in 首页文本)
        记样本("次页 201–400 且续页 401",
           "行201" in 次页文本 and "行400" in 次页文本 and "下一页 起始行=401" in 次页文本)
        记样本("末页 401–450 且无下一页",
           "行401" in 末页文本 and "行450" in 末页文本 and "下一页" not in 末页文本)
        拼表 = []
        for 页文本 in (首页文本, 次页文本, 末页文本):
            拼表 += [源码行 for 源码行 in 页文本.splitlines() if 源码行.startswith("行")]
        期望表 = ["行%03d" % 序号 for 序号 in range(1, 长行数 + 1)]
        记样本("三页无丢重（拼回 %d 行）" % len(拼表), 拼表 == 期望表)
        记样本("版本指纹三页一致",
           首页文本.split("内容指纹")[1][:16] == 次页文本.split("内容指纹")[1][:16])

        树读数 = 读页({"路径": "长件.txt", "起始行": 1, "行数": 200}, 开工号="v1-999999")
        记样本("工作树模式读未提交件（退出码 %d）" % 树读数[0],
           树读数[0] == 0 and "未提交001" in 树读数[1] and "行001" not in 树读数[1])
        记样本("工作树回执带真实路径", str(腿工作树) in 树读数[1])

        空读数 = 读页({"路径": "空件.txt", "引用": "主干"})
        记样本("空件 总行数 1 不崩（退出码 %d）" % 空读数[0], 空读数[0] == 0 and "总行数 1" in 空读数[1])
        多读数 = 读页({"路径": "多字节.txt", "引用": "主干"})
        记样本("多字节件读全（退出码 %d）" % 多读数[0],
           多读数[0] == 0 and "中文行" in 多读数[1] and "🙂" in 多读数[1])

        拒样本 = (
            ("起始行 0 ⇒ 2", {"路径": "长件.txt", "引用": "主干", "起始行": 0}, ""),
            ("起始行 -1 ⇒ 2", {"路径": "长件.txt", "引用": "主干", "起始行": -1}, ""),
            ("起始行 999 越界 ⇒ 2", {"路径": "长件.txt", "引用": "主干", "起始行": 999}, ""),
            ("行数 0 ⇒ 2", {"路径": "长件.txt", "引用": "主干", "行数": 0}, ""),
            ("行数 201 超限 ⇒ 2", {"路径": "长件.txt", "引用": "主干", "行数": 201}, ""),
            ("绝对路径 ⇒ 2", {"路径": "/etc/hosts", "引用": "主干"}, ""),
            ("`..` 路径 ⇒ 2", {"路径": "../树外.txt", "引用": "主干"}, ""),
            ("符号链接逃逸 ⇒ 2", {"路径": "逃逸链.txt"}, "v1-999999"),
        )
        for 名称, 参数表, 开工号 in 拒样本:
            退出码, _输出文本 = 读页(参数表, 开工号)
            记样本(名称 + "（实 %d）" % 退出码, 退出码 == 2)
    return 样本表
