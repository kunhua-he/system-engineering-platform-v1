# -*- coding: utf-8 -*-
"""判据 ㉗–㊱：外部支持库准入判据（机器可判的 10 条）并入主门禁。

来源 = `测试验证/准入判据/准入判据.py`（原独立跑）。**判法以本模块为准**（一处实现）：
准入判据那件仍在（它多一层「16 条逐条 + 未判登记」的口径），主门禁这 10 条与它同源同判。

判据编号 ↔ 准入判据编号：
  ㉗=④ 广播段 · ㉘=⑤ 通知口 · ㉙=⑦ 接缝冻结 · ㉚=⑧ 无死键 · ㉛=⑨ crate-type ·
  ㉜=⑩ 命令类别 · ㉝=⑪ 显式顺序 · ㉞=⑬ 报因 · ㉟=⑭ 指纹可跑 · ㊱=⑯ 并发。

**未判的 5~6 条（①②③⑥⑫⑮）不进主门禁**：它们要么要一个允许跑 cargo 的窗口、要么要一个真外部库，
是「跑一次也没有读数」的裁决项 —— 留在 `准入判据.py` 照实报「未判」（不许当通过）。
"""

from __future__ import annotations

import json
import re

from .小工具 import 违规
from .常量 import 检查名

死键 = ("提供宿主版本", "提供内核版本")


# ── 读面辅助（落点是**面**不是某个写死的文件，见 #230）──
def _件(上, 后缀, 前缀=None):
    return [
        (键, 项["文本"] or "")
        for 键, 项 in sorted(上["文件"].items())
        if 键.endswith(后缀) and 项["文本"] is not None and (前缀 is None or 键.startswith(前缀))
    ]


def _拼(上, 后缀, 前缀=None):
    return "".join(文 for _键, 文 in _件(上, 后缀, 前缀))


def _生成物面(上):
    return _拼(上, "数据.rs", "契约声明/src/")


def _读json件(仓根, 名):
    出 = []
    for 路径 in sorted(仓根.rglob(名)):
        try:
            出.append((路径, json.loads(路径.read_text(encoding="utf-8"))))
        except (OSError, ValueError):
            出.append((路径, None))
    return 出


def _读文件(仓根, 名):
    出 = []
    for 路径 in sorted(仓根.rglob(名)):
        try:
            出.append((路径, 路径.read_text(encoding="utf-8")))
        except OSError:
            出.append((路径, ""))
    return 出


def _拼文(仓根, 名):
    return "".join(文 for _p, 文 in _读文件(仓根, 名))


def 检查27_准入广播段(上: dict) -> list:
    """㉗ 准入④：扩展能申报生命周期通知号段（生命周期段按广播段判）。"""
    出 = []
    名 = 检查名[26]
    生成物面 = _生成物面(上)
    判定rs = _拼(上, "判定.rs")
    载入判定 = _拼文(上["仓根"], "载入判定.json")
    缺 = []
    范围源 = re.search(r"生命周期起:\s*u32\s*=\s*(\d+).*?生命周期止:\s*u32\s*=\s*(\d+)", 生成物面, re.S)
    if not 范围源:
        缺.append("契约生成物无 生命周期起/止（唯一来源）")
    elif (int(范围源.group(1)), int(范围源.group(2))) != (2000, 2999):
        缺.append("生命周期段不是 2000–2999（实际 %s–%s）" % (范围源.group(1), 范围源.group(2)))
    if "fn 生命周期广播段" not in 判定rs:
        缺.append("判定.rs 无 fn 生命周期广播段")
    if "通知号段::生命周期起" not in 判定rs or "通知号段::生命周期止" not in 判定rs:
        缺.append("判定.rs 未引契约常量（生命周期起/止）")
    if not re.search(r"if\s+生命周期广播段\(\s*段\.起(?:\.取\(\))?\s*,\s*段\.止(?:\.取\(\))?\s*\)", 判定rs):
        缺.append("判定.rs 通知号段循环未对广播段 continue（扩展仍会被底座预置占用拦下）")
    elif "continue;" not in 判定rs:
        缺.append("判定.rs 通知号段循环未对广播段 continue（扩展仍会被底座预置占用拦下）")
    if "广播段" not in 载入判定:
        缺.append("载入判定.json 未写明「生命周期段按广播段判」")
    if 缺:
        出.append(违规(名, "契约声明/src/*数据.rs · 判定.rs · 载入判定.json", "；".join(缺),
                       "准入判据 ④（生命周期段按广播段判）：契约常量 · 判定实现 · 载入判定文本三处必须齐。"
                       "缺哪一处都要改对应实现/声明 ⇒ 只能由对应节点补"))
    return 出


