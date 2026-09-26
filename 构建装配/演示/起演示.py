#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""起演示 —— 把「内核完整度判据②：接入封装好的支持库」收成**一条可复跑的命令**。

    cd <仓根> && . ./构建环境/进入.sh
    python 构建装配/演示/起演示.py

一条命令做完这条链（判据：项目文档/决策记录/2026-09-27_内核完整度判据.md §三 第 1 条）：

    编扩展 cdylib → 装到扫描点（生成指向它的声明）→ 起网关 → 经 HTTP 真调 1101/1102
    → 落回执 → 收工清理

这条链**真跑通过一次**（2026-09-27 渲染腿在系统临时目录手工搭的：自编网关 452608 字节 +
自编 dylib 444128 字节，启动读数「扫到扩展 1 个（装上 1 · 剔除 0）· 声明根 2 份 · 能力清单
8 条」，1101/1102 经 HTTP 200 且 成功=true）。本件把那次的手工搭法原样收编成命令：
暂存目录形状、声明形状、启动读数逐项对齐那次实证。

**必须转调既有腿，不另起第二套实现**：

- 编 dylib：**转调** `构建装配/上线切换/构建制品.py::扩展产物`（进程内 import 后调函数本体，
  cargo 命令一行不重写）。
- 起网关：**转调** `对外接口面/调用接口面/examples/启动网关.rs` 的**产物**（构建缓存里
  release/examples 的启动网关可执行件，`--声明根` / `--端口` / `--静态根` 全走它的入口参数）。
- 起停读法与 `构建装配/上线切换/上线切换.py` 同款：等 `监听 127.0.0.1:<端口>` 那一行拿实际
  端口、健康看 HTTP 不是看进程、停用 信号→等→强杀 梯度。差别只有一处：本件是**演示**，
  网关用完即停、暂存用完即删，不进已装载指针（那是上线切换的职责，演示不抢）。

**待收编的两处缺口（如实登记，见回执「待收编」段）**：

1. `构建制品.py::扩展产物` 没有独立命令形态（只能进程内调函数）——本件以 import 转调补位，
   是**最小**补法；收编方向：给它开一个 CLI 子命令。
2. 网关可执行件的构建步骤内联在 `构建制品.py::main` 里，没有可转调的节点 —— 本件只在
   产物缺失时按那一处**同形**补一条 cargo build（逐字同参，注明待收编）；产物在就不编。

**零第三方依赖**：Python 只用标准库。

