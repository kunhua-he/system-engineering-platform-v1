# -*- coding: utf-8 -*-
"""样例编造 —— 请求参数模板里的占位值 `编样例`，与去掉类型标签外壳的 `剥标签`。

`编样例` 不猜业务语义，只给**形状对、一定能过校验**的空值；真值由 `专项样例` 覆盖。
`剥标签` 是反向一步：把回包里的 `{类型标签, 值}` 还原成人能读的 JSON。
"""

import json


def 编样例(参数项):
    类型 = 参数项.get('类型标签', 0)
    默认 = 参数项.get('默认值') or {}
    有默认 = bool(默认.get('类型标签'))
    if 类型 == 100:
        return {'类型标签': 100, '值': []}
    if 类型 == 101:
        return {'类型标签': 101, '值': {}}
    if 类型 == 7:
        return {'类型标签': 7, '值': 1}
    if 类型 == 6:
        return 1
    if 类型 == 3:
        return bool(默认.get('逻辑')) if 有默认 else False
    if 类型 in (1, 2):
        return 默认.get('值', 0) if 有默认 else 0
    return ''


def 剥标签(待剥值):
    """去掉类型标签外壳，把 JSON 文本解开。"""
    if isinstance(待剥值, list):
        return [剥标签(每项) for 每项 in 待剥值]
    if isinstance(待剥值, dict) and set(待剥值) == {'类型标签', '值'}:
        内层值 = 剥标签(待剥值['值'])
        if 待剥值['类型标签'] == 4 and isinstance(内层值, str) and 内层值.strip().startswith(('{', '[')):
            try:
                return json.loads(内层值)
            except Exception:
                return 内层值
        if 待剥值['类型标签'] == 3:
            return bool(内层值)
        return 内层值
    if isinstance(待剥值, dict):
        return {键名: 剥标签(项值) for 键名, 项值 in 待剥值.items()}
    return 待剥值
