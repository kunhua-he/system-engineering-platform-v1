//! 扫扩展根 —— 「一个扩展根声明里有哪些可装载候选」的**唯一实现**。
//!
//! 从 `examples/启动网关/扫根.rs`（子目录排序 · 按后缀找可装载库）与
//! `examples/启动网关/接缝.rs`（`dlopen` + 取接缝 `GetPlatformInfo`）**搬来**：
//! 现在**启动装配（example）与运行期装载（`POST /接口/生命周期` 动作=装载）同读这一份**
//! （`项目文档/设计文档/扩展装载与开发标准.md` §六：热载入已现场验证）。搬完 example 只转调。
//!
//! 这里**不写死任何扩展名**：扫到谁就是谁（README 第五节「底座不认识任何扩展」）。
//!
//! # 库的生命周期
//!
//! `dlopen` 之后**不 `dlclose`**：库一旦载入不再卸载（卸载走生命周期通知 `2001`，
//! 不是 `dlclose`）—— 取接缝要 `&'static`，句柄得活到进程结束。

use std::ffi::{CStr, CString, c_char, c_int, c_void};
use std::fs;
use std::path::{Path, PathBuf};

use v1_adapter::平台信息;

// ════════════════════════════════════════════════════════════════════════════
// 一 扫根：一个扩展根目录里有哪些可装载库
// ════════════════════════════════════════════════════════════════════════════

/// 本件**不持有**任何后缀 —— 后缀集的唯一权威是 `扩展装载/后缀表.json`。
/// 与 `读声明根` 同一条既有路：**调用方读文件、把文本递进来**（本件不由它找路径、
/// 不认目录），后缀集由 `读后缀表` 从那份文本解出。

/// 取一个目录下的直接子目录，**按名字排序**（装载顺序即依赖序，不许随文件系统飘）。
pub fn 列子目录(扩展根目录: &Path) -> Vec<PathBuf> {
    let Ok(目录读器) = fs::read_dir(扩展根目录) else { return Vec::new() };
    let mut 输出缓冲: Vec<PathBuf> = 目录读器
        .filter_map(|目录项| 目录项.ok())
        .map(|目录项| 目录项.path())
        .filter(|路径| 路径.is_dir())
        .collect();
    输出缓冲.sort();
    输出缓冲
}

/// 后缀表解出的「本平台要扫的制品后缀」：种类 → 制品后缀（权威 = `扩展装载/后缀表.json`）。
pub struct 后缀表 {
    /// 判候选用：全部 `三类扩展[].制品后缀` 的并集。
    pub 制品后缀: Vec<String>,
    /// 种类名 → 制品后缀（`三类扩展` 逐条原样；`制品后缀` 是它的并集）。
    /// 判「这一份制品属于哪个种类」用 —— 模块读法要的是**模块那一项**，不是并集。
    pub 分类: Vec<(String, String)>,
}

impl 后缀表 {
    /// 按种类名取制品后缀（`None` = 本后缀表里没有这个种类）。
    pub fn 取种类后缀(&self, 种类名: &str) -> Option<&str> {
        self.分类.iter().find(|(名称, _)| 名称 == 种类名).map(|(_, 后缀项)| 后缀项.as_str())
    }
}

