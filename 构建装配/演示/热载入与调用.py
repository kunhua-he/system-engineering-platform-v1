# -*- coding: utf-8 -*-
"""热载入与调用 —— 「不重启网关载入新扩展」的主链与两个零件（台账 237）。

拆自 `热载入.py`（入口 ≤120 行且零实现，开发规范 §六）。本件与 `起演示.py` 的兄弟件
（`常量.py` / `装配.py` / `网关与调用.py`）是**同级**：起停与 HTTP 读法直接复用
`网关与调用.py`，不另写第二套。

一条链：

    编扩展 cdylib → 起网关（扫描点**空**）→ 往扫描点丢新扩展 → **不重启网关**
    → POST /接口/生命周期 {动作:装载} → 经 HTTP 真调新扩展的能力 ⇒ 200 且 成功=true

与 `起演示.py` 的差别**只有一处**：那边扩展在**启动时**扫到；这边扩展在**启动后**才丢进去，
靠 `POST /接口/生命周期` 的 `动作=装载`（重扫 + `适配器::追加装载`）载入 —— **全程不重启网关**。
"""

import json
import os
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from 常量 import (
    仓根, 扩展根声明源, 暂存根, 打印文本, 打点, 端口监听读数, 流量端口, 程序文本源, 被调能力号表,
    写回执, HTTP超时秒, 硬顶毫秒, 尾巴余量毫秒, 阈值毫秒, 注入人为慢,
)
from 装配 import 载入构建制品, 备网关产物, 清扫残部, 符号导出读数
from 网关与调用 import 起网关, 启动读数, 真调网关, 停网关

回执落点 = 暂存根 / "最近一次热载入回执.json"


