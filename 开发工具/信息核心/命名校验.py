# -*- coding: utf-8 -*-
r"""命名校验 —— 「出现即须登记」的只读校验口（未登记名判定）。

用途：
    python3 开发工具/信息核心/命名校验.py [--树根 <路径>] [--文件 <仓根相对路径>] [--上限 <N>]

判定口径（一句话）：扫代码件里出现的标识符名，凡**不在库 `命名登记` 表里**的 ⇒ 判「未登记」。
  · 判定**只认** `命名登记`（`select 名字 from 命名登记`），**不** JOIN `命名出现`。
    `命名出现` 是「名字出现在哪」的明细表，本模块**不拿它判**；它将来只用于回填/校正文件与行号。
  · 扫描面：后缀 `.rs` / `.py` / `.js` / `.ts` / `.vue` 的代码件；跳过 `.git/` ·
    `__pycache__/` · `.codegraph/`；跳过**仓根之外**的路径；`.md` 不扫。
  · 标识符取法：`re` + 一条通用正则（允许中文名）——
        [A-Za-z_\u4e00-\u9fff][A-Za-z0-9_\u4e00-\u9fff]*
    取之前先**剥注释与字符串字面量**（先整篇抹三引号串 / 块注释，再逐行剥单行串与行注释）。
  · 去重：同一 `(名字, 文件, 行号)` 只出一条；输出按 `(文件, 行号, 名字)` 排序。
  · **过滤（跳过，不进结果）**：先跳过**语言关键字**（Python 硬 / 软关键字 · Rust 全关键字 ·
    JS 保留字，见 `语言关键字`）；再跳过一张**显式名单**（按语言分组的字面量清单，共数百条，
    见 `内建噪声`）里的**标准库 / 内建名** —— Python 内建函数与异常 · dunder · 常用标准库模块 /
    类型 / 方法，Rust std 类型 / 宏 / 原生类型，JS 全局对象 / 构造器 / 常用方法。两张名单都是
    **字面量清单**，不含正则 · 前缀 · 词形启发式；命中即跳过（判定顺序：已登记 → 语言关键字 →
    内建噪声）。

**口径的不完美（如实写明，别当没看见）**：
  · 单行串只认「同一行内成对的引号」，**转义引号 / 行内引号不成对**（如 `"it's"`）会错配 ⇒
    可能**误报**（把串内容当标识符）或**漏报**（把真名连同串一起吃掉）。Rust 生命周期 `'a`
    与字符字面量 `'a'` 同为单引号、无法区分 ⇒ 同行成对时会被错剥（真名漏报）。
  · 未识别 Rust 原始串 `r#"..."#`、JS 模板串里的 `${...}` 插值（整串被剥 ⇒ 插值内真名漏报）。
  · 剥注释对 `.rs` 的 `#[attr]` 与 `.js/.ts` 的 `#私有名` 一并丢掉 ⇒ 那些位置真名漏报；
    Python 整除 `a // b` 被当行注释截断 ⇒ `b` 漏报。
  · 只按**词形**取名，不区分「定义 / 引用」⇒ 未登记的**引用名**（跨文件引用 · 标准库 API ·
    第三方 API）都会进结果；是否合格由 `命名登记` 表决定（本模块不替它判）。
  · 关键字已按上面两张名单滤掉，但名单**不是穷尽**的：未收进名单的标准库 / 第三方 API 名
    （方法 · 属性 · 变量）仍会当「未登记名」报出；字符串前缀 `f` `b` `r` 因剥串只去引号内容、
    不去前缀，也会残留 ⇒ 见下「剩余已知噪声 / 漏报」。

**剩余已知噪声 / 漏报（名单管不到的那部分，如实写明）**：
  · 标准库 / 第三方 API 名**未穷举**：名单只收常见名，未收录的模块 · 方法 · 属性仍会报出。
  · 字符串前缀残留：`f"…"` `b"…"` `r"…"` 剥串后留下单字母 `f` `b` `r`（本模块不去前缀）。
  · 单字母 / 泛用局部名（`x` `y` `cx` `cy` `a` `b` …）不滤 —— 无法与业务名区分。
  · 未登记的**业务引用名**仍会报出（本模块只判「在不在 `命名登记`」，不判定义 / 引用）。
  · 过滤名单是**显式**的：若某个**业务名恰与名单同形**（如 `code` `name` `path` `type`），会被
    **漏报** —— 名单可审、可增删，这是显式名单的代价。

连库方式与 `记规则.py` 一致：库路径走 `表定义.库路径(仓根)`，**不硬写库文件名**。
本模块**只读**：不建表、不改库结构、不写库。
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

仓根 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import 表定义  # noqa: E402

# 只扫代码件（`.md` 不在内）。
代码后缀 = (".rs", ".py", ".js", ".ts", ".vue")
# 任一层命中即整枝跳过。
跳过目录 = (".git", "__pycache__", ".codegraph")
# 标识符：首字符为字母 / 下划线 / 汉字，其后同集 —— 允许中文名。
标识符 = re.compile(r"[A-Za-z_\u4e00-\u9fff][A-Za-z0-9_\u4e00-\u9fff]*")
# 整篇先抹的跨行块（三引号串 / 块注释）—— 用换行数占位，保住行号。
跨行块 = (re.compile(r'""".*?"""', re.S),
        re.compile(r"'''.*?'''", re.S),
        re.compile(r"/\*.*?\*/", re.S))
# 逐行剥的单行串与行注释。
单行双引 = re.compile(r'"[^"\n]*"')
单行单引 = re.compile(r"'[^'\n]*'")
单行反引 = re.compile(r"`[^`\n]*`")
行注释 = re.compile(r"//|#")


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
abstract become box do final macro override priv typeof unsized virtual yield try union
""".split())
JS关键字 = frozenset("""
break case catch class const continue debugger default delete do else export extends finally for
function if import in instanceof let new return super switch this throw try typeof var void while
with yield async await of static null true false
""".split())
语言关键字 = Python关键字 | Python软关键字 | Rust关键字 | JS关键字

