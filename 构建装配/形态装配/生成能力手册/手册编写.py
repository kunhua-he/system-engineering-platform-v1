# -*- coding: utf-8 -*-
"""手册编写 —— 一个支持库渲染成一份 `用法说明/使用说明.md` 并落盘。

库头（请求地址 · 返回信封 · 接口数）由本件写，接口节交给 `接口段落.一段`；
`2519` 是门面，排最前。
"""

import json

from .基座常量 import 网关地址
from .接口段落 import 一段
from .样例数据 import 可采样库, 已知返回样例, 专项样例
from .猜值规则 import 猜值
from .源码字段 import 提返回字段
from .采样取回 import 采样
from .文档备注 import 公共约束


def 生成一库(库目录):
    声明文件 = sorted(库目录.glob('能力声明/*.json'), key=lambda 声明路径: int(声明路径.stem))
    if not 声明文件:
        return None

    声明们 = [json.loads(声明件.read_text(encoding='utf-8')) for 声明件 in 声明文件]
    库名 = 库目录.name
    要采样 = 库名 in 可采样库
    源码字段 = 提返回字段(库目录)

    文档行 = [
        '<!-- 生成物，禁手改',
        '生成器：构建装配/形态装配/生成能力手册.py',
        '-->',
        '# %s API' % 库名,
        '',
        '**请求地址**（全部接口共用这一个，靠请求体里的 `编号` 选能力）',
        '',
        '```http',
        'POST %s' % 网关地址,
        'Content-Type: application/json',
        '```',
        '',
        '请求体固定两层：`编号` 选接口，`命名值` 放该接口的参数。',
        '',
        '**返回信封**（全部接口统一；信封外层另带 `耗时微秒` 与 `契约身份`）',
        '',
        '```json',
        '{"成功": true,  "值": …}',
        '{"成功": false, "错误": {"码": 2506, "名称": "资源受限", "可重试": true}}',
        '```',
        '',
        '共 %d 个接口。' % len(声明们),
        '',
        '---',
        '',
    ]

    # 2519 是门面排最前，其余按编号
    排序后 = sorted(声明们, key=lambda 声明项: (声明项['编号'] != 2519, 声明项['编号']))

    for 声明 in 排序后:
        编号 = 声明['编号']
        样例 = 已知返回样例.get(str(编号))
        if 样例 is None and 要采样:
            手写 = 专项样例.get(编号) or {}
            模板 = {参数项['名称']: 手写.get(参数项['名称'], 猜值(参数项))
                    for 参数项 in (声明.get('参数表') or [])}
            样例 = 采样(编号, 模板)
        文档行 += 一段(声明, 样例, 源码字段.get(编号))
        文档行.append('---')
        文档行.append('')

    文档行.append('## 公共约束')
    文档行.append('')
    for 约束条 in 公共约束:
        文档行.append('- %s' % 约束条)
    文档行.append('')

    产出 = 库目录 / '用法说明/使用说明.md'
    产出.parent.mkdir(parents=True, exist_ok=True)
    产出.write_text('\n'.join(文档行).rstrip() + '\n', encoding='utf-8')

    return 产出, len(声明们), len(文档行)
