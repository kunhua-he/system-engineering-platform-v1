"""标准库独立计算期望；所有实际结果必须由公开HTTP取得。"""
import base64 as 编码引擎
import csv as CSV引擎
import hashlib as 摘要引擎
import io as 文本流引擎
import json
from datetime import datetime as 日期对象, timezone as 时区对象
import urllib.parse
import zlib


def 取独立样本():
    原文='中文🙂\0 /?+%'
    原字节=原文.encode()
    标准编码=编码引擎.b64encode(原字节).decode()
    CSV文本='姓名,备注\r\n门店,"订单123,中文🙂\n多行"\r\n'
    行表=list(CSV引擎.reader(文本流引擎.StringIO(CSV文本,newline='')))
    JSON文本=json.dumps(行表,ensure_ascii=False,separators=(',',':'))
    日期文本='2026-10-18T04:30:00+08:00'
    日期值=日期对象.fromisoformat(日期文本)
    UTC文本=日期值.astimezone(时区对象.utc).isoformat()
    XML文本='<根><标题>订单123&amp;中文🙂</标题><空/></根>'
    网址文本='https://example.com/a/b?键=1&键=中文'
    压缩=lambda 文本值:zlib.compress(文本值.encode()).hex().upper()
    样本表=[
        (4301,[原文],标准编码,0),(4302,[标准编码],原文,0),
        (4303,[原文],编码引擎.urlsafe_b64encode(原字节).decode().rstrip('='),0),
        (4304,[编码引擎.urlsafe_b64encode(原字节).decode().rstrip('=')],原文,0),
        (4501,[原文],原字节.hex().upper(),0),(4502,[原字节.hex()],原文,0),
        (4601,[原文],摘要引擎.sha256(原字节).hexdigest(),0),
        (4602,[原文],摘要引擎.sha512(原字节).hexdigest(),0),
        (2301,[日期文本],UTC文本,0),(2302,[日期文本,'%Y/%m/%d %H:%M %:z'],'2026/10/18 04:30 +08:00',0),
        (2303,['2026/10/18 04:30 +08:00','%Y/%m/%d %H:%M %:z'],日期文本,0),
        (3303,['/合成目录/记录.txt'],'记录.txt',0),(3302,['/合成目录/记录.txt'],'/合成目录',0),
        (3304,['/合成目录/记录.txt'],'txt',0),(3301,['/合成目录','子目录/../记录.txt'],'/合成目录/子目录/../记录.txt',0),(3301,['/合成目录','/绝对路径'],'/绝对路径',0),
        (4201,['https://EXAMPLE.COM:443/a/../b'],'https://example.com/b',0),
        (4202,['https://example.com/a/b','../c?x=1'],urllib.parse.urljoin('https://example.com/a/b','../c?x=1'),0),
        (4203,[网址文本],urllib.parse.parse_qsl(urllib.parse.urlsplit(网址文本).query),1),
        (5301,[CSV文本],行表,1),
        (4701,[XML文本],'根',0),(4702,[XML文本],'订单123&中文🙂',0),
        (4703,['<根><空/></根>'],dict(根名称='根',事件数量=3,最大深度=2,正文=''),1),
        (4702,['<?xml version="1.1"?><根>a\u0085b</根>'],'a\nb',0),
        (7969,[CSV文本],压缩(JSON文本),0),
        (7970,[CSV文本],dict(类型名称='列表',成员数量=len(行表),规范文本=JSON文本),0),
        (7971,[CSV文本,'/1/1',r'\d+'],['123'],0),
        (7973,[XML文本,r'\d+'],['123'],0),(7974,[XML文本,'/根名称'],'根',1),
        (7975,[网址文本,'/1/1'],'中文',0),
        (7976,['https://example.com/a/b','../c?x=1'],urllib.parse.quote('https://example.com/c?x=1',safe='-._~'),0),
        (7977,['/合成目录','子目录'],urllib.parse.quote('/合成目录/子目录',safe='-._~'),0),
        (7978,[日期文本],摘要引擎.sha256(UTC文本.encode()).hexdigest(),0),
        (7979,[标准编码],摘要引擎.sha256(原字节).hexdigest(),0),
        (7980,[原字节.hex()],压缩(原文),0),
        (7981,['日期\n'+日期文本+'\n','/1/0'],摘要引擎.sha256(UTC文本.encode()).hexdigest(),0)]
    for 编号 in (4301,4302,4303,4304,4501,4502):样本表.append((编号,[''],'',0))
    样本表.extend([(5301,[''],[],1),(5302,['[]'],'',0),(3302,['/'],'',0),(3304,['.配置'],'',0)])
    return 样本表,行表,JSON文本


def 核验独立样本(调用,检查,网关实例):
    样本表,行表,JSON文本=取独立样本()
    for 编号,参数表,期望值,是JSON in 样本表:
        实际值=调用(网关实例,编号,参数表)
        if 是JSON:实际值=json.loads(实际值)
        if 编号==4203:期望值=[list(键值对) for 键值对 in 期望值]
        检查(实际值==期望值,'能力%s独立标准对照'%编号,dict(期望=期望值,实际=实际值))
    CSV结果=调用(网关实例,5302,[JSON文本])
    检查(list(CSV引擎.reader(文本流引擎.StringIO(CSV结果,newline='')))==行表,'JSON转CSV保留字段与内部换行')
    编码结果=调用(网关实例,7972,[JSON文本])
    检查(list(CSV引擎.reader(文本流引擎.StringIO(编码引擎.b64decode(编码结果).decode(),newline='')))==行表,'CSV生成再编码跨库独立还原')
