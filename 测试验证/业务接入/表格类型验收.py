"""XLSX正式HTTP正反验证；复用同一驱动、网关和请求留痕。"""
import json
import zipfile


def 执行表格验收(缓存, 请求, 调用):
    assert 请求('接口/能力/6114')[1]['契约']['返回类型'] == 4
    assert 请求('接口/能力/6115')[1]['契约']['返回类型'] == 4
    输出路径 = 缓存/'多表类型.xlsx'
    输入数据 = {'工作表列表': [
        {'表名': '明细数据', '列': ['文本', '数值', '逻辑', '空值', '公式'],
         '行': [['=1+1', 12.5, True, None, {'公式': '=B2*2'}], ['中文<&', 0, False, '', None]]},
        {'表名': '空白数据', '行': []},
    ]}
    内容文本 = json.dumps(输入数据, ensure_ascii=False)
    生成结果 = json.loads(调用(6115, [内容文本, str(输出路径)], [4, 4])['值'][0]['值'])
    assert 生成结果['字节数'] == 输出路径.stat().st_size
    读取结果 = json.loads(调用(6114, [str(输出路径)], [4])['值'][0]['值'])
    assert 读取结果['工作表数'] == 2
    assert [块项['来源位置']['工作表'] for 块项 in 读取结果['块列表']] == ['明细数据', '空白数据']
    矩阵数据 = 读取结果['块列表'][0]['表格数据']
    assert 矩阵数据[0] == 输入数据['工作表列表'][0]['列']
    assert 矩阵数据[1] == ['=1+1', 12.5, True, None, '=B2*2'], 矩阵数据
    assert 矩阵数据[2][:3] == ['中文<&', 0, False]
    assert 读取结果['块列表'][1]['表格数据'] == []
    with zipfile.ZipFile(输出路径) as 归档:
        工作表XML = 归档.read('xl/worksheets/sheet1.xml').decode()
        assert '<f>B2*2</f>' in 工作表XML
        assert '<f>1+1</f>' not in 工作表XML
    稀疏路径 = 缓存/'稀疏数据.xlsx'
    def 重写单表(目标路径, 替换):
        with zipfile.ZipFile(输出路径) as 来源, zipfile.ZipFile(目标路径, 'w', compression=zipfile.ZIP_DEFLATED) as 目标:
            for 条目 in 来源.infolist():
                字节 = 来源.read(条目.filename)
                if 条目.filename == 'xl/worksheets/sheet1.xml': 字节 = 替换(字节.decode()).encode()
                目标.writestr(条目.filename, 字节)
    # 独立固定OpenXML样本，不把自产自读当成唯一依据。
    样本XML = '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="C3:D5"/><sheetData><row r="3"><c r="C3" t="inlineStr"><is><t>独立中文&lt;&amp;</t></is></c><c r="D3"><v>3.5</v></c></row><row r="4"><c r="C4" t="b"><v>1</v></c><c r="D4"><f>D3*2</f><v>7</v></c></row><row r="5"><c r="C5" t="d"><v>2026-10-30T09:30:00</v></c><c r="D5" t="e"><v>#DIV/0!</v></c></row></sheetData></worksheet>'
    重写单表(稀疏路径, lambda _: 样本XML)
    独立返回 = json.loads(调用(6114, [str(稀疏路径)], [4])['值'][0]['值'])
    assert 独立返回['块列表'][0]['表格数据'] == [
        [None]*4, [None]*4, [None, None, '独立中文<&', 3.5],
        [None, None, True, '=D3*2'], [None, None, '2026-10-30T09:30:00', '#DIV/0!']]
    外部样本 = 缓存/'独立引擎样本.xlsx'
    if 外部样本.exists():
        外部返回 = json.loads(调用(6114, [str(外部样本)], [4])['值'][0]['值'])
        assert 外部返回['工作表数'] == 2
        外部矩阵 = 外部返回['块列表'][0]['表格数据']
        assert 外部矩阵[:2] == [[None]*5, [None]*5], 外部矩阵
        assert 外部矩阵[2] == [None, None, '独立中文<&', True, 3.5], 外部矩阵
        assert 外部矩阵[3] == [None, None, '=E3*2', '2026-10-30T09:30:00', '#DIV/0!'], 外部矩阵
    # 超坐标与超行在成熟引擎分配矩形前明确拒绝，不允许巨大稀疏位置触发分配。
    for 名称, 替换 in [('超行数据.xlsx', lambda 文本值: 文本值.replace('A1', 'A10001')),
                        ('超列数据.xlsx', lambda 文本值: 文本值.replace('A1', 'IW1'))]:
        目标路径 = 缓存/名称
        重写单表(目标路径, 替换)
        assert 调用(6114, [str(目标路径)], [4], True)['错误']['码'] == 6103
    损坏路径 = 缓存/'损坏数据.xlsx'
    损坏路径.write_bytes(b'not a workbook')
    assert 调用(6114, [str(损坏路径)], [4], True)['错误']['码'] == 6103
    assert 调用(6114, [str(缓存/'不存在.xlsx')], [4], True)['错误']['码'] == 6103
    assert 调用(6114, ['相对.xlsx'], [4], True)['错误']['码'] == 6101
    超限路径 = 缓存/'解压超限.xlsx'
    with zipfile.ZipFile(超限路径, 'w', compression=zipfile.ZIP_DEFLATED) as 归档:
        归档.writestr('xl/workbook.xml', b'x' * (32 * 1024 * 1024 + 1))
    assert 调用(6114, [str(超限路径)], [4], True)['错误']['码'] == 6103
    (缓存/'独立核验生成结果.xlsx').write_bytes(输出路径.read_bytes())
    输出路径.write_bytes('保持原件'.encode())
    拒绝表 = [[], [{'表名': '重复数据', '行': []}, {'表名': '重复数据', '行': []}],
              [{'表名': '非法/数据', '行': []}], [{'表名': '数据1', '行': [[1000000000000000]]}],
              [{'表名': '数据1', '行': [[{'未知': 7}]]}], [{'表名': '数据1', '行': ['不是数组']}],
              [{'表名': '数据1', '行': [[{'公式': 'B2*2'}]]}], [{'表名': '数据1', '行': [[None]*257]}]]
    for 工作表列表 in 拒绝表:
        返回 = 调用(6115, [json.dumps({'工作表列表': 工作表列表}, ensure_ascii=False), str(输出路径)], [4, 4], True)
        assert 返回['错误']['码'] == 6101, 返回
        assert 输出路径.read_bytes() == '保持原件'.encode()
    assert 调用(6115, [内容文本, str(缓存/'缺目录/目标.xlsx')], [4, 4], True)['错误']['码'] == 6104
    assert 调用(6115, [内容文本, '相对.xlsx'], [4, 4], True)['错误']['码'] == 6101
