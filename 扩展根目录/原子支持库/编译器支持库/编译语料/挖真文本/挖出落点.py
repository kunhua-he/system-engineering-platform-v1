# -*- coding: utf-8 -*-
"""挖真文本 · 常量 —— 语料根 · 落点 · 判定阈值 · 扫描白名单（纯搬家，取值逐字不变）。"""
import os
import re
import sys
from pathlib import Path

# 本件 = <编译语料>/挖真文本/挖出落点.py ⇒ 上溯两层 = <编译语料>/（与拆分前的 语料根 同值）。
语料根 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 语料源头（易语言原版安装树）——**不再写死 `/tmp`**（易失路径，重启即丢；实测 2026-10-01
# 源头已被大幅清空）。落点走**运行数据根**（唯一解析器 `运行内核/运行数据根/`；Python 侧入口
# `开发工具/运行数据根.py`，**不自持第二份解析**）：默认 = `<运行数据根>/临时件/易语言源码`；
# 环境变量 `V1_CORPUS_ROOT`（ASCII 名）非空则原样覆盖。解析器不在 / 解析不出 ⇒ 空串
# （调用方按「未判」报，**不猜路径**）。
源码根 = ""
sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "开发工具"))
try:
    from 运行数据根 import 解析当前环境, 子目录路径
    源码根 = str(子目录路径(解析当前环境(), "临时件") / "易语言源码")
except Exception:
    源码根 = ""
if os.environ.get("V1_CORPUS_ROOT"):
    源码根 = os.environ["V1_CORPUS_ROOT"]

真文本目录 = os.path.join(语料根, "真文本")
挖出JSON路径 = os.path.join(语料根, "_挖出.json")

最大行长 = 512
最少声明行数 = 2
版本锚 = ".版本 2\r\n".encode("gbk")
版本行首 = ".版本".encode("gbk")

声明词表 = ["版本", "支持库", "程序集", "子程序", "参数", "局部变量", "程序集变量", "全局变量",
        "数据类型", "成员", "常量", "DLL命令", "自定义数据类型", "组件", "图片资源",
        "声音资源", "窗口", "菜单", "易模块", "类", "方法", "初始化", "结束",
        "信息", "作者", "描述", "代码", "模块", "链接", "结构", "属性", "公开", "私有"]
声明行正则 = re.compile(r"^\.(" + "|".join(声明词表) + r")(?![0-9A-Za-z_\u4e00-\u9fff])")

段头魔数 = b"\x19\x73\x11\x15"
段头终止 = b"\x19\x73\x00"
常量记录正则 = re.compile(rb"\x04\x00([\x20-\x7e\x81-\xfe]{1,60}?)\x00\x00", re.S)
控制字符 = bytes(码值 for 码值 in range(0x20) if 码值 != 9) + b"\x7f"

# 已知内嵌源码文本、但不是容器的文件（弱证据扫描白名单；按扩展名不可能穷举，故显式列）
弱证据白名单 = [
    "lib/ExuiKrnln/ExuiTool.exe",
    "lib/HPSocket_E.fne", "static_lib/HPSocket_E_static.lib",
    "lib/e2ee.fne", "static_lib/e2ee_static.lib",
    "lib/iDraw/eTools/Plugin/E2EE自动添加订阅函数.dll",
    "lib/iDraw/eTools/Plugin/一键加入读写方法.dll",
    "lib/iDraw/eTools/ViewEcInfo.exe", "lib/eTools/ViewEcInfo.exe",
    "ecom/模块打开方式选中这个程序.exe",
]