/// 读**后缀表文本** → 制品后缀集（与 `读声明根` 同形：文本进来、`Result` 出去、fail-closed）。
///
/// 复用 `crate::协议解析::解析协议值`（与 `读声明根` 同一份解析器，不另写）。取
/// `三类扩展[].制品后缀`，逐项非空文本；**不认任何名字**（README §五 硬边界 1）。
/// **空集即 `Err`**：后缀集是空的 ⇒ 没有候选可扫，不许静默当「扫到 0 个扩展」。
pub fn 读后缀表(源文本: &str) -> Result<后缀表, String> {
    let 根目录 = crate::协议解析::解析协议值(源文本)
        .map_err(|错误| format!("后缀表不是合法 JSON：{}", 错误.说明文字))?;
    let 扩展种类 = 根目录
        .取成员("三类扩展")
        .and_then(|待处理值| 待处理值.取数组())
        .ok_or_else(|| "后缀表缺 `三类扩展` 段".to_owned())?;
    let mut 后缀列表: Vec<String> = Vec::new();
    let mut 分类: Vec<(String, String)> = Vec::new();
    for 种类项 in 扩展种类 {
        let Some(后缀项) = 种类项.取成员("制品后缀").and_then(|待处理值| 待处理值.取文本()) else {
            continue;
        };
        let 种类名 = 种类项.取成员("种类").and_then(|待处理值| 待处理值.取文本()).unwrap_or_default();
        后缀列表.push(后缀项.to_owned());
        分类.push((种类名.to_owned(), 后缀项.to_owned()));
    }
    if 后缀列表.is_empty() {
        return Err("后缀表的 `三类扩展[].制品后缀` 一个都没有（空后缀集 ⇒ 没有候选可扫）".to_owned());
    }
    Ok(后缀表 { 制品后缀: 后缀列表, 分类 })
}

/// 是不是本平台要扫的制品（按后缀找，不按名字找 —— 名字里会有扩展名，底座不许认名字）。
pub fn 是制品(路径: &Path, 后缀表: &后缀表) -> bool {
    let 名称 = 路径.file_name().and_then(|名称| 名称.to_str());
    路径.is_file() && 名称.is_some_and(|名称| 后缀表.制品后缀.iter().any(|尾部| 名称.ends_with(尾部)))
}

// ════════════════════════════════════════════════════════════════════════════
// 二 接缝：`dlopen` / `dlsym`（零第三方依赖，直接声明 libc 的两个符号）
// ════════════════════════════════════════════════════════════════════════════

unsafe extern "C" {
    fn dlopen(路径: *const c_char, 模式: c_int) -> *mut c_void;
    fn dlsym(句柄: *mut c_void, 符号名: *const c_char) -> *mut c_void;
    fn dlerror() -> *mut c_char;
}

/// `RTLD_NOW`：装载时把符号全部解析掉 —— 缺符号当场失败，不留到调用时才炸（macOS / Linux 都是 2）。
pub const RTLD_NOW: c_int = 2;

/// 一个扩展目录 → 它的接缝指针。四步缺一步即「不是扩展」：
/// ① 目录内**恰好一个**本平台制品（后缀按 `扩展装载/后缀表.json` 找，**不按名字找**）；
/// ② **按容器解开制品**（`契约声明/src/契约声明/容器.rs::解包`，唯一 codec），取**能力码段**；
///    技能/模块没有本机机器码（能力码段空）⇒ 不进 `dlopen`（两种载入方式的分岔点：
///    它们分别由 `模块制品::取模块接口说明` / 技能本体段那条读法处理）；本函数只认
///    能力码段非空的支持库制品，其余报因剔除；
/// ③ 把能力码段字节落一份**仓外缓存件**（运行数据根的缓存类 · `v1_dataroot`），
///    对它 `dlopen`（机器码只能是真文件）；
/// ④ 取符号 `GetPlatformInfo` · 调它拿静态常量指针。
pub fn 取扩展声明(
    扩展目录: &Path,
    后缀表: &后缀表,
    缓存根目录: &Path,
) -> Result<&'static 平台信息, String> {
    let 制品文件: Vec<PathBuf> = fs::read_dir(扩展目录)
        .map_err(|错误| format!("读不到目录：{错误}"))?
        .filter_map(|目录项| 目录项.ok())
        .map(|目录项| 目录项.path())
        .filter(|路径| 是制品(路径, 后缀表))
        .collect();
    if 制品文件.len() != 1 {
        return Err(format!("本平台制品 {} 个（要求恰好 1 个）", 制品文件.len()));
    }
    // ②③：解包取能力码段 → 落仓外缓存件（模块 / 技能没有码段 ⇒ 这一步报因，不进 dlopen）。
    let 落盘路径 = v1_adapter::装载件缓存::解包到缓存(&制品文件[0], 缓存根目录)?;
    let 路径串 =
        CString::new(落盘路径.as_os_str().as_encoded_bytes()).map_err(|_| "库路径含 NUL".to_owned())?;
    // SAFETY: 路径串是 NUL 结尾的合法 C 串；句柄只装载不释放（本进程活到服务停）。
    let 句柄 = unsafe { dlopen(路径串.as_ptr(), RTLD_NOW) };
    if 句柄.is_null() {
        return Err(format!("dlopen 失败：{}", 最近错误()));
    }
    // SAFETY: 句柄非空（上面已挡）；符号名是 ASCII 静态串。
    let 符号指针 = unsafe { dlsym(句柄, c"GetPlatformInfo".as_ptr()) };
    if 符号指针.is_null() {
        return Err(format!("取不到接缝符号 GetPlatformInfo（{}）", 最近错误()));
    }
    // SAFETY: 接缝形状由 `边界协议.md` §二 冻结：`const 平台信息* GetPlatformInfo(void)`。
    let 取平台信息: extern "C" fn() -> *const 平台信息 = unsafe { core::mem::transmute(符号指针) };
    let 指针 = 取平台信息();
    if 指针.is_null() {
        return Err("GetPlatformInfo 返回空指针".to_owned());
    }
    // SAFETY: 接缝规定「返回静态常量指针，终生有效；调用方不得释放、不得修改」
    // ⇒ 解引用得到 `'static` 只读引用是契约本身担保的事，不是本文件的假设。
    Ok(unsafe { &*指针 })
}

