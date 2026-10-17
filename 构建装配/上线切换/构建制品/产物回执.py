"""扩展产物回执：Cargo构建图是路径唯一源；查找不执行构建、不扫描候选。"""
import hashlib
import json
import os
from pathlib import Path


def 扩展回执路径(清单路径, 缓存):
    清单指纹 = hashlib.sha256(str(清单路径.resolve()).encode()).hexdigest()
    return 缓存 / "产物回执" / (清单指纹 + ".json")


def 校验扩展产物路径(动态库, 缓存):
    动态库 = Path(动态库).resolve()
    if not 动态库.is_relative_to(缓存.resolve()) or not 动态库.is_file():
        raise SystemExit("构建回执产物不存在或越过本树缓存：%s" % 动态库)
    if 动态库.suffix not in (".dylib", ".so", ".dll"):
        raise SystemExit("构建回执不是可装载库：%s" % 动态库)
    return 动态库


def 记扩展产物回执(构建输出, 清单路径, 名称, 缓存):
    产物候选集 = set()
    for 源码行 in 构建输出.splitlines():
        try:
            构建事件 = json.loads(源码行)
        except json.JSONDecodeError as 错误:
            raise SystemExit("Cargo构建回执不是JSON：%s" % 错误) from 错误
        if 构建事件.get("reason") != "compiler-artifact":
            continue
        if Path(构建事件.get("manifest_path", "")).resolve() != 清单路径.resolve():
            continue
        if 构建事件.get("target", {}).get("name") != 名称:
            continue
        for 产物路径 in 构建事件.get("filenames", []):
            if Path(产物路径).suffix in (".dylib", ".so", ".dll"):
                产物候选集.add(校验扩展产物路径(产物路径, 缓存))
    if len(产物候选集) != 1:
        raise SystemExit("Cargo本次构建回执可装载库须唯一：%s，实际%s" % (清单路径, len(产物候选集)))
    动态库 = 产物候选集.pop()
    回执路径 = 扩展回执路径(清单路径, 缓存)
    回执路径.parent.mkdir(parents=True, exist_ok=True)
    产物回执 = dict(清单=str(清单路径.resolve()), 库名=名称, 产物=str(动态库), 摘要=hashlib.sha256(动态库.read_bytes()).hexdigest())
    临时回执 = 回执路径.with_suffix(".%s.tmp" % os.getpid())
    try:
        临时回执.write_text(json.dumps(产物回执, ensure_ascii=False), encoding="utf-8")
        临时回执.replace(回执路径)
    finally:
        临时回执.unlink(missing_ok=True)
    return 动态库


def 取扩展产物回执(清单路径, 名称, 缓存):
    回执路径 = 扩展回执路径(清单路径, 缓存)
    if not 回执路径.is_file():
        raise SystemExit("缺少Cargo产物回执：%s；先经正式环境步预构建，不从缓存候选猜测" % 清单路径)
    产物回执 = json.loads(回执路径.read_text(encoding="utf-8"))
    if 产物回执.get("清单") != str(清单路径.resolve()) or 产物回执.get("库名") != 名称:
        raise SystemExit("Cargo产物回执清单或库名不匹配：%s" % 清单路径)
    动态库 = 校验扩展产物路径(产物回执["产物"], 缓存)
    if hashlib.sha256(动态库.read_bytes()).hexdigest() != 产物回执.get("摘要"):
        raise SystemExit("Cargo产物回执摘要与库文件不符：%s；重新正式预构建" % 动态库)
    return 动态库
