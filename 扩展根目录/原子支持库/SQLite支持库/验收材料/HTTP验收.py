"""复杂扩展HTTP实证；只创建自有临时网关、数据库和缓存，不读取业务库。"""
import base64
import 扩展根目录.原子支持库.SQLite支持库.验收材料.扩展根目录.futures
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import time
import 扩展根目录.原子支持库.SQLite支持库.验收材料.扩展根目录.error
import 扩展根目录.原子支持库.SQLite支持库.验收材料.扩展根目录.parse
import 扩展根目录.原子支持库.SQLite支持库.验收材料.扩展根目录.request


def 执行HTTP验收(仓根, 缓存根):
    仓根 = Path(仓根).resolve()
    缓存根 = Path(缓存根).resolve()
    缓存根.mkdir(parents=True, exist_ok=True)
    连接器 = 扩展根目录.request.build_opener(扩展根目录.request.ProxyHandler({}))
    实例表 = []
    检查项 = []
    完整回执 = []

    def 请求(网关实例, 路径, 请求体=None):
        请求对象 = 扩展根目录.request.Request('http://127.0.0.1:%s%s' % (网关实例['端口'], 扩展根目录.parse.quote(路径, safe='/')), data=None if 请求体 is None else json.dumps(请求体, ensure_ascii=False).encode(), headers={'Content-Type': 'application/json'})
        try:
            with 连接器.open(请求对象, timeout=5) as 响应:
                状态码, 正文 = 响应.status, json.loads(响应.read())
        except 扩展根目录.error.HTTPError as 失败响应:
            with 失败响应:
                状态码, 正文 = 失败响应.code, json.loads(失败响应.read())
        完整回执.append({'端口': 网关实例['端口'], '路径': 路径, '请求': 请求体, 'HTTP状态': 状态码, '返回': 正文})
        return 状态码, 正文

    def 断言(条件, 名称, 返回=None):
        if not 条件:
            raise AssertionError((名称, 返回))
        检查项.append(名称)

    def 调用(网关实例, 编号, 值表, 预期错误=None):
        状态码, 正文 = 请求(网关实例, '/接口/调用', {'编号': 编号, '值': 值表})
        if 预期错误 is None:
            assert 状态码 == 200 and 正文.get('成功'), (编号, 状态码, 正文)
        else:
            assert not 正文.get('成功') and 正文.get('错误', {}).get('码') == 预期错误, (编号, 状态码, 正文)
        return 正文

    def 文本槽(文本值):
        return {'类型标签': 4, '值': str(文本值)}

    def 执行事务(网关实例, 语句表, 编号=7953, 错误=None):
        return 调用(网关实例, 编号, [文本槽(网关实例['数据库']), {'类型标签': 100, '值': [文本槽(语句文本) for 语句文本 in 语句表]}], 错误)

    def 查询(网关实例, SQL文本, 编号=7952, 错误=None):
        return 调用(网关实例, 编号, [文本槽(网关实例['数据库']), 文本槽(SQL文本)], 错误)

    def 解值(值项):
        if isinstance(值项, list): return [解值(子项) for 子项 in 值项]
        if isinstance(值项, dict):
            if '类型标签' in 值项 and '值' in 值项:
                if 值项['类型标签'] == 0: return None
                if 值项['类型标签'] == 5: return list(base64.b64decode(值项['值'], validate=True))
                return 解值(值项['值'])
            return {键名: 解值(子项) for 键名, 子项 in 值项.items()}
        return 值项

    def 起实例(实例序号):
        实例目录 = 缓存根 / ('网关实例%s' % 实例序号)
        实例目录.mkdir(exist_ok=True)
        with socket.socket() as 监听探针:
            监听探针.bind(('127.0.0.1', 0))
            端口号 = 监听探针.getsockname()[1]
        部署表 = []
        for 相对目录 in ['扩展根目录/原子支持库/SQLite支持库', '扩展根目录/组合模块库/数据库访问模块']:
            包目录 = 仓根 / 相对目录
            包声明 = json.loads((包目录 / '包声明.json').read_text())
            是模块 = '组合模块库' in 相对目录
            部署表.append({'标识串': 包声明['标识串'], '版本': {'主版本': 0, '次版本号': 1, '构建': 0}, '制品路径': str(包目录 / (包目录.name + ('.模块制品' if 是模块 else '.支持库制品'))), '启动程序': str(仓根 / '构建环境/构建缓存/debug/examples/工作进程') if 是模块 else ''})
        配置文件 = 实例目录 / '跨进程配置.json'
        配置文件.write_text(json.dumps({'跨进程': 部署表}, ensure_ascii=False))
        日志文件 = open(实例目录 / '网关.log', 'w')
        网关进程 = subprocess.Popen([str(仓根 / '构建环境/构建缓存/release/examples/启动网关'), '--声明根', '扩展装载/扩展根声明.json', '--后缀表', '扩展装载/后缀表.json', '--端口', str(端口号), '--缓存根', str(实例目录 / '装载缓存'), '--跨进程配置', str(配置文件), '--工具根', '.'], cwd=仓根, stdout=日志文件, stderr=subprocess.STDOUT, start_new_session=False)
        网关实例 = {'端口': 端口号, '进程': 网关进程, '日志': 日志文件, '数据库': 实例目录 / '验收.db', '部署': 部署表}
        实例表.append(网关实例)
        截止时刻 = time.monotonic() + 5
        while time.monotonic() < 截止时刻:
            if 网关进程.poll() is not None: raise RuntimeError((实例目录 / '网关.log').read_text())
            with socket.socket() as 连接探针:
                if 连接探针.connect_ex(('127.0.0.1', 端口号)) == 0: break
            time.sleep(0.02)
        状态码, 装载回执 = 请求(网关实例, '/接口/生命周期', {'动作': '装载'})
        assert 状态码 == 200 and 装载回执.get('成功'), 装载回执
        return 网关实例

    try:
        源库网关 = 起实例(1)
        返回 = 执行事务(源库网关, ['CREATE TABLE 实证(编号 INTEGER PRIMARY KEY, 文本 TEXT, 浮点 REAL, 原始 BLOB, 空值)', "INSERT INTO 实证 VALUES(1,'中文',1.5,X'0001FF',NULL)"])
        断言(解值(返回['值']) == [2], '模块真实事务提交', 返回)
        返回 = 查询(源库网关, 'SELECT * FROM 实证')
        完整回执.append({'类型保真原始返回': 返回})
        结果结构 = 解值(返回['值'])[0]
        断言(结果结构['列名列表'] == ['编号', '文本', '浮点', '原始', '空值'], '列序保留', 返回)
        首行 = 结果结构['行列表'][0]
        断言(首行[:3] == [1, '中文', 1.5], '整数文本浮点保真', 返回)
        断言(首行[4] is None, 'NULL保真', 返回)
        断言(首行[3] == [0, 1, 255], '二进制零字节保真', 返回)
        返回 = 查询(源库网关, "SELECT 0 AS 同名, '' AS 同名, char(65,0,66) AS 带零文本")
        断言(解值(返回['值'])[0]['行列表'] == [[0, '', 'A\x00B']], '重名列零空文本和文本NUL保真', 返回)
        返回 = 查询(源库网关, 'SELECT * FROM 实证 WHERE 0')
        断言(解值(返回['值'])[0]['行列表'] == [], '空结果不冒充失败', 返回)
        执行事务(源库网关, ["INSERT INTO 实证(编号) VALUES(2)", 'INSERT INTO 不存在表 VALUES(3)'], 错误=5103)
        with sqlite3.connect(源库网关['数据库']) as 外部连接:
            断言(外部连接.execute('SELECT count(*) FROM 实证').fetchone()[0] == 1, '失败事务外部读回整体回滚')
        执行事务(源库网关, ['INSERT INTO 实证(编号) VALUES(3); COMMIT'], 错误=5103)
        with sqlite3.connect(源库网关['数据库']) as 外部连接:
            断言(外部连接.execute('SELECT count(*) FROM 实证').fetchone()[0] == 1, '阻止提前提交破坏原子性')
        查询(源库网关, 'DELETE FROM 实证', 错误=5101); 检查项.append('只读拒写')
        查询(源库网关, 'SELECT 1; SELECT 2', 错误=5101); 检查项.append('拒绝多语句查询')
        执行事务(源库网关, [], 错误=5101); 检查项.append('空事务拒绝')
        调用(源库网关, 5102, [文本槽('相对.db'), 文本槽('SELECT 1')], 5101); 检查项.append('相对路径拒绝')
        调用(源库网关, 5102, [文本槽(缓存根 / '不存在.db'), 文本槽('SELECT 1')], 5102); 检查项.append('只读不创建缺失库')
        查询(源库网关, 'SELECT zeroblob(65537)', 错误=5105); 检查项.append('单值越界拒绝')
        查询(源库网关, 'WITH RECURSIVE 序列(编号) AS (VALUES(1) UNION ALL SELECT 编号+1 FROM 序列 WHERE 编号<1025) SELECT 编号 FROM 序列', 错误=5105); 检查项.append('行数越界拒绝')
        with sqlite3.connect(源库网关['数据库'], isolation_level=None) as 外部锁连接:
            外部锁连接.execute('BEGIN EXCLUSIVE')
            执行事务(源库网关, ['INSERT INTO 实证(编号) VALUES(4)'], 错误=5104)
            外部锁连接.execute('ROLLBACK')
        检查项.append('锁冲突有界具名失败')
        查询(源库网关, 'SELECT zeroblob(1048577)', 错误=5104); 检查项.append('引擎大值分配上界拒绝')
        查询(源库网关, 'WITH RECURSIVE 序列(编号) AS (VALUES(1) UNION ALL SELECT 编号+1 FROM 序列 WHERE 编号<100000000) SELECT sum(编号) FROM 序列', 错误=5104); 检查项.append('引擎计算预算有界中断')
        对照网关 = 起实例(2)
        执行事务(对照网关, ['CREATE TABLE 实证(编号 INTEGER)', 'INSERT INTO 实证 VALUES(99)'])
        with 扩展根目录.futures.ThreadPoolExecutor(max_workers=8) as 线程池:
            返回表 = list(线程池.map(lambda 序号: 解值(查询(源库网关 if 序号 % 2 == 0 else 对照网关, 'SELECT 编号 FROM 实证')['值'])[0]['行列表'], range(16)))
        断言(返回表 == [[[1]] if 序号 % 2 == 0 else [[99]] for 序号 in range(16)], '双实例8线程16请求不串数据')
        for 网关实例 in 实例表:
            状态码, 留痕 = 请求(网关实例, '/接口/留痕')
            留痕值 = 留痕.get('数据', {})
            能力表 = [留痕条目['能力号'] for 留痕条目 in 留痕值.get('留痕', [])]
            断言(状态码 == 200 and all(编号 in 能力表 for 编号 in [5101,5102,7952,7953]) and 留痕值.get('已丢弃') == 0, '网关实例%s内外能力留痕完整' % 网关实例['端口'], 留痕)
        for 网关实例 in 实例表:
            with sqlite3.connect(网关实例['数据库'], isolation_level=None, timeout=0) as 外部连接:
                外部连接.execute('BEGIN EXCLUSIVE'); 外部连接.execute('ROLLBACK')
        检查项.append('调用完成数据库锁已释放')
    finally:
        for 网关实例 in 实例表:
            try:
                for 部署项 in reversed(网关实例['部署']): 请求(网关实例, '/接口/生命周期', {'动作':'卸载','标识串':部署项['标识串']})
            finally:
                if 网关实例['进程'].poll() is None:
                    网关实例['进程'].terminate()
                    try: 网关实例['进程'].wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        网关实例['进程'].kill(); 网关实例['进程'].wait(timeout=3)
                网关实例['日志'].close()
        (缓存根 / '完整回执.json').write_text(json.dumps(完整回执, ensure_ascii=False, indent=2))
    报告 = {'通过数': len(检查项), '检查项': 检查项, 'HTTP请求数': len([回执 for 回执 in 完整回执 if 'HTTP状态' in 回执]), '实例数':len(实例表), '网关全部退出':all(网关实例['进程'].poll() is not None for 网关实例 in 实例表)}
    (缓存根 / '验收结果.json').write_text(json.dumps(报告, ensure_ascii=False, indent=2))
    print('复杂扩展HTTP验收通过：%s项，%s个真实请求，2个独立网关。' % (报告['通过数'], 报告['HTTP请求数']))
    return 报告
