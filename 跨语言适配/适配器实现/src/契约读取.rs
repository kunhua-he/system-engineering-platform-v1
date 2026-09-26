//! 形状翻译的零件（读侧）—— 现读声明的静态字段，**不缓存、不另存**。
//!
//! 契约规定一切串都是静态只读的 NUL 结尾串、一切表段都指向静态只读数组 ——
//! 与 `装载入口` / `统一注册表` 的前提同一份。
//!
//! 为什么单列一个文件：`lib.rs` 是路由（声明子模块 · 再导出公开面 · 零实现），
//! 单个源文件 ≤ 400 行是硬规矩（`开发规范.md` 第六节）。

use crate::{参数摘要, 错误码摘要};
use v1_contract::平台信息;
use v1_registry::命令信息;

/// 契约串的读取上限（防呆：扫不到 NUL 就当读不出，不去 `from_raw_parts` 一个巨数）。
pub(crate) const 契约串上限: usize = 4096;

/// 读一个契约串（静态只读 NUL 结尾）。空指针 / 超上限仍无 NUL ⇒ 空串。
///
/// # Safety
///
/// `指针` 要么为空，要么指向**至少 `契约串上限` 字节可读**的静态数据。
pub(crate) unsafe fn 读契约串(指针: *const u8) -> String {
    if 指针.is_null() {
        return String::new();
    }
    let mut 长 = 0usize;
    while 长 < 契约串上限 {
        // SAFETY: 由调用方保证 指针..指针+契约串上限 可读。
        if unsafe { *指针.add(长) } == 0 {
            break;
        }
        长 += 1;
    }
    if 长 == 契约串上限 {
        return String::new();
    }
    // SAFETY: 已扫到 NUL，前 长 字节可读且不再变动（静态数据）。
    let 字节 = unsafe { core::slice::from_raw_parts(指针, 长) };
    String::from_utf8_lossy(字节).into_owned()
}

/// 命令的参数表 → 参数摘要（**行序原样保留**：调用方按这个顺序填值）。
pub(crate) fn 读参数表(命令: &命令信息) -> Vec<参数摘要> {
    if 命令.参数个数 == 0 || 命令.参数表.is_null() {
        return Vec::new();
    }
    // SAFETY: 契约保证 参数表 指向静态只读数组，长度 = 参数个数
    //（`注册表::建表` 已核过「项数 > 0 却给空项表」这一条）。
    let 表 = unsafe { core::slice::from_raw_parts(命令.参数表, 命令.参数个数 as usize) };
    表.iter()
        .map(|参| 参数摘要 {
            // SAFETY: 契约保证一切串都是静态只读 NUL 结尾串。
            名称: unsafe { 读契约串(参.名称) },
            类型标签: 参.类型标签,
            状态位: 参.状态位,
            默认值: 参.默认值,
        })
        .collect()
}

/// 声明的错误码表 → 错误码摘要。
///
/// 用**声明自己的**错误码表（底座那份就是生成物 `错误码信息表`），不另存一份表。
pub(crate) fn 读错误码表(声明: &平台信息) -> Vec<错误码摘要> {
    // 按字段取值，不搬整个 `表段`：`表段<T>` 只在 `T: Copy` 时才 `Copy`，而 `错误码信息`
    // 带裸指针、不是 `Copy`（与 `统一注册表::切片` 同一理由）。
    let 项数 = 声明.错误码表.项数;
    let 项表 = 声明.错误码表.项表;
    if 项数 == 0 || 项表.is_null() {
        return Vec::new();
    }
    // SAFETY: 契约保证 错误码表 指向静态只读数组。
    let 表 = unsafe { core::slice::from_raw_parts(项表, 项数 as usize) };
    表.iter()
        .map(|码| 错误码摘要 {
            码: 码.码,
            // SAFETY: 契约保证一切串都是静态只读 NUL 结尾串。
            名称: unsafe { 读契约串(码.名称) },
            // SAFETY: 同上。
            说明: unsafe { 读契约串(码.说明) },
            可重试: 码.可重试 != 0,
            可自愈: 码.可自愈 != 0,
            需人工: 码.需人工 != 0,
        })
        .collect()
}
