# -*- coding: utf-8 -*-
"""反向样本：往干净合成仓里注入一处该抓的违规。"""

from __future__ import annotations

import json
from pathlib import Path

# 按关注点分出去的两组（再导出，调用地址逐字不变）
from .注入_号段 import 注入_资源号段挖洞, 注入_命名空间边界缺一节, 注入_类型标签越内核段  # noqa: F401
from .注入_行数 import 注入_单文件超行数, 注入_存量还在长, 注入_基线陈旧登记, 注入_基线缩水登记
from .注入_命名 import 注入_序数代称作标识符, 注入_单西文字母, 注入_形参单字, 注入_局部单字, 注入_局部单字_其余形状, 注入_下划线单字, 注入_数量代称, 注入_命名基线陈旧登记
from .注入_时间口径 import 注入_墙钟算耗时, 注入_单位没进名字
from .注入_散文 import 注入_散文落忽略目录
from .注入_入口覆盖 import 注入_入口无壳不在白名单
from .注入_运行数据 import 注入_自拼运行数据路径
from .注入_落点 import 注入_判据落点悬空
from .注入_台账号 import 注入_台账号引用  # noqa: F401
from .注入_引用 import 注入_引用不存在节  # noqa: F401
from .注入_十干 import 注入_字面十干  # noqa: F401
from .注入_命名穷举 import 注入_未登记名  # noqa: F401

from . import 常量

from .判据元数据 import _样本_编号文件, 判据元数据
from .常量 import 临时目录前缀, 契约目录名


# ════════════════════════════════════════════════════════════════════════════
# 自测：每条判据的身份证（反向样本 + 正向样本）
#
# 反向样本全部注入到**干净合成仓**上——不依赖仓库现状，所以可重复。
# 正向样本就是干净合成仓本身：不注入时，所有判据都必须通过。
# ════════════════════════════════════════════════════════════════════════════