def 检查28_准入通知口(上: dict) -> list:
    """㉘ 准入⑤：适配器有通知口，申报了就送得到。"""
    出 = []
    名 = 检查名[27]
    通知口 = _拼(上, "通知口.rs")
    适配器 = _拼(上, ".rs", "跨语言适配/适配器实现/src/")
    缺 = []
    for 记号 in ("pub fn 注册通知端点", "pub fn 请求卸载", "pub fn 延迟释放协商", "pub fn 请求卸载按标识"):
        if 记号 not in 通知口:
            缺.append("通知口.rs 缺 %s" % 记号)
    if "通知.通道.注册(声明.标识串, 函数)" not in 适配器:
        缺.append("适配器装载声明根未把申报的 通知函数 登记成端点（申报了送不到）")
    if 缺:
        出.append(违规(名, "跨语言适配/适配器实现/src/通知口.rs · lib.rs::装载声明根", "；".join(缺),
                       "准入判据 ⑤：通知口四入口齐 + 装载时登记申报的通知函数，缺一处申报就送不到 ⇒ "
                       "只能由适配器实现补"))
    return 出


def 检查29_准入接缝冻结(上: dict) -> list:
    """㉙ 准入⑦：接缝符号名与返回结构裁决定死（明示偏离并写进文档）。"""
    出 = []
    名 = 检查名[28]
    文 = _拼(上, "边界协议.md")
    启动网关 = _拼(上, ".rs", "对外接口面/调用接口面/examples/启动网关")
    声明件 = _读json件(上["仓根"], "扩展根声明.json")
    缺 = []
    if "GetPlatformInfo" not in 文:
        缺.append("边界协议未写我方符号名 GetPlatformInfo")
    if "GetNewInf" not in 文:
        缺.append("边界协议未点名参照实现 GetNewInf（无从判「1:1 还是偏离」）")
    if "不复刻" not in 文 and "偏离" not in 文:
        缺.append("边界协议未明示「偏离/不复刻」")
    if "冻结" not in 文:
        缺.append("边界协议未写「冻结」")
    实现名 = ""
    if 声明件 and isinstance(声明件[0][1], dict):
        实现名 = ((声明件[0][1].get("扫描") or {}).get("找什么")) or ""
    if 实现名 != "GetPlatformInfo":
        缺.append("扩展根声明.扫描.找什么 = %r（应 = GetPlatformInfo）" % 实现名)
    if 'c"GetPlatformInfo"' not in 启动网关:
        缺.append("启动网关未 dlsym GetPlatformInfo")
    if 缺:
        出.append(违规(名, "跨语言适配/边界协议/边界协议.md · 扩展装载/扩展根声明.json · 启动网关", "；".join(缺),
                       "准入判据 ⑦：符号名与返回结构冻结、明示不复刻参照实现、实现侧 dlsym 同名 —— "
                       "三处必须一致 ⇒ 只能由契约/实现侧改"))
    return 出


def 检查30_准入无死键(上: dict) -> list:
    """㉚ 准入⑧：扩展 包声明.json 无死键（提供宿主版本 / 提供内核版本）。"""
    出 = []
    名 = 检查名[29]
    坏 = []
    for 路径, 声 in _读json件(上["仓根"], "包声明.json"):
        if not isinstance(声, dict):
            坏.append("%s 不是合法 JSON" % 路径.name)
            continue
        for 键 in 死键:
            if 键 in 声:
                坏.append("%s 含死键 %s（平台信息无「提供*」字段，无消费者）" % (路径, 键))
    if 坏:
        出.append(违规(名, "%s/**/包声明.json" % "扩展根目录", "；".join(坏),
                       "准入判据 ⑧：扩展侧「提供宿主版本/提供内核版本」是死键（判定 ④ 只拿底座去比）⇒ "
                       "删键只能由扩展声明方做"))
    return 出


def _段含键(文, 段名, 键):
    在段 = False
    for 行 in 文.splitlines():
        净 = 行.strip()
        if 净.startswith("[") and 净.endswith("]"):
            在段 = 净 == "[%s]" % 段名
            continue
        if 在段 and 净.split("=")[0].strip() == 键:
            return True
    return False


