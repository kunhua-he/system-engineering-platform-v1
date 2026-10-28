# -*- coding: utf-8 -*-
"""网关守护壳的**真跑式**自检实现 —— `sh -n` 查不出运行期 `bad substitution`，所以这里真跑。

为什么不能拿 `sh -n` 当反证（实测）：macOS 自带 bash 3.2 里 `${中文名:-默认}` **语法合法**、
`sh -n` 退出码 0，只有**真执行那一行**才报 `bad substitution` ⇒ 整个守护壳起不来、网关无人保活。

三支断言，每支都真起子进程：

  ① 自检分支 —— `V1_GUARD_SELFTEST=1 sh 网关守护.sh` ⇒ 断言退出码 0，且 stdout+stderr 不含
     `bad substitution` / `command not found` / `unbound variable`（后两者是同一病的另外两种形态）。
  ② 覆盖分支 —— 带齐四个 `V1_*` 覆盖值 source 一次 ⇒ 回读壳内 `RUNDIR` / `REPO` / `LOG` / `PORT`
     与传进去的值逐字相等。名字写错就**静默落回默认值**，跑真网关时落的可就是真日志 ⇒ 必须断言。
  ③ 轮转分支 —— 临时目录里造 6 MiB 日志，经 `V1_GATEWAY_LOG` 交进去 ⇒ `.1` 生成、原件让位、
     字节数不变；再超界一次只覆盖 `.1`（不堆 `.2`）。**只在临时目录里动，绝不碰真网关与真日志**：
     ② 没通过就不跑 ③（那时 `LOG` 会落回真 `/tmp` 日志，再轮转就是动真件）。

跑法见同目录的入口 `网关守护自检.py`；判据 71 在一键验证里也真跑本件（改了壳不跑就红）。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

# 壳件名（入口按它取同目录那份壳；反证可直接指定别的壳路径）
守护壳件名 = "网关守护.sh"
# 四个可覆盖环境变量 → 壳内变量名。**名字必须 ASCII** —— 它们同样是变量名，写成中文一样炸。
# 第五个（自检开关 `V1_GUARD_SELFTEST`）由自检分支当场验证：写错就跑进保活循环、当场露馅。
壳内名表 = ("RUNDIR", "REPO", "LOG", "PORT")
# 运行期错误的三种形态（`sh -n` 一种都查不出）
运行期坏字表 = ("bad substitution", "command not found", "unbound variable")
# 造件取 6 MiB（壳内轮转界 5 MiB ⇒ 必越界）；轮转后字节数必须一字不变。
造件字节数 = 6 * 1024 * 1024
# 断言条数（自检 1 · 覆盖 1 · 轮转 3）。判据 71 拿它判「判据与自检没漂」，别只改一处。
自检断言条数 = 5
# 命令级硬顶：判据 ㊲ 要求代码件的超时设置 ≤5 秒
命令超时秒 = 5


def 自检分支(壳路径: Path) -> tuple:
    """① `V1_GUARD_SELFTEST=1 sh <壳>` ⇒ 退 0 且无运行期报错。"""
    已跑 = subprocess.run(["sh", str(壳路径)], capture_output=True, text=True, timeout=命令超时秒,
                        env=dict(os.environ, V1_GUARD_SELFTEST="1"))
    合流文本 = (已跑.stdout or "") + (已跑.stderr or "")
    坏字命中 = [坏字 for 坏字 in 运行期坏字表 if 坏字 in 合流文本]
    return ("自检分支：退 0 且无 bad substitution / command not found",
            已跑.returncode == 0 and not 坏字命中,
            "退出码 %d · 命中 %s · 输出 %r"
            % (已跑.returncode, 坏字命中 or "无", 合流文本.strip()[:160]))


def 覆盖分支(壳路径: Path, 临时根目录: Path) -> tuple:
    """② 四个 `V1_*` 覆盖值真被壳认（回读壳内变量逐字相等）。返回 `(断言读数, 实得表)`。"""
    期望表 = {
        "V1_RUN_ROOT": str(临时根目录 / "运行"),
        "V1_REPO_ROOT": str(临时根目录 / "仓"),
        "V1_GATEWAY_LOG": str(临时根目录 / "守卫.log"),
        "V1_GATEWAY_PORT": "43991",
    }
    回读命令 = '. "$0" || exit 9; printf "%s\\n" "$RUNDIR" "$REPO" "$LOG" "$PORT"'
    已跑 = subprocess.run(["sh", "-c", 回读命令, str(壳路径)], capture_output=True, text=True,
                        timeout=命令超时秒, env=dict(os.environ, V1_GUARD_SELFTEST="1", **期望表))
    读出行表 = (已跑.stdout or "").splitlines()
    实得表 = dict(zip(壳内名表, 读出行表[:4]))
    差异读数 = [
        "%s（%s）期望 %r 实得 %r" % (覆盖变量名, 壳内变量名, 期望值, 实得表.get(壳内变量名))
        for (覆盖变量名, 期望值), 壳内变量名 in zip(期望表.items(), 壳内名表)
        if 实得表.get(壳内变量名) != 期望值
    ]
    return (
        ("覆盖分支：四个 V1_* 覆盖值真被壳认",
         已跑.returncode == 0 and len(读出行表) >= 4 and not 差异读数,
         "退出码 %d · 差 %s · %s"
         % (已跑.returncode, 差异读数 or "无", (已跑.stderr or "").strip()[:120])),
        实得表,
    )


def 轮转分支(壳路径: Path, 临时根目录: Path, 实得表: dict) -> list:
    """③ 6 MiB 日志经 `V1_GATEWAY_LOG` 交进去 ⇒ `.1` 让位；再超界只覆盖 `.1`。"""
    日志路径 = 临时根目录 / "守卫.log"
    if 实得表.get("LOG") != str(日志路径):
        # 覆盖分支没通过 ⇒ 绝不动手：那时 LOG 落回真 `/tmp` 日志，轮转就是动真件。
        # 照样给满三条（只是都红）：断言条数是常量，少给会让「条数不符」的读数盖住真因。
        拒跑读数 = "覆盖没生效 ⇒ 拒绝执行（不碰真日志）· 壳内 LOG = %r ≠ 临时件 %r" % (
            实得表.get("LOG"), str(日志路径))
        return [("轮转分支：1 MiB 的小日志不动", False, 拒跑读数),
                ("轮转分支：6 MiB 日志轮转成 .1（原件让位）", False, 拒跑读数),
                ("轮转分支：再超界只覆盖 .1（不堆成 .2）", False, 拒跑读数)]

    def 转一次(日志件路径: Path) -> subprocess.CompletedProcess:
        """经 `V1_GATEWAY_LOG` 交一件进去，只调 `rotate_log` 那一支（不起网关）。"""
        return subprocess.run(
            ["sh", "-c", '. "$0" || exit 9; rotate_log "$LOG"', str(壳路径)],
            capture_output=True, text=True, timeout=命令超时秒,
            env=dict(os.environ, V1_GUARD_SELFTEST="1", V1_RUN_ROOT=str(临时根目录 / "运行"),
                     V1_REPO_ROOT=str(临时根目录 / "仓"), V1_GATEWAY_PORT="43991",
                     V1_GATEWAY_LOG=str(日志件路径)))

    小日志件 = 临时根目录 / "小.log"
    小日志件.write_bytes(b"y" * (1024 * 1024))
    小跑读数 = 转一次(小日志件)
    断言读数表 = [("轮转分支：1 MiB 的小日志不动",
                   小跑读数.returncode == 0 and 小日志件.is_file()
                   and not Path(str(小日志件) + ".1").exists(),
                   "退出码 %d · 原件在 %s · .1 在 %s"
                   % (小跑读数.returncode, 小日志件.is_file(),
                      Path(str(小日志件) + ".1").exists()))]
    日志路径.write_bytes(b"z" * 造件字节数)
    大跑读数 = 转一次(日志路径)
    旧份路径 = Path(str(日志路径) + ".1")
    断言读数表.append(("轮转分支：6 MiB 日志轮转成 .1（原件让位）",
                       大跑读数.returncode == 0 and 旧份路径.is_file() and not 日志路径.exists()
                       and 旧份路径.stat().st_size == 造件字节数,
                       "退出码 %d · .1 在 %s · .1 字节 %d · 原件还在 %s"
                       % (大跑读数.returncode, 旧份路径.is_file(),
                          (旧份路径.stat().st_size if 旧份路径.is_file() else 0),
                          日志路径.exists())))
    日志路径.write_bytes(b"w" * 造件字节数)
    再跑读数 = 转一次(日志路径)
    断言读数表.append(("轮转分支：再超界只覆盖 .1（不堆成 .2）",
                       再跑读数.returncode == 0 and 旧份路径.is_file()
                       and not Path(str(日志路径) + ".2").exists(),
                       "退出码 %d · .1 字节 %d · .2 在 %s"
                       % (再跑读数.returncode,
                          (旧份路径.stat().st_size if 旧份路径.is_file() else 0),
                          Path(str(日志路径) + ".2").exists())))
    return 断言读数表


def 跑自检(壳路径: Path) -> list:
    """跑三支 ⇒ `[(断言名, 通过, 读数)]`。临时件住 `mkdtemp`，跑完即删。"""
    壳路径 = Path(壳路径)
    if not 壳路径.is_file():
        return [("壳在盘上", False, "找不到 %s" % 壳路径)]
    临时根目录 = Path(tempfile.mkdtemp(prefix="网关守护自检-"))
    try:
        断言读数表 = [自检分支(壳路径)]
        覆盖读数, 实得表 = 覆盖分支(壳路径, 临时根目录)
        断言读数表.append(覆盖读数)
        断言读数表.extend(轮转分支(壳路径, 临时根目录, 实得表))
        return 断言读数表
    finally:
        shutil.rmtree(临时根目录, ignore_errors=True)
