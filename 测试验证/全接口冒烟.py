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

兜底 = {'类型1': 1, '类型2': 1.5, '类型3': False, '类型4': '示例', '类型6': 1}


def 造参(声明):
    参 = {}
    for p in 声明.get('参数表') or []:
        名 = p['名称']
        说 = p.get('说明') or ''
        类型 = p.get('类型标签', 4)
        默认 = p.get('默认值') or {}

        if 名 in 真值:
            参[名] = 真值[名]
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
        参[名] = 取值
    return 参


def 发一次(编号, 参):
    体 = json.dumps({'编号': 编号, '命名值': 参}, ensure_ascii=False).encode()
    try:
        with urllib.request.urlopen(
                 urllib.request.Request(接口, 体, {'Content-Type': 'application/json'}),
                 timeout=30) as 回:
            数据 = json.loads(回.read())
        return '成功' if 数据.get('成功') else '参数错', (数据.get('错误') or {}).get('名称', '')
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

    指定 = sys.argv[1] if len(sys.argv) > 1 else ''
    库们 = sorted(d for d in 声明根.iterdir() if d.is_dir() and not d.name.startswith('.'))
    if 指定:
        库们 = [d for d in 库们 if 指定 in d.name]

    结果 = []
    for 库 in 库们:
        for f in sorted(库.glob('能力声明/*.json')):
            声明 = json.loads(f.read_text(encoding='utf-8'))
            判, 说 = 发一次(声明['编号'], 造参(声明))
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
