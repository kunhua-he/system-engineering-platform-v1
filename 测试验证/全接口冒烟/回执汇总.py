# -*- coding: utf-8 -*-
"""回执汇总 —— 逐个能力发一次请求、收三档判定、落回执并打读数。

判据三档：
    成功   —— 真执行并返回结果
    参数错 —— 到达业务层但输入不合法（说明链路通，是参数没配对）
    协议错 —— HTTP 400，参数名或形状不对（文档与实现对不上，算真缺陷）

回执（`测试验证/全接口冒烟_回执.json`）是逐条明细，读数行是给人和父代理看的汇总。
"""

import json
import tempfile
import shutil
import subprocess
from pathlib import Path

from .参数配置 import 读配置, 造参
from .前置链 import 前置链, 前置准备, 记录调用, 释放本轮资源
from .素材备置 import 备素材
from .路径常量 import 声明根, 回执路径, 仓根
from .运行上下文 import 上下文, 重置上下文, 本轮资源
from .请求发送 import 发一次

判定次序 = ('成功', '参数错', '协议错', '连不上', '未覆盖', '回收失败')


def 列能力声明(指定库名=''):
    """按库名排序遍历能力声明件；给了 `指定库名` 就只跑名字含它的库。"""
    库们 = sorted(能力目录 for 能力目录 in 声明根.iterdir()
                  if 能力目录.is_dir() and not 能力目录.name.startswith('.'))
    if 指定库名:
        库们 = [能力目录 for 能力目录 in 库们 if 指定库名 in 能力目录.name]
    for 能力库 in 库们:
        for 声明件 in sorted(能力库.glob('能力声明/*.json')):
            yield 能力库.name, json.loads(声明件.read_text(encoding='utf-8'))


def 跑全量(配置, 指定库名=''):
    """一条能力一条判定；链式接口先解前置，解不出就记「前置未就绪」。"""
    结果表 = []
    for 库名, 声明 in 列能力声明(指定库名):
        编号 = 声明['编号']
        try:
            入参表 = 造参(声明, 库名, 配置)
            if 编号 in (3121, 3122, 3123, 3124):
                if not 上下文.get('受控工作区'):
                    raise RuntimeError('上游 3120：缺少本轮受控工作区')
                入参表['受控工作区'] = 上下文['受控工作区']
                if 编号 == 3123:
                    入参表['目标提交'] = 上下文['目标提交']
            if 编号 == 3120:
                入参表 = 准备独立仓库(配置)
            链规则 = (配置.get('链式') or {}).get(str(编号))
            if 链规则:
                入参表[链规则['填']] = 前置链(配置, 编号)
            if 编号 == 2512:
                返回值 = 前置准备(配置, 'LLM文本模型')
                判定, 说明 = '成功', ''
            elif 编号 == 2513:
                # 释放服务单独准备；不借别人的服务，不提前释放其他消费者的服务。
                入参表['服务句柄'] = 前置准备(配置, 'LLM文本模型')
                入参表['强制'] = False
                判定, 说明, 返回值 = 记录调用(编号, 入参表)
                上下文.get('本轮服务', {}).pop('LLM文本模型', None)
            elif 编号 == 2519:
                raise RuntimeError('2519 未覆盖：一次对话内部资源不归冒烟持有，待独立回收契约联调')
            else:
                判定, 说明, 返回值 = 记录调用(编号, 入参表)
            if 编号 == 3120 and 判定 == '成功':
                from .前置链 import 取前置值
                工作区 = 取前置值(返回值, {'取法': 'JSON字段', '字段': '工作区'})
                if not 工作区:
                    raise RuntimeError('上游 3120：返回缺少工作区')
                上下文['受控工作区'] = 工作区
                上下文['目标提交'] = subprocess.check_output([Git命令, '-C', 工作区, 'rev-parse', 'HEAD'], text=True).strip()
                关闭入参 = dict(入参表, 操作='关闭')
                本轮资源.append((3120, 关闭入参))
            if 编号 in (3121, 3122, 3123, 3124) and '受控工作区' not in 上下文:
                raise RuntimeError('上游 3120 未返回本轮受控工作区')
        except (RuntimeError, subprocess.SubprocessError, OSError) as 异常:
            判定, 说明 = '未覆盖', str(异常)
        if 声明['编号'] == 2516 and 判定 == '成功':
            归还判定, 归还说明, _ = 记录调用(2517, {'许可句柄': 返回值})
            if 归还判定 != '成功':
                判定, 说明 = '回收失败', '上游 2517：' + 归还说明
        for 回收说明 in 释放本轮资源((7006, 2517, 2505, 2604, 2408, 2506, 4931, 5404)):
            判定, 说明 = '回收失败', 回收说明
        结果表.append({'库': 库名, '编号': 声明['编号'],
                       '名': 声明['名称'].split('_')[-1], '判': 判定, '说': 说明})
    return 结果表


