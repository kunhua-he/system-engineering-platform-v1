"""按需执行定向实证：滑动30秒真等待，冷/热分测，只起所属临时网关。"""
import concurrent.futures
import json
import os
from pathlib import Path
import socket
import statistics
import subprocess
import threading
import time
import urllib.parse
import urllib.request

from 构建装配.上线切换.准备执行映像 import 准备执行映像


def 执行按需验收(仓根,缓存根):
    仓根=Path(仓根).resolve()
    缓存根=Path(缓存根).resolve()
    缓存根.mkdir(exist_ok=True)
    回执表=[]
    验收报告={'环境准备':准备执行映像(仓根,缓存根/'缓存',缓存根/'环境准备.log')}
    连接器=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with socket.socket() as 探针:
        探针.bind(('127.0.0.1',0));端口=探针.getsockname()[1]
    部署表=[]
    for 包路径 in sorted((仓根/'扩展根目录').glob('*/*/包声明.json')):
        if 包路径.parent.parent.name=='技能封装库':continue
        包声明=json.loads(包路径.read_text());包目录=包路径.parent
        是模块=包目录.parent.name=='组合模块库'
        部署表.append(dict(标识串=包声明['标识串'],版本=dict(主版本=包声明['实现版本']['主'],次版本号=包声明['实现版本']['次'],构建=包声明['实现版本']['构建']),制品路径=str(包目录/(包目录.name+('.模块制品' if 是模块 else '.支持库制品'))),启动程序=str(仓根/'构建环境/构建缓存/debug/examples/工作进程') if 是模块 else ''))
    配置路径=缓存根/'部署.json'
    配置路径.write_text(json.dumps(dict(跨进程=部署表,子进程数上限=2),ensure_ascii=False))
    日志文件=(缓存根/'网关.log').open('w')
    进程=subprocess.Popen([str(仓根/'构建环境/构建缓存/release/examples/启动网关'),'--声明根','扩展装载/扩展根声明.json','--后缀表','扩展装载/后缀表.json','--端口',str(端口),'--缓存根',str(缓存根/'缓存'),'--跨进程配置',str(配置路径),'--工具根','.'],cwd=仓根,stdout=日志文件,stderr=subprocess.STDOUT,start_new_session=False)
    
    def 请求(路径,参数=None):
        起点=time.perf_counter_ns()
        请求对象=urllib.request.Request('http://127.0.0.1:%s%s'%(端口,urllib.parse.quote(路径,safe='/')),data=None if 参数 is None else json.dumps(参数,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
        with 连接器.open(请求对象,timeout=5) as 响应:
            正文=json.loads(响应.read());assert 响应.status==200 and 正文.get('成功'),(路径,参数,正文)
        耗时=(time.perf_counter_ns()-起点)/1000
        回执表.append(dict(请求=参数,路径=路径,正文=正文,往返微秒=耗时,时刻=time.monotonic()))
        return 正文,耗时
    
    def 子进程表():
        行表=subprocess.check_output(['ps','-axo','pid=,ppid=,args='],text=True).splitlines()
        return {int(进程字段[0]):进程字段[2] for 进程行 in 行表 if len(进程字段:=进程行.strip().split(None,2))==3 and int(进程字段[1])==进程.pid and '工作进程' in 进程字段[2]}
    
    def 调加法(序号=0):
        正文,耗时=请求('/接口/调用',dict(编号=7950,值=[dict(类型标签=1,值=序号),dict(类型标签=1,值=3)]))
        assert 正文['值'][0]['值']==序号+3,正文
        return 正文,耗时
    
    def 调同包编号(序号):
        if 序号 % 2 == 0:
            return 调加法(序号)
        原列表 = [dict(类型标签=4,值='中文'),dict(类型标签=1,值=序号)]
        正文,耗时=请求('/接口/调用',dict(编号=7960,值=[dict(类型标签=100,值=原列表)]))
        assert 正文['值']==[dict(类型标签=100,值=原列表)],正文
        return 正文,耗时

    def 等到(期限):
        while (剩余时长:=期限-time.monotonic())>0:time.sleep(min(剩余时长,0.05))
    
    def 统计(耗时样本):
        排序表=sorted(耗时样本)
        return dict(样本数=len(排序表),中位微秒=round(statistics.median(排序表),3),P95微秒=round(排序表[min(len(排序表)-1,(len(排序表)*95+99)//100-1)],3),最大微秒=round(max(排序表),3),亚毫秒样本数=sum(耗时<1000 for 耗时 in 排序表))
    
    采样线程=None
    停止取样=threading.Event();进程峰值=[0];已观察进程=set()
    def 取样():
        while not 停止取样.is_set():
            进程表=子进程表();进程峰值[0]=max(进程峰值[0],len(进程表));已观察进程.update(进程表)
            停止取样.wait(.01)
    
    try:
        截止时刻=time.monotonic()+5
        while time.monotonic()<截止时刻:
            assert 进程.poll() is None,(缓存根/'网关.log').read_text()
            with socket.socket() as 探针:
                if 探针.connect_ex(('127.0.0.1',端口))==0:break
            time.sleep(.02)
        else:raise RuntimeError('临时网关未监听')
        _,装载耗时=请求('/接口/生命周期',dict(动作='装载'))
        正文,_=请求('/接口/生命周期')
        assert 正文['数据']['跨进程登记数']==sum(bool(部署项['启动程序']) for 部署项 in 部署表) and 正文['数据']['跨进程运行数']==0,正文
        assert not 子进程表(),'登记不应产生业务子进程'
        验收报告['静态登记']=dict(登记数=正文['数据']['跨进程登记数'],运行数=0,HTTP往返微秒=装载耗时)
        采样线程=threading.Thread(target=取样);采样线程.start()
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as 线程池:list(线程池.map(调同包编号,range(16)))
        停止取样.set();采样线程.join()
        assert 进程峰值[0]<=1 and len(子进程表())==1,(进程峰值,子进程表())
        验收报告['并发首次启动']=dict(请求数=16,观察峰值=进程峰值[0],观察到的进程=sorted(已观察进程),完成后进程=list(子进程表()))
        服务器样本=[];往返样本=[]
        for 序号 in range(200):
            正文,耗时=调加法(序号);往返样本.append(耗时);服务器样本.append(正文['耗时微秒'])
        验收报告['热加法服务端']=统计(服务器样本);验收报告['热加法完整HTTP']=统计(往返样本)
        旧进程=set(子进程表());起测时刻=time.monotonic()
        等到(起测时刻+20)
        调加法();续期时刻=time.monotonic()
        等到(起测时刻+31)
        assert set(子进程表())==旧进程,'续期后原30秒到点不应回收'
        验收报告['滑动续期保留原进程']=True
        等到(续期时刻+30.2)
        截止时刻=time.monotonic()+3
        while 子进程表() and time.monotonic()<截止时刻:time.sleep(.02)
        assert not 子进程表(),'滑动30秒到期未回收'
        正文,_=请求('/接口/生命周期')
        assert 正文['数据']['跨进程登记数']==sum(bool(部署项['启动程序']) for 部署项 in 部署表) and 正文['数据']['跨进程运行数']==0,正文
        验收报告['回收后登记仍在']=True
        正文,重启耗时=调加法();新进程=set(子进程表())
        assert len(新进程)==1 and 新进程.isdisjoint(旧进程),(新进程,旧进程)
        验收报告['回收后再调用']=dict(HTTP往返微秒=重启耗时,服务端微秒=正文['耗时微秒'],新进程=sorted(新进程))
        # 两个活进程配额下轮流调用三个域，验证空闲腾位而不是拒绝后续能力。
        for 轮次 in range(3):
            调加法(轮次)
            for 编号,文本值 in ((7954,'中文 /'),(7961,'{"值":"中文 /"}')):请求('/接口/调用',dict(编号=编号,值=[dict(类型标签=4,值=文本值)]))
            正文,_=请求('/接口/生命周期');assert 正文['数据']['跨进程运行数']<=2,正文
        验收报告['额度2执行3域']=True
        验收报告['通过']=True
    finally:
        停止取样.set()
        if 采样线程 is not None:采样线程.join(timeout=2)
        所属进程=set(子进程表())
        if 进程.poll() is None:
            进程.terminate()
            try:进程.wait(timeout=3)
            except subprocess.TimeoutExpired:进程.kill();进程.wait(timeout=3)
        日志文件.close()
        截止时刻=time.monotonic()+3
        while time.monotonic()<截止时刻:
            存活进程=set()
            for 子进程号 in 所属进程:
                try:os.kill(子进程号,0);存活进程.add(子进程号)
                except ProcessLookupError:pass
            if not 存活进程:break
            time.sleep(.02)
        验收报告['退出后所属子进程残留']=sorted(存活进程)
        (缓存根/'回执.json').write_text(json.dumps(回执表,ensure_ascii=False,indent=2))
        (缓存根/'结果.json').write_text(json.dumps(验收报告,ensure_ascii=False,indent=2))
        assert not 存活进程,验收报告
    print(json.dumps(验收报告,ensure_ascii=False))
    return 验收报告
