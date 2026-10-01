# -*- coding: utf-8 -*-
"""准入判据 ㉗–㊱ 的反向样本注入（#216）—— 每条把干净合成仓的对应夹具退回一步。"""

from __future__ import annotations

import json
from pathlib import Path


def _改写临件(临根: Path, 相对: str, 新文: str) -> str:
    路径 = 临根 / 相对
    路径.write_text(新文, encoding="utf-8")
    return 相对


def 注入_准入抽广播段(临根: Path) -> str:
    """抽掉 判定.rs 里对广播段的 continue ⇒ ㉗ 必红。"""
    return _改写临件(
        临根, "运行内核/装载入口/src/判定.rs",
        "pub fn 判广播段() -> bool {\n    true\n}\n",
    )


def 注入_准入抽通知口(临根: Path) -> str:
    """抽掉 通知口.rs 的 注册通知端点 ⇒ ㉘ 必红。"""
    return _改写临件(
        临根, "跨语言适配/适配器实现/src/通知口.rs",
        "pub struct 通知口;\n"
        "impl 通知口 {\n"
        "    pub fn 请求卸载(&self) {}\n"
        "    pub fn 延迟释放协商(&self) {}\n"
        "    pub fn 请求卸载按标识(&self) {}\n"
        "}\n",
    )


def 注入_准入抽接缝(临根: Path) -> str:
    """抽掉 边界面.rs 的「不复刻/偏离」 ⇒ ㉙ 必红（落点见 `世界.py::世界.边界协议`）。"""
    return _改写临件(
        临根, "跨语言适配/适配器实现/src/边界面.rs",
        "//! 样例边界面。\n"
        "//! 接缝符号名 `GetPlatformInfo`（冻结）；参照实现的对应符号 `GetNewInf`。\n",
    )


def 注入_准入死键(临根: Path) -> str:
    """往 包声明.json 注入 提供宿主版本 死键 ⇒ ㉚ 必红。"""
    return _改写临件(
        临根, "扩展根目录/原子支持库/样例支持库/包声明.json",
        json.dumps({"说明": "样例扩展声明", "名称": "样例支持库",
                    "提供宿主版本": {"主": 1, "次": 0, "构建": 0}},
                   ensure_ascii=False, indent=2) + "\n",
    )


def 注入_准入制品类型(临根: Path) -> str:
    """往扩展 Cargo.toml 注入 [lib] crate-type ⇒ ㉛ 必红。"""
    return _改写临件(
        临根, "扩展根目录/原子支持库/样例支持库/Cargo.toml",
        '[package]\nname = "v1-sample"\nversion = "0.1.0"\n\n[lib]\ncrate-type = ["cdylib"]\n',
    )


def 注入_准入类别号错位(临根: Path) -> str:
    """把 命令类别/0000.json 改成 类别号≠文件名 + 名/说明空 ⇒ ㉜ 必红。"""
    return _改写临件(
        临根, "契约声明/命令类别/0000.json",
        json.dumps({"类别号": 99, "名称": "", "说明": ""}, ensure_ascii=False, indent=2) + "\n",
    )


def 注入_准入抽优先级(临根: Path) -> str:
    """抽掉 载入判定.json 的「判定顺序的优先级」键 ⇒ ㉝ 必红。"""
    return _改写临件(
        临根, "扩展装载/载入约定/载入判定.json",
        json.dumps({"说明": "样例载入判定", "热载入与热卸载": "生命周期段按广播段判"},
                   ensure_ascii=False, indent=2) + "\n",
    )


def 注入_准入抽剔除(临根: Path) -> str:
    """抽掉 启动网关.rs 的「剔除的.push」台账 ⇒ ㉞ 必红。"""
    return _改写临件(
        临根, "对外接口面/调用接口面/examples/启动网关.rs",
        "pub(crate) fn 取扩展声明(扩展目录: &str) -> Result<&'static 平台信息, String> {\n"
        "    let _ = 扩展目录;\n"
        "    Ok(unsafe { &*(core::ptr::null::<平台信息>()) })\n"
        "}\n"
        "pub fn 装(落点: &str) {\n"
        "    let _ = 取扩展声明(落点);\n"
        "}\n",
    )


def 注入_准入抽指纹(临根: Path) -> str:
    """让指纹的重跑命令**跑得出「不一致」** ⇒ ㉟ 必红。

    为什么不是「抽掉生成命令」：`判_14`（判法的唯一落点）把「命令不可跑」判成**未判**，
    而反向样本要的是**失败**（红）。所以把重跑脚本改成报不一致（退出码 1）——这正是
    `判_14` 的失败路径（命令可跑，但 `--检查` 退出码非 0 = 指纹与盘面不符）。
    """
    return _改写临件(
        临根, "扩展根目录/原子支持库/编译器支持库/工具/重跑指纹.py",
        "import sys\nprint('指纹与盘面不符')\nsys.exit(1)\n",
    )


def 注入_准入抽并发(临根: Path) -> str:
    """抽掉 线程安全.rs 的 Sync 断言 ⇒ ㊱ 必红。"""
    return _改写临件(
        临根, "跨语言适配/适配器实现/src/线程安全.rs",
        "pub struct 适配器;\nunsafe impl Send for 适配器 {}\n",
    )
