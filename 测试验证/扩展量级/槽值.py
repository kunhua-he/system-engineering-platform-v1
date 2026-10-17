"""测试侧按真实槽结构解值，不参与生产执行。"""
def 解槽值(槽项):
    if isinstance(槽项,list):return [解槽值(子项) for 子项 in 槽项]
    if isinstance(槽项,dict):
        if '类型标签' in 槽项 and '值' in 槽项:return 解槽值(槽项['值'])
        return {键名:解槽值(子项) for 键名,子项 in 槽项.items()}
    return 槽项
