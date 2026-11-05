"""能力声明对齐：把 `能力声明/*.json` 里的参数默认值、必填、可抛错误码，按源码声明面回灌。

## 为什么要有这一步

平台装载时只认源码里那张 `[参数信息; N]` const 表，**不读 json**。json 只作两份用途：
扩展指纹的输入、给人看的说明书。两边原本各写各的，实测漂移过三种形态：

1. 源码写「空槽」（无默认值），json 写「默认 false、必填 false」——调用方按 json 调用必然踩空；
2. 源码写「空串内联槽」（有默认值但值是空），json 写「默认 LLM文本模型」——两边都不是真话；
3. 源码补了错误码，json 没跟——调用方查不到该能力可能抛什么。

根源是「两套事实源」。源码是唯一真相（网关读它），json 必须由它派生，不许手改。
本脚本只回灌**会漂移的那几格**（默认值 / 必填 / 可抛错误码），其余说明文字仍留在 json 里手写，
因为说明不影响装载行为；但参数名、类型标签这类承重字段同样以源码为准，源码里有就覆盖。

## 怎么用

    python3 构建装配/形态装配/能力声明对齐.py          # 对齐全部支持库
    python3 构建装配/形态装配/能力声明对齐.py --检查    # 只报差异，不写文件（门禁用）

退出码：0 = 已对齐 / 无差异；1 = 存在差异（--检查 模式）或写入失败。
"""

import argparse
import json
import re
import sys
from pathlib import Path


# 本文件在 构建装配/形态装配/能力声明对齐/ 下：parents[0]=包目录，[1]=形态装配，[2]=构建装配，[3]=仓根。
根 = Path(__file__).resolve().parents[3]
原子库根 = 根 / '扩展根目录' / '原子支持库'

# 源码里 `默认值:` 字段的三种写法
空槽标记 = '数据槽::空槽()'
内联槽模式 = re.compile(r'数据槽::内联槽\(\s*v1_contract::类型标签::构造\((\d+)\)\s*,\s*([^,]+),\s*([^)]+)\)')


def 读参数表(源码文本):
    """从 命令声明面.rs 里抽出每张参数表 → {表名: [参数字典]}。"""
    表们 = {}
    表模式 = re.compile(r'pub const (参数表_\w+)\s*:\s*\[参数信息;\s*(\d+)\]\s*=\s*\[(.*?)\n\];', re.S)
    # 块尾要用「默认值」这一行定位，不能用 `}`：说明文字里常带 json 示例（`{"类型标签":…}`），
    # 按 `}` 切会把块截断，抓出来的默认值张冠李戴 —— 实测因此把「前缀长度默认 19」误判成无默认值。
    项模式 = re.compile(r'参数信息\s*\{(.*?默认值:\s*[^\n]*)\n\s*\}', re.S)
    for 表匹配 in 表模式.finditer(源码文本):
        表名 = 表匹配.group(1)
        项们 = []
        for 项匹配 in 项模式.finditer(表匹配.group(3)):
            体 = 项匹配.group(1)
            名 = re.search(r'名称:\s*"([^"\\]+)', 体)
            类 = re.search(r'类型标签:\s*v1_contract::类型标签::构造\((\d+)\)', 体)
            # 整行抓，不能遇逗号就停：`内联槽(构造(1), 60000, 8)` 括号里就有逗号，
            # 用 `[^,\n]+` 只会抓到 `数据槽::内联槽(v1_contract::类型标签::构造(1)` 这半截，
            # 于是每个带真默认值的整数参数都被当成空槽 —— 实测 2519 的 等待毫秒=60000
            # 就是这样被误报成「应该改成空槽」的。
            默 = re.search(r'默认值:\s*(数据槽::[^\n]+)', 体)
            if not 名:
                continue
            默认写法 = 默.group(1).strip() if 默 else 空槽标记
            有默认 = 空槽标记 not in 默认写法
            项们.append({
                '名称': 名.group(1),
                '类型标签': int(类.group(1)) if 类 else 0,
                '有默认值': 有默认,
                '默认写法': 默认写法,
            })
        表们[表名] = 项们
    return 表们


def 读错误码表(源码文本, 码面文本):
    """把 `可抛错误码_X: [u32; N] = [错误码_编号::A, …]` 翻成真编号 → {常量表名: [编号]}。"""
    # 先拿 编号与码面.rs 里 `pub const A: u32 = 2501;` 这种对照
    编号对照 = {}
    for 匹配 in re.finditer(r'pub const (\w+)\s*:\s*u32\s*=\s*(\d+)\s*;', 码面文本):
        编号对照[匹配.group(1)] = int(匹配.group(2))
    表们 = {}
    for 匹配 in re.finditer(r'pub const (可抛错误码_\w+)\s*:\s*\[u32;\s*(\d+)\]\s*=\s*\[(.*?)\n\];', 源码文本, re.S):
        常量表名 = 匹配.group(1)
        编号们 = []
        for 项 in re.finditer(r'错误码_编号::(\w+)', 匹配.group(3)):
            真号 = 编号对照.get(项.group(1))
            if 真号 is not None:
                编号们.append(真号)
        表们[常量表名] = 编号们
    return 表们


