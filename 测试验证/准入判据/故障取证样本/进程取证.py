"""有界样本观察与真实退出取证；不证明生产宿主隔离或原生库初始化。"""

import hashlib
import json
import os
import platform
import selectors
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from 开发工具.运行数据根 import 子目录路径, 解析当前环境, 覆盖变量名
from .进程行为 import 故障模式表

批准夹具预算 = {"执行窗口毫秒": 200, "回收毫秒": 500,
              "单例硬顶毫秒": 1000, "每路保留字节": 65536}
未回收进程表 = []


def 文件指纹(文件路径):
    指纹对象 = hashlib.sha256()
    with Path(文件路径).open("rb") as 文件句柄:
        while 字节块 := 文件句柄.read(65536):
            指纹对象.update(字节块)
    return 指纹对象.hexdigest()


def 读源码身份():
    仓根 = Path(__file__).resolve().parents[3]
    提交哈希 = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=仓根, timeout=0.2, text=True).strip()
    工作区读数 = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=仓根, timeout=0.2)
    源件表 = sorted(Path(__file__).parent.glob("*.py")) + [
        仓根 / "开发工具/运行数据根/口径.py", 仓根 / "开发工具/运行数据根/__init__.py"]
    return {"提交哈希": 提交哈希, "工作区是否干净": not 工作区读数,
            "工作区状态指纹": hashlib.sha256(工作区读数).hexdigest(),
            "源码指纹": {str(源件.relative_to(仓根)): 文件指纹(源件) for 源件 in 源件表},
            "制品": str(Path(sys.executable).resolve()), "制品指纹": 文件指纹(sys.executable),
            "工具链": sys.version, "平台": platform.platform(), "构建模式": "Python解释执行/未构建原生制品"}


def 读描述符数():
    for 描述符目录 in (Path("/proc/self/fd"), Path("/dev/fd")):
        if 描述符目录.is_dir():
            return len(os.listdir(描述符目录))
    return None


def 进程组仍在(进程号):
    try:
        os.killpg(进程号, 0)
        return True
    except ProcessLookupError:
        return False


def 排空输出(选择器, 输出读数, 每路保留字节, 等待秒数):
    for 选择键, 就绪事件 in 选择器.select(max(0, 等待秒数)):
        通道名称 = 选择键.data
        try:
            字节块 = os.read(选择键.fd, 16384)
        except BlockingIOError:
            continue
        if not 字节块:
            选择器.unregister(选择键.fileobj)
            continue
        通道读数 = 输出读数[通道名称]
        通道读数["读取字节"] += len(字节块)
        可保留数 = max(0, 每路保留字节 - len(通道读数["保留内容"]))
        通道读数["保留内容"].extend(字节块[:可保留数])
        通道读数["丢弃字节"] += max(0, len(字节块) - 可保留数)


def 读阶段标记(输出读数, 授权令牌, 进程号, 故障模式):
    阶段表 = []
    for 标记行 in bytes(输出读数["stderr"]["保留内容"]).splitlines():
        try:
            标记值 = json.loads(标记行)
        except (ValueError, UnicodeDecodeError):
            continue
        if (isinstance(标记值, dict) and 标记值.get("令牌") == 授权令牌
                and 标记值.get("进程号") == 进程号 and 标记值.get("模式") == 故障模式):
            阶段表.append(标记值.get("阶段"))
    return 阶段表


