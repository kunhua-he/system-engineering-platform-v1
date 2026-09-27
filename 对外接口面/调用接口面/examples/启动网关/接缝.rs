//! 启动网关 · 接缝 —— `dlopen` / `dlsym`（零第三方依赖，直接声明 libc 的两个符号）
//! 与「一个扩展目录 → 它的接缝指针」。
//!
//! 从 `examples/启动网关.rs` 搬来（那是装配入口，本件是它的一个关注点；**纯搬家**）。

use std::ffi::{CStr, CString, c_char, c_int, c_void};
use std::fs;
use std::path::Path;

use v1_adapter::平台信息;

use crate::扫根::是可装载库;

unsafe extern "C" {
    fn dlopen(路径: *const c_char, 模式: c_int) -> *mut c_void;
    fn dlsym(句柄: *mut c_void, 符号: *const c_char) -> *mut c_void;
    fn dlerror() -> *mut c_char;
}

/// `RTLD_NOW`：装载时把符号全部解析掉 —— 缺符号当场失败，不留到调用时才炸（macOS / Linux 都是 2）。
pub(crate) const RTLD_NOW: c_int = 2;

/// 一个扩展目录 → 它的接缝指针。三步缺一步即「不是扩展」：① 目录内**恰好一个**可装载库文件；
/// ② 取符号 `GetPlatformInfo`；③ 调它拿静态常量指针。
pub(crate) fn 取扩展声明(扩展目录: &Path) -> Result<&'static 平台信息, String> {
    let 库文件: Vec<std::path::PathBuf> = fs::read_dir(扩展目录)
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

pub(crate) fn 最近错误() -> String {
    // SAFETY: dlerror 返回静态或线程局部的 NUL 结尾串（或空）。
    let 指针 = unsafe { dlerror() };
    if 指针.is_null() {
        return "无 dlerror 说明".to_owned();
    }
    // SAFETY: 非空 ⇒ 按 POSIX 是 NUL 结尾可读串。
    unsafe { CStr::from_ptr(指针) }.to_string_lossy().into_owned()
}
