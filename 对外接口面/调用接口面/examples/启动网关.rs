//! 启动网关 —— **生产启动入口**（装配节点）。一条链，四步，一步不少
//! （形状与判据：`构建装配/上线切换/形状.md` §四）：
//!
//! ```text
//! 读 扩展装载/扩展根声明.json  →  扫扩展根 + 调接缝 GetPlatformInfo  →  递给 服务::绑定  →  起监听
//! ```
//!
//! # 为什么必须有这个节点（网关腿回执第 8 条）
//!
//! `服务::绑定` 要的**声明根由调用方注入**，而网关**自己去找声明就是跳层**
//! （`对外接口面/调用接口面/src/lib.rs` 缺口 4 的原话）。所以「谁读扩展根声明、谁调
//! `GetPlatformInfo`、谁把声明根递进去」必须有装配侧的一个节点承接 —— 就是本文件。
//! 它落在 `examples/`：**一个 example，不是新 workspace 成员** ⇒ 根 `Cargo.toml` /
//! `Cargo.lock` 一行不动。
//!
//! # 三条硬边界（README 第五节）在这里怎么成立
//!
//! 1. **底座不认识任何扩展**：本文件里没有任何扩展的名字、路径或特例分支 —— 扫到谁就是谁。
//! 2. **改一个扩展不用动底座**：加一个扩展 = 往扩展根里放一个目录，本文件一行不改。
//! 3. **扩展缺了底座照跑**：逐个试装，装不进的**剔除并报原因**，最终用剩下的声明根起服务。
//!
//! # 用法与两处破口
//!
//! `启动网关 [--声明根 <路径>] [--端口 <N>] [--静态根 <目录>]`。`--声明根` 默认
//! `扩展装载/扩展根声明.json`（相对**当前工作目录**）；`--端口` 不给就用契约默认端口，
//! 给 `0` 让 OS 分配（装载预检用）；`--静态根` 不给就用 `常量.rs` 的 `静态根`
//! （`前端呈现/网页应用`，同相对 cwd）—— 它是 `接口面形状.md` §五 的**托管目录**，
//! 与声明根同类：都是部署事实，由装配侧注入，网关不替它猜。
//! 实际端口打在 `监听 127.0.0.1:<端口>` 一行上 —— 上线切换靠它拿端口。
//!
//! `v1_loader::底座声明()` 走本 crate 的 **dev-dependency** 边（`Cargo.toml` 已如实登记那条破口：
//! 适配器没有再导出 `底座声明`）。**修法在适配器，不在本文件。**
use std::env;
use std::ffi::{CStr, CString, c_char, c_int, c_void};
use std::fs;
use std::path::{Path, PathBuf};
use v1_adapter::{适配器, 平台信息};
use v1_gateway::{启动失败, 服务};

// ════════════════════════════════════════════════════════════════════════════
// 接缝：dlopen / dlsym（零第三方依赖，直接声明 libc 的两个符号）
// ════════════════════════════════════════════════════════════════════════════

unsafe extern "C" {
    fn dlopen(路径: *const c_char, 模式: c_int) -> *mut c_void;
    fn dlsym(句柄: *mut c_void, 符号: *const c_char) -> *mut c_void;
    fn dlerror() -> *mut c_char;
}

/// `RTLD_NOW`：装载时把符号全部解析掉 —— 缺符号当场失败，不留到调用时才炸（macOS / Linux 都是 2）。
const RTLD_NOW: c_int = 2;
/// 可装载库文件的后缀：**按后缀找，不按名字找**（名字里会有扩展名，底座不许认名字）。
const 库后缀: [&str; 3] = [".dylib", ".so", ".dll"];

// ════════════════════════════════════════════════════════════════════════════
// 最小 JSON 读（只为读扩展根声明；不引第三方 crate）
// ════════════════════════════════════════════════════════════════════════════

/// 一个 JSON 值。`空` / `真` / `假` / `数` 本文件不用，但解析器必须认得它们 ——
/// 声明里多一个数就「读不了」，比多写四个变体贵得多。
#[allow(dead_code)]
enum 值 {
    空,
    真,
    假,
    数(f64),
    串(String),
    表(Vec<(String, 值)>),
    列(Vec<值>),
}

impl 值 {
    fn 取(&self, 键: &str) -> Option<&值> {
        match self {
            值::表(项) => 项.iter().find(|(名, _)| 名 == 键).map(|(_, 值)| 值),
            _ => None,
        }
    }
    fn 串(&self) -> Option<&str> {
        if let 值::串(文) = self { Some(文) } else { None }
    }
    fn 列(&self) -> Option<&[值]> {
        if let 值::列(项) = self { Some(项) } else { None }
    }
}