def 回收样本(子进程, 选择器, 输出读数, 回收毫秒, 每路保留字节):
    回收起点 = time.monotonic()
    回收截止 = 回收起点 + 回收毫秒 / 1000
    发送信号表 = []
    for 信号值, 等待窗口 in ((signal.SIGTERM, 0.02), (signal.SIGKILL, 回收毫秒 / 1000)):
        if not 进程组仍在(子进程.pid):
            break
        try:
            os.killpg(子进程.pid, 信号值)
            发送信号表.append(int(信号值))
        except ProcessLookupError:
            break
        等待截止 = min(回收截止, time.monotonic() + 等待窗口)
        while 子进程.poll() is None and time.monotonic() < 等待截止:
            排空输出(选择器, 输出读数, 每路保留字节, min(0.005, 等待截止 - time.monotonic()))
    while 选择器.get_map() and time.monotonic() < 回收截止:
        排空输出(选择器, 输出读数, 每路保留字节, min(0.005, 回收截止 - time.monotonic()))
    已确认退出 = 子进程.poll() is not None and not 进程组仍在(子进程.pid)
    if not 已确认退出:
        未回收进程表.append(子进程)
    return {"发送信号": 发送信号表, "确认退出": 已确认退出,
            "管道已排空": not 选择器.get_map(),
            "耗时毫秒": (time.monotonic() - 回收起点) * 1000}


def 判样本观测(故障模式, 授权令牌, 观测值):
    阶段表 = 观测值["阶段"]
    if 故障模式 == "启动失败":
        return 观测值["退出状态"] == 71 and 阶段表 == ["启动"]
    if 故障模式 == "夹具初始化失败":
        return (观测值["退出状态"] == 72
                and 阶段表 == ["启动", "夹具初始化", "夹具初始化失败"])
    if 阶段表 != ["启动", "夹具初始化", "就绪", "调用触发"]:
        return False
    if 故障模式 == "正常返回":
        return (观测值["退出状态"] == 0 and 观测值["停止原因"] == "进程退出"
                and 观测值["输出"]["stdout"]["内容指纹"] == hashlib.sha256(
                    ("正常返回:" + 授权令牌 + "\n").encode("utf-8")).hexdigest())
    if 故障模式 == "调用崩溃":
        return 观测值["退出状态"] == -signal.SIGABRT
    if 故障模式 == "永久阻塞":
        return (观测值["停止原因"] == "执行截止" and 观测值["截止时仍活"]
                and 观测值["退出状态"] == -signal.SIGKILL)
    目标通道表 = {"持续标准输出": ["stdout"], "持续错误输出": ["stderr"],
               "持续双路输出": ["stdout", "stderr"]}[故障模式]
    return (观测值["停止原因"] == "输出超限" and 观测值["退出状态"] == -signal.SIGKILL
            and all(观测值["输出"][通道名称]["丢弃字节"] > 0 for 通道名称 in 目标通道表))


@contextmanager
def 准备监督命令(故障模式):
    """仅准备受控Command配置，不启动进程；调用者必须在退出上下文前确认监督回收。"""
    if os.name != "posix" or 故障模式 not in 故障模式表:
        raise ValueError("只支持POSIX受控测试模式")
    运行数据根 = 解析当前环境().resolve()
    临时目录根 = 子目录路径(运行数据根, "临时件") / "故障夹具"
    临时目录根.mkdir(mode=0o700, parents=True, exist_ok=True)
    授权令牌 = uuid.uuid4().hex
    with tempfile.TemporaryDirectory(prefix=授权令牌 + "-", dir=临时目录根) as 临时目录:
        受控目录 = Path(临时目录)
        (受控目录 / "故障夹具授权").write_text(授权令牌, encoding="utf-8")
        命令文本 = ("import sys; sys.path.insert(0, sys.argv[1]); "
                "from 测试验证.准入判据.故障取证样本.进程行为 import 执行故障样本; "
                "执行故障样本(*sys.argv[2:], 触发方式='自动')")
        yield {"程序": sys.executable, "参数": ["-I", "-B", "-c", 命令文本,
               str(Path(__file__).resolve().parents[3]), 故障模式, 授权令牌, str(受控目录)],
               "工作目录": str(受控目录), "环境": {覆盖变量名: str(运行数据根)},
               "令牌": 授权令牌, "模式": 故障模式, "预算": dict(批准夹具预算),
               "关闭责任": "调用者的真实监督执行，退出上下文前确认组内进程退出"}


