"""自建隔离PG与临时V1实例；不访问业务库、不切换常驻网关。"""
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request


def 执行验收(仓根, 缓存根, 网关路径, 启动预算毫秒):
    仓根 = Path(仓根).resolve()
    缓存根 = Path(缓存根).resolve()
    网关路径 = Path(网关路径).resolve()
    制品声明 = 网关路径.parent / '扩展根声明.json'
    网关声明 = 制品声明 if 制品声明.exists() else 仓根 / '扩展装载/扩展根声明.json'
    运行目录 = 网关路径.parent if 制品声明.exists() else 仓根
    缓存根.mkdir(parents=True, exist_ok=False)
    连接器 = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    引擎目录 = Path(subprocess.check_output(['pg_config', '--bindir'], text=True).strip())
    引擎库根 = 缓存根 / 'pgdata'
    进程环境 = dict(os.environ, LC_ALL='C')
    进程表 = []
    请求列表 = []
    检查列表 = []
    引擎已启动 = False

    def 空闲端口():
        with socket.socket() as 端口探针:
            端口探针.bind(('127.0.0.1', 0))
            return 端口探针.getsockname()[1]

    def 执行命令(命令表, 日志名称, 环境表=进程环境):
        with (缓存根 / 日志名称).open('w') as 日志文件:
            回执 = subprocess.run(命令表, cwd=仓根, env=环境表, stdout=日志文件, stderr=subprocess.STDOUT, timeout=5)
        assert 回执.returncode == 0, (日志名称, 回执.returncode)

    def 请求(端口号, 路径, 请求体=None):
        请求对象 = urllib.request.Request('http://127.0.0.1:%s%s' % (端口号, urllib.parse.quote(路径, safe='/')), data=None if 请求体 is None else json.dumps(请求体, ensure_ascii=False).encode(), headers={'Content-Type': 'application/json'})
        try:
            with 连接器.open(请求对象, timeout=5) as 响应:
                状态码, 正文 = 响应.status, json.loads(响应.read())
        except urllib.error.HTTPError as 错误响应:
            with 错误响应:
                状态码, 正文 = 错误响应.code, json.loads(错误响应.read())
        请求列表.append({'端口': 端口号, '路径': 路径, '请求': 请求体, 'HTTP状态': 状态码, '返回': 正文})
        return 状态码, 正文

    def 核验(条件, 检查名称):
        assert 条件, 检查名称
        检查列表.append(检查名称)

    def 文本槽(文本值):
        return {'类型标签': 4, '值': 文本值}

    def 句柄槽(连接编号):
        return {'类型标签': 6, '值': 连接编号}

    def 调用(端口号, 编号, 值列表, 期望错误=None):
        状态码, 正文 = 请求(端口号, '/接口/调用', {'编号': 编号, '值': 值列表})
        if 期望错误 is None:
            assert 状态码 == 200 and 正文.get('成功'), (编号, 状态码, 正文)
            return 正文['值'][0]['值']
        assert not 正文.get('成功') and 正文.get('错误', {}).get('码') == 期望错误, (编号, 状态码, 正文)
        return None

    def 查询(端口号, 连接编号, 查询语句, 期望错误=None):
        结果文本 = 调用(端口号, 5402, [句柄槽(连接编号), 文本槽(查询语句)], 期望错误)
        return {} if 结果文本 is None else json.loads(结果文本)

    def 事务(端口号, 连接编号, 语句列表, 期望错误=None):
        return 调用(端口号, 5403, [句柄槽(连接编号), 文本槽(json.dumps(语句列表))], 期望错误)

    def 起网关(实例序号):
        实例目录 = 缓存根 / ('网关%s' % 实例序号)
        实例目录.mkdir()
        端口号 = 空闲端口()
        日志文件 = (实例目录 / '网关.log').open('w')
        进程对象 = subprocess.Popen([str(网关路径), '--声明根', str(网关声明), '--后缀表', str(仓根 / '扩展装载/后缀表.json'), '--端口', str(端口号), '--缓存根', str(实例目录 / '装载缓存'), '--工具根', str(仓根)], cwd=运行目录, env=进程环境, stdout=日志文件, stderr=subprocess.STDOUT)
        进程表.append((进程对象, 日志文件))
        截止时刻 = time.monotonic() + 启动预算毫秒 / 1000
        while time.monotonic() < 截止时刻:
            assert 进程对象.poll() is None, (实例目录 / '网关.log').read_text()
            with socket.socket() as 就绪探针:
                if 就绪探针.connect_ex(('127.0.0.1', 端口号)) == 0:
                    break
            time.sleep(0.02)
        else:
            raise AssertionError('临时网关启动未就绪')
        状态码, 装载回执 = 请求(端口号, '/接口/运维/生命周期', {'动作': '装载'})
        assert 状态码 == 200 and 装载回执.get('成功'), 装载回执
        for 编号 in range(5401, 5405):
            状态码, 能力回执 = 请求(端口号, '/接口/能力/%s' % 编号)
            assert 状态码 == 200, 能力回执
        return 端口号

    try:
        执行命令([str(引擎目录 / 'initdb'), '-D', str(引擎库根), '-A', 'trust', '--no-locale', '-E', 'UTF8'], '初始化PG.log')
        引擎端口 = 空闲端口()
        # 仅监听本机TCP，避免Unix socket路径过长。
        执行命令([str(引擎目录 / 'pg_ctl'), '-D', str(引擎库根), '-l', str(缓存根 / 'postgres.log'), '-o', '-F -p %s -h 127.0.0.1 -k ""' % 引擎端口, '-w', 'start'], '启动PG.log')
        引擎已启动 = True
        连接文本 = 'host=127.0.0.1 port=%s dbname=postgres' % 引擎端口
        执行命令(['cargo', 'test', '--locked', '--offline', '--manifest-path', str(仓根 / '扩展根目录/原子支持库/PostgreSQL支持库/Cargo.toml')], 'Cargo测试.log', dict(进程环境, V1_LIBPQ_TEST_DSN=连接文本))
        首端口 = 起网关(1)
        次端口 = 起网关(2)
        首句柄 = 调用(首端口, 5401, [文本槽(连接文本)])
        次句柄 = 调用(次端口, 5401, [文本槽(连接文本)])
        首结果 = 查询(首端口, 首句柄, "SELECT pg_backend_pid(), '中文', NULL, ''")
        后端编号 = 首结果['行列表'][0][0]
        核验(首结果['行列表'][0][1:] == ['中文', None, ''], 'UTF8空文本NULL保留')
        核验(查询(首端口, 首句柄, 'SELECT pg_backend_pid()')['行列表'][0][0] == 后端编号, '跨HTTP调用同一真实PGconn')
        核验(查询(次端口, 次句柄, 'SELECT pg_backend_pid()')['行列表'][0][0] != 后端编号, '双网关独立后端')
        查询(次端口, 首句柄, 'SELECT 1', 5414)
        核验(事务(首端口, 首句柄, ['CREATE TABLE http_probe(value integer)', 'INSERT INTO http_probe VALUES(1)']) == 2, 'HTTP事务提交')
        事务(首端口, 首句柄, ['INSERT INTO http_probe VALUES(2)', 'INSERT INTO missing_http VALUES(3)'], 5413)
        外部结果 = subprocess.check_output([str(引擎目录 / 'psql'), 连接文本, '-Atqc', 'SELECT count(*) FROM http_probe'], text=True, env=进程环境).strip()
        核验(外部结果 == '1', '独立psql读回失败事务已整体回滚')
        事务(首端口, 首句柄, ['INSERT INTO http_probe VALUES(2); COMMIT'], 5413)
        事务(首端口, 首句柄, ['INSERT INTO http_probe VALUES(2)', 'COMMIT'], 5411)
        核验(查询(首端口, 首句柄, 'SELECT count(*) FROM http_probe')['行列表'][0][0] == '1', '提前提交与多语句拒绝')
        查询(首端口, 首句柄, 'WITH removed AS (DELETE FROM http_probe RETURNING *) SELECT * FROM removed', 5413)
        查询(首端口, 首句柄, 'SELECT repeat(\'a\',65537)', 5416)
        查询(首端口, 首句柄, 'SELECT pg_sleep(2)', 5413)
        核验(查询(首端口, 首句柄, 'SELECT 1')['行列表'][0][0] == '1', '越界及超时回滚后连接可复用')
        调用(首端口, 5401, [文本槽('host=127.0.0.1 port=1 dbname=missing')], 5412)
        故障句柄 = 调用(首端口, 5401, [文本槽(连接文本)])
        查询(首端口, 故障句柄, "SELECT set_config('statement_timeout','0',false)")
        查询(首端口, 故障句柄, 'SELECT pg_sleep(2)', 5417)
        查询(首端口, 故障句柄, 'SELECT 1', 5414)
        检查列表.append('客户端截止销毁真实连接并拒绝旧句柄')
        核验(调用(首端口, 5404, [句柄槽(首句柄)]) == 1, '显式释放成功')
        调用(首端口, 5404, [句柄槽(首句柄)], 5414)
        观察语句 = 'SELECT count(*) FROM pg_stat_activity WHERE pid=%s' % 后端编号
        观察截止 = time.monotonic() + 0.5
        while time.monotonic() < 观察截止:
            外部结果 = subprocess.check_output([str(引擎目录 / 'psql'), 连接文本, '-Atqc', 观察语句], text=True, env=进程环境).strip()
            if 外部结果 == '0':
                break
        核验(外部结果 == '0', '独立psql证实PQfinish已关闭后端')
        新句柄 = 调用(首端口, 5401, [文本槽(连接文本)])
        新后端编号 = 查询(首端口, 新句柄, 'SELECT pg_backend_pid()')['行列表'][0][0]
        包声明 = json.loads((仓根 / '扩展根目录/原子支持库/PostgreSQL支持库/包声明.json').read_text())
        状态码, 卸载回执 = 请求(首端口, '/接口/运维/生命周期', {'动作': '卸载', '标识串': 包声明['标识串']})
        assert 状态码 == 200 and 卸载回执.get('成功'), 卸载回执
        卸载截止 = time.monotonic() + 0.5
        while time.monotonic() < 卸载截止:
            外部结果 = subprocess.check_output([str(引擎目录 / 'psql'), 连接文本, '-Atqc', 'SELECT count(*) FROM pg_stat_activity WHERE pid=%s' % 新后端编号], text=True, env=进程环境).strip()
            if 外部结果 == '0':
                break
        核验(外部结果 == '0', '真实HTTP卸载回调关闭未释放PGconn')
        调用(次端口, 5404, [句柄槽(次句柄)])
        return {'通过数': len(检查列表), '检查项': 检查列表, 'HTTP请求数': len(请求列表)}
    finally:
        for 进程对象, 日志文件 in 进程表:
            if 进程对象.poll() is None:
                进程对象.terminate()
                try:
                    进程对象.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    进程对象.kill()
                    进程对象.wait(timeout=3)
            日志文件.close()
        if 引擎已启动:
            subprocess.run([str(引擎目录 / 'pg_ctl'), '-D', str(引擎库根), '-m', 'immediate', '-w', 'stop'], env=进程环境, capture_output=True, timeout=5, check=True)
        (缓存根 / '完整HTTP回执.json').write_text(json.dumps(请求列表, ensure_ascii=False, indent=2))
        (缓存根 / '检查结果.json').write_text(json.dumps({'检查项': 检查列表, 'HTTP请求数': len(请求列表), '网关全部退出': all(进程对象.poll() is not None for 进程对象, _ in 进程表)}, ensure_ascii=False, indent=2))
