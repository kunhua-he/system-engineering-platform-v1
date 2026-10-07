# -*- coding: utf-8 -*-
r"""落库 —— 全树扫描的**唯一写口**：把名字的出现面灌进 `命名出现` / `命名登记`。

用途（经唯一壳 `信息核心.py`）：
    python3 开发工具/信息核心/信息核心.py 落库 [--干跑]

★ **为何存在**（加固项 A3「名册新鲜度」）：本口原先住在 `开发工具/信息核心/` 那件（已删）
  的 `落库()`（该件已删）—— 那是库 `命名出现`（约 8 万行）的**唯一 insert 写口**，
  而它零调用者 ⇒ 「库说债 0」与「现场重扫还有新增」两套读数谁也管不着（磁盘 ≠ 运行时）。
  2026-10-07 蒸馏搬进本件并接回流水线：加 `信息核心.py 落库` 子命令，改名后跑它。

**写两处**（★ 2026-10-07 两处**分住两个库** —— 见 `表定义.源表` / `派生表`）：
  · `命名出现` —— **全量重写**（扫描的派生明细，不重写会留旧行）；住**派生库**
    （`信息核心_派生.db`，不进版本库）—— 8.7 万行纯派生明细，住受版本库会让整库二进制
    无法合并、把库撑到 11.4 MB。派生库不在 / 缺表 ⇒ 本口**现建**（跑 `派生建表语句`，幂等）。
  · `命名登记` —— 对**扫到的每一个名**重判 `状态` 并刷新 `出现次数`（新名插入、老名只改
    这两列，`on conflict ... do update set 状态, 出现次数`，**不动**已有语义）；本次没扫到的
    旧名 ⇒ `出现次数` **归零**（陈旧行 / 僵尸可机器判定）。住**规则库**（受版本）。**只归零不删行**。

**扫描面**：`构建装配/一键验证/一键验证/常量.py::代码后缀`（**后缀表唯一权威** ——
本件原先自持一份五后缀的表，缺 `.swift` ⇒ `前端呈现/桌面应用/壳.swift` 的名字从未进过登记面）。
跳过 `排除目录`（段形态主人 `开发工具/代码地图/落点.py`：只读参考 · 构建环境 · .git ·
.codegraph）＋本面增量（`__pycache__` · `target` · `node_modules`）· 仓根之外的路径；`.md` 不扫。
标识符取法：**转口** `一键验证.命名扫描.剥后缀`（剥注释/串/数字字面量，**只此一份**）
+ `抽标识符带位置`（排除紧跟 `.` 的成员访问，`self.名` 除外）。

**过滤**（跳过，不进结果）：语言关键字 · 显式内建噪声名单 —— 两张都是**字面量清单**，见下。
★ 为何这两张名单**住本件**（数据面）而不住 `命名扫描.py`（判据面）：它们是「这些名不算作者
  起的」的口径判断，属**语言面知识**，不该烧进底座判据（根二：变化赶到外围）；但本口要它
  去噪 —— 没有它，名册里会长出 `let`/`self`/`def`/`str` 一类（实测 266 个不滤）。

**库读不动**：抛 `表定义.库读不动`（fail-closed，绝不把空名册当「全未登记」用）。
"""
from __future__ import annotations

import collections
import re
import sqlite3
import sys
from pathlib import Path

仓根 = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(Path(__file__).resolve().parent), str(仓根 / "开发工具"),
                str(仓根 / "构建装配" / "一键验证")]

import 表定义  # noqa: E402
import 一键验证.命名扫描 as _命名扫描  # noqa: E402  —— 剥器只此一份
from 代码地图.落点 import 排除目录  # noqa: E402  —— 段形态主人，不自持第二份
# 后缀表**唯一权威**（本件不自持第二份；直接引名字，不另定义 —— 另定义就会被判据 54 报）。
from 一键验证.常量 import 代码后缀  # noqa: E402
from 代码地图 import 查名  # noqa: E402  —— 规则谓词的主人（判状态 / 判模式 / 判禁止形状）

