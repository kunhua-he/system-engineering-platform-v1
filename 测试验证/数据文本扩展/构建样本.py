"""原生库构建目标接线单元；真实引擎与HTTP另由正式预构建及验收覆盖。"""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def 执行构建接线样本():
    from 构建装配.上线切换.构建制品 import 扩展 as 构建节点
    记录表=[]
    def 记命令(命令表,**具名参数):
        记录表.append(命令表)
        return SimpleNamespace(stdout="本次Cargo回执")
    with patch.object(构建节点,'跑子进程',side_effect=记命令),patch.object(构建节点,'打包支持库制品') as 打包函数,patch.object(构建节点,'读库名',return_value='示例库名'),patch.object(构建节点,'记扩展产物回执') as 回执函数,patch.object(Path,'glob',side_effect=AssertionError('不允许扫描缓存猜依赖')):
        构建节点.建扩展产物(dict(落点=Path('示例支持库')))
        assert len(记录表)==1,记录表
        命令表=记录表[0]
        assert 命令表[:2]==['cargo','rustc'],命令表
        assert '--' not in 命令表 and '--extern' not in 命令表,命令表
        assert 命令表[-2:]==['--crate-type','cdylib'],命令表
        assert '--locked' in 命令表 and '--offline' in 命令表,命令表
        assert 打包函数.call_count==1
        assert "--message-format=json-render-diagnostics" in 命令表
        assert 回执函数.call_args.args[0]=="本次Cargo回执"
    with patch.object(构建节点,'跑子进程',side_effect=SystemExit('引擎构建拒绝')),patch.object(构建节点,'打包支持库制品') as 打包函数:
        try:
            构建节点.建扩展产物(dict(落点=Path('示例支持库')))
        except SystemExit as 错误:
            assert str(错误)=='引擎构建拒绝'
        else:
            raise AssertionError('构建失败不得当作成功')
        assert 打包函数.call_count==0,'构建失败不得继续打包'
    print('原生库构建目标接线及失败中止样本通过。')


def 自检_原生库构建目标():
    try:
        执行构建接线样本()
    except Exception as 错误:
        return ['原生库构建目标接线失败：%s'%错误]
    return []
