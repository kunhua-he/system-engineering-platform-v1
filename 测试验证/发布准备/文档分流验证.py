"""债务1001定向验收：真实Git改动判档，不用模拟业务返回。"""
import importlib
import json
import os
import subprocess
import sys
import tempfile
import sqlite3
from pathlib import Path

源码根 = Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[2]
sys.path.insert(0,str(源码根))
try:
    分流模块=importlib.import_module('开发工具.MCP服务.验证管理.文档分流')
except ModuleNotFoundError:
    raise SystemExit('未实现文档分流；正式放行仍固定进入编译与依赖功能制品的案例链')

def 执行命令(运行根,*参数):
    执行回执=subprocess.run(['git',*参数],cwd=运行根,capture_output=True,text=True,timeout=10)
    assert 执行回执.returncode==0,执行回执.stderr
    return 执行回执.stdout

验证计数=0
with tempfile.TemporaryDirectory(prefix='文档分流验证-') as 临时目录:
    运行根=Path(临时目录)
    执行命令(运行根,'init','-q')
    执行命令(运行根,'config','user.email','verifier@example.invalid')
    执行命令(运行根,'config','user.name','文档验收')
    (运行根/'README.md').write_text('初始文档\n')
    (运行根/'功能实现.py').write_text('实现编号=1\n')
    (运行根/'开发工具/信息核心').mkdir(parents=True)
    库文件=运行根/'开发工具/信息核心/信息核心.db'
    with sqlite3.connect(库文件) as 数据库连接:
        数据库连接.executescript("CREATE TABLE 条款(正文 TEXT); CREATE TABLE 规则(规则值 TEXT); CREATE TABLE 未完成(号 INTEGER); CREATE TABLE 命名登记(名字 TEXT,语义 TEXT,出现次数 INTEGER); INSERT INTO 条款 VALUES('初稿'); INSERT INTO 规则 VALUES('冻结'); INSERT INTO 命名登记 VALUES('正式名字','原语义',1);")
    执行命令(运行根,'add','README.md','功能实现.py','开发工具/信息核心/信息核心.db')
    执行命令(运行根,'commit','-qm','建立夹具基线')
    assert not 分流模块.仅文档变更(运行根);验证计数+=1
    (运行根/'README.md').write_text('更新文档\n')
    assert 分流模块.仅文档变更(运行根);验证计数+=1
    执行命令(运行根,'add','README.md')
    assert 分流模块.仅文档变更(运行根);验证计数+=1
    (运行根/'功能实现.py').write_text('实现编号=2\n')
    assert not 分流模块.仅文档变更(运行根);验证计数+=1
    执行命令(运行根,'restore','功能实现.py')
    (运行根/'未知配置.json').write_text('{}')
    assert not 分流模块.仅文档变更(运行根);验证计数+=1
    (运行根/'未知配置.json').unlink()
    (运行根/'外部引用.md').symlink_to('/dev/null')
    assert not 分流模块.仅文档变更(运行根);验证计数+=1
    (运行根/'外部引用.md').unlink()
    with sqlite3.connect(库文件) as 数据库连接:
        数据库连接.execute("UPDATE 条款 SET 正文='修订正文'")
    assert 分流模块.仅文档变更(运行根);验证计数+=1
    with sqlite3.connect(库文件) as 数据库连接:
        数据库连接.execute("UPDATE 规则 SET 规则值='改变规则'")
    assert not 分流模块.仅文档变更(运行根);验证计数+=1
    with sqlite3.connect(库文件) as 数据库连接:
        数据库连接.execute("UPDATE 规则 SET 规则值='冻结'")
        数据库连接.execute("UPDATE 命名登记 SET 出现次数=2")
    assert 分流模块.仅文档变更(运行根);验证计数+=1
    with sqlite3.connect(库文件) as 数据库连接:
        数据库连接.execute("UPDATE 命名登记 SET 语义='改写权限语义'")
    assert not 分流模块.仅文档变更(运行根);验证计数+=1
    with sqlite3.connect(库文件) as 数据库连接:
        数据库连接.execute("UPDATE 命名登记 SET 语义='原语义'")
    # 三面不一致不能用HEAD到磁盘的净差集藏掉暂存内容。
    执行命令(运行根,'restore','--source=HEAD','--staged','--worktree','开发工具/信息核心/信息核心.db')
    (运行根/'功能实现.py').write_text('实现编号=2\n')
    执行命令(运行根,'add','功能实现.py')
    (运行根/'功能实现.py').write_text('实现编号=1\n')
    assert not 分流模块.仅文档变更(运行根), '索引源码被磁盘净差集隐藏';验证计数+=1
    执行命令(运行根,'restore','--source=HEAD','--staged','--worktree','功能实现.py')
    (运行根/'README.md').write_text('暂存正文\n')
    执行命令(运行根,'add','README.md')
    (运行根/'README.md').write_text('磁盘正文\n')
    assert not 分流模块.仅文档变更(运行根), '验收正文与待提交正文不同';验证计数+=1
    执行命令(运行根,'add','README.md')
    assert 分流模块.仅文档变更(运行根);验证计数+=1
    with sqlite3.connect(库文件) as 数据库连接:
        数据库连接.execute("UPDATE 规则 SET 规则值='暂存改变规则'")
    执行命令(运行根,'add','开发工具/信息核心/信息核心.db')
    with sqlite3.connect(库文件) as 数据库连接:
        数据库连接.execute("UPDATE 规则 SET 规则值='冻结'")
    assert not 分流模块.仅文档变更(运行根), '暂存规则被磁盘正文掩盖';验证计数+=1
    执行命令(运行根,'restore','--source=HEAD','--staged','--worktree','开发工具/信息核心/信息核心.db')
    (运行根/'README.md').unlink()
    (运行根/'README.md').symlink_to('/dev/null')
    执行命令(运行根,'add','README.md')
    (运行根/'README.md').unlink()
    (运行根/'README.md').write_text('普通磁盘正文\n')
    assert not 分流模块.仅文档变更(运行根), '暂存链接类型被磁盘普通文件掩盖';验证计数+=1
    执行命令(运行根,'restore','--source=HEAD','--staged','--worktree','README.md')
    执行命令(运行根,'update-index','--chmod=+x','README.md')
    assert not 分流模块.仅文档变更(运行根), '暂存执行模式被磁盘普通模式掩盖';验证计数+=1
    执行命令(运行根,'restore','--source=HEAD','--staged','--worktree','README.md')
    (运行根/'README.md').write_text('文档改动\n')
    原值=os.environ.get('V1_FULL_GATE')
    os.environ['V1_FULL_GATE']='1'
    assert not 分流模块.仅文档变更(运行根);验证计数+=1
    if 原值 is None:os.environ.pop('V1_FULL_GATE')
    else:os.environ['V1_FULL_GATE']=原值
print(json.dumps({'真实Git判档通过':验证计数,'源码或未知变更不走快档':True},ensure_ascii=False))