def 检查31_准入制品类型(上: dict) -> list:
    """㉛ 准入⑨：扩展 crate-type 只有一条路（扩展仓不声明，装配侧现场编）。"""
    出 = []
    名 = 检查名[30]
    扩展Cargo = _件(上, "Cargo.toml", "扩展根目录" + "/")
    # 落点是**包**不是某个写死的文件（#230）：装配侧的 `--crate-type cdylib` 可能落在
    # `构建制品.py` 路由件里，也可能落在 `构建制品/扩展.py` 这样的子件里 ⇒ 收整包。
    构建制品 = _拼(上, ".py", "构建装配/上线切换/构建制品")
    必备件 = _读json件(上["仓根"], "必备件.json")
    规则 = ""
    if 必备件 and isinstance(必备件[0][1], dict):
        规则 = ((必备件[0][1].get("扩展仓的 crate-type（只有一条路）") or {}).get("判据")) or ""
    坏 = []
    for 键, 文 in 扩展Cargo:
        if _段含键(文, "lib", "crate-type"):
            坏.append("%s 的 [lib] 声明了 crate-type（只许装配侧编）" % 键)
    if "--crate-type" not in 构建制品 or "cdylib" not in 构建制品:
        坏.append("构建制品 未见装配侧 cargo rustc --crate-type cdylib（唯一那条路不在）")
    if 坏:
        出.append(违规(名, "%s/**/Cargo.toml · 构建制品 · 必备件.json" % "扩展根目录", "；".join(坏),
                       "准入判据 ⑨：扩展仓不声明 crate-type、由装配侧现场编（一条路）⇒ "
                       "只能由扩展仓/装配侧改"))
    return 出


def 检查32_准入命令类别(上: dict) -> list:
    """㉜ 准入⑩：命令信息.类别 有「类别号 → 类别名」表。"""
    出 = []
    名 = 检查名[31]
    前缀 = "契约声明/命令类别/"
    类别件 = [(键, 项["数据"]) for 键, 项 in sorted(上["文件"].items())
             if 键.startswith(前缀) and 键.endswith(".json")]
    坏 = []
    for 键, 条 in 类别件:
        if not isinstance(条, dict):
            坏.append("%s 不是合法 JSON" % 键)
            continue
        try:
            应号 = int(键.rsplit("/", 1)[1][:-5])
        except ValueError:
            坏.append("%s 文件名不是类别号" % 键)
            continue
        if 条.get("类别号") != 应号:
            坏.append("%s 类别号 %r != 文件名 %d" % (键, 条.get("类别号"), 应号))
        for 键名 in ("名称", "说明"):
            if not isinstance(条.get(键名), str) or not 条[键名]:
                坏.append("%s 的 %s 空/缺" % (键, 键名))
    if 坏:
        出.append(违规(名, 前缀 + "*.json", "；".join(坏),
                       "准入判据 ⑩：每条命令类别要「文件名 = 类别号」且名称/说明非空 ⇒ "
                       "只能由声明方补"))
    return 出


def 检查33_准入显式顺序(上: dict) -> list:
    """㉝ 准入⑪：号段冲突判定不靠检查顺序的巧合（显式优先级口径）。"""
    出 = []
    名 = 检查名[32]
    文 = _拼文(上["仓根"], "载入判定.json")
    显式 = ("先于" in 文 or "优先级" in 文 or "优先于" in 文)
    点名 = ("号段冲突" in 文) and ("自洽" in 文)
    缺 = []
    if not 显式:
        缺.append("载入判定.json 无「先于/优先级」字样（只有数组顺序 = 隐式，靠实现巧合）")
    if not 点名:
        缺.append("载入判定.json 未同时点名 号段冲突 与 自洽")
    if 缺:
        出.append(违规(名, "扩展装载/载入约定/载入判定.json", "；".join(缺),
                       "准入判据 ⑪：显式写明「号段冲突先于声明自洽」，不许靠数组顺序的巧合 ⇒ "
                       "只能由载入判定文本补"))
    return 出


def 检查34_准入报因(上: dict) -> list:
    """㉞ 准入⑬：装载失败报因（剔除并报原因，不静默）。"""
    出 = []
    名 = 检查名[33]
    文 = _拼(上, ".rs", "对外接口面/调用接口面/examples/启动网关")
    缺 = []
    if "fn 取扩展声明" not in 文 or "Result<&'static 平台信息, String>" not in 文:
        缺.append("启动网关无 取扩展声明 且失败带 String 原因")
    if "剔除的.push" not in 文:
        缺.append("启动网关未把失败落进「剔除」台账")
    if "剔除 {落点}：{原因}" not in 文:
        缺.append("启动网关未把剔除原因打出来")
    if re.search(r"let\s+_\s*=\s*取扩展声明", 文):
        缺.append("启动网关有 `let _ = 取扩展声明`（静默吞因）")
    if 缺:
        出.append(违规(名, "对外接口面/调用接口面/examples/启动网关", "；".join(缺),
                       "准入判据 ⑬：取扩展声明失败要带因、落剔除台账、打印，不许静默吞 ⇒ "
                       "只能由网关实现补"))
    return 出


