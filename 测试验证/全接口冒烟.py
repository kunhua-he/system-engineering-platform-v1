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
真值 = {
    # 数值
    '待处理数值': 1.2345, '小数位': 2, '方式': '向下', '百分位': 50,
    '数值列表': {'类型标签': 100, '值': [{'类型标签': 2, '值': 1.5},
                                        {'类型标签': 2, '值': 2.5},
                                        {'类型标签': 2, '值': 3.5}]},
    '最小值': 0, '最大值': 100, '样本数': 100,
    # 日期
    '日期文本': '2026-11-05T10:00:00+08:00', '格式文本': '%Y-%m-%d',
    '时区偏移分钟': '480', '起始文本': '2026-11-05T10:00:00+08:00',
    '结束文本': '2026-11-05T12:30:00+08:00', '单位文本': '分钟',
    # JSON
    'JSON文本': '{"名称":"示例","数值":1}',
    '列表文本': '[{"名称":"示例","数值":1},{"名称":"另一个","数值":2}]',
    '字段名': '名称', '匹配值文本': '示例', '等于值文本': '示例', '直接匹配': '假',
    '基础文本': '{"名称":"示例","数值":1}', '覆盖文本': '{"数值":2}',
    '字段映射文本': '{"名称":"标题"}',
    '载荷JSON': '{"data":{"items":[1,2,3]}}', '选择路径': 'data.items',
    '最大条目数': '10', '最大字节数': '10000', '信封键JSON': '[]',
    '元数据键': '', '数据键': 'data',
    # 文本
    '原文': '示例文本', '文本': '示例文本', '内容': '示例文本', '源文本': '示例文本',
    '待处理文本': '示例文本', '文本内容': '示例文本', '编码文本': '示例文本',
    '文本列表': {'类型标签': 100, '值': [{'类型标签': 4, '值': '第一段'},
                                        {'类型标签': 4, '值': '第二段'}]},
    '分隔符': ',', '表头': 'a,b,c', '前缀': '货号-', '查找': '示例',
    # 大语言模型连接
    '模型': '/Users/hekunhua/Documents/AI模型/文本模型/Qwen3-8B-Q4_K_M.gguf',
    '服务器地址': 'http://127.0.0.1:40001', '接口密钥': '',
    '协议': 'chat_completions', '模型类型': 'LLM文本模型',
    '静态请求头': {'类型标签': 101, '值': {}},
    '模型引用': '/Users/hekunhua/Documents/AI模型/文本模型/Qwen3-8B-Q4_K_M.gguf',
    '可执行文件': '/opt/homebrew/bin/llama-server',
    '启动参数': '-m {模型文件} --host 127.0.0.1 --port {端口} -c 4096 --no-webui',
    '监听端口': 0, '就绪路径': '', '闲置超时秒': 900, '载入超时秒': 60,
    # 编码
    '编码': 'utf-8', '待编码文本': '示例文本', '待解码文本': '5L2g5aW9',
    '十六进制编解码_编码文本': 'E7A4BAE4BE8B',
    # 正则 / 路径 / 网址
    '正则': r'\d+', '待匹配文本': 'abc123', '替换文本': 'X', '查询': '示例',
    '路径': '/tmp/全接口冒烟样本.txt', '文件路径': '/tmp/全接口冒烟样本.txt',
    '目录路径': '/tmp', '网址': 'https://example.com/a?b=1',
    '基础网址': 'https://example.com', '相对地址': '/a?b=1',
}

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


# 素材目录：冒烟要真文件、真图片，没有就先备好
素材 = Path('/tmp/全接口冒烟素材')

