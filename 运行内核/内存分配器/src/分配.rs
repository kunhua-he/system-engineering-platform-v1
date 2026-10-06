//! 分配 —— `分配器` 与它的两本账。
//!
//! 源出 `lib.rs`（拆件依据：`项目文档/开发规范/开发规范.md` 第六节「入口零实现」），**逐字搬家**。

use std::alloc::{alloc_zeroed, dealloc, Layout};
use std::collections::{HashMap, HashSet};

use v1_contract::声明数据::{分配对齐, 单次分配上限};

use crate::形状::{分配错误, 释放错误};

/// 单一跨边界分配器。
///
/// 状态显式持有，不落进程级全局（多实例安全）。
/// 账本两本：
/// - `活块`：地址 → 长度，当前尚未释放的块；
/// - `已释放`：曾经交出、且已被释放的地址，用来把「重复释放」与「外来地址」分开。
pub struct 分配器 {
    活块: HashMap<u64, u64>,
    已释放: HashSet<u64>,
}

impl 分配器 {
    pub fn 构造() -> Self {
        Self { 活块: HashMap::new(), 已释放: HashSet::new() }
    }

    /// 分配 `字节长度` 字节，返回地址。
    ///
    /// 失败一律走 `Result`，不 panic：`0` 字节 → [`分配错误::零长度`]；
    /// 超过 [`单次分配上限`] → [`分配错误::超上限`]；底层拿不到内存 → [`分配错误::内存不足`]。
    /// 成功返回的地址一定非 0，且已记账。
    pub fn 分配内存块(&mut self, 字节长度: u64) -> Result<u64, 分配错误> {
        if 字节长度 == 0 {
            return Err(分配错误::零长度);
        }
        if 字节长度 > 单次分配上限 {
            return Err(分配错误::超上限 { 请求: 字节长度, 上限: 单次分配上限 });
        }
        // 走到这里：1 <= 字节长度 <= u32::MAX，对齐固定 16。
        // 若目标平台的 usize 装不下（32 位下 size + align - 1 溢出），按超上限处理。
        let 内存布局 = Layout::from_size_align(字节长度 as usize, 分配对齐 as usize)
            .map_err(|_| 分配错误::超上限 { 请求: 字节长度, 上限: 单次分配上限 })?;
        // SAFETY: 布局已校验且非零长度，alloc_zeroed 对合法布局是安全的。
        // 用 alloc_zeroed 而非 alloc：交出去的内存先清零，跨语言读到的不是垃圾，
        // 确定性优先（README 第二节「要求确定性」）。
        let 指针 = unsafe { alloc_zeroed(内存布局) };
        if 指针.is_null() {
            return Err(分配错误::内存不足);
        }
        let 块地址 = 指针 as u64;
        self.活块.insert(块地址, 字节长度);
        // 地址可能被底层复用：重新交出后就不再是"已释放"。
        self.已释放.remove(&块地址);
        Ok(块地址)
    }

    /// 释放。
    ///
    /// 先查账再动手：账上没有的地址**一律拒绝**，绝不传给 `dealloc`。
    ///
    /// # Safety
    /// `地址` 必须来自本分配器且尚未释放。本函数会校验这一点并拒绝非法地址，
    /// 但调用方仍不得把已释放的地址当有效指针使用（那是调用方的 UB，不是本函数能兜住的）。
    pub unsafe fn 释放内存(&mut self, 块地址: u64) -> Result<(), 释放错误> {
        if 块地址 == 0 {
            return Err(释放错误::空指针);
        }
        let Some(槽字节长度) = self.活块.remove(&块地址) else {
            // 交出过但已释放 ⇒ 重复释放；从没交出过 ⇒ 外来地址。两者都不许静默。
            return Err(if self.已释放.contains(&块地址) {
                释放错误::重复释放
            } else {
                释放错误::非本分配器地址
            });
        };
        // SAFETY: 长度与对齐来自本分配器成功的一次分配，布局必然合法。
        let 内存布局 = unsafe { Layout::from_size_align_unchecked(槽字节长度 as usize, 分配对齐 as usize) };
        // SAFETY: 地址由本分配器交出、尚未释放（刚从活块账上取下），且按同一布局分配。
        unsafe { dealloc(块地址 as *mut u8, 内存布局) };
        self.已释放.insert(块地址);
        Ok(())
    }

    /// 查账：该地址当前在用块的字节长度（未在用返回 `None`）。
    pub fn 块长(&self, 块地址: u64) -> Option<u64> {
        self.活块.get(&块地址).copied()
    }

    /// 当前在用块数（对外的计数一律 `u64`）。
    pub fn 在用块数(&self) -> u64 {
        self.活块.len() as u64
    }
}