/// 最近一次 `dlopen` / `dlsym` 的错误说明（没有就给一句兜底）。
pub fn 最近错误() -> String {
    // SAFETY: dlerror 返回静态或线程局部的 NUL 结尾串（或空）。
    let 指针 = unsafe { dlerror() };
    if 指针.is_null() {
        return "无 dlerror 说明".to_owned();
    }
    // SAFETY: 非空 ⇒ 按 POSIX 是 NUL 结尾可读串。
    unsafe { CStr::from_ptr(指针) }.to_string_lossy().into_owned()
}

// ════════════════════════════════════════════════════════════════════════════
// 三 声明根 → 要扫哪些目录（启动装配与运行期装载同一条规则）
// ════════════════════════════════════════════════════════════════════════════

/// 扩展根声明读出来的「要扫哪些目录」。
pub struct 声明根扫描 {
    /// 声明里 `种类[]` 的条数（装配侧打印「种类 N 类」用）。
    pub 种类数: usize,
    /// 要扫的目录：**全部** 种类[].扩展落点（相对路径原样）。
    pub 目录s: Vec<PathBuf>,
}

/// 读**扩展根声明文本** → 要扫哪些目录。
///
/// **扫描面 = 全部 `种类[]`**：三个种类（支持库 · 模块 · 技能）**都有制品**，只是载入方式不同
/// （支持库取能力码段 · 模块/技能只解析段），所以没有哪一类该被排除在候选外。
/// 候选资格由「该子目录里有没有本种类的制品」判（`扩展装载/后缀表.json`），不由声明里的开关判。
pub fn 读声明根(源文本: &str) -> Result<声明根扫描, String> {
    let 根目录 = crate::协议解析::解析协议值(源文本)
        .map_err(|错误| format!("扩展根声明不是合法 JSON：{}", 错误.说明文字))?;
    let 扩展种类 = 根目录
        .取成员("种类")
        .and_then(|待处理值| 待处理值.取数组())
        .ok_or_else(|| "扩展根声明缺 `种类` 段".to_owned())?;
    let mut 目录s = Vec::new();
    for 种类项 in 扩展种类 {
        let Some(扩展根目录) = 种类项.取成员("扩展落点").and_then(|待处理值| 待处理值.取文本()) else {
            continue;
        };
        目录s.push(PathBuf::from(扩展根目录));
    }
    Ok(声明根扫描 { 种类数: 扩展种类.len(), 目录s })
}