# 只扫代码件（`.md` 不在内）
# 任一层命中即整枝跳过。
# ★ 段形态主人 = `开发工具/代码地图/落点.py::排除目录`（只读参考 · 构建环境 · .git · .codegraph）
# —— 本件原先自持一份 `(".git", "__pycache__", ".codegraph")`，**漏了 `构建环境`** ⇒
#    把**不入版本库**的编译缓存（`构建环境/构建缓存/审计探针/` 的 .rs/.py）扫进了
#    受版本控制的 `命名出现`/`命名登记`（实测 290 行）⇒ 主干盘上有那目录时闸绿、
#    新工作树没那目录时判据 55 当场红（名册集与现场重扫集对不上）。不再自持一份。
跳过目录 = 排除目录 + ("__pycache__", "target", "node_modules")
# `扫出现` 的扫描缓存（键 = `树根.resolve()`）—— 只给同进程内多次调它的调用方省一遍全扫
# （闸的「名册新鲜度」判据两处调它）；CLI 只调一次，不受影响。
_扫出现缓存: dict = {}


# ── 语言关键字（跳过 —— 关键字不是「标识符名」，不该进未登记名结果）──────────
# 三份都是**字面量清单**（显式枚举；不用 `keyword` 模块、不用前缀 / 词形启发式）。
Python关键字 = frozenset("""
False None True and as assert async await break class continue def del elif else except finally
for from global if import in is lambda nonlocal not or pass raise return try while with yield
""".split())
# Python 软关键字（`match` / `case` / `type` 可当软关键字；`_` 是通配占位）—— 一并滤掉。
Python软关键字 = frozenset("""_ case match type""".split())
Rust关键字 = frozenset("""
as break const continue crate else enum extern false fn for if impl in let loop match mod move mut
pub ref return self Self static struct super trait true type unsafe use where while async await dyn
abstract become box do final macro macro_rules override priv typeof unsized virtual yield try union
""".split())
JS关键字 = frozenset("""
break case catch class const continue debugger default delete do else export extends finally for
function if import in instanceof let new return super switch this throw try typeof var void while
with yield async await of static null true false
""".split())
语言关键字 = Python关键字 | Python软关键字 | Rust关键字 | JS关键字

