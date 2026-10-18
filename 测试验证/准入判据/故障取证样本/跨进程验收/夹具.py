"""跨进程执行路验收 · 夹具 —— 起真网关子进程 · 发调用 · 读槽 · 造部署配置。

★ 本件是**验收装置**，不是平台实现：它只经生产接口（HTTP `POST /接口/调用`）驱动，
不调内部函数、不复制协议。

读数口径（与 W07 同族）：每条必证给「预期 / 实际 / 退出码」；给不出底层语义的
如实标**阻断**，不因几条通过就宣布整个发布验收完成。

落盘：测试产物一律落**运行数据根**（判据 ⑳/㉕），不落源码树。
"""

import concurrent.futures
import os
import signal
import base64
import json
import tempfile
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

仓根 = Path(__file__).resolve().parents[4]  # 本件比同级样本深一层（多一个「跨进程验收/」）
sys.path.insert(0, str(仓根))

from 开发工具.运行数据根 import 子目录路径, 解析当前环境  # noqa: E402

# 验收靶子：编译器支持库 1101 词法分析（入参 类型标签 4 文本 · 返回 类型标签 5 字节集）。
靶子编号 = 1101
靶子入参标签 = 4
靶子返回标签 = 5
# 承载它的扩展名（**只住本夹具**，不进底座代码；装配侧从配置文件读它）。
靶子扩展名 = "编译器支持库"

# 「引用槽标签 4 出方向」那条必证的靶子：编译器支持库 1108 回显文本
# （入参 类型标签 4 文本 · 返回 类型标签 4 文本）。生产口原先只覆盖「文本作入参 + 字节集作返回」，
# **没有任何能力返回文本** ⇒ 本号让那条出方向有一条真读数（债务 307④）。
回显编号 = 1108
回显入参标签 = 4
回显返回标签 = 4

# 「同网关双域」那一项（`必证五` 用）的两个号与第二个域：
#   慢域 = 靶子扩展本身（1106 编译：一步到底，内部真跑 1101 → 1102 → 1103，最重的那件）；
#   健康域 = 数值计算支持库 1324 四舍五入（纯算术，最快的那类）—— 两域各自一个工作进程。
慢域编号 = 1106
健康域扩展名 = "数值计算支持库"
健康域编号 = 1324

# 「资源生产调用面」那一组（`必证七` 用）：一个资源号 + 三个操作号。
# 三条语义各占一个操作号：零输出 / 多输出拒绝 / 绑到未载入能力（失败清空）。
# 资源号与能力号是**两个号空间**（`契约声明/号段图.json`）—— 这里的资源靶子号
# 只是一个资源号，不等于任何能力号。
资源靶子号 = 7777
资源零输出操作号 = 1
资源多输出操作号 = 2
资源失败操作号 = 3

# 超时一律 ≤ 五秒硬顶（判据 ㊲ / 决策记录 2026-09-27_所有运行五秒硬顶.md）。
# 启动不是调用：它要等网关真起监听，故给到硬顶；单次调用只等一条回帧，给一半。
启动超时秒 = 5.0
单次调用超时秒 = 2.5


def 取空闲端口() -> int:
    """要一个空闲端口（不绑定、马上放掉 —— 起监听归网关）。"""
    套接字 = socket.socket()
    套接字.bind(("127.0.0.1", 0))
    监听端口 = 套接字.getsockname()[1]
    套接字.close()
    return 监听端口


def 取工作目录(新建标志: bool = False) -> Path:
    """每次运行新建独立目录，保留前次取证材料。"""
    if 新建标志:
        取工作目录.工作目录 = Path(tempfile.mkdtemp(
            prefix="跨进程验收-", dir=子目录路径(解析当前环境(), "临时件")
        ))
    return 取工作目录.工作目录


