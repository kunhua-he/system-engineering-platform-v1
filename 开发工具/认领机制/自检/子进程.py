# -*- coding: utf-8 -*-
"""真子进程夹具 —— 起真 git 仓 · 跑真命令行（提交闸读的是 `git diff --cached`）。

为什么这些样本要**真起一个 git 仓**：提交闸读的是 `git diff --cached`。
用假数据喂 `op_gate` 只能验「集合比对」这一层，验不到「路径基准是仓根不是子目录」
「改名两边都报」这两条 —— 而那两条正是 §五 第 5 条那个漏洞的入口。
判据要覆盖输出层与 git 层，故这里起真仓、真 `git add`、真子进程。
"""

import os
import shutil
import subprocess
import sys

from .核心 import HERE


def run_cli(ledger, *args):
    return subprocess.run([sys.executable, os.path.join(HERE, "认领机制.py")] + list(args),
                          capture_output=True, text=True,
                          env=dict(os.environ, CLAIM_LEDGER=ledger))


# 入口的**依赖闭包**（除同名包以外）：照仓内真实相对路径 —— 夹具仓必须是「真部署的样子」。
# 为什么要有这一步：夹具跑的是**拷进去的**入口，它 `from 构建装配.门禁 import 自门禁`
# （自门禁壳）与 `from 运行数据根 import …`（运行数据根的调用腿）。只拷入口与同名包 ⇒
# 夹具里 `ModuleNotFoundError`，十条 J5 样本一起红，而根因（少拷了两个包）看不出来 ——
# 实测撞到过两次（`认领机制.py` 加壳 · `账本.py` 加运行数据根调用腿），两次都是这十条一起红。
依赖闭包 = ("构建装配/门禁", "开发工具/运行数据根", "开发工具/运行数据根.py")


def _拷依赖(d):
    """把 `依赖闭包` 逐条拷进夹具仓（目录 copytree · 单件 copyfile）。缺件 ⇒ 当场炸。"""
    仓根 = os.path.dirname(os.path.dirname(HERE))
    for 相对 in 依赖闭包:
        源 = os.path.join(仓根, 相对)
        的 = os.path.join(d, 相对)
        if os.path.isdir(源):
            shutil.copytree(源, 的, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copyfile(源, 的)


def _冒烟(d):
    """夹具的**身份证**：拷完先跑一次入口，只断言「能装载」⇒ 缺依赖当场报出来。

    为什么要有它：少了它，缺依赖的表现是「十条样本一起红、每条只说不等于期望值」——
    看起来像判据全坏，其实是夹具缺件。这里把根因顶到第一条错误信息里。
    → 空串 = 好；非空 = 说明（夹具不合格，样本不该照跑）。
    """
    r = subprocess.run([sys.executable, os.path.join(d, "开发工具", "认领机制", "认领机制.py")],
                       capture_output=True, text=True, cwd=d,
                       env={k: v for k, v in os.environ.items() if k != "CLAIM_GATE"})
    if "ModuleNotFoundError" in r.stderr or "ImportError" in r.stderr:
        return "夹具缺依赖闭包（%s）⇒ 入口装载失败：%s" % (
            " · ".join(依赖闭包), r.stderr.strip().splitlines()[-1])
    return ""


def git_repo(d, files):
    """在 d 里造一个**能跑真命令行**的仓：git 仓 + `rust-toolchain.toml` + 一份本件脚本。

    为什么要连脚本（入口 + 同名包）一起拷进去：脚本的仓根靠「向上找 `rust-toolchain.toml`」定，
    而账本里的路径是**仓根相对**的。若脚本住在 A 仓、提交发生在 B 仓，两个仓根错开
    ⇒ 比对退化（假绿）。提交闸对这种情况报「判不了」（`op_gate` 里的基准一致性检查）。
    所以样本必须让「脚本所在仓」与「提交所在仓」是同一个 —— 这才是真部署的样子。
    入口 `认领机制.py` 现在只是路由，公开面在同名包 `认领机制/` 里 ⇒ **包必须一起拷**。
    → (仓根, 脚本路径, 说明)
    """
    def run(*args):
        return subprocess.run(["git", "-C", d] + list(args),
                              capture_output=True, text=True)
    if run("init", "-q", ".").returncode != 0:
        return None, None, "git init 失败"
    run("config", "user.email", "selftest@local")
    run("config", "user.name", "selftest")
    with open(os.path.join(d, "rust-toolchain.toml"), "w", encoding="utf-8") as f:
        f.write('channel = "stable"\n')
    files = dict(files)
    files["开发工具/认领机制/自检占位.txt"] = "占位（本仓只是样本的舞台）\n"
    for rel, body in files.items():
        p = os.path.join(d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(body)
    shutil.copyfile(os.path.join(HERE, "认领机制.py"),
                    os.path.join(d, "开发工具", "认领机制", "认领机制.py"))
    shutil.copytree(os.path.join(HERE, "认领机制"),
                    os.path.join(d, "开发工具", "认领机制", "认领机制"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    _拷依赖(d)
    if run("add", "-A").returncode != 0:
        return None, None, "git add 失败"
    c = run("commit", "-qm", "init")
    if c.returncode != 0:
        return None, None, "git commit 失败"
    坏 = _冒烟(d)
    if 坏:
        return None, None, 坏
    return d, os.path.join(d, "开发工具", "认领机制", "认领机制.py"), "git 仓就绪"


def run_gate(d, script, *args, env=None):
    """在真仓 d 里跑提交闸子进程（cwd=d ⇒ 仓根就是 d）。env 用来试 CLAIM_GATE 这个开关。"""
    e = dict(os.environ)
    e.pop("CLAIM_GATE", None)              # 不许外面环境漏进来干扰「默认」那一条
    e.update(env or {})
    return subprocess.run([sys.executable, script, "提交闸"] + list(args),
                          capture_output=True, text=True, cwd=d, env=e)


def run_claim(d, script, *args):
    """在真仓 d 里跑 `认领` 子进程（账本就落该仓自己的目录里）。"""
    return subprocess.run([sys.executable, script] + list(args),
                          capture_output=True, text=True, cwd=d)


def stage(d, *rels):
    return subprocess.run(["git", "-C", d, "add"] + list(rels),
                          capture_output=True, text=True).returncode == 0


def edit(d, rel, text="改了一行\n"):
    with open(os.path.join(d, rel), "a", encoding="utf-8") as f:
        f.write(text)
