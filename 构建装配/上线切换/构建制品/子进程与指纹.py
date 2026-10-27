"""命令 —— 跑子进程（不吞输出）· 工具链版本 · 构建平台 · 依赖指纹 · 提交哈希与工作区脏。"""

import hashlib
import subprocess

from 构建装配.门禁.git路径解析 import 解析状态零分隔

from .装配输入常量 import 仓根, 回执相对路径


def 跑子进程(命令, **附加):
    """跑一个子进程；失败即抛，**不吞输出**。"""
    运行结果 = subprocess.run(命令, capture_output=True, text=True, **附加)
    if 运行结果.returncode != 0:
        raise SystemExit(
            "命令失败（退出码 {}）：{}\n{}\n{}".format(
                运行结果.returncode, " ".join(命令), 运行结果.stdout[-2000:], 运行结果.stderr[-2000:]
            )
        )
    return 运行结果


def 工具链版本() -> str:
    return 跑子进程(["rustc", "--version"], cwd=仓根).stdout.strip()


def 构建平台() -> str:
    """构建机平台三元组（`rustc -vV` 的 `host:` 行）—— 与工具链版本一起绑定进制品清单。"""
    for 源码行 in 跑子进程(["rustc", "-vV"], cwd=仓根).stdout.splitlines():
        if 源码行.startswith("host:"):
            return 源码行.split(":", 1)[1].strip()
    return ""


def 依赖指纹() -> str:
    """`Cargo.lock` 内容的 sha256（「依赖版本」这个绑定项的机器可判标识）。"""
    return hashlib.sha256((仓根 / "Cargo.lock").read_bytes()).hexdigest()


def 提交哈希() -> tuple:
    运行结果 = 跑子进程(["git", "rev-parse", "--short=12", "HEAD"], cwd=仓根).stdout.strip()
    # 全仓最后一处「既不带 `-z`、也不走共享解析」的 status 读法：只比一条 ASCII 相对路径时
    # 眼下不会误判，但留着就是回潮入口 ⇒ 一并改成 `-z` + 唯一解析节点。
    标准输出 = 跑子进程(["git", "status", "--porcelain", "-z"], cwd=仓根).stdout
    脏行 = [路径 for _, 路径 in 解析状态零分隔(标准输出) if 路径 != 回执相对路径]
    是否脏 = bool(脏行)
    return 运行结果, 是否脏