# ── 标准库 / 内建噪声名（显式名单 · 按语言分组的字面量清单）────────────────────
# 只收**常见**的标准库 / 内建名（模块 · 类型 · 函数 · 方法 · 属性 · 宏 · 全局对象）。
# **不是穷尽清单**：未收录的标准库 / 第三方 API 名仍会进结果。
内建噪声 = frozenset((
    "abs aiter all anext any ascii bin bool breakpoint bytearray bytes callable chr classmethod compile complex delattr dict dir "
    "divmod enumerate eval exec filter float format frozenset getattr globals hasattr hash help hex id input int isinstance issubclass "
    "iter len list locals map max memoryview min next object oct open ord pow print property range repr reversed round set setattr "
    "slice sorted staticmethod str sum super tuple type vars zip __import__ self cls None True False "
    "BaseException Exception ArithmeticError AssertionError AttributeError BufferError EOFError ImportError ModuleNotFoundError "
    "LookupError IndexError KeyError MemoryError NameError NotImplementedError OSError IOError FileNotFoundError PermissionError "
    "ProcessLookupError TimeoutError ReferenceError RuntimeError RecursionError StopIteration StopAsyncIteration SyntaxError "
    "IndentationError TabError SystemError SystemExit TypeError ValueError UnicodeError UnicodeDecodeError UnicodeEncodeError "
    "ZeroDivisionError KeyboardInterrupt GeneratorExit Warning "
    "__name__ __file__ __init__ __main__ __all__ __doc__ __future__ __slots__ __dict__ __class__ __repr__ __str__ __eq__ __hash__ "
    "__enter__ __exit__ __iter__ __next__ __len__ __getitem__ __setitem__ __delitem__ __contains__ __call__ __bool__ __annotations__ "
    "__path__ __version__ __author__ __package__ __spec__ __loader__ __builtins__ __debug__ __qualname__ __module__ __getattr__ "
    "__setattr__ __delattr__ __post_init__ __init_subclass__ "
    "abc argparse array asyncio base64 binascii bisect builtins calendar collections configparser contextlib copy csv ctypes "
    "dataclasses datetime decimal difflib enum errno faulthandler fractions functools gc getpass glob gzip hashlib heapq hmac html "
    "http importlib inspect io ipaddress itertools json keyword locale logging lzma math mimetypes multiprocessing operator os pathlib "
    "pickle pkgutil platform plistlib pprint profile pstats queue random re readline secrets select shlex shutil signal site smtplib "
    "socket socketserver sqlite3 ssl stat statistics string stringprep struct subprocess sys sysconfig tarfile tempfile textwrap "
    "threading time timeit token tokenize traceback tracemalloc types typing unicodedata unittest urllib uuid venv warnings wave "
    "weakref webbrowser xml zipfile zipimport zlib "
    "Path PurePath PosixPath PurePosixPath WindowsPath Counter defaultdict OrderedDict deque namedtuple ChainMap UserDict UserList "
    "UserString dataclass field Enum IntEnum Flag IntFlag auto "
    "append clear copy extend insert pop popitem remove reverse setdefault sort update values add discard intersection isdisjoint "
    "issubset issuperset symmetric_difference union difference capitalize casefold center count encode endswith expandtabs find "
    "format_map index isalnum isalpha isascii isdecimal isdigit isidentifier islower isnumeric isprintable isspace istitle isupper "
    "join ljust lower lstrip maketrans partition removeprefix removesuffix replace rfind rindex rjust rpartition rsplit rstrip split "
    "splitlines startswith strip swapcase title translate upper zfill close fileno flush isatty read readable readline readlines seek "
    "seekable tell truncate writable write writelines read_text write_text read_bytes write_bytes as_posix exists expanduser glob "
    "group home is_absolute is_dir is_file is_symlink iterdir joinpath lchmod lstat mkdir name open owner parent parents parts "
    "relative_to rename resolve rglob rmdir samefile stat stem suffix suffixes symlink_to touch unlink with_name with_stem with_suffix "
    "cwd chmod absolute argv environ exit getcwd getenv getpid kill listdir makedirs path putenv removedirs scandir sep walk stderr "
    "stdin stdout version version_info executable platform modules maxsize getsizeof setrecursionlimit monotonic perf_counter "
    "process_time sleep strftime strptime time_ns monotonic_ns localtime gmtime mktime ctime asctime args kwargs items keys get error "
    "code "
    "Vec String Box Rc Arc RefCell Cell HashMap HashSet BTreeMap BTreeSet VecDeque Option Result Some Ok Err Cow PathBuf OsStr "
    "OsString CString CStr Duration Instant SystemTime Ordering PhantomData Pin Weak u8 u16 u32 u64 u128 usize i8 i16 i32 i64 i128 "
    "isize f32 f64 bool char std core alloc proc_macro prelude "
    "println print eprintln eprint vec panic assert assert_eq assert_ne debug_assert debug_assert_eq writeln todo unimplemented "
    "unreachable matches dbg include_str include_bytes concat env stringify unwrap unwrap_or unwrap_or_else unwrap_or_default expect "
    "clone to_owned to_string as_bytes as_str as_ptr as_mut as_ref is_empty is_some is_none is_ok is_err push_str into_iter iter_mut "
    "collect fold for_each get_mut contains contains_key entry or_insert or_default values_mut extend drain resize capacity "
    "with_capacity into try_into try_from parse write_all read_to_string lines trim starts_with ends_with to_lowercase to_uppercase "
    "extend_from_slice sort_by sort_by_key dedup retain take last first rev enumerate chain product position rposition last_mut "
    "console window document globalThis require module exports process Buffer null undefined NaN Infinity String Number Boolean Array "
    "Object Promise JSON Math Date Error RegExp Map Set WeakMap WeakSet Symbol BigInt Proxy Reflect Function parseInt parseFloat isNaN "
    "isFinite setTimeout setInterval clearTimeout clearInterval encodeURIComponent decodeURIComponent structuredClone fetch alert then "
    "catch finally push pop shift unshift slice splice concat trim toUpperCase toLowerCase indexOf includes forEach reduce some every "
    "getElementById querySelector querySelectorAll addEventListener "
).split())
# 命中的名字**一律跳过**（判定顺序：已登记 → 语言关键字 → 内建噪声）。
过滤名 = 语言关键字 | 内建噪声