**安全边界**：清理只杀**自己起的那个网关**（按本进程记下的 pid 精确发信号；残部清扫只匹配
本演示独有的暂存目录路径）——绝不碰流量端口上的常驻网关，回执里记 43110 的前后状态作证。
"""

import base64
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

仓根 = Path(__file__).resolve().parents[2]
回执落点 = 仓根 / "构建装配" / "演示" / "最近一次回执.json"
扩展根声明源 = 仓根 / "扩展装载" / "扩展根声明.json"
程序文本源 = 仓根 / "测试验证" / "案例" / "真程序文本" / "输入.程序文本"
网关产物 = 仓根 / "构建环境" / "构建缓存" / "release" / "examples" / "启动网关"
扩展落点 = 仓根 / "扩展根目录" / "原子支持库" / "编译器支持库"
暂存根 = Path(tempfile.gettempdir()) / "系统工程平台V1-演示"

# 演示只验「接入支持库」这一层：流量端口上的常驻网关与本件无关，只记状态不碰。
流量端口 = 43110
健康超时秒 = 30.0
停等秒 = 5.0
HTTP超时秒 = 10.0

# 真调样本：案例库「真程序文本」的输入（195 字节真语料，1101/1102 真调成功过的同一份）。
被调号表 = (1101, 1102)


def 打印(文: str) -> None:
    print(文, flush=True)


def 端口监听读数(端口: int) -> list:
    """`lsof` 读一个端口的 LISTEN 状态（只读取证：本演示的误杀证据链用）。"""
    成 = subprocess.run(
        ["/usr/sbin/lsof", "-nP", "-iTCP:{}".format(端口), "-sTCP:LISTEN"],
        capture_output=True, text=True,
    )
    行 = [行 for 行 in 成.stdout.splitlines() if "LISTEN" in 行]
    return 行


def 写回执(回执: dict) -> None:
    """原子写回执（同 上线切换.py::写指针 的写法：临时件 + os.replace）。"""
    回执落点.parent.mkdir(parents=True, exist_ok=True)
    临 = 回执落点.with_suffix(".json.临时")
    临.write_text(json.dumps(回执, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(临, 回执落点)


# ════════════════════════════════════════════════════════════════════════════
# 第 1 步：编扩展 cdylib —— 转调 构建制品.py::扩展产物
# ════════════════════════════════════════════════════════════════════════════


def 载入构建制品():
    """进程内加载 `构建装配/上线切换/构建制品.py`（转调它的扩展产物节点，不复制它的 cargo 命令）。"""
    清单 = 仓根 / "构建装配" / "上线切换" / "构建制品.py"
    规格 = importlib.util.spec_from_file_location("构建制品", 清单)
    模 = importlib.util.module_from_spec(规格)
    规格.loader.exec_module(模)
    return 模


def 符号导出读数(库: Path) -> dict:
    """`nm -gU` 取全局导出，验接缝符号 `GetPlatformInfo` 在（那次实证的同一验法）。"""
    成 = subprocess.run(["/usr/bin/nm", "-gU", str(库)], capture_output=True, text=True)
    if 成.returncode != 0:
        return {"命令成了": False, "接缝符号在": False, "说明": 成.stderr.strip()[:200]}
    导出 = [行.split()[-1] for 行 in 成.stdout.splitlines() if 行.strip()]
    # macOS 的 C 符号带前导下划线（_GetPlatformInfo），Linux 不带 —— 两种都认。
    在 = any(名.lstrip("_") == "GetPlatformInfo" for 名 in 导出)
    return {"命令成了": True, "接缝符号在": 在, "全局导出数": len(导出)}


# ════════════════════════════════════════════════════════════════════════════
# 第 2 步：装到扫描点 —— 暂存目录 + 指向它的扩展根声明（形状与扩展装载那份一致）
# ════════════════════════════════════════════════════════════════════════════


def 清扫残部() -> list:
    """扫掉**本演示自己**早先失败留下的残部：旧暂存目录 + 可能还活着的旧演示网关。

    匹配只按旧暂存目录的**完整独有路径**（每个 run 一个，路径里带时间与 pid）——
    常驻网关的命令行里没有这个路径，碰不到它。只扫地皮**十分钟前**的旧目录：
    更新的可能是另一场正在跑的演示，不碰。
    """
    清了的 = []
    if not 暂存根.is_dir():
        return 清了的
    for 旧 in sorted(暂存根.iterdir()):
        if not 旧.is_dir():
            continue
        if time.time() - 旧.stat().st_mtime < 600:
            continue
        成 = subprocess.run(["/usr/bin/pkill", "-f", str(旧)], capture_output=True, text=True)
        清了的.append("{}（pkill 退出码 {}）".format(旧.name, 成.returncode))
        shutil.rmtree(旧, ignore_errors=True)
    return 清了的


def 搭暂存(库: Path) -> Path:
    """搭这次的暂存目录：网关 + 扩展树 + 指向扩展树的扩展根声明（每次跑全新一份）。"""
    暂存 = 暂存根 / "演示-{}-pid{}".format(time.strftime("%Y%m%d-%H%M%S"), os.getpid())
    扩展树 = 暂存 / "扩展"
    (扩展树 / "原子支持库" / "编译器支持库").mkdir(parents=True)
    (扩展树 / "组合模块库").mkdir()
    (扩展树 / "技能封装库").mkdir()
    # 扩展目录内**恰好一个**可装载库文件（扫描判据①：按后缀找，不按名字找）。
    shutil.copy2(库, 扩展树 / "原子支持库" / "编译器支持库" / "编译器支持库.dylib")
    shutil.copy2(网关产物, 暂存 / "网关")
    (暂存 / "网关").chmod(0o755)

    源 = json.loads(扩展根声明源.read_text(encoding="utf-8"))
    声明 = dict(源)
    声明["说明"] = (
        "演示暂存副本（在系统临时目录，仓内一字未改）：种类[].目录 改指本次暂存下编出的扩展，"
        "形状与 扩展装载/扩展根声明.json 一致。生成器：构建装配/演示/起演示.py"
    )
    声明["种类"] = [
        dict(类, 目录=str(扩展树 / Path(类.get("目录", "")).name)) for 类 in 源.get("种类", [])
    ]
    (暂存 / "扩展根声明.json").write_text(
        json.dumps(声明, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 暂存


def 备网关产物() -> dict:
    """网关可执行件**转调启动网关.rs 的产物**：产物在就直接用；缺失才按 构建制品.py::main
    里那一处同形补编（逐字同参；该步骤无节点可转调 ⇒ 待收编，见模块注释）。"""
    if 网关产物.is_file():
        return {"转调产物": True, "路径": str(网关产物), "字节数": 网关产物.stat().st_size, "现编": False}
    环境 = dict(os.environ)
    成 = subprocess.run(
        ["cargo", "build", "--locked", "--offline", "--release", "-p", "v1-gateway",
         "--example", "启动网关"],
        cwd=str(仓根), capture_output=True, text=True, env=环境,
    )
    if 成.returncode != 0 or not 网关产物.is_file():
        raise RuntimeError(
            "网关产物缺失且补编失败（退出码 {}）：{}\n{}".format(
                成.returncode, 成.stdout[-500:], 成.stderr[-500:]
            )
        )
    return {"转调产物": True, "路径": str(网关产物), "字节数": 网关产物.stat().st_size, "现编": True}


# ════════════════════════════════════════════════════════════════════════════
# 第 3 步：起网关 —— 转调产物，读它的启动读数
# ════════════════════════════════════════════════════════════════════════════


def 起网关(暂存: Path) -> tuple:
    """起演示网关：`--端口 0` 让 OS 分配（绝不碰流量端口）；实际端口从
    `监听 127.0.0.1:<端口>` 那一行读（与 上线切换.py::等端口 同一读法）。"""
    日志 = 暂存 / "网关日志.txt"
    流 = 日志.open("w", encoding="utf-8")
    进程 = subprocess.Popen(
        [str(暂存 / "网关"), "--声明根", "扩展根声明.json", "--端口", "0",
         "--静态根", str(仓根 / "前端呈现" / "网页应用")],
        cwd=str(暂存), stdout=流, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL, start_new_session=True,
    )
    截止 = time.time() + 健康超时秒
    while time.time() < 截止:
        if 进程.poll() is not None:
            流.close()
            raise RuntimeError("演示网关没起来就退了（退出码 {}）：\n{}".format(
                进程.returncode, 日志.read_text(encoding="utf-8", errors="replace")))
        文 = 日志.read_text(encoding="utf-8", errors="replace")
        命 = re.search(r"监听 127\.0\.0\.1:(\d+)", 文)
        if 命:
            return 进程, 日志, int(命.group(1)), 文
        time.sleep(0.05)
    流.close()
    raise RuntimeError("等 `监听 127.0.0.1:<端口>` 超时（{} 秒）：\n{}".format(
        健康超时秒, 日志.read_text(encoding="utf-8", errors="replace")))


def 启动读数(文: str) -> dict:
    """从启动输出抠三样：扫到/装上/剔除 · 声明根份数与能力清单条数 · 扫描逐行（装上/剔除）。

    逐行按**行首词**认（启动入口打的「装上/剔除」行以落点开头），汇总行
    「扫到扩展 N 个（装上 N · 剔除 N）」里也有「装上」两个字 —— 按行首认就不会把它混进来。
    """
    出 = {"扫到扩展": None, "装上": None, "剔除": None, "声明根份数": None, "能力清单条数": None,
          "装上行": [], "剔除行": []}
    命 = re.search(r"扫到扩展 (\d+) 个（装上 (\d+) · 剔除 (\d+)）", 文)
    if 命:
        出["扫到扩展"], 出["装上"], 出["剔除"] = (int(命.group(i)) for i in (1, 2, 3))
    命 = re.search(r"声明根 (\d+) 份 · 能力清单 (\d+) 条", 文)
    if 命:
        出["声明根份数"], 出["能力清单条数"] = int(命.group(1)), int(命.group(2))
    for 行 in 文.splitlines():
        条 = 行.strip()
        if 条.startswith("装上 /"):
            出["装上行"].append(条[len("装上 "):])
        elif 条.startswith("剔除 /"):
            出["剔除行"].append(条[len("剔除 "):])
    return 出


# ════════════════════════════════════════════════════════════════════════════
# 第 4 步：经 HTTP 真调 —— POST /接口/调用（路径百分号编码，与路由侧同口径）
# ════════════════════════════════════════════════════════════════════════════


def 真调(端口: int, 被调号: int, 程序文本: str) -> dict:
    体 = json.dumps({"编号": 被调号, "值": [{"类型标签": 4, "值": 程序文本}]},
                    ensure_ascii=False).encode("utf-8")
    求 = urllib.request.Request(
        "http://127.0.0.1:{}{}".format(端口, urllib.parse.quote("/接口/调用")),
        data=体, headers={"Content-Type": "application/json"}, method="POST",
    )
    状态, 应体 = 0, ""
    try:
        with urllib.request.urlopen(求, timeout=HTTP超时秒) as 应:
            状态, 应体 = 应.status, 应.read().decode("utf-8")
    except urllib.error.HTTPError as 错:
        状态, 应体 = 错.code, 错.read().decode("utf-8", errors="replace")
    出 = {"HTTP状态": 状态, "成功": None, "返回字节数": None, "耗时微秒": None}
    try:
        果 = json.loads(应体)
    except ValueError:
        出["说明"] = "返回不是 JSON：{}".format(应体[:200])
        return 出
    出["成功"] = 果.get("成功")
    出["耗时微秒"] = 果.get("耗时微秒")
    值 = 果.get("值") or []
    if 值 and isinstance(值[0].get("值"), str):
        # 返回槽是字节集（base64 串）⇒ 解码计字节数（那次实证读的是同一形状）。
        出["返回字节数"] = len(base64.b64decode(值[0]["值"]))
    if 果.get("错误"):
        出["错误"] = 果["错误"]
    return 出


# ════════════════════════════════════════════════════════════════════════════
# 第 6 步：收工清理 —— 只杀自己起的那个
# ════════════════════════════════════════════════════════════════════════════


def 停网关(进程) -> str:
    """按本进程记下的 pid 精确停：先 礼停，等一程，还在才强杀（同 上线切换.py::停实例 梯度）。"""
    pid = 进程.pid
    try:
        os.kill(pid, 0)
    except OSError:
        return "pid {} 已不在".format(pid)
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as 错:
        return "pid {} 发信号失败：{}".format(pid, 错)
    截止 = time.time() + 停等秒
    while time.time() < 截止:
        try:
            os.kill(pid, 0)
        except OSError:
            return "pid {} 已停".format(pid)
        time.sleep(0.05)
    try:
        os.kill(pid, signal.SIGKILL)
        return "pid {} 强杀（礼停未收）".format(pid)
    except OSError:
        return "pid {} 已停".format(pid)


# ════════════════════════════════════════════════════════════════════════════
# 主链：任何一步失败就停在那一步 —— 回执写清死在哪一层哪一步，退出码非 0
# ════════════════════════════════════════════════════════════════════════════


def main() -> int:
    开跑 = time.time()
    回执 = {
        "生成物": True,
        "说明": "起演示回执 —— 「编扩展→装扫描点→起网关→HTTP 真调→清理」一条链的逐步读数。"
                "生成器：构建装配/演示/起演示.py（每次跑覆盖本件）。",
        "判据来源": "项目文档/决策记录/2026-09-27_内核完整度判据.md §三 第 1 条（② 常态接入）",
        "层": {},
        "待收编": [
            "构建制品.py::扩展产物 无独立命令形态：本件以进程内 import 调函数本体转调（最小补法）；"
            "收编方向 = 给它开 CLI 子命令。",
            "网关可执行件的构建步骤内联在 构建制品.py::main，无节点可转调：本件只在产物缺失时按"
            "同形补编一条（产物在就不编）；收编方向 = 把该步骤提成可调节点。",
        ],
    }
    暂存 = None
    进程 = None
    死层 = None
    try:
        # ── 前置 ────────────────────────────────────────────────────────────
        暂存根.mkdir(parents=True, exist_ok=True)
        回执["流量端口前状态"] = 端口监听读数(流量端口)

        # ── 第 1 步：编扩展 cdylib（转调 构建制品.py::扩展产物）──────────────
        死层 = "编扩展层"
        打印("① 编扩展 cdylib（转调 构建制品.py::扩展产物）")
        模 = 载入构建制品()
        库 = 模.扩展产物({
            "落点": 扩展落点, "种类": "支持库",
            "目录": "扩展根目录/原子支持库", "名": 扩展落点.name,
        })
        符号 = 符号导出读数(库)
        回执["层"]["编扩展"] = {
            "成了": True, "dylib路径": str(库), "dylib字节数": 库.stat().st_size,
            "符号导出": 符号, "转调": "构建制品.py::扩展产物",
        }
        打印("   dylib {}（{} 字节）· 接缝符号在：{}".format(
            库.name, 库.stat().st_size, 符号.get("接缝符号在")))
        if not 符号.get("接缝符号在"):
            raise RuntimeError("编出来的库取不到接缝符号 GetPlatformInfo：{}".format(符号))

        # ── 第 2 步：装到扫描点 ────────────────────────────────────────────
        死层 = "装配层"
        打印("② 装到扫描点（暂存目录 + 指向它的扩展根声明）")
        清了的 = 清扫残部()
        if 清了的:
            打印("   清掉早先残部：{}".format(" · ".join(清了的)))
        网关件 = 备网关产物()
        打印("   网关产物 {}（{} 字节{}）".format(
            网关件["路径"], 网关件["字节数"], "，现编" if 网关件["现编"] else ""))
        暂存 = 搭暂存(库)
        回执["层"]["装配"] = {
            "成了": True, "暂存目录": str(暂存), "网关产物": 网关件,
            "声明": str(暂存 / "扩展根声明.json"),
            "残部清扫": 清了的,
        }

        # ── 第 3 步：起网关（转调 启动网关.rs 的产物）───────────────────────
        死层 = "网关层"
        打印("③ 起网关（--端口 0，OS 分配，绝不碰流量端口）")
        进程, 日志, 端口, 启动文 = 起网关(暂存)
        读数 = 启动读数(启动文)
        回执["层"]["网关"] = dict(读数, 成了=True, pid=进程.pid, 端口=端口, 日志=str(日志))
        打印("   pid {} · 端口 {}".format(进程.pid, 端口))
        打印("   扫到扩展 {} 个（装上 {} · 剔除 {}）· 声明根 {} 份 · 能力清单 {} 条".format(
            读数["扫到扩展"], 读数["装上"], 读数["剔除"],
            读数["声明根份数"], 读数["能力清单条数"]))
        for 行 in 读数["装上行"]:
            打印("   装上 {}".format(行))
        for 行 in 读数["剔除行"]:
            打印("   剔除 {}".format(行))
        if not 读数["扫到扩展"] or not 读数["装上"]:
            raise RuntimeError(
                "扩展没被扫到/装上（扫到 {} · 装上 {}）——检查暂存声明与扩展树".format(
                    读数["扫到扩展"], 读数["装上"]))

        # ── 第 4 步：经 HTTP 真调 1101/1102 ─────────────────────────────────
        死层 = "调用层"
        程序文本 = 程序文本源.read_text(encoding="utf-8")
        打印("④ 经 HTTP 真调 {}（样本：测试验证/案例/真程序文本/输入.程序文本，{} 字节）".format(
            "/".join(str(号) for 号 in 被调号表), 程序文本源.stat().st_size))
        调用读数 = {}
        for 号 in 被调号表:
            果 = 真调(端口, 号, 程序文本)
            调用读数[str(号)] = 果
            打印("   {} → HTTP {} · 成功={} · 返回 {} 字节".format(
                号, 果["HTTP状态"], 果["成功"],
                "{} 字节".format(果["返回字节数"]) if 果["返回字节数"] is not None else "—"))
        回执["层"]["调用"] = {"成了": True, "样本": str(程序文本源), "逐号": 调用读数}
        for 号 in 被调号表:
            果 = 调用读数[str(号)]
            if 果["HTTP状态"] != 200 or 果["成功"] is not True:
                raise RuntimeError("能力 {} 真调不过：HTTP {} · 成功={} · {}".format(
                    号, 果["HTTP状态"], 果["成功"], 果.get("错误", 果.get("说明", ""))))

        # ── 判定 ───────────────────────────────────────────────────────────
        回执["判据"] = {
            "编成且符号在": 回执["层"]["编扩展"]["符号导出"]["接缝符号在"] is True,
            "扫到扩展≥1": (读数["扫到扩展"] or 0) >= 1,
            "装上≥1": (读数["装上"] or 0) >= 1,
            "1101成功真": 调用读数["1101"]["HTTP状态"] == 200 and 调用读数["1101"]["成功"] is True,
            "1102成功真": 调用读数["1102"]["HTTP状态"] == 200 and 调用读数["1102"]["成功"] is True,
        }
    except Exception as 死:
        回执["失败"] = {"死在哪一层": 死层, "原因": str(死)}
        回执["判据"] = {"到过判定": False}
        打印("✗ 死在{}：{}".format(死层, 死))
    finally:
        # ── 第 6 步：收工清理（失败也要清：网关必停、暂存必删）───────────────
        打印("⑤ 收工清理")
        清理 = {}
        if 进程 is not None:
            清理["停网关"] = 停网关(进程)
            打印("   {}".format(清理["停网关"]))
        if 暂存 is not None and 暂存.is_dir():
            try:
                shutil.rmtree(暂存)
            except OSError as 错:
                清理["暂存清理失败"] = str(错)
                打印("   暂存清不掉：{}".format(错))
            else:
                清理["暂存已删"] = not 暂存.exists()
                打印("   暂存已删 {}".format(暂存))
        清理["流量端口后状态"] = 端口监听读数(流量端口)
        清理["流量端口未被本件扰动"] = (
            清理["流量端口后状态"] == 回执.get("流量端口前状态", [])
        )
        打印("   流量端口 {} 未被本件扰动：{}".format(
            流量端口, 清理["流量端口未被本件扰动"]))
        回执["层"]["清理"] = 清理

    回执["总耗时秒"] = round(time.time() - 开跑, 2)
    过 = isinstance(回执.get("判据"), dict) and 回执["判据"].get("到过判定", True) and all(
        值 for 键, 值 in 回执["判据"].items() if 键 != "到过判定"
    ) and 回执.get("层", {}).get("清理", {}).get("暂存已删") is True
    回执["结论"] = "通过" if 过 and "失败" not in 回执 else "不通过"
    写回执(回执)
    打印("回执 → {}".format(回执落点))
    打印("结论：{} · 总耗时 {} 秒".format(回执["结论"], 回执["总耗时秒"]))
    return 0 if 回执["结论"] == "通过" else 1


if __name__ == "__main__":
    sys.exit(main())
