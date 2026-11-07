"""部署所有权定向反证；不启动网关，不触碰正式运行根。"""
import importlib
import fcntl
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

起始时刻 = time.monotonic()

仓根 = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(仓根))
sys.path.insert(0, str(仓根 / '构建装配/上线切换'))
实例模块 = importlib.import_module('上线切换.上线实例')
命令模块 = importlib.import_module('上线切换.命令')
口径模块 = importlib.import_module('运行数据根.口径')
覆盖变量名 = 口径模块.覆盖变量名
sys.argv = sys.argv[:1]


class 所有权验证(unittest.TestCase):
    def test_候选预检使用冷启动预算(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home() / '.hermes/cache/scratch')) as 暂存目录:
            暂存根 = Path(暂存目录)
            with mock.patch.object(实例模块, '运行根', 暂存根), mock.patch.object(实例模块, '制品目录', return_value=暂存根), mock.patch.object(实例模块, '准备执行映像') as 预检:
                实例模块.准备实例映像('候选制品')
                预算毫秒 = 预检.call_args.kwargs.get('预算毫秒')
                self.assertEqual(预算毫秒, 90000)

    def test_候选隔离与正式继承(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home() / '.hermes/cache/scratch')) as 暂存目录:
            暂存根 = Path(暂存目录)
            (暂存根 / '日志').mkdir()
            with mock.patch.object(实例模块, '运行根', 暂存根), mock.patch.object(实例模块, '制品目录', return_value=暂存根), mock.patch.object(实例模块.subprocess, 'Popen') as 启动口, mock.patch.object(实例模块, '等端口', return_value=43299), mock.patch.object(实例模块, '写指针'), mock.patch.dict(os.environ, {覆盖变量名: str(暂存根 / '正式根')}):
                with mock.patch.object(实例模块, '读进程指纹', return_value='归属指纹', create=True):
                    启动口.return_value.pid = 999999
                    候选台账 = 实例模块.起实例('候选制品', 0)
                    启动环境 = 启动口.call_args.kwargs.get('env', {})
                    self.assertIn(覆盖变量名, 启动环境)
                    self.assertNotEqual(启动环境[覆盖变量名], os.environ[覆盖变量名])
                    self.assertEqual(候选台账['运行数据根'], 启动环境[覆盖变量名])
                    self.assertTrue(Path(候选台账['运行数据根']).is_dir())
                    正式台账 = 实例模块.起实例('正式制品', 43298)
                    self.assertEqual(启动口.call_args.kwargs['env'][覆盖变量名], os.environ[覆盖变量名])
                    self.assertFalse(正式台账['自建运行根'])

    def test_强杀未退场不得成功(self):
        with mock.patch.object(实例模块, '进程活着', return_value=True), mock.patch.object(实例模块, '核对实例归属', create=True), mock.patch.object(实例模块, '停等秒', 0.01), mock.patch.object(实例模块.os, 'kill'):
            with self.assertRaises(SystemExit):
                实例模块.停实例({'pid': 999999, '制品落点': '/未使用'})

    def test_停止失败禁止接管(self):
        with mock.patch.object(命令模块, '流量端口', return_value=43298), mock.patch.object(命令模块, '读指针', return_value={}), mock.patch.object(命令模块, '准备实例映像'), mock.patch.object(命令模块, '活着的实例', return_value=[{'pid': 999999}]), mock.patch.object(命令模块, '停实例', side_effect=SystemExit('退出未确认')), mock.patch.object(命令模块, '起实例') as 启动口:
            with self.assertRaises(SystemExit):
                命令模块.落到流量端口('候选制品', '切换')
            启动口.assert_not_called()

    def test_指纹不符不发信号(self):
        with mock.patch.object(实例模块, '进程活着', return_value=True), mock.patch.object(实例模块.os, 'kill') as 信号口:
            with self.assertRaises(SystemExit):
                实例模块.停实例({'pid': os.getpid(), '制品落点': '/不属于此进程', '进程指纹': '过期指纹'})
            信号口.assert_not_called()

    def test_真进程强杀与只清候选根(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home() / '.hermes/cache/scratch')) as 暂存目录:
            暂存根 = Path(暂存目录)
            轻进程 = subprocess.Popen([sys.executable, '-c', 'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print("ready",flush=True); time.sleep(30)'], stdout=subprocess.PIPE, text=True)
            try:
                self.assertEqual(轻进程.stdout.readline().strip(), 'ready')
                with mock.patch.object(实例模块, '运行根', 暂存根), mock.patch.object(实例模块, '停等秒', 0.1):
                    候选根 = 暂存根 / '候选运行根' / '独立实例'
                    候选根.mkdir(parents=True)
                    (候选根 / '所有权.json').write_text('{"归属凭据":"本轮独立凭据"}')
                    实例台账 = {'pid': 轻进程.pid, '可执行路径': 实例模块.读进程执行路径(轻进程.pid), '进程指纹': 实例模块.读进程指纹(轻进程.pid), '运行数据根': str(候选根), '自建运行根': True, '归属凭据': '本轮独立凭据'}
                    实例模块.停实例(实例台账)
                    self.assertFalse(实例模块.进程活着(轻进程.pid))
                    self.assertFalse(候选根.exists())
                    self.assertEqual(轻进程.wait(timeout=2), -signal.SIGKILL)
                    正式根 = 暂存根 / '正式根'
                    正式根.mkdir()
                    实例模块.停实例({'pid': 0, '运行数据根': str(正式根), '自建运行根': False})
                    self.assertTrue(正式根.is_dir())
            finally:
                if 轻进程.poll() is None:
                    轻进程.kill()
                    轻进程.wait(timeout=2)
                轻进程.stdout.close()

    def test_真写锁退场后接管(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home() / '.hermes/cache/scratch')) as 暂存目录:
            锁文件 = Path(暂存目录) / '持有锁'
            轻进程 = subprocess.Popen([sys.executable, '-c', 'import fcntl,signal,sys,time; stream=open(sys.argv[1],"w"); fcntl.flock(stream,fcntl.LOCK_EX); signal.signal(signal.SIGTERM,signal.SIG_IGN); print("ready",flush=True); time.sleep(30)', str(锁文件)], stdout=subprocess.PIPE, text=True)
            try:
                self.assertEqual(轻进程.stdout.readline().strip(), 'ready')
                with 锁文件.open('a') as 接管流:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(接管流, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    with mock.patch.object(实例模块, '停等秒', 0.1):
                        实例模块.停实例({'pid': 轻进程.pid, '可执行路径': 实例模块.读进程执行路径(轻进程.pid), '进程指纹': 实例模块.读进程指纹(轻进程.pid)})
                    fcntl.flock(接管流, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(接管流, fcntl.LOCK_UN)
            finally:
                if 轻进程.poll() is None:
                    轻进程.kill()
                轻进程.wait(timeout=2)
                轻进程.stdout.close()

    def test_未退场保留候选根(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home() / '.hermes/cache/scratch')) as 暂存目录:
            候选根 = Path(暂存目录) / '候选运行根' / '仍活实例'
            候选根.mkdir(parents=True)
            with mock.patch.object(实例模块, '运行根', Path(暂存目录)), mock.patch.object(实例模块, '进程活着', return_value=True), mock.patch.object(实例模块, '核对实例归属'), mock.patch.object(实例模块, '停等秒', 0.01), mock.patch.object(实例模块.os, 'kill'):
                with self.assertRaises(SystemExit):
                    实例模块.停实例({'pid': 999999, '运行数据根': str(候选根), '自建运行根': True})
                self.assertTrue(候选根.is_dir())


if __name__ == '__main__':
    结局 = unittest.main(verbosity=2, exit=False)
    print('上线所有权验证墙钟 %.0f ms' % ((time.monotonic() - 起始时刻) * 1000))
    sys.exit(0 if 结局.result.wasSuccessful() else 1)
