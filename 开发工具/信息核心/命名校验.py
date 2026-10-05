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
  · 单行串只认「同一行内成对的引号」⇒ 行内引号**不成对**（如 `'a"b`）仍会错配 ⇒ 可能**误报**
    （把串内容当标识符）或**漏报**（把真名连同串一起吃掉）；串内 `\\.` 转义已认。
  · JS 模板串里的 `${…}` 插值整串被剥 ⇒ 插值内的真名漏报。
  · `.rs` 的 `#[attr]` 与 `.js/.ts` 的 `#私有名` 按注释截断 ⇒ 那些位置真名漏报（属性里几乎全是
    stdlib / 派生宏名，对本项目的命名口径本就是噪声，按注释截断是**有意的取舍**）。
  · 只按**词形**取名，不区分「定义 / 引用」⇒ 未登记的**引用名**（跨文件引用 · 标准库 API ·
    第三方 API）都会进结果；是否合格由 `命名登记` 表决定（本模块不替它判）。
  · **面**（定义面 / 形参面 / 局部面）由 `判面` **启发式**判，不是真解析器 —— 只作参考。

**已修的假阳性（2026-10-05 两轮收敛）**：① **串前缀残留** —— `f"…"` `b"…"` `r"…"` `rb"…"` `c"…"`
原先只吃引号内容、把前缀留成单字母假名（实测 `f` 1483 · `b` 287 · `r` 248）⇒ 现在**前缀连引号
一起吃**（含 `b'…'` 字节字面量 · Rust `c"…"` C 串）；② **生命周期 vs 字符字面量** —— 现在**先吃
字符字面量** `'(?:\\.|[^'\\\n])'`、**再吃生命周期** `'ident`，且**生命周期只对 `.rs` 生效**
（Python 的 `r'…'` / `'…\n…'` 原先被生命周期规则先吃掉开头引号 ⇒ 串内容整段外泄）；③ **原始串** ——
吃 `r#"…"#`（含多 `#`，可跨行）与带前缀的 `r"…"` / `rb'…'`；④ **串内转义** —— 裸串规则原先不认
`\\.`，`"\"未闭合\r\n…"` 被从转义引号处截断 ⇒ 现在串规则**认转义**；⑤ **块注释误判** —— `/* */`
原先对 `.py` 也生效，`契约声明/*.json` 这种**串内** `/*` 被当注释开头、后续真代码整段被吃 ⇒ 现在
`/* */` **只对 `.rs` / JS 系生效**。另修 `.py` 的 `a // b` 被当行注释截断（`b` 漏报）⇒ **行注释按
后缀分**（`.py` 只认 `#`，`.rs` 认 `//` 与 `#`，JS 系认 `//`）。

**剩余已知噪声 / 漏报（名单管不到的那部分，如实写明）**：
  · 标准库 / 第三方 API 名**未穷举**：名单只收常见名，未收录的仍会报出（如 `annotations`）。
  · 单字母 / 泛用局部名（`x` `y` `cx` `cy`）不滤 —— 无法与业务名区分。
  · 过滤名单是**显式**的：若某个**业务名恰与名单同形**（如 `code` `name` `path` `type`），会被
    **漏报** —— 名单可审、可增删，这是显式名单的代价。

