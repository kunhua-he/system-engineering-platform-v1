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
    if run("add", "-A").returncode != 0:
        return None, None, "git add 失败"
    c = run("commit", "-qm", "init")
    return (d, os.path.join(d, "开发工具", "认领机制", "认领机制.py"),
            "git 仓就绪" if c.returncode == 0 else "git commit 失败")


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
