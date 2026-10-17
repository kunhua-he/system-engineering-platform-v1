"""同名旧缓存与Cargo回执定位正反样本，不加载合成库字节。"""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch


def 执行产物回执样本():
    from 构建装配.上线切换.构建制品.产物回执 import 记扩展产物回执, 取扩展产物回执, 扩展回执路径
    with tempfile.TemporaryDirectory(prefix="产物回执样本_") as 临时目录:
        缓存 = Path(临时目录).resolve()
        清单路径 = 缓存 / "示例支持库" / "Cargo.toml"
        动态库 = 缓存 / "libexample.dylib"
        旧动态库 = 缓存 / "libexample-123456.dylib"
        动态库.write_bytes(b"current")
        旧动态库.write_bytes(b"legacy")
        构建事件 = dict(reason="compiler-artifact", manifest_path=str(清单路径), target=dict(name="example"), filenames=[str(动态库)])
        构建输出 = json.dumps(构建事件)
        with patch.object(Path, "glob", side_effect=AssertionError("不许扫描缓存")):
            assert 记扩展产物回执(构建输出, 清单路径, "example", 缓存) == 动态库
            assert 取扩展产物回执(清单路径, "example", 缓存) == 动态库
            assert 旧动态库.read_bytes() == b"legacy"
        for 构建事件 in (
            dict(reason="compiler-artifact", manifest_path=str(清单路径), target=dict(name="example"), filenames=[str(动态库), str(旧动态库)]),
            dict(reason="compiler-artifact", manifest_path=str(缓存 / "别库.toml"), target=dict(name="example"), filenames=[str(旧动态库)]),
            dict(reason="compiler-artifact", manifest_path=str(清单路径), target=dict(name="example"), filenames=[str(缓存.parent / "外部.dylib")]),
        ):
            try:
                记扩展产物回执(json.dumps(构建事件), 清单路径, "example", 缓存)
            except SystemExit:
                pass
            else:
                raise AssertionError("多产物、错清单和越界回执不得放行")
        动态库.write_bytes(b"modified")
        try:
            取扩展产物回执(清单路径, "example", 缓存)
        except SystemExit:
            pass
        else:
            raise AssertionError("产物摘要变更不得回退旧缓存")
        扩展回执路径(清单路径, 缓存).unlink()
        try:
            取扩展产物回执(清单路径, "example", 缓存)
        except SystemExit:
            pass
        else:
            raise AssertionError("缺回执不得选择残存库文件")
    print("产物回执6项正反样本通过。")


def 自检_扩展产物回执():
    try:
        执行产物回执样本()
    except (Exception, SystemExit) as 错误:
        return ["扩展产物回执样本失败：%s" % 错误]
    return []