连库方式与 `记规则.py` 一致：库路径走 `表定义.库路径(仓根)`，**不硬写库文件名**。
**读**：`未登记名` 只读。**写**：只有 `落库` 一个写口（写 `命名出现` + `命名登记` 的 `待改名`
行）—— 不碰已有 `合格` 行 · 不碰表结构 · 不碰源码里的任何标识符（改名是下一轮的事）。
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
# ★ 三引号串**先按「行首或空白 + 前缀」的锚吃**，再让不锚的规则兜底 —— 代码里含 `"""` 的**串字面量**
#   （如 `re.compile(r'[a-f]{0,3}("""|\'\'\')')`）会让不锚的规则从那里一路错配，实测漏下 230 条。
跨行块 = (
    re.compile(r'(?<![A-Za-z0-9_])[rR](#+)"[\s\S]*?"\1'),
    re.compile(r'(?:^|\s)[rbufRBUF]{0,2}"""[\s\S]*?"""', re.M),
    re.compile(r"(?:^|\s)[rbufRBUF]{0,2}'''[\s\S]*?'''", re.M),
    re.compile(r'(?<![A-Za-z0-9_])[rbufRBUF]{0,2}"""[\s\S]*?"""'),
    re.compile(r"(?<![A-Za-z0-9_])[rbufRBUF]{0,2}'''[\s\S]*?'''"),
)
# ★ `/* */` **只对 `.rs` / JS 系**生效：Python 没有块注释，而串内的 `/*`（如 `契约声明/*.json`）
#   会让它从那里一路吃到下一个 `*/`，把中间的真代码整段抹掉。
跨行块块注释 = re.compile(r"/\*[\s\S]*?\*/")
跨行块全 = 跨行块 + (跨行块块注释,)
# 逐行剥的串。★ 顺序有讲究，不能重排：① 带前缀字符字面量 `b'x'`（若排在裸字符字面量之后，
#   前缀 `b` 会留下 —— 实测 `b` 113 条）；② 裸字符字面量 `'x'`；③ **生命周期 `'a` 只对 `.rs`**；
#   ④ 带前缀串（前缀连同引号一起吃，否则留下 `f`/`b`/`r`/`c` 假名）；⑤ 裸串（**认 `\\.` 转义**）。
单行串 = (
    re.compile(r"(?<![A-Za-z0-9_])[rbufcRBUF]{1,2}'(?:\\.|[^'\\\n])'"),
    re.compile(r"'(?:\\.|[^'\\\n])'"),
    re.compile(r'(?<![A-Za-z0-9_])[rbufcRBUF]{1,2}"(?:\\.|[^"\\\n])*"'),
    re.compile(r"(?<![A-Za-z0-9_])[rbufcRBUF]{1,2}'(?:\\.|[^'\\\n])*'"),
    re.compile(r"(?<![A-Za-z0-9_])[rbufcRBUF]{1,2}`[^`\n]*`"),
    re.compile(r'"(?:\\.|[^"\\\n])*"'),
    re.compile(r"'(?:\\.|[^'\\\n])*'"),
    re.compile(r"`[^`\n]*`"),
)
# 生命周期 `'a` —— **只对 `.rs` 生效**（Python 的 `r'…'` 会被它先吃掉开头引号 ⇒ 串内容外泄）。
生命周期 = re.compile(r"'[A-Za-z_][A-Za-z0-9_]*")
Rust规则 = 单行串[:2] + (生命周期,) + 单行串[2:]
# 数字字面量（十六 / 二 / 八进制）—— 不抹会把 `0x5E9A` 的尾巴切成假名 `x5E9A`（实测 264 条）。
数字字面量 = re.compile(r"(?<![A-Za-z0-9_])0[xX][0-9A-Fa-f_]+|0[bB][01_]+|0[oO][0-7_]+")
# 行注释**按语言分**：`.py` 的 `//` 是整除运算符（原先在 `a // b` 处截断 ⇒ `b` 漏报）；`.rs` 的
# `#[…]` 是属性，属性里几乎全是 stdlib / 派生宏名（`derive` `test` `cfg` `Clone` …）⇒ 按注释截断
# 是**有意的取舍**（实测放开后 `test` 518 · `derive` 129 · `Clone` 123 三条噪声凭空长出来）。
行注释表 = {
    ".rs": re.compile(r"//|#"),
    ".py": re.compile(r"#"),
    ".js": re.compile(r"//"),
    ".ts": re.compile(r"//"),
    ".vue": re.compile(r"//"),
}


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
# **不是穷尽清单**：未收录的标准库 / 第三方 API 名仍会进结果（见模块 docstring「剩余已知噪声」）。
内建噪声 = frozenset((
    "abs aiter all anext any ascii bin bool breakpoint bytearray bytes callable chr classmethod compile complex delattr dict dir "  # Python 内建函数 / 类型 / 常量
    "divmod enumerate eval exec filter float format frozenset getattr globals hasattr hash help hex id input int isinstance issubclass "
    "iter len list locals map max memoryview min next object oct open ord pow print property range repr reversed round set setattr "
    "slice sorted staticmethod str sum super tuple type vars zip __import__ self cls None True False "
    "BaseException Exception ArithmeticError AssertionError AttributeError BufferError EOFError ImportError ModuleNotFoundError "  # Python 异常
    "LookupError IndexError KeyError MemoryError NameError NotImplementedError OSError IOError FileNotFoundError PermissionError "
    "ProcessLookupError TimeoutError ReferenceError RuntimeError RecursionError StopIteration StopAsyncIteration SyntaxError "
    "IndentationError TabError SystemError SystemExit TypeError ValueError UnicodeError UnicodeDecodeError UnicodeEncodeError "
    "ZeroDivisionError KeyboardInterrupt GeneratorExit Warning "
    "__name__ __file__ __init__ __main__ __all__ __doc__ __future__ __slots__ __dict__ __class__ __repr__ __str__ __eq__ __hash__ "  # Python dunder / 特殊属性
    "__enter__ __exit__ __iter__ __next__ __len__ __getitem__ __setitem__ __delitem__ __contains__ __call__ __bool__ __annotations__ "
    "__path__ __version__ __author__ __package__ __spec__ __loader__ __builtins__ __debug__ __qualname__ __module__ __getattr__ "
    "__setattr__ __delattr__ __post_init__ __init_subclass__ "
    "abc argparse array asyncio base64 binascii bisect builtins calendar collections configparser contextlib copy csv ctypes "  # Python 标准库模块名
    "dataclasses datetime decimal difflib enum errno faulthandler fractions functools gc getpass glob gzip hashlib heapq hmac html "
    "http importlib inspect io ipaddress itertools json keyword locale logging lzma math mimetypes multiprocessing operator os pathlib "
    "pickle pkgutil platform plistlib pprint profile pstats queue random re readline secrets select shlex shutil signal site smtplib "
    "socket socketserver sqlite3 ssl stat statistics string stringprep struct subprocess sys sysconfig tarfile tempfile textwrap "
    "threading time timeit token tokenize traceback tracemalloc types typing unicodedata unittest urllib uuid venv warnings wave "
    "weakref webbrowser xml zipfile zipimport zlib "
    "Path PurePath PosixPath PurePosixPath WindowsPath Counter defaultdict OrderedDict deque namedtuple ChainMap UserDict UserList "  # Python 标准库类型 / 容器
    "UserString dataclass field Enum IntEnum Flag IntFlag auto "
    "append clear copy extend insert pop popitem remove reverse setdefault sort update values add discard intersection isdisjoint "  # Python 常用方法 / 属性（str / list / dict / set / file / pathlib / os / sys / time）
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
    "Vec String Box Rc Arc RefCell Cell HashMap HashSet BTreeMap BTreeSet VecDeque Option Result Some Ok Err Cow PathBuf OsStr "  # Rust 标准类型 / 原生类型
    "OsString CString CStr Duration Instant SystemTime Ordering PhantomData Pin Weak u8 u16 u32 u64 u128 usize i8 i16 i32 i64 i128 "
    "isize f32 f64 bool char std core alloc proc_macro prelude "
    "println print eprintln eprint vec panic assert assert_eq assert_ne debug_assert debug_assert_eq writeln todo unimplemented "  # Rust std 宏 / 常用方法
    "unreachable matches dbg include_str include_bytes concat env stringify unwrap unwrap_or unwrap_or_else unwrap_or_default expect "
    "clone to_owned to_string as_bytes as_str as_ptr as_mut as_ref is_empty is_some is_none is_ok is_err push_str into_iter iter_mut "
    "collect fold for_each get_mut contains contains_key entry or_insert or_default values_mut extend drain resize capacity "
    "with_capacity into try_into try_from parse write_all read_to_string lines trim starts_with ends_with to_lowercase to_uppercase "
    "extend_from_slice sort_by sort_by_key dedup retain take last first rev enumerate chain product position rposition last_mut "
    "console window document globalThis require module exports process Buffer null undefined NaN Infinity String Number Boolean Array "  # JS 全局对象 / 构造器 / 常用方法
    "Object Promise JSON Math Date Error RegExp Map Set WeakMap WeakSet Symbol BigInt Proxy Reflect Function parseInt parseFloat isNaN "
    "isFinite setTimeout setInterval clearTimeout clearInterval encodeURIComponent decodeURIComponent structuredClone fetch alert then "
    "catch finally push pop shift unshift slice splice concat trim toUpperCase toLowerCase indexOf includes forEach reduce some every "
    "getElementById querySelector querySelectorAll addEventListener "
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


def 抹跨行块(文本: str, 后缀: str = "") -> str:
    """抹掉跨行串 / 块注释，用等量换行占位 ⇒ **行号不漂**。`/* */` 只对非 `.py` 生效。"""
    for 规则 in (跨行块 if 后缀 == ".py" else 跨行块全):
        文本 = 规则.sub(lambda 匹配: "\n" * 匹配.group(0).count("\n"), 文本)
    return 文本


def 剥行(一行: str, 后缀: str = "") -> str:
    """剥掉单行串 / 生命周期 / 行注释 ⇒ 只留「可能有标识符」的骨架（口径见模块 docstring）。

    `后缀` 决定两处口径：生命周期（**只 `.rs`**）与行注释（`.py` 的 `#` · `.rs` 的 `//` 与
    `#[…]` 属性 · JS 系的 `//`）。
    """
    for 规则 in (Rust规则 if 后缀 == ".rs" else 单行串):
        一行 = 规则.sub(" ", 一行)
    切 = 行注释表.get(后缀, 行注释表[".js"]).search(一行)
    return 数字字面量.sub(" ", 一行[:切.start()] if 切 else 一行)


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
        后缀 = 路径.suffix
        try:
            文本 = 抹跨行块(路径.read_text(encoding="utf-8", errors="ignore"), 后缀)
        except OSError:
            continue
        相对 = 相对路径(路径, 树根)
        for 序号, 一行 in enumerate(文本.splitlines(), 1):
            for 名 in 标识符.findall(剥行(一行, 后缀)):
                if 名 in 已登记 or 名 in 过滤名:
                    continue
                出[(名, 相对, 序号)] = {"名字": 名, "文件": 相对, "行号": 序号}
    return sorted(出.values(), key=lambda 一条: (一条["文件"], 一条["行号"], 一条["名字"]))


# ════════════════════════════════════════════════════════════════════════════
# 落库：扫描结果 → `命名出现`（明细） + `命名登记`（未登记名补一行 `待改名`）
# 本模块其余部分**只读**；这一段是唯一的写口，且**不碰**已有 `合格` 行 · 表结构 · 源码标识符。
# ════════════════════════════════════════════════════════════════════════════

# 判「面」用的定义关键字（启发式，见 `判面`）。
定义关键字 = re.compile(r"\b(?:fn|def|struct|enum|trait|impl|class|type|mod|const|static"
                    r"|interface|namespace|function|var|let|pub)\b")
# 名紧跟定义关键字 ⇒ 定义面。
定义位 = re.compile(r"(?:\bfn|\bdef|\bstruct|\benum|\btrait|\bimpl|\bclass|\btype|\bmod|\bconst"
                r"|\bstatic|\binterface|\bnamespace|\bfunction|\bvar|\blet|\bpub)\s+")


def 判面(骨架: str, 名: str) -> str:
    """尽力判「名在这一行属于哪个面」⇒ 定义面 / 形参面 / 局部面（**启发式，不是真解析器**）。

    名紧跟定义关键字 ⇒ 定义面；该行有定义关键字且名落在第一个 `(` 之后 ⇒ 形参面；其余 ⇒ 局部面。
    """
    if 定义位.search(骨架) and re.search(re.escape(名) + r"\b", 骨架[定义位.search(骨架).end():]):
        return "定义面"
    左 = 骨架.find("(")
    if 左 >= 0 and 定义关键字.search(骨架[:左]) and 名 in 骨架[左:]:
        return "形参面"
    return "局部面"


def 扫出现(树根) -> list:
    """扫全树 ⇒ 每条出现一条记录（四键：`名字` / `文件` / `行号` / `面`）。

    与 `未登记名` 的两处不同：**不滤已登记的名**（`命名出现` 是「名字出现在哪」的明细表，
    已登记的名也要记）；同一行同名的重复引用只出一条。关键字与内建噪声照旧跳过。
    """
    出 = []
    for 路径 in 候选文件(树根):
        后缀 = 路径.suffix
        try:
            文本 = 抹跨行块(路径.read_text(encoding="utf-8", errors="ignore"), 后缀)
        except OSError:
            continue
        相对 = 相对路径(路径, 树根)
        for 序号, 一行 in enumerate(文本.splitlines(), 1):
            骨架 = 剥行(一行, 后缀)
            for 名 in dict.fromkeys(标识符.findall(骨架)):
                if 名 in 过滤名:
                    continue
                出.append({"名字": 名, "文件": 相对, "行号": 序号, "面": 判面(骨架, 名)})
    return 出


def 拆核心词(名: str, 核心词表) -> tuple:
    """按核心词做**贪心最长匹配**切段 ⇒ `(命中词表, 残段)`。判「能不能用核心词组合表达」。"""
    词表 = sorted(核心词表, key=len, reverse=True)
    命中, 残, 位 = [], "", 0
    while 位 < len(名):
        for 词 in 词表:
            if 名.startswith(词, 位):
                命中.append(词)
                位 += len(词)
                break
        else:
            残 += 名[位]
            位 += 1
    return 命中, 残


def 待改名语义(名: str, 核心词表) -> str:
    """⇒ 该名的 `待改名` 语义栏文本：能拆成 ≥2 个核心词就给建议，否则交人工。"""
    命中, 残 = 拆核心词(名, 核心词表)
    if len(命中) >= 2 and not 残:
        return f"原名{名}，建议改为「{'·'.join(命中)}」（核心词 {'+'.join(命中)} 组合）"
    return f"原名{名}，保留但需确认是否够清晰"


def 落库(树根, 干跑: bool = False) -> dict:
    """跑一遍全树扫描并落库 ⇒ 读数。

    写两处：`命名出现` **全量重写**（它是扫描的派生明细，不重写会留旧行）；
    `命名登记` **只新增**未登记名的 `待改名` 行（`insert or replace` 也只落这些新名，
    **不动**任何已有 `合格` 行）。`干跑=True` 只算不写。
    """
    记录 = 扫出现(树根)
    连接 = sqlite3.connect(str(表定义.库路径(仓根)))
    try:
        已登记 = {一行[0] for 一行 in 连接.execute("select 名字 from 命名登记")}
        例外 = {一行[0] for 一行 in 连接.execute("select 名字 from 命名例外")}
        核心词表 = {一行[0] for 一行 in 连接.execute("select 名字 from 命名字典")}
        新名 = sorted({一条["名字"] for 一条 in 记录} - 已登记 - 例外)
        计数 = {"扫描出现": len(记录), "涉及名字": len({一条["名字"] for 一条 in 记录}),
               "新增待改名": len(新名)}
        if 干跑:
            return 计数
        连接.executemany(
            "insert or replace into 命名登记(名字, 语义, 模式, 来源, 状态) values(?,?,?,?,?)",
            [(名, 待改名语义(名, 核心词表), "对象+说明", "新定义", "待改名") for 名 in 新名])
        连接.execute("delete from 命名出现")
        连接.executemany(
            "insert into 命名出现(名字, 文件路径, 行号, 面) values(?,?,?,?)",
            [(一条["名字"], 一条["文件"], 一条["行号"], 一条["面"]) for 一条 in 记录
             if 一条["名字"] not in 例外])
        连接.commit()
        计数["出现行数"] = 连接.execute("select count(*) from 命名出现").fetchone()[0]
        return 计数
    finally:
        连接.close()
