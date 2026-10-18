"""只辨平台号段骨架的数字语义，不豁免同件里的能力调用常量。"""
import json
import re
from pathlib import Path


def 号段字面量位置(仓根, 件名, 源文本):
    if 件名 != "前端呈现/网页应用/号段表.js":
        return set()
    try:
        号段表 = json.loads((Path(仓根)/"契约声明/号段图.json").read_text(encoding="utf-8"))["能力号段"]
        源号段集 = {(号段["起"], 号段["止"]) for 号段 in 号段表}
    except (OSError, ValueError, KeyError, TypeError):
        return set()
    边界位置集 = set()
    for 骨架匹配 in re.finditer(r"\bexport\s+const\s+号段\s*=\s*\[([\s\S]*?)\]\s*;", 源文本):
        for 行块 in re.finditer(r"\{\s*段起点\s*:\s*(\d+)\s*,\s*段止\s*:\s*(\d+)\s*,", 骨架匹配.group(1)):
            if (int(行块.group(1)), int(行块.group(2))) not in 源号段集:
                continue
            for 组位 in (1, 2):
                起点, 片段终位 = 行块.span(组位)
                边界位置集.add((骨架匹配.start(1)+起点, 骨架匹配.start(1)+片段终位))
    return 边界位置集


def 自检_号段能力号分界():
    import tempfile
    from unittest.mock import patch
    from . import 判据_能力号 as 判据节点
    失败表 = []
    with tempfile.TemporaryDirectory(prefix="号段语义_") as 临时目录:
        仓根 = Path(临时目录)
        (仓根/"契约声明").mkdir()
        (仓根/"契约声明/号段图.json").write_text(json.dumps(dict(能力号段=[dict(起=7000,止=7999)])))
        件名 = "前端呈现/网页应用/号段表.js"
        骨架 = 'export const 号段 = [{ 段起点: 7000, 段止: 7999, 名字: "模块" }];'
        for 样本名, 件路径, 源文本, 期望数 in (
            ("真源边界", 件名, 骨架, 0),
            ("同件真实调用", 件名, 骨架+'调用(7999);', 1),
            ("另一件不借骨架躲检查", "对外接口面/调用.rs", 骨架, 1),
            ("不在真源的边界", 件名, 骨架.replace("7000", "7100"), 1),
            ("非骨架字段", 件名, 'const 参数 = { 段起点:7000, 段止:7999, };', 1),
            ("字符串里的调用仍拒", 件名, 骨架+'const 文本="调用7999";', 1),
        ):
            with patch.object(判据节点,"已声明能力号",return_value={7999}), patch.object(判据节点,"底座代码面",return_value={件路径:源文本}):
                实测 = 判据节点.扫硬写能力号(dict(仓根=仓根))
            if 实测.get((件路径,7999),0) != 期望数:
                失败表.append("号段与能力数字语义错判："+样本名+str(实测))
    return 失败表
