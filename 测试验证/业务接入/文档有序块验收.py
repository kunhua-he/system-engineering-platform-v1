"""DOCX有序块的正式HTTP正反验证，供唯一业务接入驱动调用。"""
import json
import zipfile


def 执行文档验收(缓存, 请求, 调用):
    assert 请求('接口/能力/6112')[1]['契约']['返回类型'] == 4
    DOCX路径 = 缓存 / '有序块样本.docx'
    输入块 = [
        {'类型': '标题', '文本': '一级标题', '层级': 1},
        {'类型': '段落', '文本': '表前段落<&中'},
        {'类型': '表格', '表格数据': [['格1', '格2'], ['格3', '格4']]},
        {'类型': '段落', '文本': ''},
        {'类型': '段落', '文本': '表后段落'},
    ]
    内容JSON = json.dumps({'块列表': 输入块}, ensure_ascii=False)
    生成结果 = json.loads(调用(6113, [内容JSON, str(DOCX路径)], [4, 4])['值'][0]['值'])
    assert 生成结果['字节数'] == DOCX路径.stat().st_size and 生成结果['输出路径'] == str(DOCX路径), 生成结果
    回读结果 = json.loads(调用(6112, [str(DOCX路径)], [4])['值'][0]['值'])
    assert 回读结果['段数'] == 4 and 回读结果['表数'] == 1, 回读结果
    assert [块项['类型'] for 块项 in 回读结果['块列表']] == ['标题', '段落', '表格', '段落', '段落'], 回读结果
    assert 回读结果['块列表'][0]['来源位置']['附加']['level'] == 1
    assert 回读结果['块列表'][2]['表格数据'] == 输入块[2]['表格数据']
    assert [块项['文本'] for 块项 in 回读结果['块列表']] == ['一级标题', '表前段落<&中', '', '', '表后段落']
    assert '段落' not in 回读结果 and '表格' not in 回读结果
    with zipfile.ZipFile(DOCX路径) as 归档:
        条目集 = set(归档.namelist())
        assert 条目集 == {'[Content_Types].xml', '_rels/.rels', 'word/document.xml',
                          'word/_rels/document.xml.rels', 'word/styles.xml'}, 条目集
        样式正文 = 归档.read('word/styles.xml').decode()
        for 层级值 in range(1, 7):
            assert f'w:styleId="Heading{层级值}"' in 样式正文
    标题块 = [{'类型': '标题', '文本': f'标题{层级值}', '层级': 层级值} for 层级值 in range(1, 7)]
    调用(6113, [json.dumps({'块列表': 标题块}, ensure_ascii=False), str(DOCX路径)], [4, 4])
    标题回读 = json.loads(调用(6112, [str(DOCX路径)], [4])['值'][0]['值'])
    assert [块项['来源位置']['附加']['level'] for 块项 in 标题回读['块列表']] == list(range(1, 7))
    命名空间 = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    def 写正文样本(文件名, 正文):
        样本路径 = 缓存 / 文件名
        with zipfile.ZipFile(样本路径, 'w', compression=zipfile.ZIP_DEFLATED) as 归档:
            归档.writestr('word/document.xml', 正文)
        return str(样本路径)
    正文前缀 = f'<x:document xmlns:x="{命名空间}"><x:body>'
    正文后缀 = '</x:body></x:document>'
    变名前缀样本 = 写正文样本('实体与空段.docx', 正文前缀 + '<x:p/><x:p><x:r><x:t>&lt;&amp;&#x4E2D;</x:t><x:tab/><x:t>文</x:t><x:br/></x:r></x:p>' + 正文后缀)
    实体回读 = json.loads(调用(6112, [变名前缀样本], [4])['值'][0]['值'])
    assert [块项['文本'] for 块项 in 实体回读['块列表']] == ['', '<&中\t文\n'], 实体回读
    拒绝样本 = [
        ('坏正文.docx', 正文前缀 + '<x:p><x:r><x:t>未闭合' + 正文后缀),
        ('错误空间.docx', '<x:document xmlns:x="urn:错误空间"><x:body/></x:document>'),
        ('含声明.docx', '<!DOCTYPE document [<!ENTITY 示例 "不可使用">]>' + 正文前缀 + '<x:p/>' + 正文后缀),
        ('嵌套表格.docx', 正文前缀 + '<x:tbl><x:tr><x:tc><x:tbl/></x:tc></x:tr></x:tbl>' + 正文后缀),
    ]
    for 文件名, 正文 in 拒绝样本:
        返回 = 调用(6112, [写正文样本(文件名, 正文)], [4], True)
        assert 返回['错误']['码'] == 6103, 返回
    解压超限路径 = 写正文样本('解压超限.docx', 'x' * (32 * 1024 * 1024 + 1))
    assert 调用(6112, [解压超限路径], [4], True)['错误']['码'] == 6103
    文件超限路径 = 缓存 / '文件超限.docx'
    with 文件超限路径.open('wb') as 文件流:
        文件流.truncate(32 * 1024 * 1024 + 1)
    assert 调用(6112, [str(文件超限路径)], [4], True)['错误']['码'] == 6103
    坏包路径 = 缓存 / '坏包.docx'
    坏包路径.write_bytes(b'not a zip')
    for 文件路径 in [str(缓存 / '不存在.docx'), str(坏包路径)]:
        assert 调用(6112, [文件路径], [4], True)['错误']['码'] == 6103
    DOCX路径.write_bytes('保持目标'.encode())
    错误内容表 = [
        '不是JSON', json.dumps({'段落': [{'文本': '旧结构'}]}),
        json.dumps({'块列表': [{'类型': '未知类型', '文本': '不能丢弃'}]}),
        json.dumps({'块列表': [{'类型': '表格', '表格数据': [[7]]}]}),
        json.dumps({'块列表': [{'类型': '标题', '文本': '标题', '层级': 7}]}),
    ]
    for 错误内容 in 错误内容表:
        assert 调用(6113, [错误内容, str(DOCX路径)], [4, 4], True)['错误']['码'] == 6101
        assert DOCX路径.read_bytes() == '保持目标'.encode()
    assert 调用(6113, [内容JSON, str(缓存 / '缺目录/拒绝.docx')], [4, 4], True)['错误']['码'] == 6104
