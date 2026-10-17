# -*- coding: utf-8 -*-
"""恢复主目录样本 —— 隔离临时仓里的正反样本（不触及项目主干）。

**为什么隔离**：恢复动作会写主目录工作区 —— 真仓的样本必须落在 `tempfile` 造出来的**独立仓**
里，跑完即删。夹具按 bare 形态设 `core.bare=true`（实现须对 bare 与非 bare 两形态都成立），实现一律显式 `--git-dir/--work-tree`。

**七个场景**（正 + 反）：
  ① 正确已保全匹配 ⇒ 恢复成功、tracked 逐件 == 提交 blob、未跟踪件保留；
  ② 未知额外 tracked 差异 ⇒ 拒、零写；
  ③ 某件盘上哈希变（≠ 计划当前指纹）⇒ 拒、零写；
  ④ `预期提交` ≠ 主干 HEAD ⇒ 拒、零写；
  ⑤ 二进制源件（含零字节）从 Git 对象逐字节复原；
  ⑥ 中途取对象失败 ⇒ 如实报「已恢复 N / 未恢复 M」，不假全成；
  ⑦ 保全缺失 ⇒ 拒、零写。
"""
import hashlib
import os
import sqlite3
import subprocess
import tempfile
from pathlib import Path

from . import 恢复主目录编排 as 恢复
from .合主干有界跑 import 干净环境


def 跑命令(工作目录, 命令表):
    """在夹具里跑一条 git（剔除宿主 Git 重定向变量）⇒ 去空白输出。"""
    环境表 = 干净环境()
    回执 = subprocess.run(["git", *命令表], cwd=str(工作目录), capture_output=True,
                      text=True, env=环境表, timeout=5)
    assert 回执.returncode == 0, (命令表, 回执.stdout, 回执.stderr)
    return 回执.stdout.strip()


def 取对象字节(工作目录, 说明符):
    """从夹具 Git 对象库读**原始字节**（二进制源件也走这里）。"""
    环境表 = 干净环境()
    回执 = subprocess.run(["git", "--git-dir", str(Path(工作目录) / ".git"),
                       "--work-tree", str(工作目录), "cat-file", "blob", 说明符],
                      cwd=str(工作目录), capture_output=True, env=环境表, timeout=5)
    assert 回执.returncode == 0, (说明符, 回执.stderr)
    return 回执.stdout


def 建夹具(夹具根):
    """独立仓主目录（`core.bare=true`）+ 已提交基线 ⇒ `(主目录, 基线提交)`。"""
    主目录 = 夹具根 / "主目录"
    主目录.mkdir()
    跑命令(主目录, ["init", "-b", "主干"])
    跑命令(主目录, ["config", "user.name", "样本"])
    跑命令(主目录, ["config", "user.email", "fixture@example.invalid"])
    (主目录 / "README.md").write_text("系统工程平台 V1\n", encoding="utf-8")
    (主目录 / "AGENTS.md").write_text("样本\n", encoding="utf-8")
    (主目录 / "源码.py").write_text("值 = 1\n", encoding="utf-8")
    库件 = 主目录 / "开发工具/信息核心/信息核心.db"
    库件.parent.mkdir(parents=True)
    with sqlite3.connect(库件) as 连接:
        连接.execute("create table 规则 (编号 integer primary key, 正文 text)")
        连接.execute("insert into 规则 values (1, '基线')")
    跑命令(主目录, ["add", "."])
    跑命令(主目录, ["commit", "-m", "基线"])
    基线提交 = 跑命令(主目录, ["rev-parse", "HEAD"])
    跑命令(主目录, ["config", "core.bare", "true"])
    return 主目录, 基线提交


def 拟表(主目录, 基线提交, 漂移表):
    """按「盘上漂移态 → 提交目标态」生成条目（含 `_源件` 便于造保全）。"""
    条目表 = []
    for 路径 in 漂移表:
        件路径 = 主目录 / 路径
        目标指纹 = 跑命令(主目录, ["rev-parse", "%s:%s" % (基线提交, 路径)])
        条目表.append({"路径": 路径,
                   "当前指纹": 恢复.算指纹值(件路径.read_bytes()),
                   "目标指纹": 目标指纹, "_源件": str(件路径)})
    return 条目表


