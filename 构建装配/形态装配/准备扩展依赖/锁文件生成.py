"""仅生成显式指定支持库的Cargo.lock；不编译、不联网、不改其他扩展。"""
import sys
import subprocess
from pathlib import Path
仓根=Path(__file__).resolve().parents[3]
if str(仓根) not in sys.path:
    sys.path.insert(0, str(仓根))
from 构建装配.形态装配.生成模块制品.编译模块 import 编译环境


def 入口函数(参数表):
    仓根=Path(__file__).resolve().parents[3]
    if not 参数表:
        print('用法：准备扩展依赖.py 仓内支持库目录 [仓内支持库目录...]')
        return 2
    for 包路径 in 参数表:
        包目录=(仓根/包路径).resolve()
        if not 包目录.is_relative_to(仓根/'扩展根目录/原子支持库'):
            print('不是仓内独立支持库：'+包路径)
            return 2
        if not (包目录/'Cargo.toml').is_file():
            # 整包迁移：源清单、包声明与源码均已撤掉，才回收本包生成锁。
            if (包目录/'包声明.json').exists() or any((包目录/'src').rglob('*.rs')):
                print('支持库仍有声明或源码，缺少Cargo清单：'+包路径)
                return 2
            if not (包目录/'Cargo.lock').is_file():
                print('既无Cargo清单也无待回收锁：'+包路径)
                return 2
            (包目录/'Cargo.lock').unlink()
            continue
        try:
            回执=subprocess.run(['cargo','generate-lockfile','--offline','--manifest-path',str(包目录/'Cargo.toml')],cwd=仓根,env=编译环境(仓根/'构建环境/构建缓存'),capture_output=True,text=True,timeout=5)
        except (OSError,subprocess.TimeoutExpired) as 错误:
            print('扩展锁生成失败：%s：%s'%(包路径,错误))
            return 1
        if 回执.returncode:
            print('扩展锁生成失败：%s：%s'%(包路径,回执.stderr or 回执.stdout))
            return 回执.returncode
        锁正文=(包目录/'Cargo.lock').read_text(encoding='utf-8')
        头标='# 生成物 · 禁手改 · 生成器：构建装配/形态装配/准备扩展依赖.py\n'
        if 头标 not in 锁正文:
            (包目录/'Cargo.lock').write_text(头标+锁正文,encoding='utf-8')
    return 0