def 检查35_准入指纹可跑(上: dict) -> list:
    """㉟ 准入⑭：扩展 指纹.json 有一条可跑的（有生成命令 + 脚本存在）重跑命令。

    **不在这里起子进程**：`--自测` 要跑几十遍 `验证`，每遍 spawn 一个解释器会把整条自测
    顶过五秒硬顶（实测）。**真跑**那条读数留在 `准入判据.py`（`--自测` 里跑，退出码 0）——
    本判据只判「命令在、脚本在」这条静态形状，并**如实声明收窄**。
    """
    出 = []
    名 = 检查名[34]
    指纹件 = _读json件(上["仓根"], "指纹.json")
    缺 = []
    if not 指纹件:
        缺.append("扩展目录下无 指纹.json")
    else:
        命 = ""
        if isinstance(指纹件[0][1], dict):
            命 = 指纹件[0][1].get("生成命令", "") or ""
        分 = 命.split()
        脚本 = [片 for 片 in 分 if 片.endswith(".py")]
        目标 = 上["仓根"] / 脚本[0] if 脚本 else None
        if not 命:
            缺.append("指纹.json 无「生成命令」")
        elif not 脚本 or not 目标.exists():
            缺.append("生成命令指向的脚本不存在：%r" % 命)
    if 缺:
        出.append(违规(名, "%s/**/指纹.json" % "扩展根目录", "；".join(缺),
                       "准入判据 ⑭：指纹.json 要有一条可跑的重跑命令（命令 + 脚本都在）⇒ "
                       "只能由扩展方补；真跑那条读数见 `测试验证/准入判据/准入判据.py --自测`"))
    return 出


def 检查36_准入并发(上: dict) -> list:
    """㊱ 准入⑯：适配器 Send/Sync ⇒ 网关能并发取连接。"""
    出 = []
    名 = 检查名[35]
    线程安全 = _拼(上, "线程安全.rs")
    网关 = _拼(上, "网关.rs")
    启动网关 = _拼(上, ".rs", "对外接口面/调用接口面/examples/启动网关")
    缺 = []
    if "unsafe impl Send for 适配器" not in 线程安全:
        缺.append("线程安全.rs 无 unsafe impl Send for 适配器")
    if "unsafe impl Sync for 适配器" not in 线程安全:
        缺.append("线程安全.rs 无 unsafe impl Sync for 适配器")
    if "pub fn 跑并发" not in 网关 or "thread::scope" not in 网关:
        缺.append("网关.rs 无 跑并发 + thread::scope（accept 仍单线程）")
    if "服务.跑服务()" not in 启动网关:
        缺.append("启动网关未走 服务.跑服务()（生产入口没接并发）")
    if 缺:
        出.append(违规(名, "跨语言适配/适配器实现/src/线程安全.rs · 网关.rs · 启动网关", "；".join(缺),
                       "准入判据 ⑯：适配器 Send/Sync 断言在 + 网关跑并发(thread::scope) + 生产入口走它 ⇒ "
                       "只能由适配器/网关实现补"))
    return 出


# ── 对象数（元数据用）：空集 ⇒ 验证面报「未判」，不许当通过 ──
def 对象数_27(上):
    return ((1 if _生成物面(上) else 0)
            + (1 if _拼(上, "判定.rs") else 0)
            + (1 if _拼文(上["仓根"], "载入判定.json") else 0))


def 对象数_28(上):
    return ((1 if _拼(上, "通知口.rs") else 0)
            + (1 if _拼(上, ".rs", "跨语言适配/适配器实现/src/") else 0))


def 对象数_29(上):
    return ((1 if _拼(上, "边界协议.md") else 0)
            + (1 if _读json件(上["仓根"], "扩展根声明.json") else 0)
            + (1 if _拼(上, ".rs", "对外接口面/调用接口面/examples/启动网关") else 0))


def 对象数_30(上):
    return len(_读json件(上["仓根"], "包声明.json"))


def 对象数_31(上):
    必备件 = _读json件(上["仓根"], "必备件.json")
    规则 = ""
    if 必备件 and isinstance(必备件[0][1], dict):
        规则 = ((必备件[0][1].get("扩展仓的 crate-type（只有一条路）") or {}).get("判据")) or ""
    if "crate-type" not in 规则:
        return 0  # 规则无单一事实源 ⇒ 未判，不许当通过
    return len(_件(上, "Cargo.toml", "扩展根目录" + "/"))


def 对象数_32(上):
    return sum(
        1 for 键 in 上["文件"]
        if 键.startswith("契约声明/命令类别/") and 键.endswith(".json")
    )


def 对象数_33(上):
    return 1 if _拼文(上["仓根"], "载入判定.json") else 0


def 对象数_34(上):
    return 1 if _拼(上, ".rs", "对外接口面/调用接口面/examples/启动网关") else 0


def 对象数_35(上):
    return len(_读json件(上["仓根"], "指纹.json"))


def 对象数_36(上):
    return ((1 if _拼(上, "线程安全.rs") else 0)
            + (1 if _拼(上, "网关.rs") else 0)
            + (1 if _拼(上, ".rs", "对外接口面/调用接口面/examples/启动网关") else 0))
