"""当前施工制品的正式 HTTP 定向验收，不代替合主干后复验。"""
import base64
import concurrent.futures
import json
import pathlib
import socket
import shutil
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
    记录返回 = 响应正文
    if 载荷 is not None and 载荷.get('编号') == 3112:
        记录返回 = dict(成功=响应正文.get('成功'), 错误=响应正文.get('错误'),
                        返回类型=响应正文.get('值', [{}])[0].get('类型标签'),
                        编码字符数=len(响应正文.get('值', [{}])[0].get('值', '')) if 响应正文.get('成功') else 0)
    记录载荷 = 载荷
    if 载荷 is not None and 载荷.get('编号') == 3113:
        记录载荷 = dict(编号=3113, 文本字节数=len(载荷['值'][2]['值'].encode()) if isinstance(载荷['值'][2]['值'], str) else None)
    回执.append(dict(路径=路径,载荷=记录载荷,状态=状态,返回=记录返回))
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
    assert 请求('接口/能力/3112')[1]['契约']['返回类型'] == 5
    for 请求字节数 in [0, 65537, 5242881, 52428800]:
        整件内容 = b'V' * 请求字节数
        (样本根/'整件样本.bin').write_bytes(整件内容)
        返回 = 调用(3112, [str(样本根), '整件样本.bin', 请求字节数], [4,4,1])
        assert base64.b64decode(返回['值'][0]['值']) == 整件内容
    调用(3112, [str(样本根), '整件样本.bin', 52428799], [4,4,1], True)
    for 请求字节数 in [-1, 52428801]:
        调用(3112, [str(样本根), '整件样本.bin', 请求字节数], [4,4,1], True)
    for 整件路径 in ['../越界', '/绝对路径', '不存在文本.txt', '.', '目录链接/中文文本.txt', '文件链接']:
        调用(3112, [str(样本根), 整件路径, 52428800], [4,4,1], True)
    调用(3112, [str(样本根), '整件样本.bin', 1.0], [4,4,2], True)
    assert 请求('接口/能力/3113')[1]['契约']['返回类型'] == 1
    写入路径 = 样本根/'写入目录/中文样本.txt'
    for 写入内容 in ['中文新建', '覆盖中文', '', '\x00' * 131072]:
        返回 = 调用(3113, [str(样本根), '写入目录/中文样本.txt', 写入内容], [4,4,4])
        assert 返回['值'][0]['值'] == len(写入内容.encode())
        assert 写入路径.read_bytes() == 写入内容.encode()
    写入路径.chmod(0o640)
    调用(3113, [str(样本根), '写入目录/中文样本.txt', '保留原文'], [4,4,4])
    assert 写入路径.stat().st_mode & 0o777 == 0o640
    拒绝返回 = 调用(3113, [str(样本根), '写入目录/中文样本.txt', 'X' * 131073], [4,4,4], True)
    assert 拒绝返回['错误']['码'] == 3012
    assert 写入路径.read_text() == '保留原文'
    for 写入目标 in ['../越界', '/绝对路径', '.', '目录链接/中文文本.txt', '文件链接']:
        调用(3113, [str(样本根), 写入目标, '错误覆盖'], [4,4,4], True)
    assert (样本根/'中文文本.txt').read_bytes() == 大字节
    调用(3113, [str(样本根), '写入目录/中文样本.txt', 7], [4,4,1], True)
    版本内容表 = ['A' * 32768, 'B' * 32768]
    调用(3113, [str(样本根), '写入目录/中文样本.txt', 版本内容表[0]], [4,4,4])
    def 并发写入(序号):
        for 轮次 in range(8):
            调用(3113, [str(样本根), '写入目录/中文样本.txt', 版本内容表[(序号+轮次)%2]], [4,4,4])
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as 写入线程池:
        写入队列 = [写入线程池.submit(并发写入, 序号) for 序号 in range(4)]
        for _ in range(24):
            返回 = 调用(3112, [str(样本根), '写入目录/中文样本.txt', 65536], [4,4,1])
            assert base64.b64decode(返回['值'][0]['值']).decode() in 版本内容表
        for 写入作业 in 写入队列: 写入作业.result()
    assert not list((样本根/'写入目录').glob('.原子写入-*'))
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
    print('首链真实HTTP通过：受控头部与整读50MiB/原子覆盖并发/限流/越界/链接/错型/8路24次并发；请求数',len(回执),flush=True)
finally:
    进程.terminate()
    try:进程.wait(3)
    except subprocess.TimeoutExpired:进程.kill();进程.wait()
    日志.close()
    (缓存/'真实回执.json').write_text(json.dumps(回执,ensure_ascii=False,indent=2))
    assert 进程.poll() is not None
    if (缓存/'样本文件').exists(): shutil.rmtree(缓存/'样本文件')
