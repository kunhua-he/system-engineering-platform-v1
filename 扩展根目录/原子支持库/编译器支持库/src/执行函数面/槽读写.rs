//! 槽读写 —— 入参从 `数据槽` 取、结果写回返回槽的五个口。
//!
//! 从 `src/lib.rs` 搬来（那是路由：声明子模块 · 再导出公开面 · 零实现）；四个函数的
//! 签名、判死条件与 SAFETY 注释**一字不改**；`写文本` 是后来新增的第五个口（1108 回显文本
//! 的返回方向，与 `写字节集` 同形，只换类型标签）。

use v1_contract::数据槽;
use v1_contract::声明数据::{类型标签_0004, 类型标签_0005, 类型标签_4294967295};

/// 从参数表第 `位置` 个槽取字节集。`None` = 槽形状不可用（类型标签不是字节集 / 引用地址为空）。
///
/// # Safety
///
/// 调用方保证 `参数表` 指向 `参数个数` 个按契约填好的可读槽。
pub(crate) unsafe fn 取字节集(参数个数: u32, 参数表: *const 数据槽, 读游标: u32) -> Option<Vec<u8>> {
    if 读游标 >= 参数个数 || 参数表.is_null() {
        return None;
    }
    // SAFETY: 由调用方保证 参数表 至少 参数个数 个槽可读，且 位置 < 参数个数。
    let 数据槽 = unsafe { &*参数表.add(读游标 as usize) };
    if 数据槽.类型标签 != 类型标签_0005 {
        return None;
    }
    if 数据槽.是否空() {
        return Some(Vec::new());
    }
    if !数据槽.是否引用() {
        return None;
    }
    let 数据指针 = 数据槽.槽值 as *const u8;
    if 数据指针.is_null() {
        return None;
    }
    // SAFETY: 契约保证「引用」槽的 值..值+长度 可读。
    Some(unsafe { core::slice::from_raw_parts(数据指针, 数据槽.槽字节长度 as usize) }.to_vec())
}

/// 把字节集写进返回槽：**所有权交出**（接收方负责释放）。类型标签 = 字节集。
///
/// # Safety
///
/// 调用方保证 `返回槽` 可写。
pub(crate) unsafe fn 写字节集(返回槽: *mut 数据槽, 字节: Vec<u8>) {
    let 槽字节长度 = 字节.len() as u64;
    let 数据指针 = Box::into_raw(字节.into_boxed_slice()) as *const u8;
    // SAFETY: 由调用方保证 返回槽 可写。
    unsafe { *返回槽 = 数据槽::指针(类型标签_0005, 数据指针 as u64, 槽字节长度, true) };
}

/// 把结构化错误码写进返回槽：类型标签 = 错误（`u32::MAX`），值 = 码。
/// **不是字符串、不是 panic。**
///
/// # Safety
///
/// 调用方保证 `返回槽` 可写。
pub(crate) unsafe fn 写错误槽(返回槽: *mut 数据槽, 错误码: u32) {
    // SAFETY: 由调用方保证 返回槽 可写。
    unsafe { *返回槽 = 数据槽::内联槽(类型标签_4294967295, 错误码 as u64, 0) };
}

/// 从参数表第 `位置` 个槽取文本。`None` = 槽形状不可用。
///
/// 三处判死（都算 `参数槽不符`）：类型标签不是文本（4）；是引用槽但地址为空；
/// 引用字节不是合法 UTF-8（契约「文本 = UTF-8」，见 `接口面形状.md` §三）。
///
/// **类型标签先判**（与 `取字节集` 同一条规矩）：类型标签 0 的空槽是「这一位没填」，
/// 不是「空文本」—— 空文本要写成类型标签 4 的槽（带 `空` 标志，或长度 0）。
///
/// # Safety
///
/// 调用方保证 `参数表` 指向 `参数个数` 个按契约填好的可读槽。
pub(crate) unsafe fn 取文本(参数个数: u32, 参数表: *const 数据槽, 读游标: u32) -> Option<String> {
    if 读游标 >= 参数个数 || 参数表.is_null() {
        return None;
    }
    // SAFETY: 由调用方保证 参数表 至少 参数个数 个槽可读，且 位置 < 参数个数。
    let 数据槽 = unsafe { &*参数表.add(读游标 as usize) };
    if 数据槽.类型标签 != 类型标签_0004 {
        return None;
    }
    // 空文本：空文件也必须切出一枚零宽的文件结束（`语言面.rs` J1）。
    if 数据槽.是否空() {
        return Some(String::new());
    }
    if !数据槽.是否引用() {
        return None;
    }
    let 数据指针 = 数据槽.槽值 as *const u8;
    if 数据指针.is_null() {
        return None;
    }
    // SAFETY: 契约保证「引用」槽的 值..值+长度 可读。
    let 字节 = unsafe { core::slice::from_raw_parts(数据指针, 数据槽.槽字节长度 as usize) };
    core::str::from_utf8(字节).ok().map(str::to_owned)
}

/// 把文本写进返回槽：**所有权交出**（接收方负责释放）。类型标签 = 文本（4）。
///
/// 与 [`写字节集`] 同一条口径（`Box<[u8]>` 交出一块堆内存，长度逐字写进槽），只换标签：
/// 契约「文本 = UTF-8」由调用方保证 —— 本函数收的是 `String`，它天然是合法 UTF-8。
///
/// # Safety
///
/// 调用方保证 `返回槽` 可写。
pub(crate) unsafe fn 写文本(返回槽: *mut 数据槽, 文本内容: String) {
    let 字节 = 文本内容.into_bytes();
    let 槽字节长度 = 字节.len() as u64;
    let 数据指针 = Box::into_raw(字节.into_boxed_slice()) as *const u8;
    // SAFETY: 由调用方保证 返回槽 可写。
    unsafe { *返回槽 = 数据槽::指针(类型标签_0004, 数据指针 as u64, 槽字节长度, true) };
}
