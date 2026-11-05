"""全接口冒烟：给每个能力配真参数发一次请求，看能不能真跑通。

为什么要有它：光发空值只能证明链路通（参数校验就拦住），证明不了接口能干活。
这里按「参数名 → 真值」配一遍，配不到的按参数说明推，还推不出就用兜底值。

判据三档：
    成功   —— 真执行并返回结果
    参数错 —— 到达业务层但输入不合法（说明链路通，是参数没配对）
    协议错 —— HTTP 400，参数名或形状不对（文档与实现对不上，算真缺陷）

用法：python3 测试验证/全接口冒烟.py [库名]
产出：测试验证/全接口冒烟_回执.json
"""

import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

根 = Path(__file__).resolve().parents[1]
声明根 = 根 / '扩展根目录/原子支持库'
接口 = 'http://127.0.0.1:43110' + urllib.parse.quote('/接口/调用')
回执 = 根 / '测试验证/全接口冒烟_回执.json'

# 参数名 → 真值。按实际参数名逐个配，配不到的走推断。
配置路径 = 根 / '测试验证/冒烟参数.json'


def 读配置():
    """参数配置住 冒烟参数.json：按编号 > 按库 > 全局，三层覆盖。
    配置与逻辑分开 —— 给某个接口调参数不用改代码。"""
    if not 配置路径.is_file():
        配置路径.write_text(json.dumps({'全局': {}, '按库': {}, '按编号': {}},
                                       ensure_ascii=False, indent=1), encoding='utf-8')
    配 = json.loads(配置路径.read_text(encoding='utf-8'))
    素材根 = Path(配.get('素材目录') or '/tmp/全接口冒烟素材')

    def 换(字典):
        return {k: (v.replace('{素材}', str(素材根)) if isinstance(v, str) else v)
                for k, v in (字典 or {}).items()}

    配['全局'] = 换(配.get('全局'))
    配['按库'] = {库: 换(值) for 库, 值 in (配.get('按库') or {}).items()}
    配['按编号'] = {号: 换(值) for 号, 值 in (配.get('按编号') or {}).items()}
    return 配


# 按参数说明推：说明里常直接给例句
推值规则 = [
    (r'点分路径如\s*([\w.]+)', None),
    (r'如\s*(\[[^\]]*\]|\{[^}]*\})', None),
    (r'真\s*/\s*假|真/假', '假'),
    (r'JSON', '{"a":1}'),
    (r'CSV|逗号分隔', 'a,b,c'),
    (r'YAML', 'a: 1'),
    (r'BASE64|base64', '5L2g5aW9'),
    (r'十六进制|HEX|hex', 'E7A4BA'),
]


# 类型 5 是字节集，必须是长度 4 倍数的合法 base64 —— 给「示例」三个字会直接判协议错
兜底 = {'类型1': 1, '类型2': 1.5, '类型3': False, '类型4': '示例', '类型5': '5YaF5a65', '类型6': 1}


def _换新名(路径):
    """输出类路径每次换新，否则第二轮必然「文件已存在」。"""
    import time
    from pathlib import Path as _P
    p = _P(路径)
    return str(p.with_name('%s_%d%s' % (p.stem, time.time_ns() % 100000, p.suffix)))


def 包标签(值, 类型):
    """复合参数必须逐层带 {"类型标签":N,"值":…}，裸 {} / [] 会被判「输入形状不符」。"""
    if isinstance(值, dict) and '类型标签' in 值 and '值' in 值:
        return 值
    if 类型 == 100:
        return {'类型标签': 100, '值': 值 if isinstance(值, list) else []}
    if 类型 == 101:
        return {'类型标签': 101, '值': 值 if isinstance(值, dict) else {}}
    if 类型 == 5:
        import base64 as _b64
        串 = 值 if isinstance(值, str) else ''
        try:
            _b64.b64decode(串, validate=True)
            if len(串) % 4:
                raise ValueError
        except Exception:
            串 = _b64.b64encode(b'\xe7\xa4\xba\xe4\xbe\x8b').decode()
        return {'类型标签': 5, '值': 串}
    return 值


def 造参(声明, 库名='', 配=None):
    参 = {}
    配 = 配 or {}
    专属 = {}
    专属.update(配.get('全局') or {})
    专属.update((配.get('按库') or {}).get(库名) or {})
    专属.update((配.get('按编号') or {}).get(str(声明.get('编号'))) or {})
    for p in 声明.get('参数表') or []:
        名 = p['名称']
        说 = p.get('说明') or ''
        类型 = p.get('类型标签', 4)
        默认 = p.get('默认值') or {}

        类型 = p.get('类型标签', 4)
        if 名 in ('输出路径', '目标路径', '输出目录') and isinstance(专属.get(名), str):
            参[名] = 包标签(_换新名(专属[名]), 类型)
            continue
        if 名 in ('服务句柄', '句柄', '任务句柄', '许可句柄', '连接句柄'):
            值 = 上下文.get(名) or 上下文.get({'任务句柄': '任务句柄', '许可句柄': '许可句柄'}.get(名, '服务句柄')) or 1
            参[名] = 包标签(值, 类型)
            continue
        if 名 in 专属:
            参[名] = 包标签(专属[名], 类型)
            continue

        if 默认.get('类型标签'):
            参[名] = 默认.get('值', 默认.get('逻辑', ''))
            continue

        取值 = None
        for 模式, 固定 in 推值规则:
            m = re.search(模式, 说)
            if m:
                取值 = 固定 if 固定 is not None else m.group(1)
                break
        if 取值 is None:
            取值 = 兜底.get('类型%d' % 类型, '示例')
        参[名] = 包标签(取值, 类型)
    return 参