# ── 标准库 / 内建噪声名（显式名单 · 按语言分组的字面量清单）────────────────────
# 只收**常见**的标准库 / 内建名（模块 · 类型 · 函数 · 方法 · 属性 · 宏 · 全局对象）。
# **不是穷尽清单**：未收录的标准库 / 第三方 API 名仍会进结果（见模块 docstring「剩余已知噪声」）。
内建噪声 = frozenset((
    # Python 内建函数 / 类型 / 常量
    "abs aiter all anext any ascii bin bool breakpoint bytearray bytes callable chr classmethod "
    "compile complex delattr dict dir divmod enumerate eval exec filter float format frozenset "
    "getattr globals hasattr hash help hex id input int isinstance issubclass iter len list locals "
    "map max memoryview min next object oct open ord pow print property range repr reversed round "
    "set setattr slice sorted staticmethod str sum super tuple type vars zip __import__ "
    "self cls None True False "
    # Python 异常
    "BaseException Exception ArithmeticError AssertionError AttributeError BufferError EOFError "
    "ImportError ModuleNotFoundError LookupError IndexError KeyError MemoryError NameError "
    "NotImplementedError OSError IOError FileNotFoundError PermissionError ProcessLookupError "
    "TimeoutError ReferenceError RuntimeError RecursionError StopIteration StopAsyncIteration "
    "SyntaxError IndentationError TabError SystemError SystemExit TypeError ValueError UnicodeError "
    "UnicodeDecodeError UnicodeEncodeError ZeroDivisionError KeyboardInterrupt GeneratorExit Warning "
    # Python dunder / 特殊属性
    "__name__ __file__ __init__ __main__ __all__ __doc__ __future__ __slots__ __dict__ __class__ "
    "__repr__ __str__ __eq__ __hash__ __enter__ __exit__ __iter__ __next__ __len__ __getitem__ "
    "__setitem__ __delitem__ __contains__ __call__ __bool__ __annotations__ __path__ __version__ "
    "__author__ __package__ __spec__ __loader__ __builtins__ __debug__ __qualname__ __module__ "
    "__getattr__ __setattr__ __delattr__ __post_init__ __init_subclass__ "
    # Python 标准库模块名
    "abc argparse array asyncio base64 binascii bisect builtins calendar collections configparser "
    "contextlib copy csv ctypes dataclasses datetime decimal difflib enum errno faulthandler "
    "fractions functools gc getpass glob gzip hashlib heapq hmac html http importlib inspect io "
    "ipaddress itertools json keyword locale logging lzma math mimetypes multiprocessing operator os "
    "pathlib pickle pkgutil platform plistlib pprint profile pstats queue random re readline secrets "
    "select shlex shutil signal site smtplib socket socketserver sqlite3 ssl stat statistics string "
    "stringprep struct subprocess sys sysconfig tarfile tempfile textwrap threading time timeit token "
    "tokenize traceback tracemalloc types typing unicodedata unittest urllib uuid venv warnings wave "
    "weakref webbrowser xml zipfile zipimport zlib "
    # Python 标准库类型 / 容器
    "Path PurePath PosixPath PurePosixPath WindowsPath Counter defaultdict OrderedDict deque "
    "namedtuple ChainMap UserDict UserList UserString dataclass field Enum IntEnum Flag IntFlag auto "
    # Python 常用方法 / 属性（str / list / dict / set / file / pathlib / os / sys / time）
    "append clear copy extend insert pop popitem remove reverse setdefault sort update values add "
    "discard intersection isdisjoint issubset issuperset symmetric_difference union difference "
    "capitalize casefold center count encode endswith expandtabs find format_map index isalnum "
    "isalpha isascii isdecimal isdigit isidentifier islower isnumeric isprintable isspace istitle "
    "isupper join ljust lower lstrip maketrans partition removeprefix removesuffix replace rfind "
    "rindex rjust rpartition rsplit rstrip split splitlines startswith strip swapcase title translate "
    "upper zfill close fileno flush isatty read readable readline readlines seek seekable tell "
    "truncate writable write writelines read_text write_text read_bytes write_bytes as_posix exists "
    "expanduser glob group home is_absolute is_dir is_file is_symlink iterdir joinpath lchmod lstat "
    "mkdir name open owner parent parents parts relative_to rename resolve rglob rmdir samefile stat "
    "stem suffix suffixes symlink_to touch unlink with_name with_stem with_suffix cwd chmod absolute "
    "argv environ exit getcwd getenv getpid kill listdir makedirs path putenv removedirs scandir sep "
    "walk stderr stdin stdout version version_info executable platform modules maxsize getsizeof "
    "setrecursionlimit monotonic perf_counter process_time sleep strftime strptime time_ns "
    "monotonic_ns localtime gmtime mktime ctime asctime args kwargs items keys get error code "
    # Rust 标准类型 / 原生类型
    "Vec String Box Rc Arc RefCell Cell HashMap HashSet BTreeMap BTreeSet VecDeque Option Result "
    "Some Ok Err Cow PathBuf OsStr OsString CString CStr Duration Instant SystemTime Ordering "
    "PhantomData Pin Weak u8 u16 u32 u64 u128 usize i8 i16 i32 i64 i128 isize f32 f64 bool char "
    "std core alloc proc_macro prelude "
    # Rust std 宏 / 常用方法
    "println print eprintln eprint vec panic assert assert_eq assert_ne debug_assert debug_assert_eq "
    "writeln todo unimplemented unreachable matches dbg include_str include_bytes concat env stringify "
    "unwrap unwrap_or unwrap_or_else unwrap_or_default expect clone to_owned to_string as_bytes as_str "
    "as_ptr as_mut as_ref is_empty is_some is_none is_ok is_err push_str into_iter iter_mut collect "
    "fold for_each get_mut contains contains_key entry or_insert or_default values_mut extend drain "
    "resize capacity with_capacity into try_into try_from parse write_all read_to_string lines trim "
    "starts_with ends_with to_lowercase to_uppercase extend_from_slice sort_by sort_by_key dedup "
    "retain take last first rev enumerate chain product position rposition last_mut "
    # JS 全局对象 / 构造器 / 常用方法
    "console window document globalThis require module exports process Buffer null undefined NaN "
    "Infinity String Number Boolean Array Object Promise JSON Math Date Error RegExp Map Set WeakMap "
    "WeakSet Symbol BigInt Proxy Reflect Function parseInt parseFloat isNaN isFinite setTimeout "
    "setInterval clearTimeout clearInterval encodeURIComponent decodeURIComponent structuredClone "
    "fetch alert then catch finally push pop shift unshift slice splice concat trim toUpperCase "
    "toLowerCase indexOf includes forEach reduce some every getElementById querySelector "
    "querySelectorAll addEventListener "
).split())
# 命中的名字**一律跳过**（判定顺序：已登记 → 语言关键字 → 内建噪声）。
过滤名 = 语言关键字 | 内建噪声