struct 读器<'a> {
    字节: &'a [u8],
    位: usize,
}

impl<'a> 读器<'a> {
    fn 新(文本: &'a str) -> Self {
        Self { 字节: 文本.as_bytes(), 位: 0 }
    }

    fn 跳空白(&mut self) {
        while self.字节.get(self.位).is_some_and(u8::is_ascii_whitespace) {
            self.位 += 1;
        }
    }

    fn 值(&mut self) -> Result<值, String> {
        self.跳空白();
        match self.字节.get(self.位) {
            None => Err("JSON 提前结束".into()),
            Some(b'{') => self.表(),
            Some(b'[') => self.列(),
            Some(b'"') => self.串().map(值::串),
            Some(b't') => self.字面("true", 值::真),
            Some(b'f') => self.字面("false", 值::假),
            Some(b'n') => self.字面("null", 值::空),
            Some(_) => self.数(),
        }
    }

    fn 字面(&mut self, 文: &str, 出: 值) -> Result<值, String> {
        if !self.字节[self.位..].starts_with(文.as_bytes()) {
            return Err(format!("第 {} 字节处不是合法 JSON 值", self.位));
        }
        self.位 += 文.len();
        Ok(出)
    }

    fn 表(&mut self) -> Result<值, String> {
        self.位 += 1; // '{'
        let mut 项 = Vec::new();
        self.跳空白();
        if self.字节.get(self.位) == Some(&b'}') {
            self.位 += 1;
            return Ok(值::表(项));
        }
        loop {
            self.跳空白();
            let 名 = self.串()?;
            self.跳空白();
            if self.字节.get(self.位) != Some(&b':') {
                return Err(format!("第 {} 字节处缺冒号", self.位));
            }
            self.位 += 1;
            项.push((名, self.值()?));
            self.跳空白();
            match self.字节.get(self.位) {
                Some(b',') => self.位 += 1,
                Some(b'}') => {
                    self.位 += 1;
                    return Ok(值::表(项));
                }
                _ => return Err(format!("第 {} 字节处缺逗号或右括号", self.位)),
            }
        }
    }

    fn 列(&mut self) -> Result<值, String> {
        self.位 += 1; // '['
        let mut 项 = Vec::new();
        self.跳空白();
        if self.字节.get(self.位) == Some(&b']') {
            self.位 += 1;
            return Ok(值::列(项));
        }
        loop {
            项.push(self.值()?);
            self.跳空白();
            match self.字节.get(self.位) {
                Some(b',') => self.位 += 1,
                Some(b']') => {
                    self.位 += 1;
                    return Ok(值::列(项));
                }
                _ => return Err(format!("第 {} 字节处缺逗号或右括号", self.位)),
            }
        }
    }

    fn 串(&mut self) -> Result<String, String> {
        if self.字节.get(self.位) != Some(&b'"') {
            return Err(format!("第 {} 字节处缺字符串", self.位));
        }
        self.位 += 1;
        let mut 出 = String::new();
        loop {
            match self.字节.get(self.位) {
                None => return Err("字符串没闭合".into()),
                Some(b'"') => {
                    self.位 += 1;
                    return Ok(出);
                }
                Some(b'\\') => {
                    self.位 += 1;
                    let 转 = self.字节.get(self.位).copied().unwrap_or(b'?');
                    self.位 += 1;
                    出.push(match 转 {
                        b'"' => '"',
                        b'\\' => '\\',
                        b'/' => '/',
                        b'b' => '\u{8}',
                        b'f' => '\u{c}',
                        b'n' => '\n',
                        b'r' => '\r',
                        b't' => '\t',
                        _ => '\u{fffd}',
                    });
                }
                Some(_) => {
                    let 余 = core::str::from_utf8(&self.字节[self.位..]).map_err(|_| "不是合法 UTF-8")?;
                    let 字 = 余.chars().next().ok_or("空字符")?;
                    出.push(字);
                    self.位 += 字.len_utf8();
                }
            }
        }
    }

    fn 数(&mut self) -> Result<值, String> {
        let 起 = self.位;
        while self
            .字节
            .get(self.位)
            .is_some_and(|字| 字.is_ascii_digit() || matches!(字, b'-' | b'+' | b'.' | b'e' | b'E'))
        {
            self.位 += 1;
        }
        core::str::from_utf8(&self.字节[起..self.位])
            .ok()
            .and_then(|文| 文.parse::<f64>().ok())
            .map(值::数)
            .ok_or_else(|| format!("第 {起} 字节处不是合法 JSON 值"))
    }
}

