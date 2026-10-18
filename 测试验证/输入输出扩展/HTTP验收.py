"""统一真实HTTP扩展验证，复用原装载、实例隔离、卸载与进程回收驱动。"""
import base64
import concurrent.futures
import hashlib
from 测试验证.扩展量级.槽值 import 解槽值
from 测试验证.通用基础扩展.HTTP验收 import 核验通用基础
from .网络靶场 import 本地靶场,网页原文
from .独立样本 import 核验基础样本
from .边界样本 import 核验边界样本


def 核验输入输出(请求,检查,实例表):
    核验通用基础(请求,检查,实例表)
    def 调用(网关实例,编号,参数表,预期错误=None):
        值表=[dict(类型标签=5,值=base64.b64encode(值).decode()) if isinstance(值,bytes) else dict(类型标签=4,值=值) for 值 in 参数表]
        状态码,正文=请求(网关实例,'/接口/调用',dict(编号=编号,值=值表))
        if 预期错误 is not None:
            检查(状态码<500 and not 正文.get('成功') and 正文.get('错误',{}).get('码')==预期错误,'输入输出原码拒绝%s'%编号,正文)
            return None
        检查(状态码==200 and 正文.get('成功') and len(正文['值'])==1,'输入输出真实HTTP成功%s'%编号,正文)
        槽项=正文['值'][0]
        return base64.b64decode(槽项['值'],validate=True) if 槽项['类型标签']==5 else 解槽值(槽项)
    with 本地靶场() as 靶场地址:
        for 网关实例 in 实例表:
            文件目录=网关实例['目录']/'文件实证'
            核验基础样本(调用,检查,网关实例,靶场地址,文件目录)
            核验边界样本(调用,检查,网关实例,靶场地址,文件目录)
        调用(实例表[0],2401,[靶场地址+'/slow'],2404)
        def 并发请求(请求序号):
            网关实例=实例表[请求序号%len(实例表)]
            实际=调用(网关实例,7988,[靶场地址+'/html'])
            assert 实际==hashlib.sha256(网页原文.encode()).hexdigest(),实际
            assert 调用(网关实例,4901,['{{ value }}','{"value":"请求%s"}'%请求序号])=='请求%s'%请求序号
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as 线程池:list(线程池.map(并发请求,range(48)))
        检查(True,'双实例12线程网络与模板组合48轮互不串扰')
    for 网关实例 in 实例表:
        _,留痕=请求(网关实例,'/接口/留痕')
        编号集={留痕项['能力号'] for 留痕项 in 留痕.get('数据',{}).get('留痕',[])}
        检查({7988,2401,4601}.issubset(编号集),'网络组合内外真实留痕',留痕)


def 执行输入输出验收(仓根,缓存根):
    from 测试验证.扩展量级.HTTP验收 import 执行量级验收
    return 执行量级验收(仓根,缓存根,扩展验证=核验输入输出)
