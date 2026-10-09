# -*- coding: utf-8 -*-
r"""命名扫描面 —— 全树命名扫描的**扫描面与分片执行**（`落库.py` 的扫描那一半）。

**为什么拆出来**（2026-10-08）：判据 55（名册新鲜度）的扫描面就是本件，
它是全闸最重的两条之一（实测单跑 8.9 s）。提速要做三件事（剪枝 · 分片并行 · 缓存），
而它们全是**纯扫描面**的事 —— 与「怎么写库」无关。挤在 `落库.py` 里会把那一件顶过
400 行硬顶（判据 ⑲）⇒ 按「一个关注点一件」拆到这里；`落库.py` 再导出，调用方向不变。

**三处提速与它们的实测读数**（真仓 · load ~8）：
  ① `候选文件` 改 `os.walk` + **自上而下剪枝**：`rglob` 会先枚举整棵树（**8.1 s**）再逐个
     `is_file()`，而本面结果集只有 888 件 ⇒ **0.05 s**，结果集逐字不变；
  ② `扫出现` 分片交 **fork 子进程**（裸 `os.fork`，非 `multiprocessing`—— 判据 55 跑在闸 1
     的 daemon 进程池里，daemon 不许再起 multiprocessing 子进程）：纯 Python 字符循环，
     GIL 下线程拿不到并行 ⇒ **1.34 s → 0.47 s**，记录**逐条同序**；
  ③ `扫出现` 按树根缓存（原有）—— 判据 55 一次运行里既取对象数又取名集。

**口径一字未改**：跳过目录清单（段形态主人 `代码地图/落点.py::排除目录`）· 后缀表唯一权威
（`一键验证.常量.命名可解析后缀`）· 剥器转口（`一键验证.命名扫描.剥后缀` + `抽标识符带位置`）·
两张字面量名单（语言关键字 · 内建噪声）全部照搬，逐字不变。
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

仓根 = Path(__file__).resolve().parents[2]
for 加目录 in (str(Path(__file__).resolve().parent), str(仓根 / "开发工具"),
            str(仓根 / "构建装配" / "一键验证")):
    if 加目录 not in sys.path:
        sys.path.insert(0, 加目录)

import 一键验证.命名扫描 as _命名扫描  # noqa: E402  —— 剥器只此一份
from 代码地图.落点 import 排除目录  # noqa: E402  —— 段形态主人，不自持第二份
# 后缀表**唯一权威**（本件不自持第二份；直接引名字，不另定义 —— 另定义就会被判据 54 报）。
from 一键验证.常量 import 命名可解析后缀  # noqa: E402

# 只扫代码件（`.md` 不在内）；任一层命中即整枝跳过。
# ★ 段形态主人 = `开发工具/代码地图/落点.py::排除目录`（只读参考 · 构建环境 · .git · .codegraph）
# —— 原先自持一份 `(".git", "__pycache__", ".codegraph")`，**漏了 `构建环境`** ⇒
#    把**不入版本库**的编译缓存扫进了受版本控制的 `命名出现`/`命名登记`（实测 290 行）。
跳过目录 = 排除目录 + ("__pycache__", "target", "node_modules")
# `扫出现` 的扫描缓存（键 = `树根.resolve()`）—— 只给同进程内多次调它的调用方省一遍全扫
# （闸的「名册新鲜度」判据两处调它）；CLI 只调一次，不受影响。
_扫出现缓存: dict = {}
# `扫出现` 的分片并行度与门槛：件数达到门槛才付叉进程的成本（夹具仓只有十几件 —— 那一路
# 退回串行，省下每次 `--自测` 都要付的进程启动）。并行度取本机核数上限 32（同闸 1 判据池）。
分片并行度 = max(1, min(32, os.cpu_count() or 1))
分片最小件数 = 64

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

# ── 标准库 / 内建噪声名（显式名单 · 按语言分组的字面量清单）────────────────
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
    而走树产出的路径是**未解析**的写法 ⇒ 不解析就 `relative_to` 失败、整棵树被判成树外
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
    """⇒ 待扫文件的绝对路径列表（按权威后缀表走树；跳过目录与树外路径一律不要）。

    ★ **为什么不用 `rglob`**（2026-10-08 实测）：`Path.rglob("*")` 会**先枚举整棵树**再逐个
      `is_file()` —— 真仓实测 **8.1 s**（仓里有 `只读参考/` 与 `运行内核/**/target` 那一大票
      不该进的枝，`rglob` 一个都剪不掉），而本函数的结果集只有 888 件。改成 `os.walk` +
      **自上而下剪枝**（命中 `跳过目录` 的目录整枝不进）⇒ 实测 **0.05 s**，结果集逐字不变
      （原口径「路径任一段命中 `跳过目录` 即排除」与剪枝等价：剪掉的枝里任何件都带那个段）。
    """
    查询读数 = []
    for 目录路径, 目录表, 文件表 in os.walk(树根):
        目录表[:] = [目录名 for 目录名 in 目录表 if 目录名 not in 跳过目录]
        for 名称 in 文件表:
            路径 = Path(目录路径) / 名称
            if 路径.suffix not in 命名可解析后缀:
                continue
            if not 是仓内(路径, 树根):
                continue
            查询读数.append(路径)
    查询读数.sort(key=lambda 路径: 路径.as_posix())
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


def 扫一批(路径表: list, 树根) -> list:
    """一条分片的重活（读一件 → 剥 → 抽标识符 → 判面）⇒ 该片的记录表。**模块级**（供子进程调）。

    这是 `扫出现` 的**唯一实现**：并行那一路把它分片发给子进程，串行那一路把整张表直接交给它。
    """
    输出表 = []
    for 路径 in 路径表:
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
    return 输出表


def 扫出现并行(树根, 路径表: list) -> list:
    """把 `路径表` 分片摊到 **fork 子进程**上跑 `扫一批`，按**原序**拼回来。

    ★ **为什么是裸 `os.fork` 而不是 `multiprocessing.Pool`**（2026-10-08 实测撞到的硬限制）：
      本函数会被**判据 55** 调用，而判据跑在闸 1 的 `multiprocessing.Pool`（**daemon** 子进程）里
      —— daemon 进程不许再起 `multiprocessing` 子进程（`AssertionError: daemonic processes
      are not allowed to have children`）。裸 `os.fork` 没有这条限制。
    ★ **为什么不用线程**：本段是**纯 Python 字符循环**（剥器 + 抽标识符 + 判面），GIL 之下线程
      拿不到并行（同 `验证.用判据进程池` 的实测结论）。
    ★ **回传用 JSON 管道**：分片结果直接 `json.dumps` 写管道 ⇒ 父进程拼回；不 pickle、不落盘。
    """
    if not 路径表:
        return []
    分片数 = min(分片并行度, len(路径表))
    if 分片数 < 2:
        return 扫一批(路径表, 树根)
    分片跨度 = -(-len(路径表) // 分片数)
    分片批表 = [路径表[起点 : 起点 + 分片跨度] for 起点 in range(0, len(路径表), 分片跨度)]
    子进程表 = []
    for 分片 in 分片批表:
        管道读端, 管道写端 = os.pipe()
        标识 = os.fork()
        if 标识 == 0:  # 子进程：写完就退，绝不回到调用方（否则父进程的逻辑会跑两遍）
            try:
                os.close(管道读端)
                with os.fdopen(管道写端, "w", encoding="utf-8") as 结果管:
                    json.dump(扫一批(分片, 树根), 结果管, ensure_ascii=False)
            except BaseException:
                os._exit(1)
            os._exit(0)
        os.close(管道写端)
        子进程表.append((标识, 管道读端))
    输出表 = []
    for 标识, 管道读端 in 子进程表:
        try:
            with os.fdopen(管道读端, "r", encoding="utf-8") as 结果管:
                输出表.extend(json.load(结果管))
        finally:
            os.waitpid(标识, 0)
    return 输出表


def 扫出现(树根) -> list:
    """扫全树 ⇒ 每条出现一条记录（五键：`名字` / `文件` / `行号` / `面` / `成员`）。

    **不滤已登记的名**（`命名出现` 是「名字出现在哪」的明细表，已登记的名也要记）；
    同一行同名的重复引用只出一条。关键字与内建噪声照旧跳过。

    ★ **按树根缓存**（2026-10-07）：闸那条「名册新鲜度」判据要在一次运行里既取**对象数**
    又取**名集**（两处都调本函数）⇒ 真仓实测一次全扫 ~950 ms，不缓存就白付两遍。
    缓存键 = `树根.resolve()`（同一进程内同一棵树不变）；CLI 只调一次，不受影响。
    ★ **分片并行**（2026-10-08）：件数过门槛就交 `扫出现并行`（fork 分片），结果与串行
    **逐条同序**（分片按原序拼回）。小仓（夹具）付不起进程启动 ⇒ 退回串行。
    """
    缓存键 = str(Path(树根).resolve())
    if 缓存键 in _扫出现缓存:
        return _扫出现缓存[缓存键]
    路径表 = 候选文件(树根)
    输出表 = 扫出现并行(树根, 路径表) if len(路径表) >= 分片最小件数 else 扫一批(路径表, 树根)
    _扫出现缓存[缓存键] = 输出表
    return 输出表


def 写库名集(树根, 库件) -> set:
    """⇒ **本口会写进 `命名出现` 的那个名字集**（现场重扫 + 排除例外与外来名）。

    ★ **为何单列这一个函数**（2026-10-07）：闸那条「名册新鲜度」判据要与本口**同一份推导**
    —— 两边若各推一遍，判据的读数就与本口写进去的东西不是同一件事（判据报绿而库里是旧的）。
    故：**推导只此一份**，`落库` 与判据都调它。

    读不动库（不在 / 读不出）⇒ 抛 `表定义.库读不动`（fail-closed）。
    """
    import collections
    import sqlite3
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
