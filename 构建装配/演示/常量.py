# -*- coding: utf-8 -*-
"""常量与三件共用读法 —— 落点 · 端口 · 超时 · 打印 · 写回执 · 端口监听。

拆自 `起演示.py`（入口 ≤120 行且零实现，开发规范 §六）。本件是**叶子**：不 import 兄弟件。
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

仓根 = Path(__file__).resolve().parents[2]
扩展根声明源 = 仓根 / "扩展装载" / "扩展根声明.json"
程序文本源 = 仓根 / "测试验证" / "案例" / "真程序文本" / "输入.程序文本"
网关产物 = 仓根 / "构建环境" / "构建缓存" / "release" / "examples" / "启动网关"
扩展落点 = 仓根 / "扩展根目录" / "原子支持库" / "编译器支持库"
暂存根 = Path(tempfile.gettempdir()) / "系统工程平台V1-演示"

# 回执落点**在临时区，不在源码树**（README §十 · 判据 ⑳「运行数据不落源码树」）。
# 本回执逐次覆盖，且记着 pid 与绝对临时路径 = **机器相关的运行状态**，不是声明、也不是可提交的
# 证据 ⇒ 落进源码树会当场坏两件事：提交里混进机器状态 · `git status` 永远不干净。
# （对照：`测试验证/案例/运行回执.jsonl` 是**入库的证据**，它记的是提交哈希与判读结果，不是本类。）
回执落点 = 暂存根 / "最近一次回执.json"

# 演示只验「接入支持库」这一层：流量端口上的常驻网关与本件无关，只记状态不碰。
流量端口 = 43110
健康超时秒 = 30.0
HTTP超时秒 = 10.0

# 停等秒 —— 发 SIGTERM 后等它自己走的**上限**，不是预期耗时。
# ★ 它同时受「所有运行五秒硬顶」约束（`项目文档/决策记录/2026-09-27_所有运行五秒硬顶.md`
# §一 范围**点名了本命令**）：本件其余步骤实测合计不到 1 秒，故 5.0 秒的容忍度会让**最坏路径**
# 也超顶 —— 容忍度必须小到「最坏仍在顶内」。实测（2026-09-27）：网关无信号处理器 ⇒ SIGTERM
# 即走（退出码 -15），正常路径 10 毫秒级，2.0 秒是纯保险。
停等秒 = 2.0

# 真调样本：案例库「真程序文本」的输入（195 字节真语料，1101/1102 真调成功过的同一份）。
被调号表 = (1101, 1102)


def 打印(文: str) -> None:
    print(文, flush=True)


def 端口监听读数(端口: int) -> list:
    """`lsof` 读一个端口的 LISTEN 状态（只读取证：本演示的误杀证据链用）。

    ★ `errors="replace"` 不是可选项：`lsof` 会把**别人的进程名**打出来，而进程名不必是
    UTF-8（实测 2026-09-27 一次运行就撞上：`UnicodeDecodeError: invalid continuation byte`
    ⇒ **整条演示命令在清理步骤崩掉**，「一条可复跑的命令」当场不成立）。
    这里只取「有没有 LISTEN」这一件事，进程名解不干净不影响判读 ⇒ 用 `replace` 兜住。
    """
    成 = subprocess.run(
        ["/usr/sbin/lsof", "-nP", "-iTCP:{}".format(端口), "-sTCP:LISTEN"],
        capture_output=True, text=True, errors="replace",
    )
    行 = [行 for 行 in 成.stdout.splitlines() if "LISTEN" in 行]
    return 行


def 写回执(回执: dict) -> None:
    """原子写回执（同 上线切换.py::写指针 的写法：临时件 + os.replace）。"""
    回执落点.parent.mkdir(parents=True, exist_ok=True)
    临 = 回执落点.with_suffix(".json.临时")
    临.write_text(json.dumps(回执, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(临, 回执落点)
