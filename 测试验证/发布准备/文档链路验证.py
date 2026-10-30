"""真实文档作业与提交钩子：隔离Git副本，无功能制品，禁止Cargo启动。"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

源码根=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(源码根))
from 开发工具.运行数据根 import 覆盖变量名
from 构建装配.门禁.硬顶常量 import 失控护栏毫秒
解释器=Path(sys.executable)
接线清单=['开发工具/MCP服务/验证管理/文档分流.py','开发工具/MCP服务/文档放行.py','开发工具/MCP服务/验证管理/放行结果.py','开发工具/MCP服务/作业.py','测试验证/测试案例/装门禁.sh','测试验证/发布准备/文档分流验证.py','测试验证/发布准备/文档链路验证.py','开发工具/信息核心/信息核心.db']
验证记录=[]

def 运行命令(参数表,目标根,环境表,期望码=0):
    执行回执=subprocess.run(参数表,cwd=目标根,env=环境表,capture_output=True,text=True,timeout=失控护栏毫秒/1000)
    if 执行回执.returncode!=期望码:
        raise AssertionError((参数表,执行回执.returncode,执行回执.stdout,执行回执.stderr))
    return 执行回执

with tempfile.TemporaryDirectory(prefix='文档链路真验收-') as 临时目录:
    临时根=Path(临时目录)
    目标根=临时根/'无功能制品仓'
    环境表=dict(os.environ)
    for 键名 in list(环境表):
        if 键名.startswith('GIT_'):环境表.pop(键名)
    环境表['V1_PY']=str(解释器)
    环境表[覆盖变量名]=str(临时根/'独立运行数据')
    环境表.pop('V1_FULL_GATE',None)
    运行命令(['git','clone','-q','--shared',str(源码根),str(目标根)],临时根,环境表)
    for 路径文本 in 接线清单:
        (目标根/路径文本).parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(源码根/路径文本,目标根/路径文本)
    # 唯一解释器可共享；不复制任何业务制品或构建缓存。
    (目标根/'构建环境/python').symlink_to(解释器.parent.parent)
    with (目标根/'.git/info/exclude').open('a') as 输出句柄:
        输出句柄.write('\n/构建环境/python\n')
    for 参数表 in [['git','config','user.name','文档验证'],['git','config','user.email','verify@example.invalid'],['git','add',*接线清单],['git','commit','--allow-empty','-qm','冻结验收工具基线']]:
        运行命令(参数表,目标根,环境表)
    # 新克隆索引作为独立环境准备，按正式回执给出的原索引器入口建齐；门禁仍实跑。
    索引器路径=shutil.which('codegraph',path=环境表.get('PATH'))
    assert 索引器路径, '缺少正式codegraph索引器'
    运行命令([索引器路径,'init',str(目标根)],目标根,环境表)
    with (目标根/'README.md').open('a') as 输出句柄:输出句柄.write('\n文档分流验证。\n')
    运行命令(['git','add','README.md'],目标根,环境表)
    assert not list((目标根/'扩展根目录').rglob('*.支持库制品'))
    禁止目录=临时根/'禁止构建';禁止目录.mkdir()
    构建标记=临时根/'误触构建.txt'
    (禁止目录/'cargo').write_text('#!/bin/sh\nprintf "误触构建\\n" >> "'+str(构建标记)+'"\nexit 91\n')
    (禁止目录/'cargo').chmod(0o755)
    环境表['PATH']=str(禁止目录)+os.pathsep+环境表.get('PATH','')
    执行代码="import subprocess;from 开发工具.MCP服务.作业 import 具名作业表;raise SystemExit(subprocess.call(具名作业表['放行'],shell=True))"
    判档诊断=运行命令(['git','status','--short','-z'],目标根,环境表)
    print('文档夹具变更：'+判档诊断.stdout,flush=True)
    正向=运行命令([str(解释器),'-c',执行代码],目标根,环境表)
    assert '文档放行通过' in 正向.stdout
    assert not 构建标记.exists()
    验证记录.append({'名称':'具名放行无功能制品文档档','退出码':0,'未调用Cargo':True})
    运行命令(['sh','测试验证/测试案例/装门禁.sh'],目标根,环境表)
    钩子=目标根/'.git/hooks/pre-commit'
    钩子回执=运行命令(['sh',str(钩子)],目标根,环境表)
    assert '文档放行通过' in 钩子回执.stdout and not 构建标记.exists()
    验证记录.append({'名称':'提交钩子文档档','退出码':0,'未调用Cargo':True})
    # 真实源码改动必须返回完整链：拦截Cargo且见退出91，不能误获文档放行。
    with (目标根/'开发工具/MCP服务/作业.py').open('a') as 输出句柄:输出句柄.write('\n# 源码档验证\n')
    反向=运行命令([str(解释器),'-c',执行代码],目标根,环境表,91)
    assert 构建标记.exists() and '文档放行通过' not in 反向.stdout
    验证记录.append({'名称':'源码变更进入原完整链','退出码':91,'捕获Cargo执行':True})
    运行命令(['git','add','开发工具/MCP服务/作业.py'],目标根,环境表)
    # 留下暂存源码，但磁盘恢复HEAD：净差看不见，完整链仍须启动。
    原始内容=运行命令(['git','show','HEAD:开发工具/MCP服务/作业.py'],目标根,环境表).stdout
    (目标根/'开发工具/MCP服务/作业.py').write_text(原始内容)
    隐藏源码回执=运行命令([str(解释器),'-c',执行代码],目标根,环境表,91)
    assert '文档放行通过' not in 隐藏源码回执.stdout
    验证记录.append({'名称':'暂存源码被磁盘还原仍进完整链','退出码':91,'捕获Cargo执行':True})

print(json.dumps({'真实文档链路':验证记录,'夹具已回收':True},ensure_ascii=False))
