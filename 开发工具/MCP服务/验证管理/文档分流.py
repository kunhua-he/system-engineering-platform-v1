"""纯文档判档唯一实现；源码、规则或未知变更保守走完整链。"""
import os
import sqlite3
import sys
import subprocess
from pathlib import Path

规则库路径 = "开发工具/信息核心/信息核心.db"

def 取Git字节(树根, *参数表):
    执行结果 = subprocess.run(["git", *参数表], cwd=树根, capture_output=True, timeout=5)
    if 执行结果.returncode:
        raise ValueError(执行结果.stderr.decode("utf-8", "replace"))
    return 执行结果.stdout

def 仅文档库变化(树根):
    旧连接 = sqlite3.connect(":memory:")
    新连接 = None
    try:
        旧连接.deserialize(取Git字节(树根, "show", "HEAD:"+规则库路径))
        新连接 = sqlite3.connect("file:"+str(Path(树根)/规则库路径)+"?mode=ro", uri=True)
        结构查询 = "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
        if 旧连接.execute(结构查询).fetchall() != 新连接.execute(结构查询).fetchall():
            return False
        for (表名文本,) in 旧连接.execute("SELECT name FROM sqlite_master WHERE type='table'"):
            if 表名文本 in ("条款", "未完成"):
                continue
            列名清单 = [列项[1] for 列项 in 旧连接.execute('PRAGMA table_info("'+表名文本+'")')]
            if 表名文本 == "命名登记":
                列名清单 = [列名文本 for 列名文本 in 列名清单 if 列名文本 != "出现次数"]
            查询语句 = 'SELECT '+','.join('"'+列名文本.replace('"','""')+'"' for 列名文本 in 列名清单)+' FROM "'+表名文本.replace('"','""')+'"'
            if set(旧连接.execute(查询语句)) != set(新连接.execute(查询语句)):
                return False
        return True
    finally:
        旧连接.close()
        if 新连接 is not None:
            新连接.close()

def 仅文档变更(树根):
    if os.environ.get("V1_FULL_GATE") == "1":
        return False
    try:
        暂存路径集 = set(取Git字节(树根, "diff", "--cached", "--name-only", "--no-renames", "-z", "HEAD").split(b"\0")) - {b""}
        磁盘路径集 = set(取Git字节(树根, "diff", "--name-only", "--no-renames", "-z").split(b"\0")) - {b""}
        # 同一路径的待提交内容与受检磁盘内容不一致，不把二者净差相抵后放行。
        if 暂存路径集 & 磁盘路径集:
            return False
        未跟踪集 = set(取Git字节(树根, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0")) - {b""}
        路径清单 = {路径字节.decode("utf-8") for 路径字节 in 暂存路径集 | 磁盘路径集 | 未跟踪集}
        for 索引条目 in 取Git字节(树根, "ls-files", "--stage", "-z").split(b"\0"):
            if not 索引条目:
                continue
            索引头, 索引路径 = 索引条目.split(b"\t", 1)
            文件模式, 对象哈希, 冲突阶段 = 索引头.split(b" ")
            if 索引路径.decode("utf-8") in 路径清单 and (文件模式 != b"100644" or 冲突阶段 != b"0"):
                return False
        if not 路径清单:
            return False
        for 路径文本 in 路径清单:
            完整路径 = Path(树根)/路径文本
            if 完整路径.is_symlink() or (完整路径.exists() and (not 完整路径.is_file() or 完整路径.stat().st_mode & 0o111)):
                return False
            if 路径文本 == 规则库路径:
                if not 完整路径.is_file() or not 仅文档库变化(树根):
                    return False
            elif not 路径文本.endswith(".md") or 路径文本.startswith(("测试验证/", "构建装配/")):
                return False
        return True
    except (OSError, ValueError, sqlite3.Error, subprocess.SubprocessError, UnicodeError):
        return False


def 执行文档放行(参数表):
    if 参数表 not in ([], ["--判档"]):
        return 2
    from .放行结果 import 记放行, 取树指纹
    树根 = Path.cwd()
    if not 仅文档变更(树根):
        return 99
    if 参数表:
        return 0
    开始指纹 = 取树指纹(树根)
    print("放行范围：文档；执行正式闸0，功能源码未变，不进入编译/预构建/案例链", flush=True)
    执行结果 = subprocess.run([sys.executable, "构建装配/一键验证/闸0.py"], cwd=树根)
    if 执行结果.returncode:
        return 执行结果.returncode
    if not 开始指纹 or 取树指纹(树根) != 开始指纹 or not 仅文档变更(树根):
        print("文档放行失败：验收期间树内容或变更范围改变，不记放行", file=sys.stderr)
        return 1
    if not 记放行(树根, 范围="文档"):
        return 1
    print("文档放行通过；静态门禁覆盖，不宣称功能验收", flush=True)
    return 0

