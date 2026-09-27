# -*- coding: utf-8 -*-
"""MCP 工具实现 —— 三个：**门禁** · **符号** · **替换**。

**为什么要有 MCP，而不是「仓里放几个脚本」**（华哥 2026-09-27 原话）：
「封装工具是没用的，agent 天然的弱点。只有 mcp 这种强制协议才不会漂移。如果不用强制协议，
本质上就算放了一大堆工具给你都没用。很少会用上的」—— 本仓自己就是这条的实证：
一腿一工作树与认领机制「**已在药柜、从未吃过**」，直到有人强制用它们才生效。
故本件把三条命令**变成工具表里的工具**（协议强制出现，不靠记性）。

**它是适配层，不是能力**（老仓 `支持库/后端/代码解析支持库/代码地图/说明/设计说明.md` §2）：
三个工具都只**转发**仓内已有的入口，零业务逻辑、零第二套实现（老仓 1.3「结果唯一即收口」）。
底座不调它、判据面不依赖它 —— 退掉它（删插件）其余一切照跑。

**写操作必须过认领机制**：`替换` 的 `应用` 模式先查 `开发工具/认领机制/账本.json` ——
有活跃租约时必须指名腿，且目标路径必须全在该腿的路径集里，否则**拒**（fail-closed）。
这条是 MCP 与「自由批量替换」的分界：改动作不是风险，**绕过所有权**才是。
"""

import json
import subprocess
import sys
from pathlib import Path

超时秒 = 5


def 跑(命令, 仓根, 超时=超时秒):
    """跑一条命令 ⇒ `(退出码, 合并输出)`。超时给退出码 `-1`（不许当成通过）。"""
    try:
        完 = subprocess.run(命令, cwd=str(仓根), capture_output=True, text=True, timeout=超时)
    except subprocess.TimeoutExpired:
        return -1, "超时（%d 秒）—— 五秒硬顶无例外，先查是哪一段慢" % 超时
    except OSError as 错:
        return -2, "起不了：%r" % (错,)
    return 完.returncode, (完.stdout or "") + (完.stderr or "")


# ── 工具一：门禁（一键编译 + 全量门禁）───────────────────────────────────────────────────

def 门禁(参数, 仓根):
    """跑 `构建装配/一键验证/闸0.py`（闸 1 声明侧 + 闸 2 实现侧并排读数）⇒ 退出码 + 读数。"""
    命令 = [sys.executable, str(仓根 / "构建装配" / "一键验证" / "闸0.py")]
    if 参数.get("自测"):
        命令 = [sys.executable, str(仓根 / "构建装配" / "一键验证" / "一键验证.py"), "--自测"]
    码, 出 = 跑(命令, 仓根)
    行 = [行 for 行 in 出.splitlines() if 行.strip() and "─" not in 行]
    return 码, "退出码 %d\n%s" % (码, "\n".join(行[-30:]))


# ── 工具二：符号（代码地图查/引用）────────────────────────────────────────────────────────

def _索引(仓根):
    """读代码地图的预建索引 ⇒ `(索引, 错误)`。索引不在 ⇒ 报「先建」而不是报空。"""
    if str(仓根 / "开发工具") not in sys.path:
        sys.path.insert(0, str(仓根 / "开发工具"))
    from 代码地图 import 索引 as 模块
    路 = 模块.索引路径()
    if not Path(路).is_file():
        return None, "还没有索引 ⇒ 先跑 `python3 开发工具/代码地图.py 建`（落点 %s）" % 路
    return 模块.读索引(Path(路), 仓根), None