def 发JSON(端口: int, 路径: str, 体对象: dict) -> tuple:
    """发一条 POST JSON，收 `(HTTP 状态, 解析后的对象)`（非 JSON 给说明字典）。"""
    请求对象 = urllib.request.Request(
        "http://127.0.0.1:{}{}".format(端口, urllib.parse.quote(路径)),
        data=json.dumps(体对象, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    状态, 应体 = 0, ""
    try:
        with urllib.request.urlopen(请求对象, timeout=HTTP超时秒) as 造应答:
            状态, 应体 = 造应答.status, 造应答.read().decode("utf-8")
    except urllib.error.HTTPError as 错误:
        状态, 应体 = 错误.code, 错误.read().decode("utf-8", errors="replace")
    try:
        结果 = json.loads(应体)
    except ValueError:
        结果 = {"说明": "返回不是 JSON：{}".format(应体[:200])}
    return 状态, 结果


def 搭暂存(网关件路径: Path) -> Path:
    """搭暂存：网关 + 指向**空扫描点**的扩展根声明（扫描点启动时**不存在**）。"""
    暂存 = 暂存根 / "热载入-{}-pid{}".format(time.strftime("%Y%m%d-%H%M%S"), os.getpid())
    暂存.mkdir(parents=True, exist_ok=True)
    shutil.copy2(网关件路径, 暂存 / "网关")
    (暂存 / "网关").chmod(0o755)
    来源 = json.loads(扩展根声明源.read_text(encoding="utf-8"))
    声明 = dict(来源)
    声明["说明"] = (
        "热载入演示暂存副本（系统临时目录，仓内一字未改）：**支持库**那条 种类[].目录 改指本次"
        "暂存下的**空扫描点**（启动时不存在）—— 扩展在启动后才丢进去；其余种类的目录改指不存在的"
        "路径（本演示只演支持库那条路）。生成器：构建装配/演示/热载入.py"
    )
    声明["种类"] = [
        dict(类别, 目录="扫描点")
        if str(类别.get("目录", "")).endswith("原子支持库")
        else dict(类别, 目录="扫描点/" + Path(str(类别.get("目录", "其他"))).name)
        for 类别 in 来源.get("种类", [])
    ]
    (暂存 / "扩展根声明.json").write_text(
        json.dumps(声明, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 暂存


def 跑主链(壳起表=None) -> int:
    """主链。任何一步失败就停在那一步，回执写清死在哪一层，退出码非 0。

    `壳起表` = 入口在**导入本件之前**记下的 `time.monotonic()`（五秒硬顶壳自量）。
    """
    完整壳 = 壳起表 is not None
    起表 = 壳起表 if 完整壳 else time.monotonic()
    开跑 = time.time()
    回执 = {
        "生成物": True,
        "说明": "热载入回执 —— 「起网关(空扫描点)→丢新扩展→不重启→装载→真调」一条链的逐步读数。"
                "生成器：构建装配/演示/热载入.py（每次跑覆盖本件）。",
        "判据来源": "项目文档/设计文档/扩展装载与开发标准.md §六（热载入已现场验证）",
        "层": {},
    }
    暂存 = None
    进程 = None
    死层 = None
    阶段 = {}
    打点起 = [time.time()]

    try:
        暂存根.mkdir(parents=True, exist_ok=True)
        回执["流量端口前状态"] = 端口监听读数(流量端口)

        # 第 1 步：编扩展 cdylib（转调）
        死层 = "编扩展层"
        打印文本("① 编扩展 cdylib（转调 构建制品.py::扩展产物）")
        制品模块 = 载入构建制品()
        本次扩展 = {"落点": 仓根 / "扩展根目录" / "原子支持库" / "编译器支持库",
                "种类": "支持库", "目录": "扩展根目录/原子支持库", "名": "编译器支持库"}
        动态库 = 制品模块.扩展产物(本次扩展)
        符号 = 符号导出读数(动态库)
        回执["层"]["编扩展"] = {"dylib路径": str(动态库), "dylib字节数": 动态库.stat().st_size,
                            "符号导出": 符号, "转调": "构建制品.py::扩展产物"}
        打印文本("   dylib {}（{} 字节）· 接缝符号在：{}".format(
            动态库.name, 动态库.stat().st_size, 符号.get("接缝符号在")))
        if not 符号.get("接缝符号在"):
            raise RuntimeError("编出来的库取不到接缝符号 GetPlatformInfo：{}".format(符号))
        打点(阶段, 打点起, "① 编扩展")

        # 第 2 步：搭暂存（扫描点**空**）+ 备网关产物
        死层 = "装配层"
        打印文本("② 搭暂存（扫描点为空）· 备网关产物")
        清了的 = 清扫残部()
        if 清了的:
            打印文本("   清掉早先残部：{}".format(" · ".join(清了的)))
        网关件 = 备网关产物([本次扩展])
        暂存 = 搭暂存(Path(网关件["路径"]))
        回执["层"]["装配"] = {"暂存目录": str(暂存), "网关产物": 网关件, "残部清扫": 清了的}
        打点(阶段, 打点起, "② 装配")

        # 第 3 步：起网关（空扫描点）
        死层 = "网关层"
        打印文本("③ 起网关（扫描点为空 ⇒ 预期 扫到 0 个）")
        进程, 日志, 端口, 启动文 = 起网关(暂存)
        读数 = 启动读数(启动文)
        回执["层"]["网关"] = dict(读数, pid=进程.pid, 端口=端口, 日志=str(日志))
        打印文本("   pid {} · 端口 {} · 扫到扩展 {} 个（装上 {} · 剔除 {}）".format(
            进程.pid, 端口, 读数["扫到扩展"], 读数["装上"], 读数["剔除"]))
        if (读数["装上"] or 0) != 0:
            raise RuntimeError("启动时就装上了扩展（应装 0）：读数 {}".format(读数))
        打点(阶段, 打点起, "③ 起网关")

        # 第 4 步：往扫描点丢新扩展（**不重启网关**）
        死层 = "投件层"
        扩展目录 = 暂存 / "扫描点" / "编译器支持库"
        扩展目录.mkdir(parents=True, exist_ok=True)
        shutil.copy2(动态库, 扩展目录 / "编译器支持库.dylib")
        打印文本("④ 往扫描点丢新扩展（不重启网关）：{}".format(扩展目录))
        打点(阶段, 打点起, "④ 投件")

        # 第 5 步：POST /接口/生命周期 {动作:装载}
        死层 = "装载层"
        状态, 装载 = 发JSON(端口, "/接口/生命周期", {"动作": "装载"})
        数据 = 装载.get("数据") if isinstance(装载, dict) else None
        回执["层"]["装载"] = {"HTTP状态": 状态, "成功": 装载.get("成功"), "数据": 数据}
        装上 = (数据 or {}).get("装上") or []
        打印文本("   POST /接口/生命周期 {{动作:装载}} → HTTP {} · 成功={} · 装上 {} 个".format(
            状态, 装载.get("成功"), len(装上)))
        if 状态 != 200 or 装载.get("成功") is not True or len(装上) < 1:
            raise RuntimeError("装载没成功：HTTP {} · {}".format(状态, json.dumps(装载, ensure_ascii=False)))
        打点(阶段, 打点起, "⑤ 装载")

        # 第 5.5 步：反向样本（动作名不合法 ⇒ 400 · 重复装载幂等 ⇒ 已在 1 · 装上 0）
        死层 = "反向样本层"
        非法状态, 非法 = 发JSON(端口, "/接口/生命周期", {"动作": "重装"})
        打印文本("   反向样本：POST {{动作:重装}} → HTTP {}（期望 400）".format(非法状态))
        再次状态, 再次 = 发JSON(端口, "/接口/生命周期", {"动作": "装载"})
        再次数据 = 再次.get("数据") if isinstance(再次, dict) else {}
        已在 = (再次数据 or {}).get("已在") or []
        再次装上 = (再次数据 or {}).get("装上") or []
        打印文本("   幂等样本：再 POST {{动作:装载}} → HTTP {} · 成功={} · 已在 {} 个 · 装上 {} 个".format(
            再次状态, 再次.get("成功"), len(已在), len(再次装上)))
        回执["层"]["反向样本"] = {
            "动作不合法": {"HTTP状态": 非法状态, "体": json.dumps(非法, ensure_ascii=False)},
            "重复装载": {"HTTP状态": 再次状态, "成功": 再次.get("成功"),
                        "已在": len(已在), "装上": len(再次装上)},
        }
        if 非法状态 != 400:
            raise RuntimeError("动作名不合法应回 400，实际 {}".format(非法状态))
        if 再次状态 != 200 or 再次.get("成功") is not True or len(已在) != 1 or len(再次装上) != 0:
            raise RuntimeError("重复装载应幂等（已在 1 · 装上 0）：HTTP {} · {}".format(
                再次状态, json.dumps(再次, ensure_ascii=False)))
        打点(阶段, 打点起, "⑤.5 反向样本")

        # 第 6 步：经 HTTP 真调新载入扩展的能力（**不重启**）
        死层 = "调用层"
        程序文本 = 程序文本源.read_text(encoding="utf-8")
        打印文本("⑥ 经 HTTP 真调 {}（新载入的能力）".format("/".join(str(号值) for 号值 in 被调能力号表)))
        调用读数 = {}
        for 号值 in 被调能力号表:
            结果 = 真调网关(端口, 号值, 程序文本)
            调用读数[str(号值)] = 结果
            打印文本("   {} → HTTP {} · 成功={} · 返回 {}".format(
                号值, 结果["HTTP状态"], 结果["成功"],
                "{} 字节".format(结果["返回字节数"]) if 结果["返回字节数"] is not None else "—"))
        回执["层"]["调用"] = {"样本": str(程序文本源), "逐号": 调用读数}
        for 号值 in 被调能力号表:
            结果 = 调用读数[str(号值)]
            if 结果["HTTP状态"] != 200 or 结果["成功"] is not True:
                raise RuntimeError("新载入的能力 {} 真调不过：HTTP {} · 成功={}".format(
                    号值, 结果["HTTP状态"], 结果["成功"]))
        打点(阶段, 打点起, "⑥ 真调")

        回执["判据"] = {
            "启动时扫到0": (读数["扫到扩展"] or 0) == 0,
            "装载装上≥1": len(装上) >= 1,
            "1101成功真": 调用读数["1101"]["HTTP状态"] == 200 and 调用读数["1101"]["成功"] is True,
            "1102成功真": 调用读数["1102"]["HTTP状态"] == 200 and 调用读数["1102"]["成功"] is True,
            "动作不合法400": 非法状态 == 400,
            "重复装载幂等": 再次状态 == 200 and len(已在) == 1 and len(再次装上) == 0,
            "全程未重启": True,
        }
    except Exception as 错误:
        回执["失败"] = {"死在哪一层": 死层, "原因": str(错误)}
        回执["判据"] = {"到过判定": False}
        打印文本("✗ 死在{}：{}".format(死层, 错误))
    finally:
        打印文本("⑦ 收工清理")
        清理 = {}
        if 进程 is not None:
            停机结果 = 停网关(进程)
            清理["停网关"] = 停机结果
            打印文本("   停网关 pid {} · {} · 停法 {}".format(
                进程.pid, 停机结果.get("结果"), 停机结果.get("停法", "—")))
        if 暂存 is not None and 暂存.is_dir():
            try:
                shutil.rmtree(暂存)
            except OSError as 错误:
                清理["暂存清理失败"] = str(错误)
            else:
                清理["暂存已删"] = not 暂存.exists()
        清理["流量端口后状态"] = 端口监听读数(流量端口)
        清理["流量端口未被本件扰动"] = 清理["流量端口后状态"] == 回执.get("流量端口前状态", [])
        回执["层"]["清理"] = 清理
        打点(阶段, 打点起, "⑦ 清理")

    回执["阶段耗时秒"] = 阶段
    回执["总耗时秒"] = round(time.time() - 开跑, 2)
    注入毫秒 = 注入人为慢()
    墙钟毫秒 = int((time.monotonic() - 起表) * 1000)
    回执["命令墙钟毫秒"] = 墙钟毫秒
    回执.setdefault("判据", {})["五秒内"] = 墙钟毫秒 <= 阈值毫秒
    是否通过 = isinstance(回执.get("判据"), dict) and 回执["判据"].get("到过判定", True) and all(
        待处理值 for 键名, 待处理值 in 回执["判据"].items() if 键名 != "到过判定"
    ) and 回执.get("层", {}).get("清理", {}).get("暂存已删") is True
    回执["结论"] = "通过" if 是否通过 and "失败" not in 回执 else "不通过"
    写回执(回执, 回执落点)
    打印文本("回执 → {}".format(回执落点))
    打印文本("命令墙钟（壳自量）{} ms · 阈值 {} ms（硬顶 {} − 尾巴余量 {}）· 人为慢注入 {} ms".format(
        墙钟毫秒, 阈值毫秒, 硬顶毫秒, 尾巴余量毫秒, 注入毫秒))
    打印文本("结论：{} · 总耗时 {} 秒".format(回执["结论"], 回执["总耗时秒"]))
    return 0 if 回执["结论"] == "通过" else 1
