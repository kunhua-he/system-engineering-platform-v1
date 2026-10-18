# -*- coding: utf-8 -*-
"""合主干重叠样本 —— 合并侧重叠工序的正反样本（挂 `--自检`；临时真仓，跑完即删）。

四场景（**不依未合长样本**）：
  ① 两条腿改同件的**不同片段** ⇒ git 自动三方合并 ⇒ **核双方裁决齐通过**（两边改动都在）；
  ② **同片段冲突** ⇒ 出**双方裁决报告**、退出码非 0、**不自动取一侧**（冲突标记仍在）；
  ③ **解决后**核双方裁决齐：两侧都在 ⇒ 通过；**任一侧被丢 ⇒ 拒**；腿侧只有**整块缩进位移**
    （内容与基逐字同）⇒ **不拒**（反样本：缩进不是内容）；**同一行两侧行尾注释不同** ⇒ **不拒**
    （行尾注释不是内容：同一行只能有一个行尾注释 ⇒ 逐字比不可能满足）；**真代码行被丢 ⇒ 照样拒**；
  ④ **无重叠登记** ⇒ 本工序休眠（空集 · 退出码 0），与原拒绝语义一致（**不误伤**）。

夹具走**临时真仓 + 临时账本**（照 `认领样本.py` 口径）；git 一律走 `合主干有界跑.干净环境`
（已剔 Git 定位变量）—— **别在 `仓操作.跑命令` 修好前污染真腿**。
"""

import subprocess
from pathlib import Path

from ...集成管理.合主干有界跑 import 干净环境

基线文本 = "def 前段函数():\n    return 1\n\n\ndef 后段函数():\n    return 2\n"
对方侧文本 = 基线文本.replace("return 1", "return 11")
异片段文本 = 基线文本.replace("return 2", "return 22")
同片段文本 = 基线文本.replace("return 1", "return 22")
纯缩进文本 = 基线文本.replace("    return", "        return")
注释异文本 = 基线文本.replace("    return 1", "    return 11  # 本腿口径改写")
重叠建表 = ("create table 认领重叠 (开工号 text, 路径 text, 工作树 text, 基线提交 text, "
        "对方开工号 text, 对方工作树 text, 对方基线提交 text, "
        "primary key (开工号, 路径, 对方开工号))")


def _跑Git(工作目录, *命令表):
    """一条 git 命令（**报错即断言失败**，脚本体裁）⇒ 合并输出。"""
    回执 = subprocess.run(["git", *命令表], cwd=str(工作目录), capture_output=True, text=True,
                       env=干净环境(), timeout=5)
    assert 回执.returncode == 0, (命令表, 回执.stdout, 回执.stderr)
    return (回执.stdout or "") + (回执.stderr or "")


def _合腿(仓根, 支线名) -> int:
    """真仓工作区 `merge --no-commit --no-ff` ⇒ 退出码（0 干净 / 1 冲突）。"""
    回执 = subprocess.run(["git", "merge", "--no-commit", "--no-ff", 支线名], cwd=str(仓根),
                       capture_output=True, text=True, env=干净环境(), timeout=5)
    return 回执.returncode


def _撤合腿(仓根) -> int:
    回执 = subprocess.run(["git", "merge", "--abort"], cwd=str(仓根), capture_output=True,
                       text=True, env=干净环境(), timeout=5)
    return 回执.returncode


def 搭夹具(临时根) -> Path:
    """搭「基线 + 两条腿分支（自分基线）+ 主干推进到对方侧改动」的临时真仓 ⇒ 仓根。

    腿分支**自分基线**（不是自分主干推进后）⇒ 主干那一侧（对方侧）与腿各自相对基都有**独有改动**
    —— ②③ 的「一角被丢」两个方向都可证。
    """
    仓根 = 临时根 / "真仓"
    仓根.mkdir()
    _跑Git(仓根, "init", "-b", "主干")
    _跑Git(仓根, "config", "user.name", "样本")
    _跑Git(仓根, "config", "user.email", "样本@example.invalid")
    (仓根 / "样例.py").write_text(基线文本, encoding="utf-8")
    _跑Git(仓根, "add", "样例.py")
    _跑Git(仓根, "commit", "-m", "基线")
    for 支线名, 文本值 in (("腿/v1-900101", 异片段文本), ("腿/v1-900102", 同片段文本),
                       ("腿/v1-900103", 纯缩进文本), ("腿/v1-900104", 注释异文本)):
        腿树 = 临时根 / 支线名.replace("/", "_")
        _跑Git(仓根, "worktree", "add", "-b", 支线名, str(腿树), "主干")
        (腿树 / "样例.py").write_text(文本值, encoding="utf-8")
        _跑Git(腿树, "add", "样例.py")
        _跑Git(腿树, "commit", "-m", 支线名)
    (仓根 / "样例.py").write_text(对方侧文本, encoding="utf-8")
    _跑Git(仓根, "add", "样例.py")
    _跑Git(仓根, "commit", "-m", "对方侧（先合主干那一侧）")
    return 仓根


