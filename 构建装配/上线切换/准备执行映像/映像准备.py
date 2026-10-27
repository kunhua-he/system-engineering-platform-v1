"""只用同一生产启动链准备宿主映像；退出后不留业务进程。"""
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time
from 构建装配.门禁.硬顶常量 import 效率目标毫秒

def 准备执行映像(仓根,代码缓存根,日志路径):
    仓根=Path(仓根).resolve();代码缓存根=Path(代码缓存根).resolve();日志路径=Path(日志路径).resolve()
    日志路径.parent.mkdir(parents=True,exist_ok=True)
    命令表=[str(仓根/'构建环境/构建缓存/release/examples/启动网关'),'--声明根','扩展装载/扩展根声明.json','--后缀表','扩展装载/后缀表.json','--缓存根',str(代码缓存根),'--端口','0','--工具根','.']
    起始时刻=time.monotonic();预算秒=效率目标毫秒/1000;截止时刻=起始时刻+预算秒
    日志字节=bytearray();已就绪=False
    进程=subprocess.Popen(命令表,cwd=仓根,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=True)
    try:
        with selectors.DefaultSelector() as 选择器,open(日志路径,'wb') as 日志文件:
            选择器.register(进程.stdout,selectors.EVENT_READ)
            while time.monotonic()<截止时刻:
                剩余预算=截止时刻-time.monotonic()
                if not 选择器.select(max(0,剩余预算)):break
                输出块=os.read(进程.stdout.fileno(),65536)
                if not 输出块:break
                日志文件.write(输出块);日志文件.flush();日志字节.extend(输出块)
                if b'127.0.0.1:' in 日志字节 and '监听 127.0.0.1:'.encode() in 日志字节:
                    已就绪=True;break
            if not 已就绪:
                raise RuntimeError('生产启动节点未就绪；预算%s秒；实际%.3f秒；%s'%(预算秒,time.monotonic()-起始时刻,日志字节.decode('utf-8',errors='replace')))
            日志正文=日志字节.decode('utf-8',errors='replace')
            坏支持库=[日志行 for 日志行 in 日志正文.splitlines() if '剔除' in 日志行 and '/原子支持库/' in 日志行]
            if 坏支持库:raise RuntimeError('支持库映像准备被剔除：'+'；'.join(坏支持库))
            准备秒=time.monotonic()-起始时刻
    finally:
        if 进程.poll() is None:
            os.killpg(进程.pid,signal.SIGTERM)
            try:进程.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(进程.pid,signal.SIGKILL);进程.wait(timeout=3)
        进程.stdout.close()
    return dict(环境准备秒=准备秒,代码缓存根=str(代码缓存根),日志路径=str(日志路径),准备进程已退出=进程.poll() is not None)