# 按库区分：同名参数在不同库要不同的东西（PDF 的文件路径要 pdf，代码解析要源码）
库专属 = {
    'PDF支持库': {'文件路径': str(素材 / '样例.pdf'), '页序号': 1, '倍率': 1.5,
                  '输出路径': str(素材 / 'pdf页.png'),
                  '页参数': '{"页序号":1,"倍率":1.5,"输出路径":"%s"}' % (素材 / 'pdf页.png')},
    '办公文档支持库': {'输入路径': str(素材 / '样例.docx'),
                       'DOCX文件路径': str(素材 / '样例.docx'),
                       'XLSX文件路径': str(素材 / '样例.xlsx'),
                       'PPTX文件路径': str(素材 / '样例.pptx'),
                       '输出路径': str(素材 / '输出.docx'),
                       '输出目录': str(素材),
                       '目标格式': 'md',
                       '超时秒': 60,
                       'Markdown源文本': '# 标题\n\n正文一段。',
                       '内容文本': '正文一段。',
                       '公式文本': 'x^2+1',
                       '变量文本': '{"x": 2}'},
    '代码解析支持库': {'文件路径': str(素材 / '样例.py'),
                       '规则文件路径': str(素材 / '切块规则.json'),
                       '规则文本': '{"块类型": ["函数"]}',
                       '文件格式': 'py', '扩展名': '.py',
                       '原始字节': {'类型标签': 5, '值': 'ZGVmIGYoKToKICAgIHJldHVybiAxCg=='},
                       '编码名': 'utf-8', '强制重载': False,
                       '内容': 'def f():\n    return 1\n'},
    '文件支持库': {'受控根目录': str(素材), '受控工作区': str(素材),
                   '相对路径': '样例.txt', '文件路径': str(素材 / '样例.txt'),
                   '路径': str(素材 / '样例.txt'), '目录路径': str(素材),
                   '目标路径': str(素材) + '/副本.txt',
                   '文本内容': '写入的内容',
                   '字节内容': {'类型标签': 5, '值': '5YaF5a65'},
                   '字节数': 30, '最大字节数': 1024, '操作': '读取',
                   '提交范围': '已提交', '偏移': 0, '长度': 30},
}

# 图像处理库的图统一用同一张 PNG
_图 = (素材 / '样例png_base64.txt')
_图值 = _图.read_text().strip() if _图.is_file() else ''
库专属['图像处理支持库'] = {
    '图像base64': _图值, '底图base64': _图值, '叠加base64': _图值,
    '宽度': 320, '高度': 240, '目标宽': 160, '目标高': 120,
    '背景颜色': '#FFFFFF', '前景颜色': '#000000', '文本': '示例',
    '占位类型': '纯色', '转置方式': '顺时针90',
}

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


def 造参(声明, 库名=''):
    参 = {}
    专属 = 库专属.get(库名, {})
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
        if 名 in 真值:
            参[名] = 包标签(真值[名], 类型)
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


def 前置准备():
    """链式接口（连接→提交→读结果）单独调必然「句柄无效」，先把前置资源备好。"""
    判, 说, 值 = 发一次带值(2512, {
        '模型引用': 真值['模型引用'],
        '可执行文件': 真值['可执行文件'],
        '启动参数': 真值['启动参数'],
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
    # 冒烟要读的文件先备好，免得「文件不存在」掩盖真问题
    样本 = Path('/tmp/全接口冒烟样本.txt')
    if not 样本.is_file():
        样本.write_text('第一行\n第二行\n第三行\n', encoding='utf-8')

    素材.mkdir(parents=True, exist_ok=True)
    if not (素材 / '样例.py').is_file():
        (素材 / '样例.py').write_text('def f():\n    return 1\n', encoding='utf-8')
    if not (素材 / '切块规则.json').is_file():
        (素材 / '切块规则.json').write_text('{"块类型": ["函数"], "按行切": true}', encoding='utf-8')

    指定 = sys.argv[1] if len(sys.argv) > 1 else ''
    库们 = sorted(d for d in 声明根.iterdir() if d.is_dir() and not d.name.startswith('.'))
    if 指定:
        库们 = [d for d in 库们 if 指定 in d.name]

    前置准备()
    print('前置服务句柄: %s' % (上下文['服务句柄'] or '没拉起'))

    结果 = []
    for 库 in 库们:
        for f in sorted(库.glob('能力声明/*.json')):
            声明 = json.loads(f.read_text(encoding='utf-8'))
            判, 说 = 发一次(声明['编号'], 造参(声明, 库.name))
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
