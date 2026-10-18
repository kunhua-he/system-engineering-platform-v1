"""多扩展真实HTTP验收：公开调用、独立对照、并发、反复装卸和资源回收。"""
import concurrent.futures
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib


def 执行量级验收(仓根, 缓存根, 扩展验证=None, 装载后验证=None):
    仓根, 缓存根 = Path(仓根).resolve(), Path(缓存根).resolve()
    缓存根.mkdir(parents=True, exist_ok=True)
    from 构建装配.门禁.常量 import 效率目标毫秒
    连接器 = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    实例表, 回执表, 检查表 = [], [], []
    代码缓存根 = 缓存根/'执行映像'
    环境准备秒 = None
    包目录表 = sorted(声明路径 for 声明路径 in (仓根 / '扩展根目录').glob('*/*/包声明.json')
                if 声明路径.parent.parent.name != '技能封装库')

    def 请求(网关实例, 路径, 请求体=None):
        起始时刻 = time.monotonic()
        批量装载 = 路径 == '/接口/生命周期' and 请求体 and 请求体.get('动作') == '装载'
        请求预算秒 = 效率目标毫秒 / 1000 if 批量装载 else min(5, 效率目标毫秒 / 1000)
        请求对象 = urllib.request.Request('http://127.0.0.1:%s%s' % (网关实例['端口'], urllib.parse.urlunsplit(('', '', urllib.parse.quote(urllib.parse.urlsplit(路径).path, safe='/'), urllib.parse.quote(urllib.parse.urlsplit(路径).query, safe='=&%+/?'), ''))), data=None if 请求体 is None else json.dumps(请求体, ensure_ascii=False).encode(), headers={'Content-Type':'application/json'})
        try:
            with 连接器.open(请求对象, timeout=请求预算秒) as 响应: 状态码, 返回 = 响应.status, json.loads(响应.read())
        except urllib.error.HTTPError as 错误响应:
            with 错误响应: 状态码, 返回 = 错误响应.code, json.loads(错误响应.read())
        except (TimeoutError, urllib.error.URLError) as 请求失败:
            已用秒 = time.monotonic()-起始时刻
            回执表.append(dict(端口=网关实例['端口'],路径=路径,请求=请求体,动作=(请求体 or {}).get('动作'),HTTP状态=None,错误=str(请求失败),预算秒=请求预算秒,实际秒=已用秒))
            raise RuntimeError('HTTP失败：%s；动作=%s；预算=%s秒；实际=%.3f秒；%s' % (路径,(请求体 or {}).get('动作'),请求预算秒,已用秒,请求失败)) from 请求失败
        回执表.append(dict(端口=网关实例['端口'],路径=路径,请求=请求体,动作=(请求体 or {}).get('动作'),HTTP状态=状态码,返回=返回,预算秒=请求预算秒,实际秒=time.monotonic()-起始时刻))
        return 状态码, 返回

    def 检查(条件, 名称, 返回=None):
        assert 条件, (名称, 返回)
        检查表.append(名称)

    def 调用(网关实例, 编号, 输入文本, 错误码=None):
        状态码, 返回 = 请求(网关实例,'/接口/调用',dict(编号=编号,值=[dict(类型标签=4,值=输入文本)]))
        if 错误码 is not None:
            assert not 返回.get('成功') and 返回.get('错误',{}).get('码')==错误码, (编号,返回)
            return None
        assert 状态码==200 and 返回.get('成功'), (编号,返回)
        assert len(返回['值'])==1,返回
        return 返回['值'][0]['值']

    def 起网关(实例序号):
        实例目录=缓存根/('网关实例%s'%实例序号); 实例目录.mkdir(exist_ok=True)
        with socket.socket() as 监听探针:
            监听探针.bind(('127.0.0.1',0)); 端口号=监听探针.getsockname()[1]
        部署表=[]
        for 声明路径 in 包目录表:
            包目录=声明路径.parent; 包声明=json.loads(声明路径.read_text())
            模块包=包目录.parent.name=='组合模块库'
            制品后缀='.模块制品' if 模块包 else '.支持库制品'
            部署表.append(dict(标识串=包声明['标识串'],版本=dict(主版本=包声明['实现版本']['主'],次版本号=包声明['实现版本']['次'],构建=包声明['实现版本']['构建']),制品路径=str(包目录/(包目录.name+制品后缀)),启动程序=str(仓根/'构建环境/构建缓存/debug/examples/工作进程') if 模块包 else ''))
        配置路径=实例目录/'跨进程.json'; 配置路径.write_text(json.dumps(dict(跨进程=部署表,子进程数上限=sum(bool(部署项['启动程序']) for 部署项 in 部署表)),ensure_ascii=False))
        日志文件=open(实例目录/'网关.log','w')
        网关进程=subprocess.Popen([str(仓根/'构建环境/构建缓存/release/examples/启动网关'),'--声明根','扩展装载/扩展根声明.json','--后缀表','扩展装载/后缀表.json','--端口',str(端口号),'--缓存根',str(代码缓存根),'--跨进程配置',str(配置路径),'--工具根','.'],cwd=仓根,stdout=日志文件,stderr=subprocess.STDOUT,start_new_session=False)
        网关实例=dict(端口=端口号,进程=网关进程,日志=日志文件,部署=部署表,目录=实例目录)
        实例表.append(网关实例)
        准备预算秒=5
        截止时刻=time.monotonic()+准备预算秒
        while time.monotonic()<截止时刻:
            if 网关进程.poll() is not None: raise RuntimeError((实例目录/'网关.log').read_text())
            with socket.socket() as 连接探针:
                if 连接探针.connect_ex(('127.0.0.1',端口号))==0: return 网关实例
            time.sleep(0.02)
        raise RuntimeError('网关%s启动超时；预算%s秒；日志：%s'%(实例序号,准备预算秒,(实例目录/'网关.log').read_text()))

    def 装载(网关实例):
        状态码,返回=请求(网关实例,'/接口/生命周期',dict(动作='装载'))
        检查(状态码==200 and 返回.get('成功'),'全部扩展装载调用成功',返回)
        拒绝包表=[条目 for 条目 in 返回.get('数据',{}).get('剔除',[]) if '技能封装库' not in 条目.get('落点','')]
        检查(not 拒绝包表,'全部执行包无装载剔除',拒绝包表)

    def 卸载(网关实例):
        for 部署项 in reversed(网关实例['部署']):
            状态码,返回=请求(网关实例,'/接口/生命周期',dict(动作='卸载',标识串=部署项['标识串']))
            检查(状态码==200 and 返回.get('成功'),'逐包正式卸载',返回)
            if 部署项['启动程序']:
                检查(返回.get('数据',{}).get('物理回收')==1,'模块执行域物理回收',返回)

    try:
        from 构建装配.上线切换.准备执行映像 import 准备执行映像
        准备回执=准备执行映像(仓根,代码缓存根,缓存根/'环境准备.log')
        环境准备秒=准备回执['环境准备秒']
        检查(准备回执['准备进程已退出'],'正式发布准备完成且准备进程退出')
        print('执行映像环境准备 %.3f 秒；随后两份新实例复用不可变代码，不冒充无准备冷跑。'%环境准备秒,flush=True)
        for 实例序号 in range(2): 起网关(实例序号)
        for 网关实例 in 实例表: 装载(网关实例)
        if 装载后验证 is not None: 装载后验证(请求,检查,实例表)
        源库网关=实例表[0]
        原文='中文🙂 /?+%\x00跨库'
        编码文=urllib.parse.quote(原文,safe='-._~')
        压缩文=zlib.compress(原文.encode()).hex().upper()
        for 编号 in (3201,7954): 检查(调用(源库网关,编号,原文)==压缩文,'压缩与标准库逐字节对照')
        for 编号 in (3202,7955): 检查(调用(源库网关,编号,压缩文)==原文,'解压保真')
        for 编号 in (4101,7956): 检查(调用(源库网关,编号,原文)==编码文,'URI与标准库逐字节对照')
        for 编号 in (4102,7957): 检查(调用(源库网关,编号,编码文)==原文,'URI解码保真')
        跨库文=调用(源库网关,7958,原文)
        检查(跨库文==zlib.compress(编码文.encode()).hex().upper(),'两支持库嵌套组合真实结果')
        检查(调用(源库网关,7959,跨库文)==原文,'两库反向嵌套还原')
        _,留痕=请求(源库网关,'/接口/留痕')
        留痕编号=[条目['能力号'] for 条目 in 留痕.get('数据',{}).get('留痕',[])]
        检查(all(编号 in 留痕编号 for 编号 in (7958,7959,3201,3202,4101,4102)),'跨库内外调用留痕',留痕)
        for 编号,坏文本,错误码 in [(7955,'GG',3201),(7955,'00',3202),(7957,'%',4101),(7957,'%FF',4101),(7959,'00',3202),(7954,'中'*22000,3203),(7956,'中'*22000,4103)]:
            调用(源库网关,编号,坏文本,错误码); 检查表.append('模块失败原码透传')
        调用(源库网关,7958,'中'*10000,3203)
        调用(源库网关,7959,zlib.compress(b'bad%').hex().upper(),4101)
        检查表.append('跨库中间值产生后失败仍原码返回并回收')
        炸弹=zlib.compress(b'x'*65537).hex().upper()
        调用(源库网关,7955,炸弹,3203); 检查表.append('解压膨胀超界拒绝')
        调用(源库网关,7955,压缩文+'00',3201); 检查表.append('压缩流尾随垃圾拒绝')
        for 列表值 in ([],[dict(类型标签=4,值='中文'),dict(类型标签=1,值=0)],
                      [dict(类型标签=100,值=[dict(类型标签=4,值='嵌套')])]):
            状态码,返回=请求(源库网关,'/接口/调用',dict(编号=7960,值=[dict(类型标签=100,值=列表值)]))
            检查(状态码==200 and 返回.get('成功') and 返回['值'][0]==dict(类型标签=100,值=列表值),'列表模块空值及嵌套整槽保真',返回)
        for 错误值表 in ([], [dict(类型标签=1,值=7)]):
            状态码,返回=请求(源库网关,'/接口/调用',dict(编号=7954,值=错误值表))
            检查(not 返回.get('成功') and 返回.get('错误',{}).get('码')==25,'文本模块错型少参拒绝',返回)
        for 原文 in ('','\0','🙂'*100,'-._~','%00+'):
            检查(调用(源库网关,7959,调用(源库网关,7958,原文))==原文,'空文及边界往返')
        for 网关实例 in 实例表:
            数据库=网关实例['目录']/'独立.db'
            with sqlite3.connect(数据库) as 外部连接: 外部连接.execute('create table 独立(编号 integer)'); 外部连接.execute('insert into 独立 values (?)',(网关实例['端口'],))
            状态码,返回=请求(网关实例,'/接口/调用',dict(编号=7952,值=[dict(类型标签=4,值=str(数据库)),dict(类型标签=4,值='SELECT 编号 FROM 独立')]))
            检查(状态码==200 and 返回.get('成功'),'SQLite复合类型与新文本库同实例共存',返回)
            状态码,返回=请求(网关实例,'/接口/调用',dict(编号=7950,值=[dict(类型标签=1,值=2),dict(类型标签=1,值=3)]))
            检查(状态码==200 and 返回.get('成功') and 返回['值'][0]['值']==5,'旧模块同网关不回退',返回)
        for 网关实例 in 实例表:
            数值列表=[dict(类型标签=1,值=2),dict(类型标签=2,值=5.5)]
            状态码,原子返回=请求(网关实例,'/接口/调用',dict(编号=1330,值=[dict(类型标签=100,值=数值列表)]))
            检查(状态码==200 and 原子返回.get('成功'),'数值原子真实求和',原子返回)
            状态码,模块返回=请求(网关实例,'/接口/调用',dict(编号=7951,值=[dict(类型标签=100,值=数值列表)]))
            检查(状态码==200 and 模块返回.get('成功') and 模块返回['值']==原子返回['值'],'同包列表求和跨域真实返回与原子一致',模块返回)
        if 扩展验证 is not None:
            扩展验证(请求,检查,实例表)
        def 并发往返(请求序号):
            网关实例=实例表[请求序号%2]; 原文='网关%s-请求%s-中文🙂'%(网关实例['端口'],请求序号)
            assert 调用(网关实例,7959,调用(网关实例,7958,原文))==原文
        for 轮次 in range(3):
            if 轮次:
                for 网关实例 in 实例表: 装载(网关实例)
            with concurrent.futures.ThreadPoolExecutor(max_workers=12) as 线程池: list(线程池.map(并发往返,range(96)))
            检查表.append('双网关12线程96次跨库往返')
            for 网关实例 in 实例表: 卸载(网关实例)
    finally:
        for 网关实例 in 实例表:
            if 网关实例['进程'].poll() is None:
                网关实例['进程'].terminate()
                try: 网关实例['进程'].wait(timeout=3)
                except subprocess.TimeoutExpired:
                    网关实例['进程'].kill(); 网关实例['进程'].wait(timeout=3)
            网关实例['日志'].close()
        (缓存根/'完整回执.json').write_text(json.dumps(回执表,ensure_ascii=False,indent=2))
    报告=dict(环境准备秒=环境准备秒,环境准备实例数=1,代码缓存复用=True,通过数=len(检查表),HTTP请求数=len(回执表),包数=len(包目录表),实例数=len(实例表),检查项=检查表,网关均退出=all(网关实例['进程'].poll() is not None for 网关实例 in 实例表))
    (缓存根/'验收结果.json').write_text(json.dumps(报告,ensure_ascii=False,indent=2))
    print('扩展量级验收通过：%s包，%s项，%s个HTTP请求。'%(报告['包数'],报告['通过数'],报告['HTTP请求数']))
    return 报告