def 造跨进程条目(扩展名: str, 启动程序: str, 启动参数=None):
    """造**一条**跨进程条目（键名与形状**逐字照网关侧的读口** `跨进程装配.rs::读部署配置`）。

    标识串与版本都从扩展自身目录现读 —— **不写死**（改了扩展就得跟着变）。
    """
    扩展目录 = 仓根 / "扩展根目录" / "原子支持库" / 扩展名
    包声明 = json.loads((扩展目录 / "包声明.json").read_text(encoding="utf-8"))
    构建制品 = 扩展目录 / (扩展名 + ".支持库制品")
    # 包声明用短键（主 / 次 / 构建），部署配置用长键（主版本 / 次版本号 / 构建）：
    # 两个形状都是各自的本体，不改任何一侧，在这里翻译。
    声明版本 = 包声明["实现版本"]
    return {
        "标识串": 包声明["标识串"],
        "版本": {
            "主版本": 声明版本["主"],
            "次版本号": 声明版本["次"],
            "构建": 声明版本["构建"],
        },
        "制品路径": str(构建制品),
        "启动程序": str(启动程序),
        "启动参数": (
            [str(参数项) for 参数项 in 启动参数]
            if 启动参数 is not None
            else [str(构建制品), str(仓根 / "构建环境" / "构建缓存")]
        ),
    }


def 造部署配置(工作目录: Path, 启动程序: str, 启动参数=None, 扩展名: str = 靶子扩展名, 附加扩展名表=()):
    """造一份**部署配置**：已校验的扩展身份 + 实现版本 + 实际制品 + 工作进程启动参数。

    形状：`{ "跨进程": [ <条目>, … ] }`（条目见 [`造跨进程条目`]）。

    `启动参数` 默认 = `[制品, 缓存根]`：这是**工作进程自身的用法**（它要被告知加载哪份真制品、
    临时解包往哪放）。制品路径同时也写在 `制品路径` 键里 —— 两个地方同源同值：一个是
    「装配侧校验的那一份」，一个是「运行期真加载的那一份」，传一样才不会校验过了却加载别份。

    `附加扩展名表` 非空 ⇒ 一次登记**多个执行域**（每名一个域、各自一个工作进程）：
    `必证五` 的「同网关双域」靠它 —— 慢域与健康域各自独立，才判得了「一个慢域阻塞不了健康域」。
    """
    配置 = {
        "跨进程": [
            造跨进程条目(域扩展名, 启动程序, 启动参数)
            for 域扩展名 in (扩展名,) + tuple(附加扩展名表)
        ]
    }
    配置文件 = 工作目录 / "跨进程部署.json"
    配置文件.write_text(json.dumps(配置, ensure_ascii=False, indent=2), encoding="utf-8")
    return 配置文件


def 起网关(工作目录: Path, 监听端口: int, 跨进程配置=None, 额外参数=()):
    """起一个**真网关子进程**（生产装配入口 `examples/启动网关`）。

    返回 `(子进程, 端口)`；调用方负责 `停网关`。
    """
    命令 = [
        str(仓根 / "构建环境" / "构建缓存" / "debug" / "examples" / "启动网关"),
        "--端口",
        str(监听端口),
        "--工具根",
        str(仓根),
    ]
    if 跨进程配置 is not None:
        命令 += ["--跨进程配置", str(跨进程配置)]
    命令 += [str(参数项) for 参数项 in 额外参数]
    日志文件 = 工作目录 / f"网关-{监听端口}.log"
    日志句柄 = 日志文件.open("w", encoding="utf-8")
    进程 = subprocess.Popen(
        命令, cwd=str(仓根), stdout=日志句柄, stderr=subprocess.STDOUT, text=True
    )
    日志句柄.close()
    进程.日志文件 = 日志文件
    # 等它真的起监听（轮询自描述根）。
    截止 = time.monotonic() + 启动超时秒
    while time.monotonic() < 截止:
        if 进程.poll() is not None:
            输出 = 进程.日志文件.read_text(encoding="utf-8")
            raise RuntimeError(f"网关启动即退出（码 {进程.returncode}）：\n{输出}")
        try:
            # 路径里的中文必须先百分号编码（`http.client` 只发 ASCII 请求行）。
            探活地址 = "http://127.0.0.1:%d/%s" % (监听端口, urllib.parse.quote("接口"))
            回应 = urllib.request.urlopen(探活地址, timeout=1.0)
            if 回应.status == 200:
                return 进程, 监听端口
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.15)
    停网关(进程)
    raise RuntimeError(f"网关在 {启动超时秒} 秒内未起监听（端口 {监听端口}）")


