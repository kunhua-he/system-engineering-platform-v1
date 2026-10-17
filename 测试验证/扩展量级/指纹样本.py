"""指纹节点正反样本：仅改自有临时扩展，不触碰生产源码或正式快照。"""
import contextlib
import io
from pathlib import Path
import tempfile
from unittest.mock import patch


def 执行指纹样本():
    from 构建装配.形态装配.扩展指纹 import 核心
    with tempfile.TemporaryDirectory(prefix='v1指纹反例-') as 临时目录:
        临时根 = Path(临时目录)
        伪入口 = 临时根/'构建装配/形态装配/扩展指纹/核心.py'
        包目录 = 临时根/'扩展根目录/原子支持库/指纹验证库'
        包目录.mkdir(parents=True)
        (包目录/'包声明.json').write_text('{}')
        伪入口.parent.mkdir(parents=True)
        with patch.object(核心,'__file__',str(伪入口)), contextlib.redirect_stdout(io.StringIO()):
            assert 核心.入口函数(['--检查'])==1
            assert 核心.入口函数([])==0
            assert 核心.入口函数(['--检查'])==0
            (包目录/'包声明.json').write_text('{"名称":"已变"}')
            assert 核心.入口函数(['--检查'])==1
            import sys
            from types import SimpleNamespace
            import subprocess
            sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'准入判据'))
            from 准入判据.判据 import 判_14_指纹重跑命令
            伪入口.write_text('')
            测试世界 = SimpleNamespace(仓根=临时根, 指纹件=lambda:包目录/'指纹.json', 指纹脚本=lambda:伪入口)
            # 只替代原编译器专用外部命令；通用检查真实读取临时包与失配快照。
            with patch('准入判据.判据.subprocess.run', return_value=subprocess.CompletedProcess([],0,'','')):
                assert 判_14_指纹重跑命令(测试世界)[0]=='失败', '通用失配不得准入通过'
                assert 核心.入口函数([])==0
                assert 判_14_指纹重跑命令(测试世界)[0]=='通过', '刷新后必须通过'
            assert 核心.入口函数([])==0
            (包目录/'新增.程序文本').write_text('返回 1')
            assert 核心.入口函数(['--检查'])==1
            assert 核心.入口函数([])==0
            (包目录/'新增.程序文本').unlink()
            assert 核心.入口函数(['--检查'])==1
    print('指纹正反样本通过：缺快照、正常、内容漂移、新件、删件均按预期。')


def 自检_扩展指纹接线():
    try:
        执行指纹样本()
    except Exception as 错误:
        return ['扩展指纹接线正反样本失败：%s' % 错误]
    return []