// ════════════════════════════════════════════════════════════════════════════
// 扫扩展根（怎么扫 = 扩展根声明的「扫描」段；本文件不写死任何扩展名）
// ════════════════════════════════════════════════════════════════════════════

/// 取一个目录下的直接子目录，**按名字排序**（装载顺序即依赖序，不许随文件系统飘）。
fn 子目录(目录: &Path) -> Vec<PathBuf> {
    let Ok(读) = fs::read_dir(目录) else { return Vec::new() };
    let mut 出: Vec<PathBuf> = 读
        .filter_map(|项| 项.ok())
        .map(|项| 项.path())
        .filter(|路| 路.is_dir())
        .collect();
    出.sort();
    出
}

/// 是不是可装载库文件（按后缀找，不按名字找）。
fn 是可装载库(路: &Path) -> bool {
    let 名 = 路.file_name().and_then(|名| 名.to_str());
    路.is_file() && 名.is_some_and(|名| 库后缀.iter().any(|尾| 名.ends_with(尾)))
}

/// 一个扩展目录 → 它的接缝指针。三步缺一步即「不是扩展」：① 目录内**恰好一个**可装载库文件；
/// ② 取符号 `GetPlatformInfo`；③ 调它拿静态常量指针。
fn 取扩展声明(扩展目录: &Path) -> Result<&'static 平台信息, String> {
    let 库文件: Vec<PathBuf> = fs::read_dir(扩展目录)
        .map_err(|错| format!("读不到目录：{错}"))?
        .filter_map(|项| 项.ok())
        .map(|项| 项.path())
        .filter(|路| 是可装载库(路))
        .collect();
    if 库文件.len() != 1 {
        return Err(format!("可装载库文件 {} 个（要求恰好 1 个）", 库文件.len()));
    }
    let 路 = &库文件[0];
    let 路径串 =
        CString::new(路.as_os_str().as_encoded_bytes()).map_err(|_| "库路径含 NUL".to_owned())?;
    // SAFETY: 路径串是 NUL 结尾的合法 C 串；句柄只装载不释放（本进程活到服务停）。
    let 句柄 = unsafe { dlopen(路径串.as_ptr(), RTLD_NOW) };
    if 句柄.is_null() {
        return Err(format!("dlopen 失败：{}", 最近错误()));
    }
    // SAFETY: 句柄非空（上面已挡）；符号名是 ASCII 静态串。
    let 符号 = unsafe { dlsym(句柄, c"GetPlatformInfo".as_ptr()) };
    if 符号.is_null() {
        return Err(format!("取不到接缝符号 GetPlatformInfo（{}）", 最近错误()));
    }
    // SAFETY: 接缝形状由 `边界协议.md` §二 冻结：`const 平台信息* GetPlatformInfo(void)`。
    let 取平台信息: extern "C" fn() -> *const 平台信息 = unsafe { core::mem::transmute(符号) };
    let 指针 = 取平台信息();
    if 指针.is_null() {
        return Err("GetPlatformInfo 返回空指针".to_owned());
    }
    // SAFETY: 接缝规定「返回静态常量指针，终生有效；调用方不得释放、不得修改」
    // ⇒ 解引用得到 `'static` 只读引用是契约本身担保的事，不是本文件的假设。
    Ok(unsafe { &*指针 })
}

fn 最近错误() -> String {
    // SAFETY: dlerror 返回静态或线程局部的 NUL 结尾串（或空）。
    let 指针 = unsafe { dlerror() };
    if 指针.is_null() {
        return "无 dlerror 说明".to_owned();
    }
    // SAFETY: 非空 ⇒ 按 POSIX 是 NUL 结尾可读串。
    unsafe { CStr::from_ptr(指针) }.to_string_lossy().into_owned()
}

/// 失败 → 一句可读的原因（**不吞段位**：失败是结构化的，这里只做转写，不做判断）。
///
/// 这里**不解构** `装载失败` 的变体：解构要写出「载入 + 左括号」这个形状，而判据 ⑪ 数的正是「调用内核入口 载入 的处数」（`一键验证.py` 的模式），会被数成第二条腿（实测撞到）。
fn 说清启动失败(错: &启动失败) -> String {
    match 错 {
        启动失败::装载(错) => format!("装载失败：{错:?}"),
        启动失败::绑定(错) => format!("端口绑不上：{错}"),
    }
}