def 符号(参数, 仓根):
    """按关键词查符号，或按**限定名精确**查它出现在哪几处（定义 + 引用）。"""
    索引, 错 = _索引(仓根)
    if 错:
        return 1, 错
    if str(仓根 / "开发工具") not in sys.path:
        sys.path.insert(0, str(仓根 / "开发工具"))
    from 代码地图 import 索引 as 模块

    限定名 = str(参数.get("限定名") or "")
    if 限定名:
        命中 = 模块.引用(索引, 限定名)
        出 = ["`%s` 出现 %d 处：" % (限定名, sum(len(符["出现"]) for 符 in 命中))]
        for 符 in 命中:
            for 路, 行, 列 in 符["出现"]:
                出.append("  %s:%d:%d" % (路, 行, 列))
        return 0, "\n".join(出)

    关键词 = str(参数.get("关键词") or "")
    if not 关键词:
        return 2, "缺 `关键词`（查符号）或 `限定名`（查出现位置）"
    命中 = 模块.查(索引, 关键词, 上限=int(参数.get("上限") or 40))
    出 = ["命中 %d 个符号（索引 %d 行 · %d 文档）" % (len(命中), 索引["行数"], 索引["文档数"])]
    for 符 in 命中:
        位 = " · ".join("%s:%d" % (路, 行) for 路, 行 in 符["定义"]) or "（无定义位置）"
        出.append("  %s  %s  [出现 %d 处]" % (模块.名字(符), 位, len(符["出现"])))
    return 0, "\n".join(出)


# ── 工具三：替换（**符号级**批量替换）─────────────────────────────────────────────────────

def _租约(仓根):
    """读认领账本 ⇒ 租约列表；读不出 ⇒ `None`（**判不了**，不是「没有租约」）。"""
    账 = 仓根 / "开发工具" / "认领机制" / "账本.json"
    try:
        数据 = json.loads(账.read_text(encoding="utf-8"))
    except Exception:
        return None
    租约 = 数据.get("租约")
    return 租约 if isinstance(租约, list) else None


def _放行(仓根, 路径集, 腿):
    """写操作的所有权闸 ⇒ `(允许?, 说明)`。**有活跃租约就必须指名腿**（fail-closed）。"""
    租约 = _租约(仓根)
    if 租约 is None:
        return False, "读不出认领账本 ⇒ 判不了（不许当成「没有租约」）"
    活跃 = [条 for 条 in 租约 if 条.get("到期时间")]
    if not 活跃:
        return True, "账本里 0 条活跃租约 ⇒ 放行（无人认领 = 无争用）"
    if not 腿:
        return False, "有 %d 条活跃租约 ⇒ 必须给 `腿`（否则不知道这次改动算谁的）" % len(活跃)
    我的 = [条 for 条 in 活跃 if 条.get("腿标识") == 腿]
    if not 我的:
        return False, "账本里没有腿 `%s` 的活跃租约" % 腿
    认领集 = set(我的[0].get("路径集") or [])
    越界 = sorted(件 for 件 in 路径集 if 件 not in 认领集)
    if 越界:
        return False, "这些路径不在腿 `%s` 的认领集里 ⇒ 拒：%s" % (腿, " · ".join(越界))
    return True, "腿 `%s` 的认领集覆盖全部 %d 个目标件" % (腿, len(路径集))


def _按列换(行, 列, 旧名, 新名):
    """按 **UTF-16 列**换掉行内一段（LSIF 的 `positionEncoding` 是 utf-16）。
    切出来的文本不等于 `旧名` ⇒ 返回 `None`（**fail-closed**：位置漂了就不猜）。"""
    单位 = 行.encode("utf-16-le")
    起 = 列 * 2
    旧字节 = 旧名.encode("utf-16-le")
    段 = 单位[起:起 + len(旧字节)]
    if 段 != 旧字节:
        return None
    return (单位[:起] + 新名.encode("utf-16-le") + 单位[起 + len(旧字节):]).decode("utf-16-le")