def 造保全(保全位置, 条目表):
    """按当前漂移态造保全证据目录（`记录/manifest.tsv` + `原文件/`）。"""
    (保全位置 / 恢复.记录目录).mkdir(parents=True)
    (保全位置 / 恢复.副本目录).mkdir(parents=True)
    行表 = []
    for 条目项 in 条目表:
        源件 = Path(条目项["_源件"])
        文件字节 = 源件.read_bytes()
        复制文件 = 保全位置 / 恢复.副本目录 / 条目项["路径"]
        复制文件.parent.mkdir(parents=True, exist_ok=True)
        复制文件.write_bytes(文件字节)
        行表.append("%s\t%s\t%s\t%s" % (hashlib.sha256(文件字节).hexdigest(),
                                   oct(源件.stat().st_mode & 0o777)[2:],
                                   len(文件字节), 条目项["路径"]))
    (保全位置 / 恢复.记录目录 / 恢复.清单文件).write_text("\n".join(行表) + "\n", encoding="utf-8")
    return 保全位置


def 净条目(条目表):
    """剥掉仅样本用的 `_源件`。"""
    return [{"路径": 条目项["路径"], "当前指纹": 条目项["当前指纹"], "目标指纹": 条目项["目标指纹"]}
            for 条目项 in 条目表]


def 跑恢复(主目录, 条目表, 预期提交, 保全位置):
    """调实现入口 ⇒ `(退出码, 输出文本)`。"""
    return 恢复.派发({"预期提交": 预期提交, "保全位置": str(保全位置),
                  "拟恢复文件表": 净条目(条目表)}, 主目录)


