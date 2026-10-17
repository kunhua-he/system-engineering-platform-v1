"""真实Git主仓与工作树：共享依赖家、隔离编译输出，不启动业务服务。"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from unittest.mock import patch
from 构建装配.形态装配.生成模块制品.编译模块 import 编译环境


def 自检_共享构建缓存():
    from 构建装配.一键验证.一键验证.判据_散文 import 版本库环境
    with patch.dict(os.environ,版本库环境(),clear=True):
        return _验证共享缓存()


def _验证共享缓存():
    源入口=Path(__file__).resolve().parents[2]/"构建环境/进入.sh"
    断言表=[]
    with tempfile.TemporaryDirectory(prefix="构建缓存语义_") as 临时路径:
        主目录=Path(临时路径).resolve()/"主目录";主目录.mkdir()
        工作目录=Path(临时路径).resolve()/"工作目录"
        (主目录/"构建环境").mkdir()
        (主目录/"构建环境/进入.sh").write_text(源入口.read_text())
        (主目录/"rust-toolchain.toml").write_text('[toolchain]\nchannel="stable"\n')
        def 跑版本命令(*参数表):
            return subprocess.run(["git","-C",str(主目录),*参数表],check=True,capture_output=True,timeout=5)
        跑版本命令("init")
        跑版本命令("add",".")
        跑版本命令("-c","user.name=构建环境验收","-c","user.email=build@example.invalid","-c","core.hooksPath=/dev/null","commit","-m","构建环境样本")
        跑版本命令("worktree","add","--detach",str(工作目录),"HEAD")
        环境表=[];原目录=Path.cwd()
        try:
            with patch.dict(os.environ):
                os.environ["CARGO_HOME"]=str(Path(临时路径)/"错误依赖家")
                os.environ.pop("CARGO_TARGET_DIR",None)
                for 当前目录 in (主目录,工作目录):
                    os.chdir(当前目录)
                    环境表.append(编译环境(Path(临时路径)/"暂存"))
                断言表.append(("主仓与新工作树共用主仓唯一依赖缓存",环境表[0]["CARGO_HOME"]==环境表[1]["CARGO_HOME"]==str(主目录/"构建环境/构建缓存/cargo"),""))
                断言表.append(("默认编译产物按工作树隔离",环境表[0]["CARGO_TARGET_DIR"]!=环境表[1]["CARGO_TARGET_DIR"]==str(工作目录/"构建环境/构建缓存"),""))
                断言表.append(("正式编译保持离线",all(环境项["CARGO_NET_OFFLINE"]=="true" for 环境项 in 环境表),""))
                os.environ["CARGO_TARGET_DIR"]=str(Path(临时路径)/"显式编译目录")
                断言表.append(("保留调用方显式指定的编译输出目录",编译环境(Path(临时路径)/"暂存")["CARGO_TARGET_DIR"]==os.environ["CARGO_TARGET_DIR"],""))
                os.chdir(临时路径)
                try:
                    编译环境(Path(临时路径)/"暂存")
                except RuntimeError as 错误:
                    断言表.append(("正式环境入口不存在必须具体报错","进入.sh" in str(错误),str(错误)))
                else:
                    断言表.append(("正式环境入口不存在必须具体报错",False,"未拒绝"))
        finally:
            os.chdir(原目录)
    return 断言表
