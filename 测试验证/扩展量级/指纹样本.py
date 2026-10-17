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
            assert 核心.入口函数([])==0
            (包目录/'新增.程序文本').write_text('返回 1')
            assert 核心.入口函数(['--检查'])==1
            assert 核心.入口函数([])==0
            (包目录/'新增.程序文本').unlink()
            assert 核心.入口函数(['--检查'])==1
    print('指纹正反样本通过：缺快照、正常、内容漂移、新件、删件均按预期。')