def 注入_文件名与字段不一致(临根: Path) -> str:
    """类型声明/0000.json 的 类型标签 改成 9（文件名还是 0000）。"""
    路径 = 临根 / 契约目录名 / "类型声明" / "0000.json"
    数据 = json.loads(路径.read_text(encoding="utf-8"))
    数据["类型标签"] = 9
    路径.write_text(json.dumps(数据, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return "契约声明/类型声明/0000.json"


def 注入_类型标签重复(临根: Path) -> str:
    """新增 类型声明/1.json（与 0000.json 是同一个号，文件名拼写不同）。"""
    目录 = 临根 / 契约目录名 / "类型声明"
    (目录 / "1.json").write_text(
        (目录 / "0000.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    return "契约声明/类型声明/1.json"


def 注入_作废号又活跃(临根: Path) -> str:
    """把 能力声明/9001.json 的号（9001）按**能力空间**写进 作废号表.json。

    作废行按号空间分账（`号空间: "能力"`）：只比**同空间**的号 —— 缺了 `号空间`，
    这一行会被判「号空间认不出」而报红，但那报的不是本条要抓的「活跃号又被作废」。
    """
    路径 = 临根 / 契约目录名 / "作废号表.json"
    数据 = json.loads(路径.read_text(encoding="utf-8"))
    数据["作废"] = [
        {"编号": 9001, "原名称": "旧样例能力", "作废于": "2026-09-27", "原因": "样例",
         "号空间": "能力"}
    ]
    路径.write_text(json.dumps(数据, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return "契约声明/作废号表.json"


def 注入_号段图相交(临根: Path) -> str:
    """把 号段图.json 的能力号段第 2 段改成 7000–7999，与模块段完全重叠。"""
    路径 = 临根 / 契约目录名 / "号段图.json"
    数据 = json.loads(路径.read_text(encoding="utf-8"))
    数据["能力号段"][1]["起"] = 7000
    数据["能力号段"][1]["止"] = 7999
    路径.write_text(json.dumps(数据, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return "契约声明/号段图.json"


def 注入_占用越布局(临根: Path) -> str:
    """把 平台声明.json 的能力号段改成 [(0,999),(6900,7100)]——第二段跨了两个布局段。"""
    路径 = 临根 / 契约目录名 / "平台声明.json"
    数据 = json.loads(路径.read_text(encoding="utf-8"))
    数据["能力号段"] = [{"起": 0, "止": 999}, {"起": 6900, "止": 7100}]
    路径.write_text(json.dumps(数据, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return "契约声明/平台声明.json"


def 注入_参数类型不在表里(临根: Path) -> str:
    """能力声明/9001.json 的参数表加一行，类型标签 77 在类型表里查不到。"""
    路径 = 临根 / 契约目录名 / "能力声明" / "9001.json"
    数据 = json.loads(路径.read_text(encoding="utf-8"))
    数据["参数表"] = [{"名称": "样例参数", "说明": "样例", "类型标签": 77, "状态位": 0}]
    路径.write_text(json.dumps(数据, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return "契约声明/能力声明/9001.json"


def 注入_返回类型不在表里(临根: Path) -> str:
    """能力声明/9001.json 的 返回类型 改成 88（类型表里没有）。"""
    路径 = 临根 / 契约目录名 / "能力声明" / "9001.json"
    数据 = json.loads(路径.read_text(encoding="utf-8"))
    数据["返回类型"] = 88
    路径.write_text(json.dumps(数据, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return "契约声明/能力声明/9001.json"


def 注入_错误码业务登记项缺一(临根: Path) -> str:
    """删掉 错误码表/0001.json 的 需人工，并把 可自愈 改成 null。"""
    路径 = 临根 / 契约目录名 / "错误码表" / "0001.json"
    数据 = json.loads(路径.read_text(encoding="utf-8"))
    数据.pop("需人工", None)
    数据["可自愈"] = None
    路径.write_text(json.dumps(数据, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return "契约声明/错误码表/0001.json"


def 注入_作废的码又活跃(临根: Path) -> str:
    """把 错误码表/0001.json 的码写进 作废号表.json，而那份活跃声明不撤。

    这是**错误码**这一路（原样本 `作废号又活跃` 走的是类型声明）：作废一个码必须同时把
    `错误码表/<码>.json` 撤下，否则「作废的码」还留在表里、还能被抛出去。
    `号空间: "错误码"` 是「这个号在错误码空间里作废」的依据 —— 缺了它，码 1 会被当成
    能力号 1 一起封（实测的假冲突）。
    """
    路径 = 临根 / 契约目录名 / "作废号表.json"
    数据 = json.loads(路径.read_text(encoding="utf-8"))
    数据["作废"] = [
        {"编号": 1, "原名称": "样例错误", "作废于": "2026-09-27", "原因": "样例",
         "号空间": "错误码"}
    ]
    路径.write_text(json.dumps(数据, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return "契约声明/错误码表/0001.json"


def 注入_作废的类型标签又活跃(临根: Path) -> str:
    """把 类型声明/0000.json 的标签（0）按**类型空间**写进 作废号表.json，而那份活跃声明不撤。

    这是**类型**这一路（另两条样本 `作废号又活跃` 走能力、`作废的码又活跃` 走错误码）。
    它证明**类型空间真被检查 3 覆盖**：`号空间: "类型"` 不在 `号空间到目录` 里时，这一行会被
    **静默跳过** —— 类型声明掉出覆盖，只靠「标签撞作废号」被顺带覆盖（
    那是跨空间比较，本身就是缺陷）。类型标签是独立空间（`字段名册与引用方式.md` §五
    「与上面四个不通」），故补成第五个号空间后，`类型声明/` 必须对到 `类型` 空间。
    """
    路径 = 临根 / 契约目录名 / "作废号表.json"
    数据 = json.loads(路径.read_text(encoding="utf-8"))
    数据["作废"] = [
        {"编号": 0, "原名称": "旧空类型", "作废于": "2026-09-27", "原因": "样例",
         "号空间": "类型"}
    ]
    路径.write_text(json.dumps(数据, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return "契约声明/类型声明/0000.json"


def 注入_作废行缺号空间(临根: Path) -> str:
    """作废行**不写** `号空间`（退回「全局排除」口径）。

    这是「号空间互不相通」的反向样本：缺 `号空间` 的行必须当场报红 —— 否则它会
    退化成「一个号在五个空间一起封」，正是实测的假冲突（错误码 16 去封能力号 16）。
    """
    路径 = 临根 / 契约目录名 / "作废号表.json"
    数据 = json.loads(路径.read_text(encoding="utf-8"))
    数据["作废"] = [
        {"编号": 1, "原名称": "样例错误", "作废于": "2026-09-27", "原因": "样例"}
    ]
    路径.write_text(json.dumps(数据, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return "契约声明/作废号表.json"


def 注入_可抛错误码引用作废码(临根: Path) -> str:
    """能力声明/9001.json 的可抛错误码指向一个**已作废**的码 16（错误码表里已无该码）。"""
    作废路径 = 临根 / 契约目录名 / "作废号表.json"
    作废 = json.loads(作废路径.read_text(encoding="utf-8"))
    作废["作废"] = [
        {"编号": 16, "原名称": "类型标签未显式", "作废于": "2026-09-27", "原因": "样例",
         "号空间": "错误码"}
    ]
    作废路径.write_text(json.dumps(作废, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    路径 = 临根 / 契约目录名 / "能力声明" / "9001.json"
    数据 = json.loads(路径.read_text(encoding="utf-8"))
    数据["可抛错误码"] = [16]
    路径.write_text(json.dumps(数据, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return "契约声明/能力声明/9001.json"


def 注入_通知号越方向(临根: Path) -> str:
    """把 通知号段/2000.json 的通知号改成 1500（落在上行段），方向仍是 下行。"""
    目录 = 临根 / 契约目录名 / "通知号段"
    数据 = json.loads((目录 / "2000.json").read_text(encoding="utf-8"))
    数据["通知号"] = 1500
    文本 = json.dumps(数据, ensure_ascii=False, indent=2) + "\n"
    (目录 / "1500.json").write_text(文本, encoding="utf-8")
    (目录 / "2000.json").unlink()
    return "契约声明/通知号段/1500.json"


def 注入_冻结落点不存在(临根: Path) -> str:
    """冻结项 落点 指向一个不存在的文件。"""
    路径 = 临根 / 契约目录名 / "冻结登记.json"
    数据 = json.loads(路径.read_text(encoding="utf-8"))
    数据["冻结项"][0]["落点"] = "契约声明/src/没有这个文件.rs::平台信息"
    路径.write_text(json.dumps(数据, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return "契约声明/冻结登记.json"


def 注入_冻结形状被改(临根: Path) -> str:
    """把 平台信息 的 `目标字宽` 类型由 `u16` 改成 `u32`（形状变了、指纹必不符）。

    只改**声明文本**里的一个类型名 ⇒ 判据 ⑨ 的 `形状指纹` 比对必红（反向样本：
    证明那条比对不是空转）。别的判据同时红是正常的（样本按 (样本名, 判据名) 定位）。
    """
    路径 = 临根 / 契约目录名 / "src" / "lib.rs"
    文本 = 路径.read_text(encoding="utf-8")
    改后 = 文本.replace("pub 目标字宽: u16,", "pub 目标字宽: u32,", 1)
    assert 改后 != 文本, "样本前置条件不成立：契约声明/src/lib.rs 里没有 `pub 目标字宽: u16,`"
    路径.write_text(改后, encoding="utf-8")
    return "契约声明/src/lib.rs"


def 注入_段类型号越界(临根: Path) -> str:
    """新增段类型号写成 `256` —— 盘面段类型是 u8，`256` 装不下（这正是历史上写错的那个号）。"""
    路径 = 临根 / 契约目录名 / "冻结登记.json"
    数据 = json.loads(路径.read_text(encoding="utf-8"))
    数据["段类型号登记"]["新增"]["接口说明段"] = 256
    路径.write_text(json.dumps(数据, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return "契约声明/冻结登记.json"


def 注入_段类型号撞已占用(临根: Path) -> str:
    """新增段类型号撞上参照实现已占用的号（`3` = 程序段）—— 那就不是「不动旧段」了。"""
    路径 = 临根 / 契约目录名 / "冻结登记.json"
    数据 = json.loads(路径.read_text(encoding="utf-8"))
    数据["段类型号登记"]["新增"]["指纹段"] = 3
    路径.write_text(json.dumps(数据, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return "契约声明/冻结登记.json"


def 注入_运行数据落源码树(临根: Path) -> str:
    """在仓里造一个 `日志/` 目录（运行数据落源码树）⇒ 判据 ⑳ 当场红。"""
    路径 = 临根 / "日志"
    路径.mkdir(parents=True, exist_ok=True)
    (路径 / "今天.log").write_text("样例运行日志\n", encoding="utf-8")
    return "日志"


def 注入_手写平台信息(临根: Path) -> str:
    """在底座一个 crate 里塞一处字段值全手写的 平台信息 构造点。"""
    路径 = 临根 / "运行内核" / "资源网关口" / "src" / "lib.rs"
    路径.write_text(
        路径.read_text(encoding="utf-8")
        + "static 手写声明: 静态 = 静态(平台信息 {\n"
        + "    目标字宽: 64,\n"
        + '    名称: b"手写".as_ptr(),\n'
        + "});\n",
        encoding="utf-8",
    )
    return "运行内核/资源网关口/src/lib.rs"


def 注入_第二处导出(临根: Path) -> str:
    """再导出一个 C ABI 符号——宿主侧对外边界多一个，就是第二条腿的形状。"""
    路径 = 临根 / "运行内核" / "实例状态" / "src" / "lib.rs"
    路径.parent.mkdir(parents=True, exist_ok=True)
    路径.write_text(
        '#[unsafe(export_name = "SecondDoor")]\n'
        'pub extern "C" fn 第二道门() -> usize { 0 }\n',
        encoding="utf-8",
    )
    return "运行内核/实例状态/src/lib.rs"


def 注入_扩展多导出一个(临根: Path) -> str:
    """样例扩展再导出一个符号（第二条接缝）。"""
    路径 = 临根 / "扩展根目录" / "原子支持库" / "样例支持库" / "src" / "lib.rs"
    路径.write_text(
        路径.read_text(encoding="utf-8")
        + '\n#[unsafe(export_name = "GetSomethingElse")]\n'
        + 'pub extern "C" fn 另一个() -> usize { 0 }\n',
        encoding="utf-8",
    )
    return "扩展根目录/原子支持库/样例支持库/src/lib.rs"


def 注入_常量重定义(临根: Path) -> str:
    """往一个内核 crate 里塞一份与常量表同名的常量定义。"""
    路径 = 临根 / "运行内核" / "实例状态" / "src" / "lib.rs"
    路径.parent.mkdir(parents=True, exist_ok=True)
    路径.write_text("pub const 目标字宽: u32 = 64;\n", encoding="utf-8")
    return "运行内核/实例状态/src/lib.rs"


def 注入_第二处载入调用(临根: Path) -> str:
    """在适配器里再调一次内核入口 `载入声明`——第二条腿的形状（全局连接器与网关 第四节判据 3）。"""
    路径 = 临根 / "跨语言适配" / "适配器实现" / "src" / "lib.rs"
    路径.write_text(
        路径.read_text(encoding="utf-8")
        + "\npub fn 再装一次(声明: &'static v1_loader::平台信息) { 载入声明(声明); }\n",
        encoding="utf-8",
    )
    return "跨语言适配/适配器实现/src/lib.rs"


def 注入_第二处资源出入口(临根: Path) -> str:
    """在另一个 crate 里再定义一个**冻结访问形状**的资源出入口——第二条腿（判据 4）。

    函数名故意改成 `另一个出入口`：证明收窄后判据**不认函数名**（
    「换个命名就红」）——它认的是 资源网关口.md §四 的冻结形状，不是名字。
    """
    路径 = 临根 / "运行内核" / "实例状态" / "src" / "lib.rs"
    路径.parent.mkdir(parents=True, exist_ok=True)
    路径.write_text(
        "pub fn 另一个出入口(资源号: u32, 操作号: u32, 输入槽表: &[数据槽]) -> 关口结果 {\n"
        "    let _ = (资源号, 操作号, 输入槽表);\n"
        "    关口结果::成功\n"
        "}\n",
        encoding="utf-8",
    )
    return "运行内核/实例状态/src/lib.rs"


def 注入_元判据缺反向样本(临根: Path):
    """元判据的反向样本：注入一条「没有反向样本」的判据（返回元数据覆盖）。"""
    覆盖 = dict(判据元数据)
    覆盖["⑮ 样例判据（没有反向样本）"] = {
        "扫描面": ("契约声明",),
        "对象数": _样本_编号文件,
        "反向样本": "",
        "正向样本": "干净合成仓",
    }
    return 覆盖


def 注入_行号引用(临根: Path) -> str:
    """判据 ⑮ 的反向样本：往干净合成仓里注入**一条按行号引用** ⇒ 必须报红且指到该件。

    注入的形状就是现场实测的那一种（`路径.扩展名:行号`）。
    **为什么行号写成 `{12}` 而不是裸数字**：本文件是 `.py`，判据 ⑮ 扫 `.py` ——
    源码里直接写一整条形号引用会被它读成一处**真违规** ⇒ 给判据面造一处假红
    （同 `测试验证/契约一致性/扫实现.py` 把 Rust 形状拆开拼的先例）。
    """
    路径 = 临根 / "项目文档/行号引用样例.md"
    路径.parent.mkdir(parents=True, exist_ok=True)
    路径.write_text(
        f"样例：见 `运行内核/装载入口/src/lib.rs:{12}`（这是按行号引用，应改成 `::符号名`）。\n",
        encoding="utf-8",
    )
    return "项目文档/行号引用样例.md"


def 注入_底座点名扩展(临根: Path) -> str:
    """判据 ⑯ 的反向样本：往干净合成仓的**底座代码**里写上一个扩展的名字 ⇒ 必须报红。

    注入的形状就是现场实测的那一种：`对外接口面/调用接口面/src/工具响应_未落.rs` 的回执
    文本里那句「编译链 1101→1102→1103→1106」，以及前端 `号段表.js` 的 `扩展表`。
    这里写成 `const` 的字符串值（不是注释、不是测试）—— 判据 ⑯ 只看生产区的**代码与字符串**，
    注释不算（注释里的引用是叙述，不产生耦合；`保串=True` 让字符串留下、注释被抹掉）。
    """
    路径 = 临根 / "运行内核" / "实例状态" / "src" / "lib.rs"
    路径.parent.mkdir(parents=True, exist_ok=True)
    路径.write_text(
        '/// 样例支持库的显示名（这条是反向样本：底座不许点名扩展）。\n'
        + 'pub const 样例扩展显示名: &str = "样例支持库";\n',
        encoding="utf-8",
    )
    return "运行内核/实例状态/src/lib.rs"


def 注入_临时件落源码树(临根: Path) -> str:
    """判据 ⑰ 的反向样本：把临时声明根落在**源码树里** ⇒ 必须报红且指到该件。

    临时根里故意塞三样「别的判据本来会抓」的东西，用来同时证明扫描面排除是承重的：
      · 一个与常量表同名的常量定义（⑬ 会抓）；
      · 一条按行号引用（⑮ 会抓）；
      · 一份声明 JSON（若被读进 `契约声明/`，编号类判据会抓）。
    因为路径含 `_临时_` 前缀，扫描面已排除它们 ⇒ 只有 ⑰ 该报「树里有临时件」。
    """
    根目录 = 临根 / (常量.临时目录前缀 + "外部库声明根")
    根目录.mkdir(parents=True, exist_ok=True)
    (根目录 / "样例.rs").write_text(
        "pub const 目标字宽: u32 = 64;\n"
        f"// 见 `运行内核/装载入口/src/lib.rs:{12}`（按行号引用）\n",
        encoding="utf-8",
    )
    (根目录 / "包声明.json").write_text('{"名称": "临时样例"}\n', encoding="utf-8")
    return 常量.临时目录前缀 + "外部库声明根"


def 注入_硬顶失效(临根: Path) -> str:
    """判据 ⑱ 的反向样本：把命令级硬顶临时压到 **0 ms** ⇒ 本命令墙钟（恒 >0）当场红。

    为什么用「阈值失效」而不是「真造一条 5 s 的慢命令」：决策记录 §三.4 自身给了两条路
    （「注入一次 5.1 s 慢命令 ⇒ 必红」**或**「让判据阈值临时失效」）。真造 5 s 慢会把
    `--自测` 顶过它自身的 5000 ms 硬顶（自测本身也是一条命令）⇒ 自测里用**阈值失效**这条，
    真·>5 s 的注入另在 `自检_延迟判据承重` 里用**真读数**做（它不睡满 5 s，用真延时 + 低阈值）。
    注入把 `硬顶毫秒` 写坏 ⇒ 由 `自测` 的用例循环在每轮结束后**还原**（`try/finally`）。
    """
    常量.硬顶毫秒 = 0
    return "本命令墙钟"
