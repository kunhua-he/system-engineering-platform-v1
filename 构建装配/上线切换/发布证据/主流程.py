"""主流程 —— 命令行入口本体：采证据 · 查兼容矩阵 · 阻断发布。"""

import argparse

from .正式证据 import 出证据, 写证据
from .阻断发布 import 打印阻断, 查缺项
from .兼容矩阵 import 查矩阵


def 入口函数(命令行参数: list) -> int:
    解析器 = argparse.ArgumentParser(description="发布证据 / 兼容矩阵 / 缺材料阻断（只读，只往构建缓存落一件）")
    解析器.add_argument("--阻断", action="store_true", help="只做阻断判定：缺材料即非零退出")
    解析器.add_argument("--兼容矩阵", action="store_true", help="只校验 契约声明/兼容矩阵.json")
    解析器.add_argument("--不落件", action="store_true", help="只采不落（预演）")
    命名空间 = 解析器.parse_args(命令行参数)
    if 命名空间.兼容矩阵:
        违规行, 矩阵 = 查矩阵()
        for 违规行 in 违规行:
            print("  兼容矩阵：" + 违规行, flush=True)
        if 矩阵 is None:
            print("兼容矩阵：未判（矩阵读不动，上面逐条）", flush=True)
            return 1
        print("兼容矩阵：%s" % ("通过" if not 违规行 else "不通过（上面逐条）"), flush=True)
        return 1 if 违规行 else 0
    if 命名空间.阻断:
        缺项, 证据 = 查缺项()
        if 缺项:
            打印阻断(缺项)
            return 1
        print("阻断判定：四类正式材料齐 ⇒ 放行。", flush=True)
        return 0
    退出码 = 0
    证据, 缺项 = 出证据()
    if 缺项:
        打印阻断(缺项)
        退出码 = 1
    elif 命名空间.不落件:
        print("预演：四类材料齐 · 证据指纹 " + 证据["证据指纹"], flush=True)
    else:
        print("正式证据落盘：" + 写证据(证据), flush=True)
        print("  证据指纹：" + 证据["证据指纹"], flush=True)
    违规行, 矩阵 = 查矩阵()
    for 违规行 in 违规行:
        print("  兼容矩阵：" + 违规行, flush=True)
    if 违规行:
        退出码 = 1
    return 退出码
