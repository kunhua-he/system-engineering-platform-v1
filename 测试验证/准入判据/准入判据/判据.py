"""判据 —— 机器可判的 10 条：每条一个纯函数 `世界 → (判定, 证据, 对象数)`。

判定 ∈ {"通过", "失败", "未判"}。
"""

import re
import subprocess
import sys

from .世界 import 世界, 读JSON


def 判_4(世: 世界):
    """④ 扩展能申报生命周期通知号段（生命周期段按广播段判）。"""
    缺 = []
    范围源 = re.search(r"生命周期起:\s*u32\s*=\s*(\d+).*?生命周期止:\s*u32\s*=\s*(\d+)",
                     世.生成物面, re.S)
    if not 范围源:
        缺.append("契约生成物无 生命周期起/止（唯一来源）")
    else:
        起, 止 = int(范围源.group(1)), int(范围源.group(2))
        if (起, 止) != (2000, 2999):
            缺.append(f"生命周期段不是 2000–2999（实际 {起}–{止}）")
    # 判定.rs 必须用契约常量，不许把 2000/2999 抄成本地常量
    if "fn 生命周期广播段" not in 世.判定rs:
        缺.append("判定.rs 无 fn 生命周期广播段")
    if "通知号段::生命周期起" not in 世.判定rs or "通知号段::生命周期止" not in 世.判定rs:
        缺.append("判定.rs 未引契约常量（生命周期起/止）")
    # 广播段跳过那一处：`段` 是号段切片给的包装型，字段要 `.取()` 才是 `u32`
    # （2026-09-27 实测：判定.rs 写成 `生命周期广播段(段.起.取(), 段.止.取())`）。
    # 判据的**意图**是「通知号段循环对广播段 continue」，不是某个字面写法 ⇒ 用正则吃两种形，
    # 不许因一个 `.取()` 就假红（判据自己写窄 = 假红，比漏判更费时间）。
    if not re.search(
        r"if\s+生命周期广播段\(\s*段\.起(?:\.取\(\))?\s*,\s*段\.止(?:\.取\(\))?\s*\)",
        世.判定rs,
    ):
        缺.append("判定.rs 通知号段循环未对广播段 continue（扩展仍会被底座预置占用拦下）")
    elif "continue;" not in 世.判定rs:
        缺.append("判定.rs 通知号段循环未对广播段 continue（扩展仍会被底座预置占用拦下）")
    if "广播段" not in 世.载入判定文:
        缺.append("载入判定.json 未写明「生命周期段按广播段判」")
    对象数 = 3  # 生成物面 · 判定.rs · 载入判定.json
    if 缺:
        return "失败", "；".join(缺), 对象数
    return "通过", "广播段口径三处齐（契约常量 · 判定实现 · 载入判定文本）", 对象数


def 判_5(世: 世界):
    """⑤ 适配器有通知口，申报了就送得到。"""
    缺 = []
    for 记号 in ["pub fn 注册通知端点", "pub fn 请求卸载", "pub fn 延迟释放协商",
               "pub fn 请求卸载按标识"]:
        if 记号 not in 世.通知口:
            缺.append(f"通知口.rs 缺 {记号}")
    if "通知.通道.注册(声明.标识串, 函数)" not in 世.适配器lib:
        缺.append("适配器装载声明根未把申报的 通知函数 登记成端点（申报了送不到）")
    对象数 = 2  # 通知口.rs · 适配器 lib.rs
    if 缺:
        return "失败", "；".join(缺), 对象数
    return "通过", "通知口四入口齐 + 装载时登记申报的 通知函数", 对象数