def 跑样本():
    """跑七个场景 ⇒ 退出码（0 全过）。断言失败也如实报，不抛给调用方。"""
    读数表 = []
    with tempfile.TemporaryDirectory(prefix="v1恢复样本-") as 临时目录:
        夹具根 = Path(临时目录)
        主目录, 基线提交 = 建夹具(夹具根)
        源码件 = 主目录 / "源码.py"
        说明件 = 主目录 / "AGENTS.md"
        库件 = 主目录 / "开发工具/信息核心/信息核心.db"
        未知件 = 主目录 / "未知未跟踪.txt"
        漂移表 = ["源码.py", "AGENTS.md", "开发工具/信息核心/信息核心.db"]
        基线源码 = 源码件.read_bytes()

        def 回基线():
            跑命令(主目录, ["--git-dir", str(主目录 / ".git"), "--work-tree", str(主目录),
                        "checkout", "--", "."])

        # ① 正确已保全匹配 ⇒ 恢复成功
        源码件.write_bytes("值 = 999\n".encode("utf-8"))
        说明件.write_bytes("漂移\n".encode("utf-8"))
        库件.write_bytes(b"\x00\x01\x02 drift\x00" * 40)
        未知件.write_text("用户未知成果\n", encoding="utf-8")
        计划表 = 拟表(主目录, 基线提交, 漂移表)
        保全位置 = 造保全(夹具根 / "证据", 计划表)
        退出码, 输出文本 = 跑恢复(主目录, 计划表, 基线提交, 保全位置)
        读数表.append(("① 正确已保全匹配恢复成功",
                   退出码 == 0 and "已恢复 3/3" in 输出文本, 输出文本.splitlines()[:1]))
        目标指纹表 = {条目项["路径"]: 条目项["目标指纹"] for 条目项 in 计划表}
        盘后表 = {路径: 恢复.算指纹值((主目录 / 路径).read_bytes()) for 路径 in 漂移表}
        读数表.append(("①b 恢复后 tracked 逐件 == 提交 blob", 盘后表 == 目标指纹表, 盘后表))
        读数表.append(("①c 未跟踪件保留",
                   未知件.read_text(encoding="utf-8") == "用户未知成果\n", ""))
        目标库字节 = 取对象字节(主目录, "%s:%s" % (基线提交, 漂移表[2]))
        读数表.append(("⑤ 二进制源件从对象逐字节复原",
                   库件.read_bytes() == 目标库字节 and b"\x00" in 目标库字节, ""))

        # ② 未知额外 tracked 差异 ⇒ 拒零写
        回基线()
        后备证据 = 造保全(夹具根 / "后备证据", 拟表(主目录, 基线提交, ["源码.py"]))
        说明件.write_bytes("额外未知\n".encode("utf-8"))
        退出码, 输出文本 = 跑恢复(主目录, 拟表(主目录, 基线提交, ["源码.py"]), 基线提交, 后备证据)
        读数表.append(("② 未知额外 tracked 差异 ⇒ 拒零写",
                   退出码 == 3 and "未知 tracked 差异" in 输出文本
                   and 源码件.read_bytes() == 基线源码, 输出文本.splitlines()[:1]))

        # ③ 盘上哈希变（≠ 计划当前指纹）⇒ 拒零写
        回基线()
        后备计划 = 拟表(主目录, 基线提交, ["源码.py"])
        源码件.write_bytes("值 = 变化后\n".encode("utf-8"))
        退出码, 输出文本 = 跑恢复(主目录, 后备计划, 基线提交, 后备证据)
        读数表.append(("③ 盘上哈希变 ⇒ 拒零写",
                   退出码 == 3 and "≠ 拟定当前" in 输出文本
                   and 源码件.read_bytes() == "值 = 变化后\n".encode("utf-8"), 输出文本.splitlines()[:1]))

        # ④ 预期提交 ≠ 主干 HEAD ⇒ 拒零写
        回基线()
        源码件.write_bytes("值 = 999\n".encode("utf-8"))
        计划四 = 拟表(主目录, 基线提交, ["源码.py"])
        证据四 = 造保全(夹具根 / "证据四", 计划四)
        退出码, 输出文本 = 跑恢复(主目录, 计划四, "0" * 40, 证据四)
        读数表.append(("④ 预期提交 ≠ HEAD ⇒ 拒零写",
                   退出码 == 3 and 源码件.read_bytes() == "值 = 999\n".encode("utf-8"),
                   输出文本.splitlines()[:1]))

        # ⑦ 保全缺失 ⇒ 拒零写
        退出码, 输出文本 = 跑恢复(主目录, 计划四, 基线提交, 夹具根 / "不存在的保全")
        读数表.append(("⑦ 保全缺失 ⇒ 拒零写",
                   退出码 == 3 and 源码件.read_bytes() == "值 = 999\n".encode("utf-8"),
                   输出文本.splitlines()[:1]))

        # ⑥ 中途取对象失败 ⇒ 如实报「已恢复 / 未恢复」
        回基线()
        源码件.write_bytes("值 = 999\n".encode("utf-8"))
        说明件.write_bytes("漂移\n".encode("utf-8"))
        库件.write_bytes(b"\x00\x01\x02 drift\x00" * 40)
        计划六 = 拟表(主目录, 基线提交, 漂移表)
        证据六 = 造保全(夹具根 / "证据六", 计划六)
        原取对象 = 恢复.取对象字节
        次数表 = {"次": 0}

        def 假取字节(主目录, 指纹值):
            次数表["次"] += 1
            return None if 次数表["次"] == 2 else 原取对象(主目录, 指纹值)

        恢复.取对象字节 = 假取字节
        try:
            退出码, 输出文本 = 跑恢复(主目录, 计划六, 基线提交, 证据六)
        finally:
            恢复.取对象字节 = 原取对象
        读数表.append(("⑥ 中途失败如实报已恢复/未恢复",
                   退出码 == 4 and "已恢复 1/3" in 输出文本 and "未恢复" in 输出文本
                   and "对象读不出" in 输出文本, 输出文本.splitlines()[:3]))

    通过 = all(是否好 for _, 是否好, _ in 读数表)
    for 名称, 是否好, 附注 in 读数表:
        print("  %s %s%s" % ("✓" if 是否好 else "✗", 名称, "" if 是否好 else "  ← %s" % (附注,)))
    print("恢复主目录样本：%s（场景 %d）" % ("全过" if 通过 else "有不过", len(读数表)))
    return 0 if 通过 else 1