def 样本列表(仓根=None, 工具表=None) -> list:
    import sqlite3
    import tempfile

    from ...集成管理 import 合主干重叠

    输出表 = []
    with tempfile.TemporaryDirectory(prefix="v1合主干重叠-") as 临时目录:
        临时根 = Path(临时目录)
        仓库根 = 搭夹具(临时根)
        有登记 = sqlite3.connect(str(临时根 / "有登记.db"))
        有登记.row_factory = sqlite3.Row
        有登记.execute(重叠建表)
        有登记.execute("insert into 认领重叠 values ('v1-900001', '样例.py', ?, ?, 'v1-900002', ?, ?)",
                  (str(仓库根), "0" * 40, str(仓库根), "0" * 40))
        有登记.commit()
        空登记 = sqlite3.connect(str(临时根 / "空登记.db"))
        空登记.row_factory = sqlite3.Row
        空登记.execute(重叠建表)
        空登记.commit()
        无表 = sqlite3.connect(str(临时根 / "无表.db"))
        无表.row_factory = sqlite3.Row

        # ① 不同片段 ⇒ 自动三方合并 ⇒ 双方裁决齐
        合码 = _合腿(仓库根, "腿/v1-900101")
        退出码, 行表, 已知集 = 合主干重叠.审重叠("v1-900001", 仓库根, "腿/v1-900101", [], 连接=有登记)
        合并文本 = (仓库根 / "样例.py").read_text(encoding="utf-8")
        输出表.append(("重叠①不同片段：合腿退出码 %d（期望 0）· 审重叠退出码 %d（期望 0）· "
                "双方改动都在（对方 return 11 %s · 本腿 return 22 %s）"
                % (合码, 退出码, "在" if "return 11" in 合并文本 else "**丢**",
                   "在" if "return 22" in 合并文本 else "**丢**"),
                合码 == 0 and 退出码 == 0 and "return 11" in 合并文本 and "return 22" in 合并文本))
        _撤合腿(仓库根)

        # ② 同片段冲突 ⇒ 报告 + 非 0 + 不取一侧
        合码 = _合腿(仓库根, "腿/v1-900102")
        退出码, 行表, 已知集 = 合主干重叠.审重叠("v1-900001", 仓库根, "腿/v1-900102", [], 连接=有登记)
        报告文本 = "\n".join(行表)
        冲突文本 = (仓库根 / "样例.py").read_text(encoding="utf-8")
        输出表.append(("重叠②同片段：合腿退出码 %d（期望 1）· 审重叠退出码 %d（期望 1）· "
                "报告含两侧值（对方 return 11 %s · 本腿 return 22 %s）· 冲突标记仍在 %s"
                % (合码, 退出码, "有" if "return 11" in 报告文本 else "**缺**",
                   "有" if "return 22" in 报告文本 else "**缺**",
                   "是" if "=======" in 冲突文本 else "**否**"),
                合码 == 1 and 退出码 == 1 and "return 11" in 报告文本 and "return 22" in 报告文本
                and "=======" in 冲突文本))

        # ④ 无重叠登记 ⇒ 休眠（同一冲突现场；空表 + 无表两路）
        空码, 空行表, 空已知集 = 合主干重叠.审重叠("v1-900001", 仓库根, "腿/v1-900102", [], 连接=空登记)
        缺表登记 = 合主干重叠.读重叠登记("v1-900001", 连接=无表)
        输出表.append(("重叠④无登记：审重叠退出码 %d（期望 0）· 已知重叠集 %s（期望空）· "
                "表不存在读空 %s（期望是）"
                % (空码, "空" if not 空已知集 else "**非空**", "是" if 缺表登记 == [] else "否"),
                空码 == 0 and not 空已知集 and 缺表登记 == []))

        # ③ 解决后核双方裁决齐：两侧都在 ⇒ 0；任一侧被丢 ⇒ 1
        好解文本 = "def 前段函数():\n    return 11\n    return 22\n\n\ndef 后段函数():\n    return 2\n"
        丢本腿文本 = "def 前段函数():\n    return 11\n\n\ndef 后段函数():\n    return 2\n"
        丢对方文本 = "def 前段函数():\n    return 22\n\n\ndef 后段函数():\n    return 2\n"
        # 反样本：腿/v1-900103 相对基**只把整块缩进挪了 4 格**（内容逐字同），主干侧改了内容 ⇒
        # 取主干内容 + 腿的缩进**不算丢一侧**；同一夹具下真丢主干内容仍要拒（正向对照）。
        缩进解文本 = "def 前段函数():\n        return 11\n\n\ndef 后段函数():\n        return 2\n"
        缩进丢内容文本 = "def 前段函数():\n        return 1\n\n\ndef 后段函数():\n        return 2\n"
        # 行尾注释不同：腿侧只把注释写不同（代码行与基逐字同）⇒ 应得 0（注释不是内容）
        注释解文本 = "def 前段函数():\n    return 11  # 本腿口径改写\n\n\ndef 后段函数():\n    return 2  # 主干侧口径\n"
        记录表 = []
        for 说明, 文本值, 期望码, 腿分支 in (("两侧都在", 好解文本, 0, "腿/v1-900102"),
                                      ("丢本腿一侧", 丢本腿文本, 1, "腿/v1-900102"),
                                      ("丢对方一侧", 丢对方文本, 1, "腿/v1-900102"),
                                      ("腿侧纯缩进位移", 缩进解文本, 0, "腿/v1-900103"),
                                      ("同夹具丢对方内容", 缩进丢内容文本, 1, "腿/v1-900103"),
                                      ("行尾注释不同", 注释解文本, 0, "腿/v1-900104")):
            (仓库根 / "样例.py").write_text(文本值, encoding="utf-8")
            _跑Git(仓库根, "add", "样例.py")
            件码, 核行表, _ = 合主干重叠.审重叠("v1-900001", 仓库根, 腿分支, [], 连接=有登记)
            记录表.append((说明, 件码, "\n".join(核行表)))
        应拒表 = [记录表[序号] for 序号 in (1, 2, 4)]
        输出表.append(("重叠③解决后核双方裁决齐：两侧都在 %d（期望 0）· 丢本腿 %d 丢对方 %d（期望 1）· "
                "腿侧纯缩进位移 %d（期望 0）· 同夹具丢对方内容 %d（期望 1）· 行尾注释不同 %d（期望 0）· "
                "拒因说「一侧独有改动被丢」%s"
                % (记录表[0][1], 记录表[1][1], 记录表[2][1], 记录表[3][1], 记录表[4][1], 记录表[5][1],
                   "是" if all("一侧独有改动被丢" in 核果记录[2] for 核果记录 in 应拒表) else "否"),
                [核果记录[1] for 核果记录 in 记录表] == [0, 1, 1, 0, 1, 0]
                and all("一侧独有改动被丢" in 核果记录[2] for 核果记录 in 应拒表)))
        _撤合腿(仓库根)
        from ...集成管理.合主干集成树 import 提交合并
        记录表 = []
        for 说明, 文本值 in (("记录钩子", "exit 0"), ("拒绝钩子", "exit 1")):
            (仓库根 / ".git/hooks/pre-commit").write_text(
                "#!/bin/sh\nprintf '执行\n' >> hook-record\n" + 文本值 + "\n", encoding="utf-8")
            (仓库根 / ".git/hooks/pre-commit").chmod(0o755)
            (仓库根 / "样例.py").write_text(说明 + "\n", encoding="utf-8")
            _跑Git(仓库根, "add", "样例.py")
            合并文本 = _跑Git(仓库根, "rev-parse", "HEAD").strip()
            退出码, 报告文本 = 提交合并(仓库根, "腿/v1-900101", "v1-900001")
            记录表.append(退出码 == 0 if 文本值 == "exit 0" else
                         退出码 != 0 and _跑Git(仓库根, "rev-parse", "HEAD").strip() == 合并文本)
        输出表[-1] = (输出表[-1][0] + "·真实提交钩子执行且拒绝不推进HEAD",
                     输出表[-1][1] and all(记录表)
                     and (仓库根 / "hook-record").read_text().splitlines() == ["执行", "执行"])
        有登记.close()
        空登记.close()
        无表.close()
    return 输出表