def 判_7(世: 世界):
    """⑦ 接缝符号名与返回结构裁决定死（明示偏离并写进文档）。"""
    缺 = []
    文 = 世.边界协议
    if "GetPlatformInfo" not in 文:
        缺.append("边界协议未写我方符号名 GetPlatformInfo")
    if "GetNewInf" not in 文:
        缺.append("边界协议未点名参照实现 GetNewInf（无从判「1:1 还是偏离」）")
    if "不复刻" not in 文 and "偏离" not in 文:
        缺.append("边界协议未明示「偏离/不复刻」")
    if "冻结" not in 文:
        缺.append("边界协议未写「冻结」")
    # 实现侧必须 dlsym 的正是这个冻结名
    实现名 = (世.扩展根声明.get("扫描") or {}).get("找什么", "")
    if 实现名 != "GetPlatformInfo":
        缺.append(f"扩展根声明.扫描.找什么 = {实现名!r}（应 = GetPlatformInfo）")
    if 'c"GetPlatformInfo"' not in 世.启动网关:
        缺.append("启动网关.rs 未 dlsym GetPlatformInfo")
    对象数 = 3  # 边界协议.md · 扩展根声明.json · 启动网关.rs
    if 缺:
        return "失败", "；".join(缺), 对象数
    return "通过", "符号名 GetPlatformInfo 冻结 · 明示不复刻 GetNewInf · 实现侧 dlsym 同名", 对象数


死键 = ["提供宿主版本", "提供内核版本"]


def 判_8(世: 世界):
    """⑧ 扩展 包声明.json 无死键（提供宿主版本 / 提供内核版本）。"""
    对象数 = len(世.包声明表)
    if 对象数 == 0:
        return "未判", "扩展根目录下 0 份 包声明.json（空集不算通过）", 0
    坏 = []
    for 路, 声 in 世.包声明表:
        if not isinstance(声, dict):
            坏.append(f"{路.name} 不是合法 JSON")
            continue
        for 键 in 死键:
            if 键 in 声:
                坏.append(f"{路} 含死键 {键}（平台信息无「提供*」字段，无消费者）")
    if 坏:
        return "失败", "；".join(坏), 对象数
    return "通过", f"{对象数} 份扩展声明均无死键", 对象数


def 判_9(世: 世界):
    """⑨ 扩展 crate-type 只有一条路（扩展仓不声明，装配侧现场编）。"""
    对象数 = len(世.扩展Cargo表)
    规则 = (世.必备件.get("扩展仓的 crate-type（只有一条路）") or {}).get("判据", "")
    if "crate-type" not in 规则:
        return "未判", "必备件.json 未定死 crate-type 规则（规则无单一事实源）", 对象数
    if 对象数 == 0:
        return "未判", "扩展根目录下 0 份扩展 Cargo.toml（空集不算通过）", 0
    坏 = []
    for 路, 文 in 世.扩展Cargo表:
        if 段含键(文, "lib", "crate-type"):
            坏.append(f"{路} 的 [lib] 声明了 crate-type（只许装配侧编）")
    if "--crate-type" not in 世.构建制品 or "cdylib" not in 世.构建制品:
        坏.append("构建制品.py 未见装配侧 cargo rustc --crate-type cdylib（唯一那条路不在）")
    if 坏:
        return "失败", "；".join(坏), 对象数
    return "通过", f"{对象数} 份扩展 Cargo.toml 均未声明 crate-type · 装配侧现场编在", 对象数


def 段含键(文: str, 段名: str, 键: str) -> bool:
    """粗判 TOML：段 [段名] 到下一个 [ 之间是否出现 键。"""
    行 = 文.splitlines()
    在段 = False
    for 行文 in 行:
        净 = 行文.strip()
        if 净.startswith("[") and 净.endswith("]"):
            在段 = 净 == f"[{段名}]"
            continue
        if 在段 and 净.split("=")[0].strip() == 键:
            return True
    return False


def 判_10(世: 世界):
    """⑩ 命令信息.类别 有「类别号 → 类别名」表。"""
    对象数 = len(世.命令类别)
    if 对象数 == 0:
        return "未判", "契约声明/命令类别/ 为空（机制在、值域未裁 —— 空集不算通过）", 0
    坏 = []
    for 路 in 世.命令类别:
        条 = 读JSON(路)
        if not isinstance(条, dict):
            坏.append(f"{路.name} 不是合法 JSON")
            continue
        try:
            应号 = int(路.stem)
        except ValueError:
            坏.append(f"{路.name} 文件名不是类别号")
            continue
        if 条.get("类别号") != 应号:
            坏.append(f"{路.name} 类别号 {条.get('类别号')!r} != 文件名 {应号}")
        for 键 in ["名称", "说明"]:
            if not isinstance(条.get(键), str) or not 条[键]:
                坏.append(f"{路.name} 的 {键} 空/缺")
    if 坏:
        return "失败", "；".join(坏), 对象数
    return "通过", f"{对象数} 条类别号→名映射齐", 对象数