上下文 = {'服务句柄': 0, '任务句柄': 0, '许可句柄': 0, '句柄': 0}


def 前置准备(配=None):
    """链式接口（连接→提交→读结果）单独调必然「句柄无效」，先把前置资源备好。"""
    配 = 配 or {}
    表 = 配.get('全局') or {}
    判, 说, 值 = 发一次带值(2512, {
        '模型引用': 表.get('模型引用', ''),
        '可执行文件': 表.get('可执行文件', '/opt/homebrew/bin/llama-server'),
        '启动参数': 表.get('启动参数', ''),
        '监听端口': 0, '就绪路径': '', '模型类型': 'LLM文本模型',
        '闲置超时秒': 900, '载入超时秒': 60,
    })
    if 判 == '成功' and isinstance(值, int):
        上下文['服务句柄'] = 值
    # 等它真就绪
    for _ in range(20):
        判2, _, 就 = 发一次带值(2515, {'服务句柄': 上下文['服务句柄'], '超时毫秒': 800})
        if 就 is True:
            break


def 发一次带值(编号, 参):
    """同 发一次，但把成功时的值也带回来（前置准备要用）。"""
    体 = json.dumps({'编号': 编号, '命名值': 参}, ensure_ascii=False).encode()
    try:
        with urllib.request.urlopen(
                 urllib.request.Request(接口, 体, {'Content-Type': 'application/json'}),
                 timeout=60) as 回:
            数据 = json.loads(回.read())
        if not 数据.get('成功'):
            return '参数错', (数据.get('错误') or {}).get('名称', ''), None
        值 = 数据.get('值')
        if isinstance(值, list) and len(值) == 1:
            值 = 值[0]
        if isinstance(值, dict) and set(值) == {'类型标签', '值'}:
            值 = 值['值']
        return '成功', '', 值
    except Exception as e:
        return '连不上', type(e).__name__, None


def 发一次(编号, 参):
    体 = json.dumps({'编号': 编号, '命名值': 参}, ensure_ascii=False).encode()
    try:
        with urllib.request.urlopen(
                 urllib.request.Request(接口, 体, {'Content-Type': 'application/json'}),
                 timeout=30) as 回:
            数据 = json.loads(回.read())
        错名 = (数据.get('错误') or {}).get('名称', '')
        if 错名 == '文件已存在':
            错名 = '文件已存在（输出路径撞名，非缺陷）'
        return '成功' if 数据.get('成功') else '参数错', 错名
    except urllib.error.HTTPError as e:
        文 = e.read().decode()
        try:
            协议 = json.loads(文).get('协议错误', '')
        except Exception:
            协议 = 文[:120]
        return '协议错', 协议[:160]
    except Exception as e:
        return '连不上', type(e).__name__


def 主():
    配 = 读配置()
    # 冒烟要读的文件先备好，免得「文件不存在」掩盖真问题
    样本 = Path('/tmp/全接口冒烟样本.txt')
    if not 样本.is_file():
        样本.write_text('第一行\n第二行\n第三行\n', encoding='utf-8')

    素材 = Path(配.get('素材目录') or '/tmp/全接口冒烟素材')
    素材.mkdir(parents=True, exist_ok=True)
    if not (素材 / '样例.py').is_file():
        (素材 / '样例.py').write_text('def f():\n    return 1\n', encoding='utf-8')
    if not (素材 / '切块规则.json').is_file():
        (素材 / '切块规则.json').write_text('{"块类型": ["函数"], "按行切": true}', encoding='utf-8')

    指定 = sys.argv[1] if len(sys.argv) > 1 else ''
    库们 = sorted(d for d in 声明根.iterdir() if d.is_dir() and not d.name.startswith('.'))
    if 指定:
        库们 = [d for d in 库们 if 指定 in d.name]

    前置准备(配)
    print('前置服务句柄: %s' % (上下文['服务句柄'] or '没拉起'))

    结果 = []
    for 库 in 库们:
        for f in sorted(库.glob('能力声明/*.json')):
            声明 = json.loads(f.read_text(encoding='utf-8'))
            判, 说 = 发一次(声明['编号'], 造参(声明, 库.name, 配))
            结果.append({'库': 库.name, '编号': 声明['编号'],
                         '名': 声明['名称'].split('_')[-1], '判': 判, '说': 说})

    回执.write_text(json.dumps(结果, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')

    总 = len(结果)
    分 = {}
    for r in 结果:
        分[r['判']] = 分.get(r['判'], 0) + 1
    print('共 %d 个接口' % 总)
    for 判 in ('成功', '参数错', '协议错', '连不上'):
        if 判 in 分:
            print('  %-4s %3d' % (判, 分[判]))

    协议错 = [r for r in 结果 if r['判'] == '协议错']
    if 协议错:
        print('\n协议错（文档与实现对不上，真缺陷）：')
        for r in 协议错[:15]:
            print('  %d %s → %s' % (r['编号'], r['名'], r['说'][:90]))
    print('\n回执 %s' % 回执)
    return 0


if __name__ == '__main__':
    sys.exit(主())
