"""发布映像接线的隔离反证；真实制品HTTP启动另行验证。"""
import importlib
from pathlib import Path
import sys
import tempfile
from unittest import mock


def 执行自检(仓根):
    仓根 = Path(仓根).resolve()
    sys.path.insert(0, str(仓根))
    sys.path.insert(0, str(仓根 / '构建装配/上线切换'))
    实例模块 = importlib.import_module('上线切换.上线实例')
    命令模块 = importlib.import_module('上线切换.命令')
    准备模块 = importlib.import_module('构建装配.上线切换.准备执行映像.映像准备')
    with tempfile.TemporaryDirectory(prefix='发布接线-', dir=str(Path.home() / '.hermes/cache/scratch')) as 暂存目录:
        运行目录 = Path(暂存目录)
        (运行目录 / '日志').mkdir()
        制品目录 = 运行目录 / '目标制品'
        制品目录.mkdir()
        # 第一项：环境准备必须选择目标不可变制品，不偷用源仓产物。
        with mock.patch.object(准备模块.subprocess, 'Popen', side_effect=RuntimeError('探针停止')) as 起进程:
            try:
                准备模块.准备执行映像(仓根, 运行目录 / '缓存', 运行目录 / '准备.log', 制品根目录=制品目录)
            except RuntimeError as 异常:
                assert str(异常) == '探针停止', str(异常)
            调用参数 = 起进程.call_args
            assert 调用参数.args[0][0] == str(制品目录 / '网关'), 调用参数
            assert 调用参数.kwargs['cwd'] == 制品目录, 调用参数
        # 第二项：准备和真实启动必须指向同一缓存根，日志句柄要关闭。
        with mock.patch.object(实例模块, '运行根', 运行目录), \
             mock.patch.object(实例模块, '制品目录', return_value=制品目录), \
             mock.patch.object(实例模块, '准备执行映像', return_value={}) as 准备引擎, \
             mock.patch.object(实例模块.subprocess, 'Popen') as 起进程, \
             mock.patch.object(实例模块, '等端口', return_value=45678), \
             mock.patch.object(实例模块, '写指针'):
            实例模块.准备实例映像('目标制品')
            实例模块.起实例('目标制品', 0)
            启动命令 = 起进程.call_args.args[0]
            实际缓存 = 启动命令[启动命令.index('--缓存根') + 1]
            assert 实际缓存 == str(准备引擎.call_args.args[1]), 启动命令
            assert 准备引擎.call_args.kwargs['制品根目录'] == 制品目录
            assert 起进程.call_args.kwargs['stdout'].closed
        # 第三项：目标准备失败时，不许先停旧实例。
        动作表 = []
        def 拒绝准备(标识):
            动作表.append('准备')
            raise RuntimeError('目标准备失败')
        with mock.patch.object(命令模块, '流量端口', return_value=45678), \
             mock.patch.object(命令模块, '读指针', return_value={'制品标识': '在服制品', 'pid': 123}), \
             mock.patch.object(命令模块, '活着的实例', return_value=[{'制品标识': '在服制品', 'pid': 123}]), \
             mock.patch.object(命令模块, '进程活着', return_value=False), \
             mock.patch.object(命令模块, '停实例', side_effect=lambda 实例台账: 动作表.append('停止')), \
             mock.patch.object(命令模块, '准备实例映像', side_effect=拒绝准备, create=True), \
             mock.patch.object(命令模块, '起实例', side_effect=RuntimeError('不应到达启动')), \
             mock.patch.object(命令模块, '记回退账'), \
             mock.patch.object(命令模块, '运行根', 运行目录):
            try:
                命令模块.落到流量端口('目标制品', '切换')
            except RuntimeError:
                pass
            assert 动作表 == ['准备'], 动作表
    print('发布准备接线：3项隔离反证通过')

