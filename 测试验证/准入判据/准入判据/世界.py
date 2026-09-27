"""世界 —— 一次判读的全部输入。判据只读它，**不各自去开文件**（便于自测注入变异）。"""

import json
from pathlib import Path

契约目录名 = "契约声明"
扩展根目录名 = "扩展根目录"


def 找仓根() -> str:
    for 起 in [Path.cwd(), Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
        if (起 / 契约目录名).is_dir() and (起 / "扩展装载").is_dir():
            return str(起)
    return str(Path.cwd())


def 读文本(路: Path) -> str:
    try:
        return 路.read_text(encoding="utf-8")
    except OSError:
        return ""


def 读JSON(路: Path):
    try:
        return json.loads(路.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def 读生成物面(根: Path) -> str:
    """拼接**生成物全集**的文本：`契约声明/src/` 下以「数据.rs」结尾的 `.rs`（路由件 + 子件）。

    生成物按表拆后不再是单个 `声明数据.rs`；判据凡要读生成物内容（判据 ④ 读 `生命周期起/止`）
    一律走这里。写死单个路径，拆一次就静默丢覆盖面（#230 记的正是这个病）。
    """
    目录 = 根 / "契约声明/src"
    if not 目录.is_dir():
        return ""
    return "".join(
        读文本(路) for 路 in sorted(目录.glob("*数据.rs"))
    )


def 读装配器源码(根: Path) -> str:
    """装配器 = 入口 `构建制品.py` + 同名字文件夹 `构建制品/`。

    判据 ⑨ 要在**装配器源码**里找「现场编 cdylib」那一条路。入口拆成路由后，
    那条路落在 `构建制品/扩展.py`；故这里把入口与包一起读进来（口径见
    `开发规范.md` §六「主文件是路由」）。
    """
    文本 = 读文本(根 / "构建装配/上线切换/构建制品.py")
    return 文本 + "".join(
        读文本(路) for 路 in sorted((根 / "构建装配/上线切换/构建制品").rglob("*.py"))
    )


def 读目录全部rs(目录: Path) -> str:
    """一个目录下全部 `.rs`（含子目录）拼起来 —— 判据读「面」，不读某一个写死的文件。"""
    if not 目录.is_dir():
        return ""
    return "".join(读文本(路) for 路 in sorted(目录.rglob("*.rs")))


def 读件与包(根: Path, 相对: str) -> str:
    """路由件 + **同名字文件夹**（`启动网关.rs` + `启动网关/`）。

    #230 记的病：判据把落点写成**单个文件路径** ⇒ 那个件一拆成路由（`mod` + 子件），
    判据就读不到搬进子件的记号，静默丢覆盖面（闸还照绿）。故一律读「件 + 它的包」。
    """
    件 = 根 / 相对
    return 读文本(件) + 读目录全部rs(件.with_suffix(""))


class 世界:
    """一次判读的全部输入。判据只读它，**不各自去开文件**（便于自测注入变异）。

    每条判据的扫描面 = 本类里被它读到的那几个字段。
    """

    def __init__(self, 根: str):
        根 = Path(根)
        self.仓根 = 根
        self.边界协议 = 读文本(根 / "跨语言适配/边界协议/边界协议.md")
        self.扩展根声明 = 读JSON(根 / "扩展装载/扩展根声明.json") or {}
        self.包声明表 = sorted(
            (p, 读JSON(p)) for p in (根 / 扩展根目录名).rglob("包声明.json")
        )
        self.扩展Cargo表 = sorted(
            (p, 读文本(p)) for p in (根 / 扩展根目录名).rglob("Cargo.toml")
        )
        self.必备件 = 读JSON(根 / "扩展装载/开发标准/必备件.json") or {}
        self.构建制品 = 读装配器源码(根)
        self.载入判定 = 读JSON(根 / "扩展装载/载入约定/载入判定.json") or {}
        self.载入判定文 = 读文本(根 / "扩展装载/载入约定/载入判定.json")
        self.判定rs = 读文本(根 / "运行内核/装载入口/src/判定.rs")
        self.通知口 = 读文本(根 / "跨语言适配/适配器实现/src/通知口.rs")
        # 适配器 crate 的 `lib.rs` 是路由（子件散在 `src/` 下）⇒ 读**整个 crate 源**，
        # 不是那一个 `lib.rs`（否则 `通知.通道.注册(...)` 搬进 `核心实现/适配器定义.rs` 就丢了）。
        self.适配器lib = 读目录全部rs(根 / "跨语言适配/适配器实现/src")
        self.线程安全 = 读文本(根 / "跨语言适配/适配器实现/src/线程安全.rs")
        self.网关 = 读文本(根 / "对外接口面/调用接口面/src/网关.rs")
        # 启动网关是路由件（子件在 `examples/启动网关/`）⇒ 读「件 + 包」。
        self.启动网关 = 读件与包(根, "对外接口面/调用接口面/examples/启动网关.rs")
        # 生成物**按表拆**后是一组件（路由件 `声明数据.rs` + 子件，都以「数据.rs」结尾）。
        # 判据要的是**生成物全集**，不是某一个写死的路径 —— 写死单路径，拆一次就静默丢覆盖面
        # （#230 记的正是这个病）。这里拼全部生成物文本（判据 ④ 读 `生命周期起/止`）。
        self.生成物面 = 读生成物面(根)
        self.命令类别 = sorted((根 / "契约声明/命令类别").glob("*.json"))
        self.工具响应扩展 = 读文本(根 / "对外接口面/调用接口面/src/工具响应_扩展.rs")

    # 扩展目录（目前恰好 1 个；多处判据要它）
    def 扩展目录(self) -> Path:
        return self.仓根 / 扩展根目录名 / "原子支持库" / "编译器支持库"

    def 指纹件(self) -> Path:
        return self.扩展目录() / "指纹.json"

    def 指纹脚本(self) -> Path:
        命 = (读JSON(self.指纹件()) or {}).get("生成命令", "")
        # 生成命令形如 "python3 扩展根目录/…/重跑指纹.py"（仓库根相对）
        分 = 命.split()
        参 = [x for x in 分 if x.endswith(".py")]
        return self.仓根 / 参[0] if 参 else self.仓根 / "__缺__"
