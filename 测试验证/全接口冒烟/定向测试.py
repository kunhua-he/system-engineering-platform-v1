# -*- coding: utf-8 -*-
"""纯替身回归，不触达模型、浏览器或真实网关。"""
import importlib
import sys
import time
import unittest

起始时刻 = time.monotonic()
from unittest.mock import patch

链模块 = importlib.import_module('测试验证.全接口冒烟.前置链')
上下文模块 = importlib.import_module('测试验证.全接口冒烟.运行上下文')
# 回收与归属那一组在同名字件里，跑本入口时一并带上。
from 测试验证.全接口冒烟.回收归属测试 import 回收归属验证  # noqa: F401


class 冒烟前置验证(unittest.TestCase):
    def setUp(自身):
        上下文模块.上下文.clear()
        if hasattr(上下文模块, '本轮资源'):
            上下文模块.本轮资源.clear()

    def test_属性读取真实数字(自身):
        自身.assertEqual(链模块.取前置值("<div data-hs-h='12345'></div>", {'取法': 'HTML属性'}), 12345)

    def test_网页回执选择表格(自身):
        回文 = '{"片段":"<div data-hs-h=\"11\"><table class=\"hs-表格\" data-hs-h=\"12\"></table></div>"}'
        自身.assertEqual(链模块.取前置值(回文, {'取法': 'HTML属性', '组件类型': '表格'}), 12)

    def test_无模型目标不扫描服务(自身):
        with patch.object(链模块, '发一次带值', return_value=('参数错', '不可用', None)) as 发送:
            链模块.前置准备({})
            自身.assertEqual(发送.call_count, 0)

    def test_许可不能缓存复用(自身):
        配置 = {'链式': {'2517': {'前置': 2516, '取法': '首值', '填': '许可句柄'}}}
        with patch.object(链模块, '发一次带值', side_effect=[('成功', '', 321), ('成功', '', 322)]):
            自身.assertEqual(链模块.前置链(配置, 2517), 321)
            自身.assertEqual(链模块.前置链(配置, 2517), 322)

    def test_前置错误保留上游编号(自身):
        配置 = {'链式': {'7002': {'前置': 7001, '填': '会话句柄'}}}
        with patch.object(链模块, '发一次带值', return_value=('协议错', '缺字段', None)):
            with 自身.assertRaisesRegex(RuntimeError, '7001.*缺字段'):
                链模块.前置链(配置, 7002)

    def test_向量缺模型不可借聊天(自身):
        with patch.object(链模块, '发一次带值') as 发送:
            with 自身.assertRaisesRegex(RuntimeError, '未覆盖.*EM向量模型'):
                链模块.前置准备({}, 'EM向量模型')
            发送.assert_not_called()



    def test_依赖环不可递归挂死(自身):
        配置 = {'链式': {'7001': {'前置': 7002, '填': '会话句柄'}, '7002': {'前置': 7001, '填': '会话句柄'}}}
        with 自身.assertRaisesRegex(RuntimeError, '依赖环'):
            链模块.前置链(配置, 7001)

    def test_两轮配置输出隔离(自身):
        汇总模块 = importlib.import_module('测试验证.全接口冒烟.回执汇总')
        from pathlib import Path
        配置 = {'全局': {'文件路径': '/tmp/history/示例.txt'}, '素材根路径': '/not-present'}
        本轮 = 汇总模块.隔离配置(配置, Path('/owned/round-one'))
        下轮 = 汇总模块.隔离配置(配置, Path('/owned/round-two'))
        自身.assertNotEqual(本轮['全局']['文件路径'], 下轮['全局']['文件路径'])

    def test_独立仓库只读克隆来源(自身):
        汇总模块 = importlib.import_module('测试验证.全接口冒烟.回执汇总')
        with patch.object(汇总模块.subprocess, 'run') as 克隆:
            克隆.return_value.returncode = 0
            入参表 = 汇总模块.准备独立仓库({'轮根': '/owned/round-one', 'Git准备': {'仓库路径': '/readonly/source'}})
            自身.assertEqual(入参表['仓库路径'], '/owned/round-one/独立仓库')
            自身.assertIn('--no-checkout', 克隆.call_args.args[0])
            自身.assertEqual(克隆.call_args.args[0][-2], '/readonly/source')

    def test_真实表格标记筛选(自身):
        回文 = '<div data-hs-h="11"><div class="hs-tree-node hs-card" data-组件标记="冒烟表格" data-hs-h="12"></div></div>'
        自身.assertEqual(链模块.取前置值(回文, {'取法': 'HTML属性', '属性筛选': {'data-组件标记': '冒烟表格'}}), 12)

    def test_缺权重不启动服务(自身):
        配置 = {'模型准备': {'EM向量模型': {'模型类型': 'EM向量模型', '模型引用': '/not-existing/model.gguf'}}}
        with patch.object(链模块, '发一次带值') as 发送:
            with 自身.assertRaisesRegex(RuntimeError, '2512 未覆盖.*权重不存在'):
                链模块.前置准备(配置, 'EM向量模型')
            发送.assert_not_called()


    def test_入口异常仍然回收资源(自身):
        汇总模块 = importlib.import_module('测试验证.全接口冒烟.回执汇总')
        with patch.object(汇总模块, '读配置', side_effect=RuntimeError('配置拒绝')), patch.object(汇总模块, '释放本轮资源', return_value=[]) as 回收:
            with 自身.assertRaisesRegex(RuntimeError, '配置拒绝'):
                汇总模块.入口函数([])
            回收.assert_called_once()

    def test_非模型目标仅调目标能力(自身):
        汇总模块 = importlib.import_module('测试验证.全接口冒烟.回执汇总')
        声明 = {'编号': 6110, '名称': '办公文档支持库_求值', '参数表': []}
        with patch.object(汇总模块, '列能力声明', return_value=[('办公文档支持库', 声明)]), patch.object(链模块, '发一次带值', return_value=('成功', '', 2)) as 发送:
            结果表 = 汇总模块.跑全量({}, '办公文档支持库')
            自身.assertEqual(结果表[0]['判'], '成功')
            自身.assertEqual(发送.call_count, 1)
            自身.assertEqual(发送.call_args.args[0], 6110)

    def test_缺向量模型目标明确未覆盖(自身):
        汇总模块 = importlib.import_module('测试验证.全接口冒烟.回执汇总')
        声明 = {'编号': 2509, '名称': '大语言模型支持库_向量', '参数表': []}
        配置 = {'链式': {'2509': {'前置': 2508, '填': '句柄'}, '2508': {'前置': '服务状态', '模型类型': 'EM向量模型', '填': '服务器地址'}}}
        with patch.object(汇总模块, '列能力声明', return_value=[('大语言模型支持库', 声明)]), patch.object(链模块, '发一次带值') as 发送:
            结果表 = 汇总模块.跑全量(配置)
            自身.assertEqual(结果表[0]['判'], '未覆盖')
            自身.assertIn('2512 未覆盖', 结果表[0]['说'])
            发送.assert_not_called()



    def test_模型就绪按显式期限观察(自身):
        配置 = {'模型准备': {'EM向量模型': {'模型类型': 'EM向量模型', '模型引用': '/真实权重.gguf', '载入超时秒': 60}}}
        载入中 = {'存活': True, '状态': '载入中', '模型类型': 'EM向量模型'}
        已就绪 = dict(载入中, 状态='已载入')
        with patch.object(链模块.Path, 'is_file', return_value=True), \
             patch.object(链模块, '记录调用', side_effect=[('成功', '', 987), ('成功', '', 载入中), ('成功', '', 已就绪)]) as 发送, \
             patch('time.sleep'):
            自身.assertEqual(链模块.前置准备(配置, 'EM向量模型'), 987)
            自身.assertEqual([调用.args[0] for 调用 in 发送.call_args_list], [2512, 2514, 2514])


if __name__ == '__main__':
    结局 = unittest.main(exit=False)
    print('定向测试墙钟 %.0f ms' % ((time.monotonic() - 起始时刻) * 1000))
    sys.exit(0 if 结局.result.wasSuccessful() else 1)
