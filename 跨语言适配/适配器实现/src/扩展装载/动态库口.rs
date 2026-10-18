//! 动态库口 —— `dlopen` / `dlsym` / `dlerror` 三个 libc 符号的**唯一声明处**。
//!
//! # 为什么抽成一件
//!
//! 本仓零第三方依赖 ⇒ 动态装载只能直接声明 libc 那几个符号。声明两处就是**两套**：
//! `工作进程.rs` 是**支持库那条腿**（取 `GetPlatformInfo`）、`模块执行体装载.rs` 是
//! **模块那条腿**（取 `v1_module_exec`）。同一类东西出现两处 ⇒ 抽节点管它
//! （`AGENTS.md` §十二「重复错误就抽节点」）。
//!
//! 本件**只声明符号与那一句错误说明**，不含任何扫描 / 后缀表 / 声明根 / 制品逻辑 ——
//! 那些各腿各的，不许往这里堆。

use core::ffi::{CStr, c_char, c_int, c_void};

unsafe extern "C" {
    pub(crate) fn dlopen(路径: *const c_char, 模式: c_int) -> *mut c_void;
    pub(crate) fn dlsym(句柄: *mut c_void, 符号名: *const c_char) -> *mut c_void;
    pub(crate) fn dlerror() -> *mut c_char;
}

/// `RTLD_NOW`：装载时把符号全部解析掉 —— 缺符号当场失败，不留到调用时才炸。
pub(crate) const RTLD_NOW: c_int = 2;

/// 最近一次 `dlopen` / `dlsym` 的错误说明（没有就给一句兜底）。
pub(crate) fn 最近装载错误() -> String {
    // SAFETY: dlerror 返回静态或线程局部的 NUL 结尾串（或空）。
    let 指针 = unsafe { dlerror() };
    if 指针.is_null() {
        return String::from("dlopen/dlsym 未给出原因");
    }
    // SAFETY: 非空 ⇒ 按 POSIX 是 NUL 结尾可读串。
    unsafe { CStr::from_ptr(指针) }.to_string_lossy().into_owned()
}