def 跑故障探针(故障模式, 源码身份, 配置预算):
    if 故障模式 not in 故障模式表 or 配置预算 != 批准夹具预算:
        raise ValueError("只接受批准的模式和200/500毫秒、每路64KiB预算")
    if os.name != "posix":
        raise ValueError("此夹具只覆盖POSIX进程组；Windows未覆盖")
    仓根 = Path(__file__).resolve().parents[3]
    必须源件 = {str(源件.relative_to(仓根)) for 源件 in Path(__file__).parent.glob("*.py")}
    if not 必须源件.issubset(源码身份["源码指纹"]):
        raise ValueError("不能用缺少夹具源码的身份制造运行证据")
    运行数据根 = 解析当前环境().resolve()
    临时目录根 = 子目录路径(运行数据根, "临时件") / "故障夹具"
    日志目录根 = 子目录路径(运行数据根, "日志") / "故障夹具"
    for 分类根 in (临时目录根, 日志目录根):
        分类根.mkdir(mode=0o700, parents=True, exist_ok=True)
    授权令牌 = uuid.uuid4().hex
    日志目录 = 日志目录根 / 授权令牌
    日志目录.mkdir(mode=0o700)
    描述符前数 = 读描述符数()
    输出读数 = {通道名称: {"保留内容": bytearray(), "读取字节": 0, "丢弃字节": 0}
            for 通道名称 in ("stdout", "stderr")}
    子进程 = None
    触发时刻 = None
    停止原因 = "未启动"
    截止时仍活 = False
    回收读数 = {"确认退出": False}
    管道前数 = 0
    管道后数 = 0
    异常说明 = None
    起始时刻 = time.monotonic()
    执行截止 = 起始时刻 + 配置预算["执行窗口毫秒"] / 1000
    with tempfile.TemporaryDirectory(prefix=授权令牌 + "-", dir=临时目录根) as 临时目录:
        受控目录 = Path(临时目录)
        (受控目录 / "故障夹具授权").write_text(授权令牌, encoding="utf-8")
        仓根 = Path(__file__).resolve().parents[3]
        命令文本 = ("import sys; sys.path.insert(0, sys.argv[1]); "
                "from 测试验证.准入判据.故障取证样本.进程行为 import 执行故障样本; "
                "执行故障样本(*sys.argv[2:])")
        命令参数 = [sys.executable, "-I", "-B", "-c", 命令文本,
                str(仓根), 故障模式, 授权令牌, str(受控目录)]
        with selectors.DefaultSelector() as 选择器:
            try:
                子进程 = subprocess.Popen(
                    命令参数, cwd=受控目录, env={覆盖变量名: str(运行数据根)},
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    start_new_session=True, bufsize=0)
                管道前数 = sum(not 管道句柄.closed for 管道句柄 in
                           (子进程.stdin, 子进程.stdout, 子进程.stderr))
                for 通道名称 in ("stdout", "stderr"):
                    管道句柄 = getattr(子进程, 通道名称)
                    os.set_blocking(管道句柄.fileno(), False)
                    选择器.register(管道句柄, selectors.EVENT_READ, 通道名称)
                while time.monotonic() < 执行截止:
                    排空输出(选择器, 输出读数, 配置预算["每路保留字节"],
                         min(0.005, 执行截止 - time.monotonic()))
                    阶段表 = 读阶段标记(输出读数, 授权令牌, 子进程.pid, 故障模式)
                    if "就绪" in 阶段表 and 触发时刻 is None:
                        子进程.stdin.write((授权令牌 + "\n").encode("ascii"))
                        子进程.stdin.close()
                        触发时刻 = time.monotonic()
                    if any(通道读数["丢弃字节"] for 通道读数 in 输出读数.values()):
                        停止原因 = "输出超限"
                        break
                    if 子进程.poll() is not None:
                        停止原因 = "进程退出"
                        break
                else:
                    停止原因 = "执行截止"
                    截止时仍活 = 子进程.poll() is None
            except Exception as 异常对象:
                停止原因 = "探针错误"
                异常说明 = repr(异常对象)
            finally:
                停止时刻 = time.monotonic()
                if 子进程 is not None:
                    try:
                        回收读数 = 回收样本(子进程, 选择器, 输出读数,
                                      配置预算["回收毫秒"], 配置预算["每路保留字节"])
                    finally:
                        for 管道句柄 in (子进程.stdin, 子进程.stdout, 子进程.stderr):
                            管道句柄.close()
                        管道后数 = sum(not 管道句柄.closed for 管道句柄 in
                                   (子进程.stdin, 子进程.stdout, 子进程.stderr))
        观测值 = {"模式": 故障模式, "令牌": 授权令牌, "命令参数": 命令参数,
                "进程号": 子进程.pid if 子进程 else None,
                "退出状态": 子进程.returncode if 子进程 else None,
                "阶段": 读阶段标记(输出读数, 授权令牌, 子进程.pid, 故障模式) if 子进程 else [],
                "停止原因": 停止原因, "截止时仍活": 截止时仍活,
                "执行耗时毫秒": (停止时刻 - 起始时刻) * 1000,
                "触发偏移毫秒": (触发时刻 - 起始时刻) * 1000 if 触发时刻 else None,
                "执行截止单调秒": 执行截止, "回收": 回收读数, "异常": 异常说明}
    观测值["输出"] = {}
    for 通道名称, 通道读数 in 输出读数.items():
        原始路径 = 日志目录 / (通道名称 + ".bin")
        原始路径.write_bytes(通道读数["保留内容"])
        观测值["输出"][通道名称] = {
            "读取字节": 通道读数["读取字节"], "丢弃字节": 通道读数["丢弃字节"],
            "保留字节": len(通道读数["保留内容"]), "内容指纹": 文件指纹(原始路径),
            "原始路径": str(原始路径)}
    观测值["总耗时毫秒"] = (time.monotonic() - 起始时刻) * 1000
    描述符后数 = 读描述符数()
    os.kill(os.getpid(), 0)
    观测值["资源"] = {"观察器进程号": os.getpid(), "观察器仍活": True,
                   "描述符前数": 描述符前数, "描述符后数": 描述符后数,
                   "受控子进程前数": 0, "受控子进程后数": int(not 回收读数["确认退出"]),
                   "管道前数": 管道前数, "管道后数": 管道后数,
                   "临时目录残留": 受控目录.exists(), "缓存": "夹具不创建缓存，生产缓存未测"}
    源码未漂移 = all(文件指纹(仓根 / 路径名) == 指纹值
               for 路径名, 指纹值 in 源码身份["源码指纹"].items())
    符合期望 = (判样本观测(故障模式, 授权令牌, 观测值)
            and 回收读数["确认退出"] and 回收读数["管道已排空"]
            and 回收读数["耗时毫秒"] <= 配置预算["回收毫秒"]
            and (观测值["执行耗时毫秒"] + 回收读数["耗时毫秒"]
                 <= 配置预算["执行窗口毫秒"] + 配置预算["回收毫秒"])
            and 观测值["总耗时毫秒"] < 配置预算["单例硬顶毫秒"]
            and 描述符前数 is not None and 描述符前数 == 描述符后数
            and 管道前数 == 3 and 管道后数 == 0
            and not 受控目录.exists() and 源码未漂移 and 异常说明 is None)
    证据值 = {"案例名": "故障夹具/" + 故障模式, "结果": "通过" if 符合期望 else "失败",
            "符合期望": 符合期望, "证据范围": "样本进程行为/非生产宿主",
            "源码身份": 源码身份, "配置预算": 配置预算, "源码未漂移": 源码未漂移,
            "实际": 观测值, "生产宿主": "未执行", "健康域继续调用": "未执行",
            "原生库初始化": "不覆盖", "生产IPC": "不覆盖（缺生产入口）",
            "权限沙箱": "不覆盖", "证据路径": str(日志目录 / "证据.json")}
    Path(证据值["证据路径"]).write_text(json.dumps(证据值, ensure_ascii=False, indent=2), encoding="utf-8")
    return 证据值