class 库读不动(Exception):
    """规则库读不出来 —— fail-closed，绝不把空名册当「全未登记」用。"""


def 读已登记(根) -> set:
    """⇒ 库 `命名登记` 表的**全部名字**集合（判定「未登记」只认这一张表）。"""
    库件 = 表定义.库路径(根)
    if not Path(库件).is_file():
        raise 库读不动(f"规则库不在：{库件}（先跑 `python3 开发工具/信息核心/信息核心.py 建库`）")
    连接 = sqlite3.connect("file:%s?mode=ro" % 库件, uri=True)
    try:
        名字集 = {一行[0] for 一行 in 连接.execute("select 名字 from 命名登记")}
    except sqlite3.Error as 错误:
        raise 库读不动(f"规则库读不动：{错误}") from 错误
    finally:
        连接.close()
    return 名字集


def 抹跨行块(文本: str) -> str:
    """抹掉三引号串与 `/* */` 块注释，用等量换行占位 ⇒ **行号不漂**。"""
    for 规则 in 跨行块:
        文本 = 规则.sub(lambda 匹配: "\n" * 匹配.group(0).count("\n"), 文本)
    return 文本


def 剥行(一行: str) -> str:
    """剥掉单行串与行注释 ⇒ 只留「可能有标识符」的骨架（口径见模块 docstring）。"""
    一行 = 单行双引.sub('""', 一行)
    一行 = 单行单引.sub("''", 一行)
    一行 = 单行反引.sub("``", 一行)
    切 = 行注释.search(一行)
    return 一行[:切.start()] if 切 else 一行