# 判「面」用的定义关键字（启发式，见 `判面`）。
定义关键字 = re.compile(r"\b(?:fn|def|struct|enum|trait|impl|class|type|mod|const|static"
                    r"|interface|namespace|function|var|let|pub)\b")
# 名紧跟定义关键字 ⇒ 定义面。
定义位 = re.compile(r"(?:\bfn|\bdef|\bstruct|\benum|\btrait|\bimpl|\bclass|\btype|\bmod|\bconst"
                r"|\bstatic|\binterface|\bnamespace|\bfunction|\bvar|\blet|\bpub)\s+")


def 是仓内(路径: Path, 树根) -> bool:
    """`路径` 是否落在**树根之内**（树根自身也算）—— 树外路径一律不扫。

    ★ 2026-10-07：原先（旧套）写死比 `仓根`（本件所在那棵树）—— 那会让本口只能扫本件
    所在那棵树，对**别的**工作树 / 夹具仓整枝判成树外（`改名面.py` 那处注释早就记过
    同一个缺陷）。改吃 `树根` 入参：本口既能在本仓跑，也能在夹具仓 / 别的树上跑。
    ★ **两侧都要 `.resolve()`**：macOS 的 `/tmp` 与 `/var` 都是 symlink（`/var` → `/private/var`），
    而 `Path.rglob` 产出的路径是**未解析**的写法 ⇒ 不解析就 `relative_to` 失败、整棵树被判成树外
    （实测：夹具仓 0 个候选文件 ⇒ 名册新鲜度在正向样本上假红）。
    """
    try:
        路径.resolve().relative_to(Path(树根).resolve())
        return True
    except ValueError:
        return False


def 相对路径(路径: Path, 树根) -> str:
    """⇒ 仓根相对路径（正斜杠）；不在仓根下则退回树根相对，再退回绝对。"""
    for 基准值 in (仓根, Path(树根)):
        try:
            return 路径.resolve().relative_to(基准值.resolve()).as_posix()
        except ValueError:
            continue
    return 路径.resolve().as_posix()


def 候选文件(树根) -> list:
    """⇒ 待扫文件的绝对路径列表（按权威后缀表走树；跳过目录与树外路径一律不要）。"""
    查询读数 = []
    for 路径 in Path(树根).rglob("*"):
        if not 路径.is_file() or 路径.suffix not in 代码后缀:
            continue
        if any(路径段 in 跳过目录 for 路径段 in 路径.parts):
            continue
        if not 是仓内(路径, 树根):
            continue
        查询读数.append(路径)
    return 查询读数


def 判面(骨架: str, 标识符: str) -> str:
    """尽力判「名在这一行属于哪个面」⇒ 定义面 / 形参面 / 局部面（**启发式，不是真解析器**）。

    名紧跟定义关键字 ⇒ 定义面；该行有定义关键字且名落在第一个 `(` 之后 ⇒ 形参面；其余 ⇒ 局部面。
    """
    if 定义位.search(骨架) and re.search(re.escape(标识符) + r"\b", 骨架[定义位.search(骨架).end():]):
        return "定义面"
    左括号位 = 骨架.find("(")
    if 左括号位 >= 0 and 定义关键字.search(骨架[:左括号位]) and 标识符 in 骨架[左括号位:]:
        return "形参面"
    return "局部面"


