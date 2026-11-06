# -*- coding: utf-8 -*-
"""接口段落 —— 一个接口渲染成一节：请求参数模板 · 这个接口干什么 · 参数 · 返回。

四块的顺序是照 HTTP API 文档的读法排的：先能直接发（模板），再知道它是干什么的，
再看逐条参数，最后看返回长什么样。返回样例只放现场采到的，采不到就只报类型。
"""

import json

from .基座常量 import 类型名
from .样例编造 import 编样例
from .样例数据 import 专项样例
from .文档备注 import 备注表
from .源码字段 import 手写返回字段


def 提取返回描述(说明):
    """声明里常写「返回 字段/结构」，把这句挖出来单独放返回栏。"""
    命中位 = 说明.find('返回')
    if 命中位 < 0:
        return ''
    说明段 = 说明[命中位:]
    for 句末 in ('；', '。'):
        切点 = 说明段.find(句末)
        if 切点 > 0:
            说明段 = 说明段[:切点]
            break
    return 说明段.strip()[:160]


def 一段(声明, 样例, 字段们=None):
    编号 = 声明['编号']
    短名 = (声明.get('名称') or '').split('_')[-1]
    返回 = 类型名.get(声明.get('返回类型', 0), '未知')
    参数们 = 声明.get('参数表') or []
    星标 = ' ★' if 编号 == 2519 else ''

    文档行 = ['## %d · %s%s' % (编号, 短名, 星标), '']

    手写 = 专项样例.get(编号) or {}
    模板 = {参数项['名称']: 手写.get(参数项['名称'], 编样例(参数项)) for 参数项 in 参数们}
    文档行.append('**请求参数模板**（把值改成你的就能直接发）')
    文档行.append('')
    文档行.append('```json')
    文档行.append(json.dumps({'编号': 编号, '命名值': 模板}, ensure_ascii=False, indent=1))
    文档行.append('```')
    文档行.append('')

    文档行.append('**这个接口干什么**')
    文档行.append('')
    文档行.append((声明.get('说明') or '').rstrip('。') + '。')
    文档行.append('')

    if 参数们:
        文档行.append('**参数**')
        文档行.append('')
        for 参数项 in 参数们:
            类型 = 类型名.get(参数项.get('类型标签', 0), '未知')
            默认 = 参数项.get('默认值') or {}
            有默认 = bool(默认.get('类型标签'))
            简述 = (参数项.get('说明') or '').rstrip('。')
            if 简述 == 参数项['名称']:
                简述 = ''
            默认值 = 默认.get('值', 默认.get('逻辑', ''))
            if 有默认 and 默认值 not in ('', None) and '默认' not in 简述:
                简述 += '。默认 %s' % 默认值
            文档行.append('- %s · %s · %s%s' % (
                参数项['名称'], 类型, '可选' if 有默认 else '必填', (' — ' + 简述) if 简述 else ''))
        文档行.append('')

    文档行.append('**返回**')
    文档行.append('')
    if 样例 is not None:
        文档行.append('```json')
        文档行.append(json.dumps(样例, ensure_ascii=False, indent=1)[:1400])
        文档行.append('```')
        文档行.append('')
        文档行.append('（上面的样例是现场发请求调出来的）')
    else:
        文档行.append('返回类型：%s。' % 返回)
        人工 = 手写返回字段.get(声明['编号'])
        if 字段们:
            文档行.append('')
            文档行.append('返回字段：%s' % '、'.join('%s（%s）' % (字段名, 字段型) for 字段名, 字段型 in 字段们))
        elif 人工:
            文档行.append('')
            文档行.append('返回字段：%s（读源码确认，见 %s）' % ('、'.join(人工[0]), 人工[1]))
        描述 = 提取返回描述(声明.get('说明') or '')
        if 描述:
            文档行.append('')
            文档行.append('返回内容：%s' % 描述)
    文档行.append('')

    备注 = [备注条 for 备注条 in (备注表.get(编号) or []) if 备注条.strip()]
    if 备注:
        文档行.append('**备注**')
        文档行.append('')
        for 备注条 in 备注:
            文档行.append('- %s' % 备注条)
        文档行.append('')

    return 文档行