fn 取值(名: &str) -> Option<String> {
    let 参: Vec<String> = env::args().collect();
    参.iter().position(|项| 项 == 名).and_then(|位| 参.get(位 + 1).cloned())
}

fn main() -> Result<(), String> {
    let 声明根路径 =
        PathBuf::from(取值("--声明根").unwrap_or_else(|| "扩展装载/扩展根声明.json".to_owned()));
    let 端口: Option<u16> = match 取值("--端口") {
        Some(文) => Some(文.parse::<u16>().map_err(|_| format!("--端口 不是整数：{文}"))?),
        None => None,
    };
    // §五 的静态托管根：不给就用契约侧常量（相对 cwd），给了就注入 ——
    // 与 `--声明根` 同一口径（都是部署事实，装配侧说了算）。
    let 静态根 = 取值("--静态根");

    // ── 第一步：读扩展根声明 ────────────────────────────────────────────────
    let 文本 = fs::read_to_string(&声明根路径)
        .map_err(|错| format!("读不到扩展根声明 {}：{错}", 声明根路径.display()))?;
    let 根 = 读器::新(&文本)
        .值()
        .map_err(|错| format!("扩展根声明不是合法 JSON：{错}"))?;
    let 种类 = 根
        .取("种类")
        .and_then(|值| 值.列())
        .ok_or_else(|| "扩展根声明缺 `种类` 段".to_owned())?;
    println!(
        "扩展根声明 {} · 种类 {} 类",
        fs::canonicalize(&声明根路径)
            .map(|路| 路.display().to_string())
            .unwrap_or_else(|_| 声明根路径.display().to_string()),
        种类.len()
    );

    // ── 第二步：扫扩展根 + 调接缝 GetPlatformInfo ──────────────────────────
    let mut 候选: Vec<&'static 平台信息> = vec![v1_loader::底座声明()];
    let mut 装上的: Vec<String> = Vec::new();
    let mut 剔除的: Vec<(String, String)> = Vec::new();
    for 类 in 种类 {
        let Some(目录) = 类.取("目录").and_then(|值| 值.串()) else {
            continue;
        };
        let 目录 = PathBuf::from(目录);
        if !目录.is_dir() {
            println!("跳过 {}：目录不存在", 目录.display());
            continue;
        }
        for 子 in 子目录(&目录) {
            let 落点 = 子.display().to_string();
            match 取扩展声明(&子) {
                Err(原因) => 剔除的.push((落点, 原因)),
                Ok(声明) => {
                    // 试装：拿**同一个** `适配器::装载声明根` 走一遍（与 `服务::绑定` 内部
                    // 用的是同一条装载路，不另写一套）。装得上才算这份声明根的一份。
                    let mut 试 = 候选.clone();
                    试.push(声明);
                    match 适配器::装载声明根(&试) {
                        Ok(_) => {
                            候选.push(声明);
                            装上的.push(落点);
                        }
                        Err(错) => 剔除的.push((落点, 说清启动失败(&启动失败::装载(错)))),
                    }
                }
            }
        }
    }
    println!(
        "扫到扩展 {} 个（装上 {} · 剔除 {}）",
        装上的.len() + 剔除的.len(),
        装上的.len(),
        剔除的.len()
    );
    for 落点 in &装上的 {
        println!("  装上 {落点}");
    }
    for (落点, 原因) in &剔除的 {
        println!("  剔除 {落点}：{原因}");
    }

    // ── 第三步：递给 服务::绑定（静态托管根给了就注入，见 `接口面形状.md` §五）────
    let 服务 = match 端口 {
        Some(号) => 服务::绑定(&候选, 号),
        None => 服务::绑定默认端口(&候选),
    }
    .map_err(|错| format!("起服务失败：{}", 说清启动失败(&错)))?;
    let 服务 = match 静态根 {
        Some(根) => 服务.托管静态根(根),
        None => 服务,
    };

    // ── 第四步：起监听（这一行是给上线切换读的：它靠它拿实际端口）──────────
    println!("监听 127.0.0.1:{}", 服务.端口());
    println!("静态托管根 {}（`GET /` 从这里回 index.html）", 服务.静态根().display());
    println!(
        "声明根 {} 份 · 能力清单 {} 条",
        服务.适配器().已装载声明数(),
        服务.适配器().能力清单().len()
    );
    let _ = 服务.跑();
    Ok(())
}