def 判_11(世: 世界):
    """⑪ 号段冲突判定不靠检查顺序的巧合（显式优先级口径）。"""
    文 = 世.载入判定文
    对象数 = 1
    显式 = ("先于" in 文 or "优先级" in 文 or "优先于" in 文)
    点名 = ("号段冲突" in 文) and ("自洽" in 文)
    if 显式 and 点名:
        return "通过", "载入判定.json 显式写明「号段冲突先于声明自洽」", 对象数
    缺 = []
    if not 显式:
        缺.append("载入判定.json 无「先于/优先级」字样（只有数组顺序 = 隐式，靠实现巧合）")
    if not 点名:
        缺.append("载入判定.json 未同时点名 号段冲突 与 自洽")
    return "失败", "；".join(缺), 对象数


def 判_13(世: 世界):
    """⑬ 装载失败报因（剔除并报原因，不静默）。"""
    缺 = []
    文 = 世.启动网关
    if "fn 取扩展声明" not in 文 or "Result<&'static 平台信息, String>" not in 文:
        缺.append("启动网关.rs 无 取扩展声明 且失败带 String 原因")
    if "剔除的.push" not in 文:
        缺.append("启动网关.rs 未把失败落进「剔除」台账")
    if "剔除 {落点}：{原因}" not in 文:
        缺.append("启动网关.rs 未把剔除原因打出来")
    if re.search(r"let\s+_\s*=\s*取扩展声明", 文):
        缺.append("启动网关.rs 有 `let _ = 取扩展声明`（静默吞因）")
    对象数 = 1
    if 缺:
        return "失败", "；".join(缺), 对象数
    return "通过", "取扩展声明失败带因 → 落剔除台账 → 打印；无静默吞因", 对象数


def 判_14(世: 世界):
    """⑭ 扩展 指纹.json 有一条**可跑的**重跑命令，且跑得出「一致」。"""
    命 = (读JSON(世.指纹件()) or {}).get("生成命令", "")
    脚本 = 世.指纹脚本()
    if not 命 or not 脚本.exists():
        return "未判", f"生成命令不可跑（命令={命!r} · 脚本在={脚本.exists()}）", 1
    try:
        果 = subprocess.run(
            [sys.executable, str(脚本), "--检查"],
            cwd=str(世.仓根), capture_output=True, text=True, timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as 错:
        return "未判", f"重跑命令跑不起来：{错}", 1
    if 果.returncode == 0:
        return "通过", "生成命令可跑 · --检查 退出码 0（指纹与盘面一致）", 1
    return "失败", f"生成命令可跑，但 --检查 退出码 {果.returncode}（指纹与盘面不符=制品滞后）：{果.stdout.strip() or 果.stderr.strip()}", 1


def 判_16(世: 世界):
    """⑯ 适配器 Send/Sync ⇒ 网关能并发 accept。"""
    缺 = []
    if "unsafe impl Send for 适配器" not in 世.线程安全:
        缺.append("线程安全.rs 无 unsafe impl Send for 适配器")
    if "unsafe impl Sync for 适配器" not in 世.线程安全:
        缺.append("线程安全.rs 无 unsafe impl Sync for 适配器")
    if "pub fn 跑并发" not in 世.网关 or "thread::scope" not in 世.网关:
        缺.append("网关.rs 无 跑并发 + thread::scope（accept 仍单线程）")
    if "服务.跑()" not in 世.启动网关:
        缺.append("启动网关.rs 未走 服务.跑()（生产入口没接并发）")
    对象数 = 3
    if 缺:
        return "失败", "；".join(缺), 对象数
    return "通过", "适配器 Send/Sync 断言在 · 网关 跑并发(thread::scope) · 生产入口走它", 对象数
