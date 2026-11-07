"""上线实例 —— 起 · 停 · 健康检查（起没起来看健康，不看进程在不在）。"""

import json
import ctypes
import sys
import shutil
import tempfile
import uuid
import os
import re
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .落点环境常量 import 仓根, 停等秒, 运行根, 健康超时秒
from .指针 import 读指针, 写指针
from .上线制品 import 制品目录
from .输出 import 打印文本
from 运行数据根 import 解析当前环境
from 运行数据根.口径 import 覆盖变量名
from 构建装配.上线切换.准备执行映像 import 准备执行映像
from 构建装配.门禁.硬顶常量 import 失控护栏毫秒


候选启动预检预算毫秒 = 失控护栏毫秒


def 进程活着(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    # 僵死进程已退出，文件描述符与写锁已释放；不误当成仍持写权。
    进程状态 = subprocess.run(["ps", "-p", str(pid), "-o", "stat="], capture_output=True, text=True, timeout=2)
    return 进程状态.returncode != 0 or not 进程状态.stdout.strip().startswith("Z")


def 读进程执行路径(pid: int) -> str:
    if sys.platform == "darwin":
        路径缓冲 = ctypes.create_string_buffer(4096)
        if ctypes.CDLL("/usr/lib/libproc.dylib").proc_pidpath(pid, 路径缓冲, len(路径缓冲)) <= 0:
            raise SystemExit("无法确认实例执行路径，拒绝发信号")
        return os.fsdecode(路径缓冲.value)
    return os.readlink("/proc/{}/exe".format(pid))


def 读进程指纹(pid: int) -> str:
    进程读数 = subprocess.run(["ps", "-p", str(pid), "-o", "lstart="], capture_output=True, text=True, timeout=2)
    if 进程读数.returncode:
        if not 进程活着(pid):
            return ""
        raise SystemExit("无法确认实例进程指纹，拒绝发信号")
    return 进程读数.stdout.strip() + " " + 读进程执行路径(pid)


def 核对实例归属(实例台账: dict) -> None:
    pid = int(实例台账.get("pid") or 0)
    当前指纹 = 读进程指纹(pid)
    if not 当前指纹:
        return
    归属指纹 = 实例台账.get("进程指纹")
    if 归属指纹 and 当前指纹 != 归属指纹:
        raise SystemExit("pid {} 归属指纹不符，拒绝发信号".format(pid))
    可执行路径 = 实例台账.get("可执行路径") or str(Path(实例台账.get("制品落点") or "") / "网关")
    指纹分段 = 当前指纹.split(None, 5)
    if len(指纹分段) != 6 or Path(指纹分段[5]).resolve() != Path(可执行路径).resolve():
        raise SystemExit("pid {} 可执行路径不符，拒绝发信号".format(pid))
    # 旧台账没有启动指纹时，按原 pid + 精确制品执行路径迁移核对，绝不按端口杀。


def 等实例退出(pid: int) -> bool:
    截止 = time.monotonic() + 停等秒
    while 进程活着(pid):
        if time.monotonic() >= 截止:
            return False
        time.sleep(0.02)
    return True


def 清候选运行根(实例台账: dict) -> None:
    if not 实例台账.get("自建运行根"):
        return
    候选根 = Path(实例台账.get("运行数据根") or "")
    候选父根 = 运行根 / "候选运行根"
    if 候选根.is_symlink() or 候选根.parent.resolve() != 候选父根.resolve():
        raise SystemExit("候选运行根归属越界，保留现场")
    if not 候选根.exists():
        return
    归属凭据 = 实例台账.get("归属凭据")
    if not 归属凭据 or json.loads((候选根 / "所有权.json").read_text(encoding="utf-8")).get("归属凭据") != 归属凭据:
        raise SystemExit("候选运行根凭据不符，保留现场")
    shutil.rmtree(候选根)


def 准备实例映像(标识: str) -> dict:
    """发布准备使用目标制品；与正式启动共用同一内容寻址缓存。"""
    return 准备执行映像(
        仓根, 运行根 / "执行映像", 运行根 / "日志" / "{}-映像准备.log".format(标识),
        制品根目录=制品目录(标识),
        预算毫秒=候选启动预检预算毫秒,
    )


def 起实例(标识: str, 监听端口: int) -> dict:
    """起一份制品的网关实例。`端口=0` ⇒ 由 OS 分配（装载预检用，流量不动）。"""
    制品落点目录 = 制品目录(标识)
    日志 = 运行根 / "日志" / "{}-{}.log".format(标识, 监听端口 or "随机")
    启动环境 = os.environ.copy()
    自建运行根 = 监听端口 == 0
    归属凭据 = uuid.uuid4().hex
    if 自建运行根:
        候选父根 = 运行根 / "候选运行根"
        候选父根.mkdir(parents=True, exist_ok=True)
        实例运行根 = Path(tempfile.mkdtemp(prefix="候选-", dir=str(候选父根)))
        (实例运行根 / "所有权.json").write_text(json.dumps({"归属凭据": 归属凭据}), encoding="utf-8")
    else:
        实例运行根 = 解析当前环境()
    启动环境[覆盖变量名] = str(实例运行根)
    输出流 = 日志.open("w", encoding="utf-8")
    # cwd 必须是**制品目录**：制品内 `扩展根声明.json` 的 `路径基准` 就是「工作目录」，
    # `种类[].扩展落点` 指的是制品内的 `扩展/`（`上线切换/形状.md` §三）。扩展这条路靠 cwd 走。
    # 但**静态件与案例库住在仓根**（`接口面形状.md` §五 静态托管根 = `前端呈现/网页应用`；
    # §七 工具族案例根 = `测试验证/测试案例`），两者默认都相对进程工作目录解 —— 与 cwd 口径冲突。
    # 故按仓根**注入**这两个部署事实（`启动网关 --静态根 / --工具根`），不互相借 cwd。
    # 实测（2026-09-27）：只给 `cwd=制品目录` ⇒ `GET /` 全 404、`GET /接口/案例` 恒 9002。
    try:
        进程 = subprocess.Popen(
            [
                str(制品落点目录 / "网关"),
                "--声明根", "扩展根声明.json",
                "--端口", str(监听端口),
                "--缓存根", str(运行根 / "执行映像"),
                "--静态根", str(仓根 / "前端呈现" / "网页应用"),
                "--工具根", str(仓根),
                # ★ 后缀表（候选资格的唯一权威）：制品目录里**没有** `扩展装载/`（制品不自含部署
                #   事实，见 `上线切换/形状.md`）⇒ 与 `--静态根` / `--工具根` 同口径按仓根注入。
                #   此前漏这一项 ⇒ 启动入口按 cwd（= 制品目录）读不到 ⇒ 装载 / 切换 / 回退一律
                #   `Error: 读不到后缀表`（实测退出码 1，三个命令全废）。
                "--后缀表", str(仓根 / "扩展装载" / "后缀表.json"),
            ],
            cwd=str(制品落点目录),
            env=启动环境,
            stdout=输出流,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,  # 脱离本进程组：起完就走，实例活到被显式停掉
        )
    except BaseException:
        输出流.close()
        清候选运行根({"自建运行根": 自建运行根, "运行数据根": str(实例运行根), "归属凭据": 归属凭据})
        raise
    try:
        实例台账 = {"制品标识": 标识, "pid": 进程.pid, "端口": 监听端口, "日志": str(日志), "制品落点": str(制品落点目录),
                  "可执行路径": str(制品落点目录 / "网关"),
                  "运行数据根": str(实例运行根), "自建运行根": 自建运行根, "归属凭据": 归属凭据}
        if 自建运行根:
            (实例运行根 / "所有权.json").write_text(json.dumps(实例台账), encoding="utf-8")
        实例台账["进程指纹"] = 读进程指纹(进程.pid)
        if 自建运行根:
            (实例运行根 / "所有权.json").write_text(json.dumps(实例台账), encoding="utf-8")
        # 先登记所有权再等启动；失败且退场未确认时保留根与台账，不自动删活资源。
        写指针("已装载/{}".format(标识), 实例台账)
    except BaseException:
        进程.kill()
        try:
            进程.wait(timeout=停等秒)
        except subprocess.TimeoutExpired:
            raise SystemExit("新实例 pid {} 登记失败且退出未确认；保留候选根 {}".format(进程.pid, 实例运行根))
        finally:
            输出流.close()
        清候选运行根({"自建运行根": 自建运行根, "运行数据根": str(实例运行根), "归属凭据": 归属凭据})
        raise
    try:
        实际 = 等端口(日志, 进程)
        if 实际 is None:
            停实例(实例台账)
            raise SystemExit("实例没起来（日志 {}）：\n{}".format(日志, 日志.read_text(encoding="utf-8")))
        实例台账["端口"] = 实际
        写指针("已装载/{}".format(标识), 实例台账)
        return 实例台账
    finally:
        输出流.close()


def 等端口(日志: Path, 进程) -> int:
    """等启动入口打出 `监听 127.0.0.1:<端口>` 那一行（约定见 制品清单.启动入口读数约定）。"""
    截止 = time.time() + 健康超时秒
    while time.time() < 截止:
        if 日志.is_file():
            匹配结果 = re.search(r"监听 127\.0\.0\.1:(\d+)", 日志.read_text(encoding="utf-8", errors="replace"))
            if 匹配结果:
                return int(匹配结果.group(1))
        if 进程.poll() is not None:
            return None
        time.sleep(0.05)
    return None


def 停实例(实例台账: dict) -> str:
    pid = int(实例台账.get("pid") or 0)
    if not pid or not 进程活着(pid):
        清候选运行根(实例台账)
        return "pid {} 已不在".format(pid or "?")
    核对实例归属(实例台账)
    try:
        os.kill(pid, signal.SIGTERM)
        if not 等实例退出(pid):
            核对实例归属(实例台账)
            os.kill(pid, signal.SIGKILL)
            if not 等实例退出(pid):
                raise SystemExit("pid {} 退出未确认，拒绝接管；保留运行根与台账".format(pid))
    except ProcessLookupError:
        if 进程活着(pid):
            raise SystemExit("pid {} 退出未确认，拒绝接管".format(pid))
    except OSError as 错误:
        raise SystemExit("pid {} 停止失败，拒绝接管：{}".format(pid, 错误)) from 错误
    清候选运行根(实例台账)
    return "pid {} 已确认退出".format(pid)


def 取健康读数(监听端口: int) -> tuple:
    """`GET /接口` → (HTTP 状态, 读数)。这是接口可达判据，不证明图任务持久存储可用。

    **实测**：路径必须**百分号编码**。端点名是中文，而 Python 标准库的 `http.client`
    按 ASCII 编请求行 ⇒ 不编码当场 `UnicodeEncodeError`（实测撞到）。网关侧认百分号编码
    （`端点路由.rs`），故两边口径一致。
    """
    路径 = urllib.parse.quote("/接口")
    try:
        with urllib.request.urlopen("http://127.0.0.1:{}{}".format(监听端口, 路径), timeout=健康超时秒) as 造应答:
            源文本 = 造应答.read().decode("utf-8")
            状态码 = 造应答.status
    except (urllib.error.URLError, socket.timeout, ConnectionError) as 错误:
        return 0, "连不上：{}".format(错误)
    try:
        应答描述 = json.loads(源文本)
    except ValueError:
        return 状态码, "返回不是 JSON（{} 字节）".format(len(源文本))
    契约版本 = 应答描述.get("契约版本") or {}
    return 状态码, "契约版本 {}.{}.{} · 实际端口 {} · 能力 {} 条".format(
        契约版本.get("主", "?"), 契约版本.get("次", "?"), 契约版本.get("构建", "?"),
        应答描述.get("实际端口"), len(应答描述.get("能力", [])),
    )


def 要求健康读数(监听端口: int) -> None:
    状态码, 读数 = 取健康读数(监听端口)
    if 状态码 != 200:
        raise SystemExit("健康检查不过（端口 {}）：{}".format(监听端口, 读数))
    打印文本("  健康检查 GET /接口 → 200 · {}".format(读数))


def 活着的实例() -> list:
    if not (运行根 / "已装载").is_dir():
        return []
    return [读指针("已装载/{}".format(路径.stem)) for 路径 in sorted((运行根 / "已装载").glob("*.json"))]


def 端口空着(监听端口: int) -> bool:
    """流量口是否**空着**（模式=停 的判据：「停下 + 流量口空着」）。

    判法是**连一次**：连得上 ⇒ 还有东西在听（不空）；连接被拒 ⇒ 空。
    **不是**看进程在不在（同 §二 判据 5 的口径：进程活着但答不了 ≠ 起得来，反过来也一样）。
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as 套接字:
        套接字.settimeout(0.5)
        try:
            套接字.connect(("127.0.0.1", 监听端口))
            return False
        except OSError:
            return True
