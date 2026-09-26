//! 读数零件：静态只读串 / 号段表 → 切片。
//!
//! 判定六步与载入都从契约主结构的裸指针里取值，取法只有这一份。
//! 这里**只做形状与越界防呆**，不判归属、不判自洽（那是 `声明校验` 的事）。

use v1_contract::{号段, 表段};

/// 标识串字节数：32 位十六进制（不含结尾 NUL）。
pub(crate) const 标识串字节数: usize = 32;

/// 一张号段表的项数上限（防呆：超过就当表段形状不可用，避免拿巨数去 `from_raw_parts`）。
pub(crate) const 号段表上限: usize = 256;

/// 读一个 NUL 结尾的串，最多读 `上限` 字节。空指针 / 超上限仍无 NUL ⇒ `None`。
///
/// # Safety
///
/// 调用方保证 `指针` 要么为空，要么指向**至少 `上限` 字节可读**的静态数据
/// （契约规定：一切串都是静态只读的 NUL 结尾串）。
pub(crate) unsafe fn 读串(指针: *const u8, 上限: usize) -> Option<&'static [u8]> {
    if 指针.is_null() {
        return None;
    }
    let mut 长 = 0usize;
    while 长 < 上限 {
        // SAFETY: 由调用方保证 指针..指针+上限 可读。
        if unsafe { *指针.add(长) } == 0 {
            // SAFETY: 已扫到 NUL，前 长 字节可读且不再变动（静态数据）。
            return Some(unsafe { core::slice::from_raw_parts(指针, 长) });
        }
        长 += 1;
    }
    None
}

/// 标识串形状：恰好 32 位十六进制字符。
pub(crate) fn 是合法标识串(串: &[u8]) -> bool {
    串.len() == 标识串字节数 && 串.iter().all(|字节| 字节.is_ascii_hexdigit())
}

/// 号段表 → 切片（判定的合法性由 `判号段表` 负责；此处项数 0 或项表空一律给空切片）。
pub(crate) fn 号段切片(表: 表段<号段>) -> &'static [号段] {
    if 表.项数 == 0 || 表.项表.is_null() || 表.项数 as usize > 号段表上限 {
        return &[];
    }
    // SAFETY: 契约保证号段表指向静态只读数组；项数 > 0 且项表非空。
    unsafe { core::slice::from_raw_parts(表.项表, 表.项数 as usize) }
}

/// 号段表 → 段表。项数 0 或项表空 ⇒ 空（`登记` 用；判定的合法性由 `判号段表` 负责）。
pub(crate) fn 读号段表(表: 表段<号段>) -> Vec<号段> {
    if 表.项数 == 0 || 表.项表.is_null() || 表.项数 as usize > 号段表上限 {
        return Vec::new();
    }
    // SAFETY: 契约保证号段表指向静态只读数组；项数 > 0 且项表非空。
    unsafe { core::slice::from_raw_parts(表.项表, 表.项数 as usize) }.to_vec()
}
