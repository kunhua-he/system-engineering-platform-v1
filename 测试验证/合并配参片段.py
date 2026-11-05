"""把子代理回传的配参片段合并进 冒烟参数.json 的「按编号」层。

为什么要有它：配参是并行派活做的，每个子代理只写自己那组的片段，
合并只认片段里的键，冲突时后写的覆盖先写的（片段按编号分，实际不会撞）。

用法：python3 测试验证/合并配参片段.py
"""

import json
import sys
from pathlib import Path

根 = Path(__file__).resolve().parents[1]
配置路径 = 根 / '测试验证/冒烟参数.json'


def 主():
    配 = json.loads(配置路径.read_text(encoding='utf-8'))
    按号 = 配.setdefault('按编号', {})

    片段们 = sorted(Path('/tmp').glob('配参片段_*.json'))
    片段们 = [p for p in 片段们 if '未通' not in p.name]
    if not 片段们:
        print('没找到配参片段（/tmp/配参片段_*.json）')
        return 1

    新增 = 0
    for 片段 in 片段们:
        try:
            数据 = json.loads(片段.read_text(encoding='utf-8'))
        except Exception as 错:
            print('  %s 读不动：%s' % (片段.name, 错))
            continue
        if not isinstance(数据, dict):
            print('  %s 格式不对，跳过' % 片段.name)
            continue
        for 号, 参 in 数据.items():
            if not isinstance(参, dict) or not 参:
                continue   # 空字典不许覆盖已有配置
            按号[str(号)] = 参
            新增 += 1

    配置路径.write_text(json.dumps(配, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('合并 %d 个片段，按编号层共 %d 条参数配置' % (len(片段们), len(按号)))

    未通 = sorted(Path('/tmp').glob('配参片段_*_未通.json'))
    if 未通:
        总 = 0
        for 一 in 未通:
            try:
                数据 = json.loads(一.read_text(encoding='utf-8'))
                总 += len(数据)
            except Exception:
                pass
        print('另有 %d 条仍未配通（片段在 /tmp/配参片段_*_未通.json）' % 总)
    return 0


if __name__ == '__main__':
    sys.exit(主())
