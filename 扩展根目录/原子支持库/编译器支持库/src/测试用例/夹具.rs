//! 测试 · 夹具 —— 各用例共用的声明目录读取 · 样例数据槽 · 静态串读取。
//!
//! 从 `src/lib.rs` 的 `#[cfg(test)] mod 测试` 搬来（那是 crate 路由，本件是它的一个关注点）；
//! 夹具函数体一字不改，只把取址改成 `crate::…` / `super::…`。

use std::path::{Path, PathBuf};

use v1_contract::声明数据::{类型标签_0004, 类型标签_0005};
use v1_contract::{数据槽, 平台信息};

use crate::容器;

use super::最小JSON;

pub(crate) fn 声明目录() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).to_path_buf()
}

pub(crate) fn 读JSON件(相对: &str) -> 最小JSON::JSON值 {
    let 路径 = 声明目录().join(相对);
    let 文本 = std::fs::read_to_string(&路径)
        .unwrap_or_else(|错误| panic!("读不到 {}：{错误}", 路径.display()));
    最小JSON::解析JSON值(&文本).unwrap_or_else(|| panic!("{} 不是合法 JSON", 路径.display()))
}

/// 造一条**类型 2（系统信息）**的合法容器：段名用实测 GBK 字节。
pub(crate) fn 样例容器() -> 容器::容器 {
    const GBK系统信息段: &[u8] =
        &[0xCF, 0xB5, 0xCD, 0xB3, 0xD0, 0xC5, 0xCF, 0xA2, 0xB6, 0xCE];
    容器::容器 {
        段表: vec![容器::容器段 {
            头: 容器::段头 {
                校验和: 0x0A06CD88,
                段类型: 容器::段类型::系统信息.取号值(),
                名称区: [0; 27],
                段名: GBK系统信息段.to_vec(),
            },
            数据: vec![1, 0, 0, 0],
        }],
    }
}

/// 造一个「引用字节集」的数据槽（不交出所有权：调用方保留 Vec）。
pub(crate) fn 字节集槽(字节: &[u8]) -> 数据槽 {
    数据槽::指针(类型标签_0005.into(), 字节.as_ptr() as u64, 字节.len() as u64, false)
}

/// 造一个「引用文本」的数据槽（不交出所有权：调用方保留 `&str`）。
pub(crate) fn 文本槽(文本: &str) -> 数据槽 {
    数据槽::指针(类型标签_0004.into(), 文本.as_ptr() as u64, 文本.len() as u64, false)
}

/// 一段真的程序文本（原生格式：UTF-8 · LF · 缩进 4 个半角空格）。
pub(crate) const 真程序文本: &str = ".版本 2\n.子程序 _启动子程序, 整数型\n    返回 (0)\n";

/// 从返回槽取回字节集。
///
/// # Safety
/// 数据槽必须是本模块的执行函数刚写出的「引用 + 交出所有权」槽。
pub(crate) unsafe fn 取返回字节(数据槽: &数据槽) -> Vec<u8> {
    assert_eq!(数据槽.类型标签, 类型标签_0005, "返回槽该是字节集");
    assert!(数据槽.是否引用(), "返回槽该是引用");
    // SAFETY: 由调用方保证数据槽是刚写出的引用槽。
    unsafe { core::slice::from_raw_parts(数据槽.值 as *const u8, 数据槽.长度 as usize) }.to_vec()
}

/// 按「交出所有权」的契约释放返回槽里的字节集（测试里必须做，否则泄漏）。
///
/// # Safety
/// 数据槽必须来自本模块执行函数写出的字节集槽。
pub(crate) unsafe fn 释放返回字节(数据槽: &数据槽) {
    if 数据槽.类型标签 == 类型标签_0005 && 数据槽.是否引用() && 数据槽.值 != 0 {
        let 片段 = core::ptr::slice_from_raw_parts_mut(数据槽.值 as *mut u8, 数据槽.长度 as usize);
        // SAFETY: 由调用方保证该指针来自 Box<[u8]>，且只释放一次。
        drop(unsafe { Box::from_raw(片段) });
    }
}

/// 读一个静态 NUL 结尾串（不含 NUL）。扫到上限仍无 NUL ⇒ `None`（**不 panic、不越界长扫**）。
///
/// 口径与 `运行内核/装载入口/src/读数.rs::读串` **同一份**（上限 `契约串上限` = 4096、
/// 空指针 / 越界给 `None`）。本 crate 是扩展，只依赖底座公布的契约、不依赖底座内部节点
/// （`Cargo.toml`）⇒ 同名同口径地本地留一份，**不另立无上限的弱口径**。
///
/// # Safety
/// 指针要么为空，要么指向至少 `契约串上限` 字节可读的静态数据。
pub(crate) unsafe fn 读串(指针: *const u8) -> Option<&'static [u8]> {
    const 契约串上限: usize = 4096;
    if 指针.is_null() {
        return None;
    }
    let mut 长度 = 0usize;
    while 长度 < 契约串上限 {
        // SAFETY: 由调用方保证 指针..指针+契约串上限 可读。
        if unsafe { *指针.add(长度) } == 0 {
            // SAFETY: 已扫到 NUL，前 长 字节可读且不再变动（静态数据）。
            return Some(unsafe { core::slice::from_raw_parts(指针, 长度) });
        }
        长度 += 1;
    }
    None
}

/// 取声明的错误段位表切片。
pub(crate) fn 读段位表切片(声明: &'static 平台信息) -> &'static [u32] {
    assert!(声明.错误段位表.项数 > 0 && !声明.错误段位表.项表.is_null());
    // SAFETY: 项数 > 0 且项表非空，指向静态只读数组。
    unsafe { core::slice::from_raw_parts(声明.错误段位表.项表, 声明.错误段位表.项数 as usize) }
}