def 是仓内(路径: Path) -> bool:
    """`路径` 是否落在**仓根之内**（仓根自身也算）—— 仓外路径一律不扫。"""
    try:
        路径.relative_to(仓根)
        return True
    except ValueError:
        return False


def 相对路径(路径: Path, 树根) -> str:
    """⇒ 仓根相对路径（正斜杠）；不在仓根下则退回树根相对，再退回绝对。"""
    for 基 in (仓根, Path(树根)):
        try:
            return 路径.resolve().relative_to(基.resolve()).as_posix()
        except ValueError:
            continue
    return 路径.resolve().as_posix()


def 候选文件(树根, 文件=None) -> list:
    """⇒ 待扫文件的绝对路径列表。给了 `文件` ⇒ 只那一个；否则走整棵树。"""
    if 文件:
        指定 = Path(文件)
        if not 指定.is_absolute():
            指定 = 仓根 / 指定
            if not 指定.is_file():
                指定 = Path(树根) / 文件
        return [指定] if 指定.is_file() else []
    结果 = []
    for 路径 in Path(树根).rglob("*"):
        if not 路径.is_file() or 路径.suffix not in 代码后缀:
            continue
        if any(段 in 跳过目录 for 段 in 路径.parts):
            continue
        if not 是仓内(路径.resolve()):
            continue
        结果.append(路径)
    return 结果


def 未登记名(树根, 文件=None) -> list[dict]:
    """扫代码里的标识符名，凡不在库 `命名登记` 表里的 ⇒ 判「未登记」。
    语言关键字与显式内建噪声名已先滤掉（两张名单见模块 docstring）。

    `树根`：扫描起点（一般为仓根）。`文件`：只扫那一个文件（**仓根相对路径**，正斜杠）；
    不给则扫整棵树。返回 `list[dict]`，每个 dict 至少三键 `{"名字", "文件", "行号"}`；
    同一 `(名字, 文件, 行号)` 只出一条，按 `(文件, 行号, 名字)` 排序。
    库读不动 ⇒ 抛 `库读不动`（fail-closed，不返回空表）。
    """
    已登记 = 读已登记(仓根)
    出 = {}
    for 路径 in 候选文件(树根, 文件):
        try:
            文本 = 抹跨行块(路径.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
        相对 = 相对路径(路径, 树根)
        for 序号, 一行 in enumerate(文本.splitlines(), 1):
            for 名 in 标识符.findall(剥行(一行)):
                if 名 in 已登记 or 名 in 过滤名:
                    continue
                出[(名, 相对, 序号)] = {"名字": 名, "文件": 相对, "行号": 序号}
    return sorted(出.values(), key=lambda 一条: (一条["文件"], 一条["行号"], 一条["名字"]))
