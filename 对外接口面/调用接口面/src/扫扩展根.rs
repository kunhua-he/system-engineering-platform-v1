//! 扫扩展根 —— 「一个扩展根声明里有哪些可装载候选」的**唯一实现**。
//!
//! 从 `examples/启动网关/扫根.rs`（子目录排序 · 按后缀找可装载库）与
//! `examples/启动网关/接缝.rs`（`dlopen` + 取接缝 `GetPlatformInfo`）**搬来**：
//! 现在**启动装配（example）与运行期装载（`POST /接口/生命周期` 动作=装载）同读这一份**
//! （台账 237「不重启网关载入新扩展」）。搬完 example 只转调。
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

/// 可装载库文件的后缀：**按后缀找，不按名字找**（名字里会有扩展名，底座不许认名字）。
pub const 库后缀: [&str; 3] = [".dylib", ".so", ".dll"];

/// 取一个目录下的直接子目录，**按名字排序**（装载顺序即依赖序，不许随文件系统飘）。
pub fn 子目录(目录: &Path) -> Vec<PathBuf> {
    let Ok(读器) = fs::read_dir(目录) else { return Vec::new() };
    let mut 输出缓冲: Vec<PathBuf> = 读器
        .filter_map(|一项| 一项.ok())
        .map(|一项| 一项.path())
        .filter(|路径| 路径.is_dir())
        .collect();
    输出缓冲.sort();
    输出缓冲
}

/// 是不是可装载库文件（按后缀找，不按名字找）。
pub fn 是可装载库(路径: &Path) -> bool {
    let 名称 = 路径.file_name().and_then(|名称| 名称.to_str());
    路径.is_file() && 名称.is_some_and(|名称| 库后缀.iter().any(|尾部| 名称.ends_with(尾部)))
}

// ════════════════════════════════════════════════════════════════════════════
// 二 接缝：`dlopen` / `dlsym`（零第三方依赖，直接声明 libc 的两个符号）
// ════════════════════════════════════════════════════════════════════════════

unsafe extern "C" {
    fn dlopen(路径: *const c_char, 模式: c_int) -> *mut c_void;
    fn dlsym(句柄: *mut c_void, 符号: *const c_char) -> *mut c_void;
    fn dlerror() -> *mut c_char;
}

/// `RTLD_NOW`：装载时把符号全部解析掉 —— 缺符号当场失败，不留到调用时才炸（macOS / Linux 都是 2）。
pub const RTLD_NOW: c_int = 2;

/// 一个扩展目录 → 它的接缝指针。三步缺一步即「不是扩展」：① 目录内**恰好一个**可装载库文件；
/// ② 取符号 `GetPlatformInfo`；③ 调它拿静态常量指针。
pub fn 取扩展声明(扩展目录: &Path) -> Result<&'static 平台信息, String> {
    let 库文件: Vec<PathBuf> = fs::read_dir(扩展目录)
        .map_err(|错误| format!("读不到目录：{错误}"))?
        .filter_map(|一项| 一项.ok())
        .map(|一项| 一项.path())
        .filter(|路径| 是可装载库(路径))
        .collect();
    if 库文件.len() != 1 {
        return Err(format!("可装载库文件 {} 个（要求恰好 1 个）", 库文件.len()));
    }
    let 路径 = &库文件[0];
    let 路径串 =
        CString::new(路径.as_os_str().as_encoded_bytes()).map_err(|_| "库路径含 NUL".to_owned())?;
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
    /// 要扫的目录：只含 `可装载件 = true` 的种类[].目录（相对路径原样）。
    pub 目录s: Vec<PathBuf>,
}

/// 读**扩展根声明文本** → 要扫哪些目录。
///
/// **候选面收窄到 `可装载件 = true`**（与装配侧 `构建装配/上线切换/构建制品/扩展.py::可装载种类`
/// 走**同一条规则**）：只有 `可装载件 = true` 的种类（支持库）的直接子目录才是可装载件候选；
/// 模块（组装件）与技能（声明/工作流）不编可装载库、不 `dlopen`，不进候选。
///
/// `可装载件` **缺键 / 非布尔 ⇒ fail-closed 指路，不给默认值**：默认 `true` 会把旁路放回来，
/// 默认 `false` 会把支持库静默漏掉。
pub fn 读声明根(文本: &str) -> Result<声明根扫描, String> {
    let 根目录 = crate::协议解析::解析(文本)
        .map_err(|错误| format!("扩展根声明不是合法 JSON：{}", 错误.说明))?;
    let 种类 = 根目录
        .取成员("种类")
        .and_then(|待处理值| 待处理值.取数组())
        .ok_or_else(|| "扩展根声明缺 `种类` 段".to_owned())?;
    let mut 目录s = Vec::new();
    for 类别 in 种类 {
        let 类名 = 类别.取成员("种类").and_then(|待处理值| 待处理值.取文本()).unwrap_or("?");
        let 可装载 = match 类别.取成员("可装载件") {
            Some(crate::协议值::协议值::逻辑真) => true,
            Some(crate::协议值::协议值::逻辑假) => false,
            _ => {
                return Err(format!(
                    "扩展根声明的 种类[{类名}] 缺 `可装载件`（或不是布尔）。\n  \
                     这个键决定「这一类的直接子目录要不要当可装载件候选」（支持库 true · \
                     模块/技能 false）；不给默认值——默认 true 会把旁路放回来，默认 false \
                     会把支持库静默漏掉。见 扩展装载/扩展根声明.json 的种类[].可装载件"
                ));
            }
        };
        if !可装载 {
            continue;
        }
        let Some(目录) = 类别.取成员("目录").and_then(|待处理值| 待处理值.取文本()) else {
            continue;
        };
        目录s.push(PathBuf::from(目录));
    }
    Ok(声明根扫描 { 种类数: 种类.len(), 目录s })
}