def 扫出现(树根) -> list:
    """扫全树 ⇒ 每条出现一条记录（五键：`名字` / `文件` / `行号` / `面` / `成员`）。

    **不滤已登记的名**（`命名出现` 是「名字出现在哪」的明细表，已登记的名也要记）；
    同一行同名的重复引用只出一条。关键字与内建噪声照旧跳过。

    ★ **按树根缓存**（2026-10-07）：闸那条「名册新鲜度」判据要在一次运行里既取**对象数**
    又取**名集**（两处都调本函数）⇒ 真仓实测一次全扫 ~950 ms，不缓存就白付两遍。
    缓存键 = `树根.resolve()`（同一进程内同一棵树不变）；CLI 只调一次，不受影响。
    """
    缓存键 = str(Path(树根).resolve())
    if 缓存键 in _扫出现缓存:
        return _扫出现缓存[缓存键]
    输出表 = []
    for 路径 in 候选文件(树根):
        源码后缀 = 路径.suffix
        try:
            源文本 = _命名扫描.剥后缀(源码后缀, 路径.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
        相对 = 相对路径(路径, 树根)
        for 序号, 文本行 in enumerate(源文本.splitlines(), 1):
            本行 = {}
            for 标识符, 起始位 in _命名扫描.抽标识符带位置(文本行):
                if 标识符 not in 过滤名:
                    本行[标识符] = 本行.get(标识符, True) and 文本行[:起始位].rstrip().endswith(".")
            for 标识符, 全成员 in 本行.items():
                输出表.append({"名字": 标识符, "文件": 相对, "行号": 序号, "面": 判面(文本行, 标识符), "成员": 全成员})
    _扫出现缓存[缓存键] = 输出表
    return 输出表


def 读名单(连接, 表名: str, 分组: str = "") -> set:
    """⇒ 库某张名单表的全部名字；给了 `分组` 再按分组筛（名单住库里，不写死在代码里）。"""
    return {文本行[0] for 文本行 in 连接.execute(
        f"select 名字 from {表名}" + (" where 分组=?" if 分组 else ""), (分组,) if 分组 else ())}


def 写库名集(树根, 库件) -> set:
    """⇒ **本口会写进 `命名出现` 的那个名字集**（现场重扫 + 排除例外与外来名）。

    ★ **为何单列这一个函数**（2026-10-07）：闸那条「名册新鲜度」判据要与本口**同一份推导**
    —— 两边若各推一遍，判据的读数就与本口写进去的东西不是同一件事（判据报绿而库里是旧的）。
    故：**推导只此一份**，`落库` 与判据都调它。

    读不动库（不在 / 读不出）⇒ 抛 `表定义.库读不动`（fail-closed）。
    """
    import 表定义 as _表定义
    库件 = Path(库件)
    if not 库件.is_file():
        raise _表定义.库读不动("规则库不在：%s" % 库件)
    扫描记录 = 扫出现(树根)
    连接 = sqlite3.connect("file:%s?mode=ro" % 库件, uri=True)
    try:
        已登记 = {文本行[0] for 文本行 in 连接.execute("select 名字 from 命名登记")}
        例外 = {文本行[0] for 文本行 in 连接.execute("select 名字 from 命名例外")}
    except sqlite3.Error as 错误:
        raise _表定义.库读不动("规则库读不动：%s" % 错误) from 错误
    finally:
        连接.close()
    面数, 全成员 = collections.Counter(), collections.defaultdict(lambda: True)
    for 记录条 in 扫描记录:
        面数[记录条["名字"]] += 记录条["面"] == "定义面"
        全成员[记录条["名字"]] &= 记录条["成员"]
    全部名 = {记录条["名字"] for 记录条 in 扫描记录} - 例外
    外来 = {标识符 for 标识符 in 全部名
          if 标识符 not in 已登记 and 标识符.isascii() and 面数[标识符] == 0 and 全成员[标识符]}
    return 全部名 - 外来


def 落库(树根, 干跑: bool = False) -> dict:
    """跑一遍全树扫描并落库 ⇒ 读数（`干跑=True` 只算不写）。

    **写两处（分住两库）**：`命名出现` **全量重写** ⇒ **派生库**（非版本，缺则现建）；
    `命名登记` 对**扫到的每一个名**重判 `状态` 并刷新 `出现次数` ⇒ **规则库**（受版本）
    （新名插入、老名只改 `状态` 与 `出现次数`，**不动**已有语义）；本次没扫到的旧名
    ⇒ `出现次数` **归零**（陈旧行可机器判定，见读数 `陈旧归零`）；**只归零不删行**。

    ★ **写序**：先写派生库 `命名出现`、再写规则库 `命名登记` —— 派生库写失败时不改规则库，
    判据 55（比对 `命名登记`）仍能报出陈旧，不会假绿。
    ★ 库路径按 `仓根`（本件所在那棵树）取 —— 与旧套同口径：库是**全仓一份**的
    规则库，不跟着 `树根` 走（只有本仓有规则库；夹具仓的库由 `夹具规则库.建夹具规则库` 造，
    它**自行**调 `扫出现` 去填，不调本函数）。
    """
    扫描记录 = 扫出现(树根)
    库件 = 表定义.库路径(仓根)
    if not Path(库件).is_file():
        raise 表定义.库读不动("规则库不在：%s" % 库件)
    连接 = sqlite3.connect(str(库件))
    try:
        已登记 = {文本行[0] for 文本行 in 连接.execute("select 名字 from 命名登记")}
        例外 = {文本行[0] for 文本行 in 连接.execute("select 名字 from 命名例外")}
        动作词, 泛名表 = 读名单(连接, "命名字典", "动作"), 读名单(连接, "命名泛名")
        面数, 全成员 = collections.Counter(), collections.defaultdict(lambda: True)
        for 记录条 in 扫描记录:
            面数[记录条["名字"]] += 记录条["面"] == "定义面"
            全成员[记录条["名字"]] &= 记录条["成员"]
        出现计数 = collections.Counter(记录条["名字"] for 记录条 in 扫描记录)
        # 件名（文件基名）也是「这个名还在不在」的一个面：只经相对导入 / 动态装载的模块名
        # 不会被扫成标识符（`from .X import Y` 里 `X` 紧跟 `.` 被排除）⇒ 不按**文件基名**补计，
        # 一个仍在用的模块名会被误报成僵尸（实测：`夹具规则库` / `名册僵尸` 本体）。**只补计数，
        # 不把件名塞进名册**（收口方裁：`命名登记` 只管代码标识符，件名不登记 —— 见 `判据_命名件.py`）。
        for 路径 in 候选文件(树根):
            出现计数[路径.stem] += 1
        全部名 = sorted({记录条["名字"] for 记录条 in 扫描记录} - 例外)
        新名 = [标识符 for 标识符 in 全部名 if 标识符 not in 已登记]
        # 别人家的名字：纯 ASCII · 全仓无定义面 · 只以 `.成员` 形式出现。
        外来 = {标识符 for 标识符 in 新名 if 标识符.isascii() and 面数[标识符] == 0 and 全成员[标识符]}
        判定 = [(标识符,) + 查名.判状态(标识符, 泛名表, 动作词) for 标识符 in 全部名 if 标识符 not in 外来]
        计数表 = {"扫描出现": len(扫描记录), "涉及名字": len({记录条["名字"] for 记录条 in 扫描记录}),
               "新增": len(新名), "其中外部强加": len(外来),
               "其中待改名": sum(1 for _, 本条状态, _, _ in 判定 if 本条状态 == "待改名")}
        if 干跑:
            return 计数表
        # ① `命名出现` ⇒ **派生库**（非版本；不在 / 缺表则现建，幂等）。全量重写。
        派生连接 = sqlite3.connect(str(表定义.派生库路径(仓根)))
        try:
            for 语句 in 表定义.派生建表语句:
                派生连接.execute(语句)
            派生连接.execute("delete from 命名出现")
            派生连接.executemany(
                "insert into 命名出现(名字, 文件路径, 行号, 面) values(?,?,?,?)",
                [(记录条["名字"], 记录条["文件"], 记录条["行号"], 记录条["面"]) for 记录条 in 扫描记录
                 if 记录条["名字"] not in 例外 and 记录条["名字"] not in 外来])
            派生连接.commit()
            计数表["出现行数"] = 派生连接.execute("select count(*) from 命名出现").fetchone()[0]
        finally:
            派生连接.close()
        # ② `命名登记`（+ 新增外来进 `命名例外`）⇒ **规则库**（受版本）。
        连接.executemany("insert or ignore into 命名例外(名字, 说明) values(?,?)",
            [(标识符, "外部强加：只以 .成员 出现且全仓无定义面（标准库 / 第三方 API / DOM 属性）") for 标识符 in 外来])
        # **全部扫到的名都重判状态 + 刷新出现次数**（原先只判新增、且 `出现次数` 从不写 ⇒
        # 「在用 vs 僵尸」量不出）。`on conflict` **只改 `状态` 与 `出现次数`**（后者是派生/自动列），
        # 不覆盖已有行的 `语义`/`模式`/`来源`（手工登记的语义是资料，不该被自动文案冲掉）。
        连接.executemany(
            "insert into 命名登记(名字, 语义, 模式, 来源, 状态, 出现次数) values(?,?,?,?,?,?) "
            "on conflict(名字) do update set 状态=excluded.状态, 出现次数=excluded.出现次数",
            [(标识符, 语义, 模式, "新定义", 状态, 出现计数[标识符]) for 标识符, 状态, 模式, 语义 in 判定])
        # 全表刷新 `出现次数`：扫到的（标识符面或件名面）⇒ 本次出现条数；两者都没扫到的
        # （陈旧行 / 僵尸）⇒ 归零 —— 「在用 vs 僵尸」自此可机器区分（`出现次数 > 0` ⟺ 现量里仍出现）。
        # **只改计数，不删行**（删行走 `命名字典登记 --删`，受版本表跨腿删有重放风险，须人确认）。
        连接.execute("create temp table if not exists 本次扫描名(名字 text primary key, 次数 integer)")
        连接.executemany("insert or replace into 本次扫描名(名字, 次数) values(?,?)",
                    list(出现计数.items()))
        连接.execute("update 命名登记 set 出现次数 = coalesce("
                  "(select 次数 from 本次扫描名 where 名字 = 命名登记.名字), 0)")
        计数表["陈旧归零"] = 连接.execute(
            "select count(*) from 命名登记 where 出现次数 = 0").fetchone()[0]
        连接.commit()
        return 计数表
    finally:
        连接.close()


用法文本 = ("用法：信息核心.py 落库 [--干跑]\n"
          "  全树扫描 ⇒ 全量重写库 `命名出现` + 对扫到的名重判 `命名登记.状态`。\n"
          "  `--干跑` 只算不写（改名前先看一眼读数）。")


def 入口函数(命令行参数: list) -> int:
    """命令行入口（由 `信息核心.py` 路由调用，本件不自带 `__main__`）。"""
    if "--帮助" in 命令行参数 or "-h" in 命令行参数:
        print(用法文本, file=sys.stderr)
        return 0
    干跑 = "--干跑" in 命令行参数
    try:
        读数 = 落库(仓根, 干跑=干跑)
    except 表定义.库读不动 as 错误:
        print("落库跑不动：%s" % 错误, file=sys.stderr)
        print("修法：python3 开发工具/信息核心/信息核心.py 建库", file=sys.stderr)
        return 1
    输出行 = "（干跑，未写库）" if 干跑 else ""
    print("落库%s：扫描出现 %d · 涉及名字 %d · 新增 %d · 其中外部强加 %d · 其中待改名 %d"
          % (输出行, 读数["扫描出现"], 读数["涉及名字"], 读数["新增"],
             读数["其中外部强加"], 读数["其中待改名"]))
    if "出现行数" in 读数:
        print("命名出现：全量重写 ⇒ %d 行" % 读数["出现行数"])
    if "陈旧归零" in 读数:
        print("命名登记：陈旧行（出现次数=0，疑似僵尸）%d 行（**只归零不删**；删行走 `登记 --删`）"
              % 读数["陈旧归零"])
    if not 干跑:
        print("★ 库变了 ⇒ 收口前记得 `v1_task` 功能=6 记账"
              "（`源件` = `开发工具/信息核心/信息核心.db`），否则释放的越界检测会拒")
    return 0
