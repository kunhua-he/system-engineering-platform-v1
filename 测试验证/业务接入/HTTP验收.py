"""当前施工制品的正式 HTTP 定向验收，不代替合主干后复验。"""
import base64
import concurrent.futures
import json
import pathlib
import socket
import sys
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

验收仓根=pathlib.Path.cwd()
缓存=pathlib.Path(sys.argv[1]).resolve()
缓存.mkdir(exist_ok=True)
连接=urllib.request.build_opener(urllib.request.ProxyHandler({}))
回执=[]
with socket.socket() as 探针:
    探针.bind(('127.0.0.1',0)); 端口=探针.getsockname()[1]
日志=open(缓存/'网关日志.txt','w')
进程=subprocess.Popen([str(验收仓根/'构建环境/构建缓存/release/examples/启动网关'),'--声明根','扩展装载/扩展根声明.json','--后缀表','扩展装载/后缀表.json','--端口',str(端口),'--缓存根',str(缓存/'执行映像'),'--工具根','.'],stdout=日志,stderr=subprocess.STDOUT)
def 请求(路径,载荷=None):
    请求对象=urllib.request.Request(f'http://127.0.0.1:{端口}/'+urllib.parse.quote(路径,safe='/'),data=None if 载荷 is None else json.dumps(载荷,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
    try:
        with 连接.open(请求对象,timeout=5) as 响应: 状态,响应正文=响应.status,json.load(响应)
    except urllib.error.HTTPError as 错误:
        状态,响应正文=错误.code,json.load(错误)
    回执.append(dict(路径=路径,载荷=载荷,状态=状态,返回=响应正文))
    return 状态,响应正文

def 调用(编号,值,类型,失败=False):
    状态,返回=请求('接口/调用',dict(编号=编号,值=[dict(类型标签=参数类型,值=子值) for 子值,参数类型 in zip(值,类型)]))
    assert (返回.get('成功') is False if 失败 else 状态==200 and 返回.get('成功') is True),(状态,返回)
    return 返回
try:
    截止=time.monotonic()+60
    while time.monotonic()<截止:
        if 进程.poll() is not None: raise RuntimeError((缓存/'网关日志.txt').read_text())
        try:
            if 请求('接口')[0]==200: break
        except (OSError,urllib.error.URLError):time.sleep(.05)
    else:raise RuntimeError('网关准备超时')
    装载=请求('接口/运维/生命周期',{'动作':'装载'})
    assert 装载[0]==200,装载
    assert 请求('接口/能力/3111')[1]['契约']['返回类型']==5
    assert 请求('接口/能力/6101')[1]['契约']['返回类型']==103
    样本根=缓存/'样本文件';样本根.mkdir(exist_ok=True)
    大字节=('中文预览🙂\n'*120000).encode()
    (样本根/'中文文本.txt').write_bytes(大字节)
    (样本根/'空白文本.txt').write_bytes(b'')
    for 请求字节数 in [0,65537,1048576]:
        返回=调用(3111,[str(样本根),'中文文本.txt',请求字节数],[4,4,1]);assert base64.b64decode(返回['值'][0]['值'])==大字节[:请求字节数]
    assert base64.b64decode(调用(3111,[str(样本根),'空白文本.txt',100],[4,4,1])['值'][0]['值'])==b''
    for 路径 in ['../越界','/绝对路径','不存在文本.txt','.']:
        调用(3111,[str(样本根),路径,100],[4,4,1],True)
    for 名称,目标 in [('目录链接',样本根),('文件链接',样本根/'中文文本.txt')]:
        链接=样本根/名称
        if not 链接.is_symlink():链接.symlink_to(目标)
    for 路径 in ['目录链接/中文文本.txt','文件链接']:
        调用(3111,[str(样本根),路径,100],[4,4,1],True)
    调用(3111,[str(样本根),'中文文本.txt',1048577],[4,4,1],True)
    调用(3111,[str(样本根),'中文文本.txt',1.0],[4,4,2],True)
    for 失败次数,锁定 in [(0,0),(4,0),(5,1),(6,1)]:
        返回=调用(6102,[失败次数,5],[1,1]);assert 返回['值'][0]['值']==锁定
    调用(6102,[-1,5],[1,1],True)
    调用(6102,[0,0],[1,1],True)
    for 令牌,预期 in [(10.0,True),(0.0,False)]:
        返回=调用(6101,[10,2.0,令牌,100.0,100.0,1],[1,2,2,2,2,1]);assert 返回['值'][0]['值']['放行']['值']==int(预期)
    调用(6101,[0,2.0,0.0,100.0,101.0,1],[1,2,2,2,2,1],True)
    def 并发样本(序号):
        返回=调用(3111,[str(样本根),'中文文本.txt',65537+序号],[4,4,1]);assert base64.b64decode(返回['值'][0]['值'])==大字节[:65537+序号]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as 线程池:list(线程池.map(并发样本,range(24)))
    print('首链真实HTTP通过：受控读取/限流/越界/链接/错型/8路24次并发；请求数',len(回执),flush=True)
finally:
    进程.terminate()
    try:进程.wait(3)
    except subprocess.TimeoutExpired:进程.kill();进程.wait()
    日志.close()
    (缓存/'真实回执.json').write_text(json.dumps(回执,ensure_ascii=False,indent=2))
    assert 进程.poll() is not None
