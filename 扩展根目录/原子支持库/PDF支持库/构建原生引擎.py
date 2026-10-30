"""构建V1扩展拥有的原生PDFKit执行体。

产物文件名不能直接交给swiftc：非ASCII名会被写进链接器ad-hoc签名标识，
实测CoreML执行流随即报e5rt错误（同源同图，ASCII名10/10成功、中文名0/10失败）。
因此先编译到ASCII临时名，成功后再改名为目标中文名。
编译完默认跑一次预热：执行体首次运行要加载系统模型（实测13.24秒），
预热后热调用0.24秒；项目超时硬顶5秒，所以加载必须发生在调用之外。

落点：缺省构建到包内 原生执行体/PDF处理（唯一构建源）。制品装配把它复制到
制品根（与 网关 同级），运行期支持库按 current_exe 同目录解析；部署到运行根时再从
包内复制过去。漏带这一件，换制品实例后能力会在运行期报 6205。
"""
import argparse as 参数解析
import os as 环境读取
import pathlib as 路径处理
import subprocess as 进程调用
import time

编译超时秒 = 5
预热超时秒 = 5

def 主入口():
    参数对象=参数解析.ArgumentParser(description='构建原生PDFKit执行体（编译后默认预热）')
    参数对象.add_argument('输出路径',nargs='?',default=str(路径处理.Path(__file__).resolve().parent/'原生执行体'/'PDF处理'),help='构建落点；缺省=包内 原生执行体/PDF处理（制品装配从这里带进制品根），部署时再复制到网关执行体同目录')
    参数对象.add_argument('--跳过预热',action='store_true',help='只编译，不跑预热')
    调用参数=参数对象.parse_args()
    输出路径=路径处理.Path(调用参数.输出路径)
    if not 输出路径.is_absolute():
        参数对象.error('输出路径必须为绝对路径')
    开始时刻=time.monotonic()
    输出路径.parent.mkdir(parents=True,exist_ok=True)
    原生源码=路径处理.Path(__file__).parent/'原生引擎'/'PDF处理.swift'
    临时产物=输出路径.parent/'v1-pdf.build'
    环境变量=dict(环境读取.environ)
    环境变量.setdefault('DEVELOPER_DIR','/Library/Developer/CommandLineTools')
    进程调用.run(['xcrun','swiftc','-O',str(原生源码),'-o',str(临时产物)],env=环境变量,check=True,timeout=编译超时秒)
    临时产物.replace(输出路径)
    预热状态='跳过'
    if not 调用参数.跳过预热:
        try:
            进程调用.run([str(输出路径),'--预热'],check=True,timeout=预热超时秒)
            预热状态='完成'
        except 进程调用.TimeoutExpired:
            预热状态='超时（首次加载仍慢，请再跑一次本脚本）'
    用时毫秒=int((time.monotonic()-开始时刻)*1000)
    print('产物 %s · 预热 %s · 用时 %d 毫秒' % (输出路径,预热状态,用时毫秒))

if __name__=='__main__':
    主入口()