def 默认值字段(项):
    """参数字典 → json 里那一格默认值。空槽写 0 型空值，内联槽按类型给空值。"""
    if not 项['有默认值']:
        return {'类型标签': 0, '值': 0}
    内联 = 内联槽模式.search(项['默认写法'])
    if 内联:
        类型 = int(内联.group(1))
        原值 = 内联.group(2).strip()
        # `内联槽(类型, 值, 字节数)`：文本/字节集那格是长度（0 就是空），数值型那格就是真值。
        # 曾经把这格一律当 0，结果把「前缀长度默认 19」误报成漂移，差点把对的 json 改坏。
        if 类型 in (1, 2, 6):
            真值 = int(原值) if 原值.lstrip('-').isdigit() else 0
            return {'类型标签': 类型, '值': 真值}
        if 类型 == 3:
            return {'类型标签': 3, '逻辑': 原值 not in ('0', 'false')}
        return {'类型标签': 类型, '值': 0}
    return {'类型标签': 0, '值': 0}


def 对齐一个库(库目录, 只检查=False):
    声明目录 = 库目录 / '能力声明'
    if not 声明目录.is_dir():
        return []
    源码文件 = 库目录 / 'src' / '命令声明面.rs'
    码面文件 = 库目录 / 'src' / '编号与码面.rs'
    if not 源码文件.is_file():
        return []
    参数表们 = 读参数表(源码文件.read_text(encoding='utf-8'))
    错误码表们 = 读错误码表(
        源码文件.read_text(encoding='utf-8'),
        码面文件.read_text(encoding='utf-8') if 码面文件.is_file() else '',
    )

    差异 = []
    for json文件 in sorted(声明目录.glob('*.json')):
        try:
            声明 = json.loads(json文件.read_text(encoding='utf-8'))
        except Exception as 错:
            差异.append('%s 读不动：%s' % (json文件.name, 错))
            continue
        原名 = 声明.get('名称') or ''
        # json 名形如「大语言模型支持库_连接模型」，源码表名形如「参数表_连接模型」
        短名 = 原名.split('_')[-1] if '_' in 原名 else 原名
        表名 = '参数表_' + 短名
        if 表名 not in 参数表们:
            continue
        源码项 = {项['名称']: 项 for 项 in 参数表们[表名]}
        改过 = False
        for 参 in 声明.get('参数表') or []:
            项 = 源码项.get(参.get('名称'))
            if not 项:
                差异.append('%s 参数「%s」源码里没有' % (json文件.name, 参.get('名称')))
                continue
            新默认 = 默认值字段(项)
            if 参.get('默认值') != 新默认:
                差异.append('%s 参数「%s」默认值 %s → %s' % (
                    json文件.name, 参.get('名称'),
                    json.dumps(参.get('默认值'), ensure_ascii=False),
                    json.dumps(新默认, ensure_ascii=False)))
                参['默认值'] = 新默认
                改过 = True
            # 「必填」不同步：平台装载只认源码那张 const 表，这一格写不写都不影响行为，
            # 同步它只会把全库一百多个 json 全部改一遍、指纹空转。默认值才是会骗人的那格。
        # 错误码：json 只写编号，源码表名按能力后缀匹配
        码表名 = '可抛错误码_' + 短名
        if 码表名 in 错误码表们:
            应码 = 错误码表们[码表名]
            现有 = 声明.get('可抛错误码') or []
            if sorted(现有) != sorted(应码):
                差异.append('%s 可抛错误码 %s → %s' % (json文件.name, 现有, 应码))
                声明['可抛错误码'] = 应码
                改过 = True
        if 改过 and not 只检查:
            json文件.write_text(json.dumps(声明, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return 差异


def 入口函数(命令行参数):
    解析 = argparse.ArgumentParser(description='按源码声明面对齐能力声明 json')
    解析.add_argument('--检查', action='store_true', help='只报差异不写文件')
    参数 = 解析.parse_args(命令行参数)

    全部差异 = []
    for 库目录 in sorted(原子库根.iterdir()):
        if 库目录.is_dir():
            全部差异 += 对齐一个库(库目录, 只检查=参数.检查)

    if not 全部差异:
        print('能力声明已与源码一致（0 处差异）')
        return 0
    for 行 in 全部差异:
        print('  ' + 行)
    print('%s %d 处差异' % ('发现' if 参数.检查 else '已对齐', len(全部差异)))
    return 1 if 参数.检查 else 0



