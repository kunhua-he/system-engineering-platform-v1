# -*- coding: utf-8 -*-
"""素材备置 —— 冒烟要读的样本与素材先落好，免得「文件不存在」掩盖真问题。

落点取配置里那一层（`{素材}` 的落点，见 `参数配置.读配置`）；没配就用运行数据根的
临时件子目录（见 `路径常量`）—— 两种落点都由唯一解析器给，本件不自拼临时路径。
"""

from pathlib import Path

from .路径常量 import 样本文件名
from .路径常量 import 素材根 as 默认素材根

样本正文 = '第一行\n第二行\n第三行\n'
样例源码 = 'def f():\n    return 1\n'
切块规则正文 = '{"块类型": ["函数"], "按行切": true}'


def 备素材(素材目录路径=None):
    """样本件 + 素材目录里的最小可读件；已存在就不覆盖（保留上一轮的真参数产出）。"""
    素材根路径 = Path(素材目录路径 or 默认素材根)
    素材根路径.mkdir(parents=True, exist_ok=True)
    样本件 = 素材根路径 / 样本文件名
    if not 样本件.is_file():
        样本件.write_text(样本正文, encoding='utf-8')
    if not (素材根路径 / '样例.py').is_file():
        (素材根路径 / '样例.py').write_text(样例源码, encoding='utf-8')
    if not (素材根路径 / '切块规则.json').is_file():
        (素材根路径 / '切块规则.json').write_text(切块规则正文, encoding='utf-8')