def 打读数(结果表):
    """总数 · 三档分布 · 协议错明细（只列前 15 条，其余在回执里）。"""
    分档 = {}
    for 单条结果 in 结果表:
        分档[单条结果['判']] = 分档.get(单条结果['判'], 0) + 1
    print('共 %d 个接口' % len(结果表))
    for 判定 in 判定次序:
        if 判定 in 分档:
            print('  %-4s %3d' % (判定, 分档[判定]))
    协议错们 = [单条结果 for 单条结果 in 结果表 if 单条结果['判'] == '协议错']
    if 协议错们:
        print('\n协议错（文档与实现对不上，真缺陷）：')
        for 单条结果 in 协议错们[:15]:
            print('  %d %s → %s' % (单条结果['编号'], 单条结果['名'], 单条结果['说'][:90]))


def 入口函数(argv=None):
    """用法：`python3 测试验证/全接口冒烟.py [库名]`。"""
    参数表 = list(argv if argv is not None else [])
    指定库名 = 参数表[0] if 参数表 else ''
    重置上下文()
    结果表 = []
    轮根 = Path(tempfile.mkdtemp(prefix='全接口冒烟-', dir=str(Path.home() / '.hermes/cache/scratch')))
    try:
        配置 = 读配置()
        配置 = 隔离配置(配置, 轮根)
        备素材(配置.get('素材根路径'))
        结果表 = 跑全量(配置, 指定库名)
    finally:
        工作区 = 上下文.get('受控工作区')
        if 工作区 and Path(工作区).resolve().is_relative_to(轮根.resolve()):
            清理回执 = subprocess.run([Git命令, '-C', 工作区, 'reset', '--hard', 'HEAD'], capture_output=True, text=True)
            if 清理回执.returncode:
                结果表.append({'库': '本轮资源', '编号': 3120, '名': '回收', '判': '回收失败', '说': 清理回执.stderr})
        for 说明 in 释放本轮资源():
            结果表.append({'库': '本轮资源', '编号': 0, '名': '回收', '判': '回收失败', '说': 说明})
        if 本轮资源 or any(单条.get('判') == '回收失败' for 单条 in 结果表):
            上下文['未回收轮根'] = str(轮根)
            归属件 = 轮根 / '资源归属.json'
            归属暂存 = 归属件.with_suffix('.写入中')
            归属暂存.write_text(json.dumps({'待回收': 本轮资源, '轮根': str(轮根)}, ensure_ascii=False), encoding='utf-8')
            归属暂存.replace(归属件)
            结果表.append({'库': '本轮资源', '编号': 0, '名': '保留归属', '判': '回收失败', '说': '退出未确认，保留轮根：' + str(轮根)})
        else:
            shutil.rmtree(轮根)
    暂存件 = 回执路径.with_suffix('.json.new')
    暂存件.write_text(json.dumps(结果表, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    暂存件.replace(回执路径)
    打读数(结果表)
    print('\n回执 %s' % 回执路径)
    return 1 if not 结果表 or any(单条['判'] != '成功' for 单条 in 结果表) else 0


def 隔离配置(配置, 轮根):
    """所有历史临时路径映射到本轮；输入素材保留原文件。"""
    原素材根 = 配置.get('素材根路径', '')

    def 转换参数(参数值):
        if isinstance(参数值, dict):
            return {参数键: 转换参数(子值) for 参数键, 子值 in 参数值.items()}
        if isinstance(参数值, list):
            return [转换参数(子值) for 子值 in 参数值]
        if isinstance(参数值, str):
            if 参数值.startswith('/tmp/全接口冒烟素材'):
                return str(轮根 / '素材') + 参数值.removeprefix('/tmp/全接口冒烟素材')
            if 参数值.startswith('/tmp/'):
                return str(轮根 / 参数值.removeprefix('/tmp/'))
            if 参数值.startswith('file:///tmp/'):
                return 'file://' + str(轮根 / 参数值.removeprefix('file:///tmp/'))
            if 原素材根 and 参数值.startswith(原素材根):
                return str(轮根 / '素材' / 参数值.removeprefix(原素材根).lstrip('/'))
            try:
                嵌套值 = json.loads(参数值)
            except (ValueError, TypeError):
                return 参数值
            if isinstance(嵌套值, (dict, list)):
                return json.dumps(转换参数(嵌套值), ensure_ascii=False)
        return 参数值

    配置 = 转换参数(配置)
    配置['素材根路径'] = str(轮根 / '素材')
    if 原素材根 and Path(原素材根).is_dir():
        shutil.copytree(原素材根, 轮根 / '素材', dirs_exist_ok=True)
    配置['轮根'] = str(轮根)
    return 配置


Git命令 = '/Library/Developer/CommandLineTools/usr/bin/git'


def 准备独立仓库(配置):
    """只读源仓库，所有 Git 写操作落到本轮独立克隆。"""
    轮根 = Path(配置['轮根']).resolve()
    克隆仓库 = 轮根 / '独立仓库'
    来源仓库 = (配置.get('Git准备') or {}).get('仓库路径', str(仓根))
    克隆 = subprocess.run([Git命令, 'clone', '--shared', '--no-checkout', '--', 来源仓库, str(克隆仓库)], capture_output=True, text=True)
    if 克隆.returncode:
        raise RuntimeError('上游 3120：独立克隆失败：' + 克隆.stderr)
    return {'操作': '创建', '仓库路径': str(克隆仓库), '工作区标识': 'smoke', '临时工作区根': str(轮根 / '仓外')}
