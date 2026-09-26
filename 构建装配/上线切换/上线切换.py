#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""上线切换 —— 装载 · 切换 · 回退 三条命令（形状与判据见 形状.md §二）。

    python3 构建装配/上线切换/上线切换.py 装载 <制品标识>
    python3 构建装配/上线切换/上线切换.py 切换 <制品标识>
    python3 构建装配/上线切换/上线切换.py 回退 [<制品标识>]     # 不给就用「上一份」
    python3 构建装配/上线切换/上线切换.py 现状

三条命令各做一件可数的事：

| 命令 | 做什么 | 流量 |
|---|---|---|
| 装载 | 起一份新制品（**临时端口**）→ 健康检查 → 记进已装载 | **不动** |
| 切换 | 停掉所有活着的实例 → 在**流量端口**上起目标 → 原子改「当前」 | 指过去 |
| 回退 | 同切换，但目标默认取「上一份」；**指定任意一份已产出制品**都行 | 指回去 |

运行数据**不在源码树内**（README 第十节）：默认落系统临时目录，可用环境变量
`ZCODE_SWITCH_RUN_ROOT` 换。源码树里只有本文件、`构建制品.py`、三条 `.sh` 与 `形状.md`。
（环境变量名一律 **ASCII**：sh 不认非 ASCII 变量名 —— 实测过，用中文名时 `export` 不生效。）
"""

import json
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

仓根 = Path(__file__).resolve().parents[2]
制品落点 = 仓根 / "构建装配" / "制品产物"
运行根 = Path(os.environ.get("ZCODE_SWITCH_RUN_ROOT") or Path(tempfile.gettempdir()) / "系统工程平台V1-上线切换")
健康超时秒 = 15.0
停等秒 = 5.0


def 打印(文: str) -> None:
    print(文, flush=True)


# ════════════════════════════════════════════════════════════════════════════
# 运行态（指针文件 · 原子写）
# ════════════════════════════════════════════════════════════════════════════


def 就绪() -> None:
    for 子 in ("已装载", "日志"):
        (运行根 / 子).mkdir(parents=True, exist_ok=True)


def 读指针(名: str) -> dict:
    路 = 运行根 / "{}.json".format(名)
    if not 路.is_file():
        return {}
    try:
        return json.loads(路.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def 写指针(名: str, 值: dict) -> None:
    """原子写：先写同目录临时件再 `os.replace`（换指针必须是**一步**，不许读到半个）。"""
    路 = 运行根 / "{}.json".format(名)
    临 = 路.with_suffix(".json.临时")
    临.write_text(json.dumps(值, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(临, 路)


def 清指针(名: str) -> None:
    路 = 运行根 / "{}.json".format(名)
    if 路.is_file():
        路.unlink()


# ════════════════════════════════════════════════════════════════════════════
# 制品：身份 · 不可变判据 · 端口来源
# ════════════════════════════════════════════════════════════════════════════


def 制品目录(标识: str) -> Path:
    return 制品落点 / 标识


def 读清单(标识: str) -> dict:
    路 = 制品目录(标识) / "制品清单.json"
    if not 路.is_file():
        raise SystemExit("制品不存在或没有清单：{}\n可用的制品：{}".format(路, " · ".join(列制品()) or "（一份都没有）"))
    return json.loads(路.read_text(encoding="utf-8"))


def 列制品() -> list:
    if not 制品落点.is_dir():
        return []
    return sorted(路.name for 路 in 制品落点.iterdir() if (路 / "制品清单.json").is_file())


def 不可变读数(标识: str) -> tuple:
    """重算制品清单里的每个文件指纹（判据：0 处不符 · 0 个清单外文件 · 0 个缺件）。"""
    import hashlib

    目录 = 制品目录(标识)
    记的 = 读清单(标识).get("文件清单", {})
    现在 = {}
    for 路 in sorted(目录.rglob("*")):
        if 路.is_file() and 路.name != "制品清单.json":
            现在[路.relative_to(目录).as_posix()] = hashlib.sha256(路.read_bytes()).hexdigest()
    不符 = [键 for 键, 值 in 记的.items() if 现在.get(键) != 值]
    多余 = [键 for 键 in 现在 if 键 not in 记的]
    缺件 = [键 for 键 in 记的 if 键 not in 现在]
    return 不符, 多余, 缺件


def 流量端口() -> int:
    """流量端口 = 契约里的默认端口（唯一定义处：`契约声明/常量表.json`），可用 `ZCODE_TRAFFIC_PORT` 覆盖。"""
    if os.environ.get("ZCODE_TRAFFIC_PORT"):
        return int(os.environ["ZCODE_TRAFFIC_PORT"])
    表 = json.loads((仓根 / "契约声明" / "常量表.json").read_text(encoding="utf-8"))
    return int(next(条["值"] for 条 in 表["常量"] if 条["名"] == "接口端口"))


# ════════════════════════════════════════════════════════════════════════════
# 实例：起 · 停 · 健康检查
# ════════════════════════════════════════════════════════════════════════════


def 活着(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def 起实例(标识: str, 端口: int) -> dict:
    """起一份制品的网关实例。`端口=0` ⇒ 由 OS 分配（装载预检用，流量不动）。"""
    目录 = 制品目录(标识)
    日志 = 运行根 / "日志" / "{}-{}.log".format(标识, 端口 or "随机")
    流 = 日志.open("w", encoding="utf-8")
    # cwd 必须是**制品目录**：制品内 `扩展根声明.json` 的 `路径基准` 就是「工作目录」，
    # `种类[].目录` 指的是制品内的 `扩展/`（`上线切换/形状.md` §三）。扩展这条路靠 cwd 走。
    # 但**静态件与案例库住在仓根**（`接口面形状.md` §五 静态托管根 = `前端呈现/网页应用`；
    # §七 工具族案例根 = `测试验证/案例`），两者默认都相对进程工作目录解 —— 与 cwd 口径冲突。
    # 故按仓根**注入**这两个部署事实（`启动网关 --静态根 / --工具根`），不互相借 cwd。
    # 实测（2026-09-27）：只给 `cwd=制品目录` ⇒ `GET /` 全 404、`GET /接口/案例` 恒 9002。
    进程 = subprocess.Popen(
        [
            str(目录 / "网关"),
            "--声明根", "扩展根声明.json",
            "--端口", str(端口),
            "--静态根", str(仓根 / "前端呈现" / "网页应用"),
            "--工具根", str(仓根),
        ],
        cwd=str(目录),
        stdout=流,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,  # 脱离本进程组：起完就走，实例活到被显式停掉
    )
    实际 = 等端口(日志, 进程)
    if 实际 is None:
        进程.kill()
        raise SystemExit("实例没起来（日志 {}）：\n{}".format(日志, 日志.read_text(encoding="utf-8")))
    记录 = {"制品标识": 标识, "pid": 进程.pid, "端口": 实际, "日志": str(日志), "制品落点": str(目录)}
    写指针("已装载/{}".format(标识), 记录)
    return 记录


def 等端口(日志: Path, 进程) -> int:
    """等启动入口打出 `监听 127.0.0.1:<端口>` 那一行（约定见 制品清单.启动入口读数约定）。"""
    截止 = time.time() + 健康超时秒
    while time.time() < 截止:
        if 日志.is_file():
            命 = re.search(r"监听 127\.0\.0\.1:(\d+)", 日志.read_text(encoding="utf-8", errors="replace"))
            if 命:
                return int(命.group(1))
        if 进程.poll() is not None:
            return None
        time.sleep(0.05)
    return None


def 停实例(记录: dict) -> str:
    pid = int(记录.get("pid") or 0)
    if not pid or not 活着(pid):
        return "pid {} 已不在".format(pid or "?")
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as 错:
        return "发信号失败：{}".format(错)
    截止 = time.time() + 停等秒
    while time.time() < 截止 and 活着(pid):
        time.sleep(0.05)
    if 活着(pid):
        os.kill(pid, signal.SIGKILL)
        return "pid {} 强杀（SIGTERM 未收）".format(pid)
    return "pid {} 已停".format(pid)


def 健康(端口: int) -> tuple:
    """`GET /接口` → (HTTP 状态, 读数)。这是「起没起来」的唯一判据（不是看进程在不在）。

    **实测**：路径必须**百分号编码**。端点名是中文，而 Python 标准库的 `http.client`
    按 ASCII 编请求行 ⇒ 不编码当场 `UnicodeEncodeError`（实测撞到）。网关侧认百分号编码
    （`路由.rs`），故两边口径一致。
    """
    路径 = urllib.parse.quote("/接口")
    try:
        with urllib.request.urlopen("http://127.0.0.1:{}{}".format(端口, 路径), timeout=5) as 应:
            文 = 应.read().decode("utf-8")
            状 = 应.status
    except (urllib.error.URLError, socket.timeout, ConnectionError) as 错:
        return 0, "连不上：{}".format(错)
    try:
        描 = json.loads(文)
    except ValueError:
        return 状, "返回不是 JSON（{} 字节）".format(len(文))
    版 = 描.get("契约版本") or {}
    return 状, "契约版本 {}.{}.{}.{} · 实际端口 {} · 能力 {} 条".format(
        版.get("主", "?"), 版.get("次", "?"), 版.get("修订", "?"), 版.get("构建", "?"),
        描.get("实际端口"), len(描.get("能力", [])),
    )


def 要求健康(端口: int) -> None:
    状, 读数 = 健康(端口)
    if 状 != 200:
        raise SystemExit("健康检查不过（端口 {}）：{}".format(端口, 读数))
    打印("  健康检查 GET /接口 → 200 · {}".format(读数))


def 活着的实例() -> list:
    if not (运行根 / "已装载").is_dir():
        return []
    return [读指针("已装载/{}".format(路.stem)) for 路 in sorted((运行根 / "已装载").glob("*.json"))]


# ════════════════════════════════════════════════════════════════════════════
# 三条命令
# ════════════════════════════════════════════════════════════════════════════


def 命令装载(标识: str) -> int:
    打印("装载 {}".format(标识))
    不符, 多余, 缺件 = 不可变读数(标识)
    打印("  制品不可变判据：指纹不符 {} · 清单外文件 {} · 缺件 {}".format(len(不符), len(多余), len(缺件)))
    if 不符 or 多余 or 缺件:
        raise SystemExit("制品被改过，拒绝装载（制品不可变）：{} {} {}".format(不符, 多余, 缺件))
    已 = 读指针("已装载/{}".format(标识))
    if 已 and 活着(int(已["pid"])):
        打印("  幂等：已有实例 pid={} 端口={}".format(已["pid"], 已["端口"]))
        记录 = 已
    else:
        记录 = 起实例(标识, 0)
        打印("  实例 pid={} 端口={}（临时端口，流量不动）".format(记录["pid"], 记录["端口"]))
    要求健康(int(记录["端口"]))
    当 = 读指针("当前")
    打印("  当前 = {}".format(当.get("制品标识", "无")))
    return 0


def 落到流量端口(标识: str, 来源: str) -> int:
    """切换与回退共用的动作：停掉所有活着的实例 → 在流量端口上起目标 → 原子改「当前」。"""
    端口 = 流量端口()
    当 = 读指针("当前")
    if 当.get("制品标识") == 标识 and int(当.get("端口") or 0) == 端口 and 活着(int(当.get("pid") or 0)):
        打印("  幂等：当前已是它（pid={} 端口={}），只复核健康".format(当.get("pid"), 端口))
        要求健康(端口)
        return 0

    停的 = []
    for 记录 in 活着的实例():
        停的.append("{}（pid {}：{}）".format(记录.get("制品标识"), 记录.get("pid"), 停实例(记录)))
        (运行根 / "已装载" / "{}.json".format(记录.get("制品标识"))).unlink(missing_ok=True)
    for 记录 in [当]:
        if 记录.get("pid") and 活着(int(记录["pid"])):
            停的.append("当前（pid {}：{}）".format(记录.get("pid"), 停实例(记录)))
    打印("  停掉活着的实例 {} 个：{}".format(len(停的), " · ".join(停的) or "无"))

    记录 = 起实例(标识, 端口)
    打印("  实例 pid={} 端口={}（流量端口）".format(记录["pid"], 记录["端口"]))
    要求健康(端口)

    写指针("当前", dict(记录, 来源=来源))
    写指针("上一份", 当)
    打印("  当前 = {}（来源：{}）· 上一份 = {}".format(标识, 来源, 当.get("制品标识", "无")))
    return 0


def 命令切换(标识: str) -> int:
    读清单(标识)  # 不在制品落点里即拒
    打印("切换 → {}".format(标识))
    if not (读指针("已装载/{}".format(标识)) or {}).get("pid"):
        打印("  目标还没装载过，先装载（预检）")
        命令装载(标识)
    return 落到流量端口(标识, "切换")


def 命令回退(标识: str) -> int:
    来源 = "显式指定" if 标识 else "上一份"
    if not 标识:
        标识 = (读指针("上一份") or {}).get("制品标识") or ""
        if not 标识:
            raise SystemExit("没有「上一份」可回退。可回退的制品：{}".format(" · ".join(列制品()) or "（一份都没有）"))
    读清单(标识)  # 不在制品落点里即拒（回退到任意一份**已产出**的制品都行，不必先装载）
    打印("回退 → {}（来源：{}）".format(标识, 来源))
    return 落到流量端口(标识, "回退")


def 命令现状() -> int:
    当 = 读指针("当前")
    打 = 读指针("上一份")
    打印("运行根 {}".format(运行根))
    打印("当前 制品={} pid={} 端口={}".format(当.get("制品标识", "无"), 当.get("pid", "-"), 当.get("端口", "-")))
    打印("上一份 制品={}".format(打.get("制品标识", "无")))
    存活 = 活着的实例()
    打印("活着的实例 {} 个：{}".format(len(存活), " · ".join("{}:{}".format(项.get("制品标识"), 项.get("pid")) for 项 in 存活) or "无"))
    打印("可回退的制品 {} 份：{}".format(len(列制品()), " · ".join(列制品()) or "无"))
    return 0


def main(参: list) -> int:
    就绪()
    if not 参:
        raise SystemExit(__doc__)
    命 = 参[0]
    if 命 == "装载" and len(参) == 2:
        return 命令装载(参[1])
    if 命 == "切换" and len(参) == 2:
        return 命令切换(参[1])
    if 命 == "回退" and len(参) in (1, 2):
        return 命令回退(参[1] if len(参) == 2 else "")
    if 命 == "现状" and len(参) == 1:
        return 命令现状()
    raise SystemExit("用法：上线切换.py 装载 <制品标识> ｜ 切换 <制品标识> ｜ 回退 [<制品标识>] ｜ 现状")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
