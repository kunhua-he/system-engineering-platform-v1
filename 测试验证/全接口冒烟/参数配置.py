# -*- coding: utf-8 -*-
"""参数配置 —— 按参数名配真值：配置三层覆盖 + 按说明推断 + 类型兜底。

为什么要有它：光发空值只能证明链路通（参数校验就拦住），证明不了接口能干活。
配置与逻辑分开 —— 给某个接口调参数只改 `测试验证/冒烟参数.json`，不改代码。

复合参数的形状（类型 5/100/101 的标签包装）也归这里，一处包得住，别处不许再包一遍。
"""

import base64 as 编码器
import json
import re
import time
from pathlib import Path

from .路径常量 import 配置路径
from .路径常量 import 素材根 as 默认素材根
from .运行上下文 import 上下文

# 按参数说明推：说明里常直接给例句。
推值规则 = [
    (r'点分路径如\s*([\w.]+)', None),
    (r'如\s*(\[[^\]]*\]|\{[^}]*\})', None),
    (r'真\s*/\s*假|真/假', '假'),
    (r'JSON', '{"a":1}'),
    (r'CSV|逗号分隔', 'a,b,c'),
    (r'YAML', 'a: 1'),
    (r'BASE64|base64', '5L2g5aW9'),
    (r'十六进制|HEX|hex', 'E7A4BA'),
]

# 类型 5 是字节集，必须是长度 4 倍数的合法 base64 —— 给「示例」三个字会直接判协议错。
兜底值 = {'类型1': 1, '类型2': 1.5, '类型3': False, '类型4': '示例', '类型5': '5YaF5a65', '类型6': 1}

# 这些参数名要的是「每次新的输出落点」，否则第二轮必然「文件已存在」。
输出类参数名 = ('输出路径', '目标路径', '输出目录')


def 替换占位(字典, 素材根路径, 时间戳):
    """把 `{素材}` / `{戳}` 换成真值；输出类路径再加时间戳，避免两轮撞名。"""
    转换结果 = {}
    for 参数键, 参数值 in (字典 or {}).items():
        if isinstance(参数值, str):
            参数值 = 参数值.replace('{素材}', str(素材根路径)).replace('{戳}', 时间戳)
            if 参数键 in ('输出路径', '目标路径') and 参数值.startswith('/'):
                目录部分, 分隔符, 名字末段 = 参数值.rpartition('/')
                名字主体, 点号, 后缀部分 = 名字末段.partition('.')
                参数值 = '%s/%s_%s%s%s' % (目录部分, 名字主体, 时间戳, 点号, 后缀部分)
        转换结果[参数键] = 参数值
    return 转换结果


def 读配置():
    """配置住 `冒烟参数.json`：按编号 > 按库 > 全局，三层覆盖。缺件则写一份空骨架。"""
    if not 配置路径.is_file():
        raise FileNotFoundError('冒烟配置不存在：%s' % 配置路径)
    配置 = json.loads(配置路径.read_text(encoding='utf-8'))
    素材根路径 = Path(配置.get('素材目录') or str(默认素材根))
    时间戳 = str(time.time_ns())
    配置['全局'] = 替换占位(配置.get('全局'), 素材根路径, 时间戳)
    配置['按库'] = {库名: 替换占位(库配置, 素材根路径, 时间戳)
                    for 库名, 库配置 in (配置.get('按库') or {}).items()}
    配置['按编号'] = {编号键: 替换占位(号配置, 素材根路径, 时间戳)
                      for 编号键, 号配置 in (配置.get('按编号') or {}).items()}
    配置['素材根路径'] = str(素材根路径)
    return 配置


def 换新名(路径):
    """输出类路径每次换新，否则第二轮必然「文件已存在」。"""
    原路径 = Path(路径)
    return str(原路径.with_name('%s_%d%s' % (原路径.stem, time.time_ns() % 100000, 原路径.suffix)))


def 包标签(值, 类型标签):
    """复合参数必须逐层带 {"类型标签":N,"值":…}，裸 {} / [] 会被判「输入形状不符」。"""
    if isinstance(值, dict) and '类型标签' in 值 and '值' in 值:
        return 值
    if 类型标签 == 100:
        return {'类型标签': 100, '值': 值 if isinstance(值, list) else []}
    if 类型标签 == 101:
        return {'类型标签': 101, '值': 值 if isinstance(值, dict) else {}}
    if 类型标签 == 5:
        文本串 = 值 if isinstance(值, str) else ''
        try:
            编码器.b64decode(文本串, validate=True)
            if len(文本串) % 4:
                raise ValueError
        except Exception:
            文本串 = 编码器.b64encode(b'\xe7\xa4\xba\xe4\xbe\x8b').decode()
        return {'类型标签': 5, '值': 文本串}
    return 值


def 造参(声明, 库名='', 配置=None):
    """一条能力的入参：专属配置 > 句柄上下文 > 声明默认值 > 说明推断 > 类型兜底。"""
    入参表 = {}
    配置 = 配置 or {}
    专属 = {}
    专属.update(配置.get('全局') or {})
    专属.update((配置.get('按库') or {}).get(库名) or {})
    专属.update((配置.get('按编号') or {}).get(str(声明.get('编号'))) or {})
    for 参声明 in 声明.get('参数表') or []:
        参数名 = 参声明['名称']
        说明 = 参声明.get('说明') or ''
        类型标签 = 参声明.get('类型标签', 4)
        默认值 = 参声明.get('默认值') or {}

        if 参数名 in ('输出路径', '目标路径', '输出目录') and isinstance(专属.get(参数名), str):
            入参表[参数名] = 包标签(换新名(专属[参数名]), 类型标签)
            continue
        if 参数名 in ('服务句柄', '句柄', '任务句柄', '许可句柄', '连接句柄', '会话句柄', '组件句柄', '连接编号'):
            链规则 = (配置.get('链式') or {}).get(str(声明.get('编号'))) or {}
            if 链规则.get('填') == 参数名:
                continue
            if not 上下文.get(参数名):
                raise RuntimeError('%s 未覆盖：缺少本轮 %s 的创建前置' % (声明.get('编号'), 参数名))
            入参表[参数名] = 包标签(上下文[参数名], 类型标签)
            continue
        if 参数名 in 专属:
            入参表[参数名] = 包标签(专属[参数名], 类型标签)
            continue
        if 默认值.get('类型标签'):
            入参表[参数名] = 默认值.get('值', 默认值.get('逻辑', ''))
            continue

        取值 = None
        for 模式, 固定值 in 推值规则:
            命中 = re.search(模式, 说明)
            if 命中:
                取值 = 固定值 if 固定值 is not None else 命中.group(1)
                break
        if 取值 is None:
            取值 = 兜底值.get('类型%d' % 类型标签, '示例')
        入参表[参数名] = 包标签(取值, 类型标签)
    return 入参表