def 替换(参数, 仓根):
    """把某个符号的**全部出现位置**（定义 + 引用，由索引给出）换成新名。默认 dry-run。

    与文本替换的分界：本工具只动**索引认得的那几处**，不动字符串 / 注释 / 同名别的符号。
    """
    限定名 = str(参数.get("限定名") or "")
    新名 = str(参数.get("新名") or "")
    应用 = bool(参数.get("应用"))
    if not 限定名 or not 新名:
        return 2, "缺 `限定名` 或 `新名`"
    旧名 = 限定名.rsplit("::", 1)[-1]
    索引, 错 = _索引(仓根)
    if 错:
        return 1, 错
    if str(仓根 / "开发工具") not in sys.path:
        sys.path.insert(0, str(仓根 / "开发工具"))
    from 代码地图 import 索引 as 模块
    命中 = [符 for 符 in 模块.引用(索引, 限定名) if 符["出现"]]
    if not 命中:
        return 1, "索引里没有 `%s`（先建索引；或换用限定名 —— 用 `符号` 工具查）" % 限定名
    位置 = sorted({位 for 符 in 命中 for 位 in 符["出现"]})
    按件 = {}
    for 路, 行, 列 in 位置:
        按件.setdefault(路, []).append((行, 列))

    头 = ["`%s` → `%s`：%d 处，落在 %d 个件" % (旧名, 新名, len(位置), len(按件))]
    for 路 in sorted(按件):
        头.append("  %s × %d" % (路, len(按件[路])))

    if not 应用:
        return 0, "\n".join(头 + ["", "**dry-run**（没改任何文件）。要真改：`应用: true`"
                                  "（有活跃租约时还要给 `腿`）。"])

    放, 说明 = _放行(仓根, sorted(按件), 参数.get("腿"))
    if not 放:
        return 3, "\n".join(头 + ["", "**拒**（所有权闸）：%s" % 说明])

    改过, 拒 = [], []
    for 路 in sorted(按件):
        文件 = 仓根 / 路
        原行 = 文件.read_text(encoding="utf-8").split("\n")
        # 同一行多处 ⇒ 从右往左换（否则前列会挪位）。
        for 行号, 列 in sorted(按件[路], reverse=True):
            新行 = _按列换(原行[行号 - 1], 列, 旧名, 新名)
            if 新行 is None:
                拒.append("%s:%d:%d（切出的文本不是 `%s` ⇒ 位置漂了）" % (路, 行号, 列, 旧名))
                continue
            原行[行号 - 1] = 新行
        if 拒:
            continue
        文件.write_text("\n".join(原行), encoding="utf-8")
        改过.append(路)
    if 拒:
        return 4, "\n".join(头 + ["", "**拒绝**（fail-closed，未写入任何文件）："] + 拒)
    return 0, "\n".join(头 + ["", "**已改 %d 个件**。%s" % (len(改过), 说明),
                              "接着跑 `门禁` 工具验（索引已过期，要重跑 `代码地图.py 建`）。"])


工具表 = {
    "v1_门禁": (门禁, "跑本仓的一键门禁（闸 0：闸 1 声明侧 + 闸 2 实现侧），返回退出码与读数。"
                      "`自测: true` 改跑反向样本自检。", {
        "type": "object",
        "properties": {"自测": {"type": "boolean", "description": "跑反向样本自检而不是闸 0"}},
    }),
    "v1_符号": (符号, "查本仓代码地图的**预建符号索引**（不是文本匹配）：给 `关键词` 查符号；"
                      "给 `限定名` 查它的全部出现位置（定义 + 引用，带路径:行:列）。", {
        "type": "object",
        "properties": {
            "关键词": {"type": "string", "description": "符号名 / 限定名 / 路径的子串"},
            "限定名": {"type": "string", "description": "限定名（精确），查它的全部出现位置"},
            "上限": {"type": "integer", "description": "最多返回几条（默认 40）"},
        },
    }),
    "v1_替换": (替换, "**符号级**批量替换：只动索引认得的那几处（定义 + 引用），"
                      "不动字符串 / 注释 / 同名别的符号。默认 dry-run；`应用: true` 才写盘，"
                      "写盘前过认领机制的所有权闸（有活跃租约时须给 `腿`）。", {
        "type": "object",
        "properties": {
            "限定名": {"type": "string", "description": "要改的符号的限定名"},
            "新名": {"type": "string", "description": "新名字（末段）"},
            "应用": {"type": "boolean", "description": "true 才真写盘（默认 false = dry-run）"},
            "腿": {"type": "string", "description": "腿标识（有活跃租约时必填，用于所有权校验）"},
        },
        "required": ["限定名", "新名"],
    }),
}
