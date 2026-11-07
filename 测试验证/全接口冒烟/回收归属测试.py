# -*- coding: utf-8 -*-
"""回收与归属的纯替身回归：只验「谁该被回收、回收失败怎么记」，不触达真实网关。"""
import importlib
import unittest
from unittest.mock import patch

链模块 = importlib.import_module('测试验证.全接口冒烟.前置链')
上下文模块 = importlib.import_module('测试验证.全接口冒烟.运行上下文')


class 回收归属验证(unittest.TestCase):
    def setUp(自身):
        上下文模块.上下文.clear()
        if hasattr(上下文模块, '本轮资源'):
            上下文模块.本轮资源.clear()

    def test_回收只用本轮句柄(自身):
        with patch.object(链模块, '发一次带值', side_effect=[('成功', '', 765), ('成功', '', True)]) as 发送:
            链模块.记录调用(7001, {'临时根目录': '/owned'})
            自身.assertEqual(链模块.释放本轮资源(), [])
            自身.assertEqual(发送.call_args.args, (7006, {'会话句柄': 765}))

    def test_已归还许可不再归还(自身):
        with patch.object(链模块, '发一次带值', side_effect=[('成功', '', 777), ('成功', '', True)]) as 发送:
            链模块.记录调用(2516, {'服务句柄': 888})
            链模块.记录调用(2517, {'许可句柄': 777})
            自身.assertEqual(链模块.释放本轮资源(), [])
            自身.assertEqual(发送.call_count, 2)

    def test_回收失败明确报告(自身):
        with patch.object(链模块, '发一次带值', side_effect=[('成功', '', 765), ('参数错', '回收拒绝', None)]):
            链模块.记录调用(7001, {'临时根目录': '/owned'})
            自身.assertRegex(链模块.释放本轮资源()[0], '7006.*回收拒绝')

    def test_轮次清空资源与缓存(自身):
        上下文模块.上下文['服务句柄'] = 123
        上下文模块.重置上下文()
        自身.assertEqual(上下文模块.上下文, {})

    def test_仅回收短生命周期资源(自身):
        with patch.object(链模块, '发一次带值', side_effect=[('成功', '', 765), ('成功', '', 876), ('成功', '', True)]) as 发送:
            链模块.记录调用(7001, {'临时根目录': '/owned'})
            链模块.记录调用(2512, {'模型类型': 'LLM文本模型'})
            自身.assertEqual(链模块.释放本轮资源((7006,)), [])
            自身.assertEqual(发送.call_args.args[0], 7006)
            自身.assertEqual(上下文模块.本轮资源[0][0], 2513)

    def test_释放回假不得注销资源(自身):
        with patch.object(链模块, '发一次带值', side_effect=[('成功', '', 777), ('成功', '', False)]):
            链模块.记录调用(2516, {'服务句柄': 888})
            链模块.记录调用(2517, {'许可句柄': 777})
            自身.assertEqual(len(上下文模块.本轮资源), 1)

    def test_未回收资源禁止被新轮抹掉(自身):
        上下文模块.本轮资源.append((7006, {'会话句柄': 765}))
        with 自身.assertRaisesRegex(RuntimeError, '未回收'):
            上下文模块.重置上下文()
        自身.assertEqual(len(上下文模块.本轮资源), 1)

    def test_回收失败保留归属目录(自身):
        import tempfile
        from pathlib import Path
        汇总模块 = importlib.import_module('测试验证.全接口冒烟.回执汇总')
        with tempfile.TemporaryDirectory(dir=str(Path.home() / '.hermes/cache/scratch')) as 测试根:
            轮根 = Path(测试根) / '隔离轮次'
            轮根.mkdir()
            with patch.object(汇总模块.tempfile, 'mkdtemp', return_value=str(轮根)), \
                 patch.object(汇总模块, '读配置', return_value={}), \
                 patch.object(汇总模块, '隔离配置', return_value={}), \
                 patch.object(汇总模块, '备素材'), \
                 patch.object(汇总模块, '跑全量', return_value=[{'库': '浏览器', '编号': 7001, '名': '创建', '判': '成功', '说': ''}]), \
                 patch.object(汇总模块, '释放本轮资源', return_value=['7006 未确认退出']), \
                 patch.object(汇总模块, '回执路径', Path(测试根) / '回执.json'):
                自身.assertEqual(汇总模块.入口函数([]), 1)
            自身.assertTrue(轮根.exists(), '回收未确认时不得删除仍可能被占用的轮根')