def 停网关(进程):
    """停本次网关并从独立日志件读出完整输出。"""
    if 进程 is None:
        return ""
    if 进程.poll() is None:
        进程.terminate()
        try:
            进程.wait(timeout=5)
        except subprocess.TimeoutExpired:
            进程.kill()
            进程.wait(timeout=5)
    输出 = 进程.日志文件.read_text(encoding="utf-8")
    return 输出


def 造文本位(值: str):
    """造一个**文本**参位（JSON 字符串）。"""
    return {"类型标签": 靶子入参标签, "值": 值}


def 造字节集位(字节: bytes):
    """造一个**字节集**参位（base64 字符串）。"""
    return {"类型标签": 5, "值": base64.b64encode(字节).decode("ascii")}


def 造浮点位(值: float):
    """造一个**浮点**参位（类型标签 2）—— 数值计算支持库那类入参。"""
    return {"类型标签": 2, "值": 值}


def 造整数位(值: int):
    """造一个**整数**参位（类型标签 1）—— 数值计算支持库那类入参。"""
    return {"类型标签": 1, "值": 值}


def 发调用(监听端口: int, 编号: int, 参位表, 超时秒: float = 单次调用超时秒):
    """发一次生产调用，返回 `(HTTP 码, 响应体字典或 None, 原始文本)`。

    ★ 走的就是生产入口：`POST /接口/调用`。不调任何内部函数。
    """
    进程体 = json.dumps({"编号": 编号, "值": list(参位表)}, ensure_ascii=False).encode("utf-8")
    请求 = urllib.request.Request(
        "http://127.0.0.1:%d/%s" % (监听端口, urllib.parse.quote("接口/调用")),
        data=进程体,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(请求, timeout=超时秒) as 回应:
            原始 = 回应.read().decode("utf-8")
            try:
                return 回应.status, json.loads(原始), 原始
            except json.JSONDecodeError:
                return 回应.status, None, 原始
    except urllib.error.HTTPError as 错误:
        原始 = 错误.read().decode("utf-8")
        try:
            return 错误.code, json.loads(原始), 原始
        except json.JSONDecodeError:
            return 错误.code, None, 原始
    except (urllib.error.URLError, OSError) as 错误:
        return 0, None, "连接被对端打断：%s" % 错误


def 造资源声明根(工作目录: Path, 能力号: int, 未载入号: int) -> Path:
    """造一份**资源声明根**（部署侧 JSON）：资源声明表 + 资源绑定表。

    三条操作各证一条资源语义（`必证七` 用）：
      ① 零输出操作号 —— `输出类型` 空表，绑到真能力（成功且 `值` 是空数组）；
      ② 多输出操作号 —— `输出类型` 两位，单槽协议载不动（明确拒，码 28）；
      ③ 失败操作号 —— 绑到**未载入**能力号（转调失败 ⇒ 失败清空）。

    键名与形状**逐字照装配侧读口**（`对外接口面/调用接口面/src/执行装配/资源装配.rs::读资源声明根`）：
    本夹具不猜第三种写法。
    """
    声明 = {
        "资源声明": [
            {
                "资源号": 资源靶子号,
                "标识": "验收资源靶子",
                "扩展种类": "不透明外部程序",
                "载体": "本机进程",
                "崩溃影响面": "仅本资源",
                "可重建": True,
                "留痕": False,
                "允许": {"读文件": False, "写文件": False, "联网": False, "派生进程": False},
                "操作": [
                    {
                        "操作号": 资源零输出操作号,
                        "名字": "零输出",
                        "输入类型": [靶子入参标签],
                        "输出类型": [],
                        "超时毫秒": 2000,
                        "需要副作用": [],
                    },
                    {
                        "操作号": 资源多输出操作号,
                        "名字": "多输出",
                        "输入类型": [靶子入参标签],
                        "输出类型": [靶子返回标签, 靶子返回标签],
                        "超时毫秒": 2000,
                        "需要副作用": [],
                    },
                    {
                        "操作号": 资源失败操作号,
                        "名字": "绑未载入",
                        "输入类型": [靶子入参标签],
                        "输出类型": [靶子返回标签],
                        "超时毫秒": 2000,
                        "需要副作用": [],
                    },
                ],
            }
        ],
        "资源绑定": [
            {
                "资源号": 资源靶子号,
                "操作到能力": [
                    {"操作号": 资源零输出操作号, "能力号": 能力号},
                    {"操作号": 资源多输出操作号, "能力号": 能力号},
                    {"操作号": 资源失败操作号, "能力号": 未载入号},
                ],
            }
        ],
    }
    资源声明根件 = 工作目录 / "资源声明根.json"
    资源声明根件.write_text(json.dumps(声明, ensure_ascii=False, indent=2), encoding="utf-8")
    return 资源声明根件


def 发资源调用(监听端口: int, 资源号: int, 操作号: int, 参位表, 超时秒: float = 单次调用超时秒):
    """发一次**资源**生产调用，返回 `(HTTP 码, 响应体字典或 None, 原始文本)`。

    ★ 走的就是资源生产入口：`POST /接口/资源调用`（资源号与能力号是两个号空间，
    不搭 `/接口/调用` 那条腿）。不调任何内部函数。
    """
    体文本 = json.dumps(
        {"资源号": 资源号, "操作号": 操作号, "输入槽表": list(参位表)},
        ensure_ascii=False,
    ).encode("utf-8")
    请求 = urllib.request.Request(
        "http://127.0.0.1:%d/%s" % (监听端口, urllib.parse.quote("接口/资源调用")),
        data=体文本,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(请求, timeout=超时秒) as 回应:
            原始 = 回应.read().decode("utf-8")
            try:
                return 回应.status, json.loads(原始), 原始
            except json.JSONDecodeError:
                return 回应.status, None, 原始
    except urllib.error.HTTPError as 错误:
        原始 = 错误.read().decode("utf-8")
        try:
            return 错误.code, json.loads(原始), 原始
        except json.JSONDecodeError:
            return 错误.code, None, 原始
    except (urllib.error.URLError, OSError) as 错误:
        return 0, None, "连接被对端打断：%s" % 错误


def 取返回表(响应体):
    """从响应体里取调用结果。

    成功 ⇒ `(参位表, "")`；失败 ⇒ `(None, 说明文本)`。
    """
    if not isinstance(响应体, dict):
        return None, "响应体不是对象"
    if 响应体.get("成功") is not True:
        return None, f"业务失败：{json.dumps(响应体, ensure_ascii=False)}"
    for 键名 in ("值",):
        候选值 = 响应体.get(键名)
        if isinstance(候选值, list):
            return 候选值, ""
    return None, f"响应里找不到返回槽：{json.dumps(响应体, ensure_ascii=False)[:300]}"


def 解字节集(槽项) -> bytes:
    """把返回项里的字节集解回来（base64 ⇒ bytes）。"""
    return base64.b64decode(槽项["值"])


def 取元素表(槽项):
    """把返回槽读成**复合类型的元素表**（不是元素表就给 None）。

    形状由生产侧 `槽编码.rs::元素表到协议值` 定：列表型（100）出数组，
    字典 / JSON值 / 结果结构（101–103）出「名称 → 值项」对象，每项自带 `类型标签`。
    解不出载荷时生产侧落**引用形状**（带 `引用` 标志的整数槽）⇒ 那种形状不是元素表。
    """
    if not isinstance(槽项, dict) or 槽项.get("引用") is True:
        return None
    待处理值 = 槽项.get("值")
    return 待处理值 if isinstance(待处理值, (dict, list)) else None


def 判失败码(响应体):
    """从响应体里取错误码（没有给 None）。

    形状照生产的失败应答（`网关.rs::组装应答` → `错误对象`）：
      { "成功": false, "错误": { "码": 34, "段位": 0, … } }
    **只读这一个形状**：本夹具不猜第三种写法。
    """
    if not isinstance(响应体, dict):
        return None
    错误对象 = 响应体.get("错误")
    if isinstance(错误对象, dict):
        return 错误对象.get("码")
    return 响应体.get("码")


def 取所属进程(网关进程):
    """只认本次网关的直接子进程，并记录真实用户、父进程与命令。"""
    输出 = subprocess.run(
        ["ps", "-axo", "pid=,ppid=,user=,command="],
        capture_output=True, text=True, timeout=2, check=True,
    ).stdout
    工作进程路径 = str(仓根 / "构建环境/构建缓存/debug/examples/工作进程")
    return [行文本.strip() for 行文本 in 输出.splitlines()
            if len(行文本.split(None, 3)) == 4
            and 行文本.split(None, 3)[1] == str(网关进程.pid)
            and 行文本.split(None, 3)[3].startswith(工作进程路径 + " ")]


def 杀所属进程(网关进程):
    """逐个复核所有者后只杀本次验收的子进程。"""
    进程行表 = 取所属进程(网关进程)
    for 行文本 in 进程行表:
        os.kill(int(行文本.split()[0]), signal.SIGKILL)
    return 进程行表


def 取资源读数(网关端口: int, 超时秒: float = 单次调用超时秒):
    """读 `GET /接口/资源读数`（生产读数口），返回 `数据` 字典；读不到给 None。

    ★ 走的就是生产入口，不调任何内部函数。
    """
    读数地址 = "http://127.0.0.1:%d/%s" % (网关端口, urllib.parse.quote("接口/资源读数"))
    try:
        with urllib.request.urlopen(读数地址, timeout=超时秒) as 应答:
            return json.loads(应答.read().decode("utf-8")).get("数据")
    except Exception:
        return None


def 取存活分配计数(网关端口: int, 超时秒: float = 单次调用超时秒):
    """读「跨分配器存活分配计数」—— 发布验收 必证三 要的就是这个数（读不到给 None）。

    它是**生产进程**的数：生产二进制 `examples/启动网关.rs` 挂了计数分配器
    （包一层 `System` 只加两个计数），`v1_gateway::分配读数` 提供读法。
    """
    读数载荷 = 取资源读数(网关端口, 超时秒)
    if not isinstance(读数载荷, dict):
        return None
    分配面 = 读数载荷.get("分配")
    return 分配面.get("存活分配计数") if isinstance(分配面, dict) else None


def 取资源快照(网关进程, 名称):
    """留存进程所有者与文件描述符证据，不把调用成功当内存回收证明。"""
    进程行表 = 取所属进程(网关进程)
    进程号表 = [str(网关进程.pid)] + [行文本.split()[0] for 行文本 in 进程行表]
    输出 = subprocess.run(
        ["lsof", "-nP", "-p", ",".join(进程号表)],
        capture_output=True, text=True, errors="replace", timeout=2,
    )
    (取工作目录() / f"资源-{名称}.log").write_text(
        "\n".join(进程行表) + "\n" + 输出.stdout + 输出.stderr, encoding="utf-8"
    )
    return 进程行表, 输出.returncode, len(输出.stdout.splitlines())


def 验并发调用(监听端口):
    """同一网关32次并发，每次以返回原文字节判本请求的结果。"""
    def 发并发样本(序次):
        源文本 = f"concurrent {序次}"
        HTTP码, 应答体, 原文 = 发调用(监听端口, 靶子编号, [造文本位(源文本)])
        槽表, 说明文本 = 取返回表(应答体)
        字节串 = 解字节集(槽表[0]) if 槽表 else b""
        return (序次, HTTP码, 判失败码(应答体),
                bool(槽表) and 字节串[4:4 + len(源文本)] == 源文本.encode(), 说明文本)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as 并发池:
        并发读数 = list(并发池.map(发并发样本, range(32)))
    (取工作目录() / "同域并发.json").write_text(
        json.dumps(并发读数, ensure_ascii=False), encoding="utf-8"
    )
    return sum(1 for 读数行 in 并发读数 if 读数行[3])


def 查残留进程(清理进程号表):
    """只核停止前已归属本次网关的PID，不以同名进程推定回收。"""
    输出 = subprocess.run(["ps", "-axo", "pid=,ppid=,user=,command="],
                          capture_output=True, text=True, timeout=2).stdout
    残留进程号表 = [行文本 for 行文本 in 输出.splitlines()
                     if 行文本.split() and 行文本.split()[0] in 清理进程号表]
    (取工作目录() / "退出后进程.log").write_text("\n".join(残留进程号表), encoding="utf-8")
    return 残留进程号表
