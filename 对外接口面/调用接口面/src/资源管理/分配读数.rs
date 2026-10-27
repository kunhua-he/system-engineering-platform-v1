//! 分配读数 —— **生产口**的存活分配计数（跨分配器读得到的那一个数）。
//!
//! # 为什么要有它
//!
//! 发布验收（`测试验证/准入判据/故障取证样本/跨进程验收/验收必证项/八条必证.py::必证三_清理`）原先只能靠
//! 「调用成功 + owner/FD 快照」**推定**「没有泄漏」—— 推定不是证据。本件把「跨分配器存活分配计数」
//! 搬到生产口：调用前后各读一次，**差为 0** 才叫没有泄漏。
//!
//! # 为什么住在对外接口面，不住跨语言适配
//!
//! 判据 ⑫（边界纪律 · `边界协议.md` 第四节）要求 `跨语言适配/` 里 **0 状态** —— 而计数分配器天然
//! 带两个**进程级**计数（`static AtomicUsize`）。实测把本件放在 `跨语言适配/适配器实现/src/` 下，
//! 闸 1 直接判「边界里有 2 处模块级 static」⇒ 落点跟着功能走：用它的两头（读数口 `资源响应.rs` ·
//! 生产二进制 `examples/启动网关.rs`）都在本层。
//!
//! # 与测试档那份的关系（不是第二套事实）
//!
//! 测试档本来就有同一件事：`边界测试.rs` 的 `泄漏读数_计数分配器`。两者分工不同，不许合并：
//!   · 测试档那份盯**一个具体地址**，证「指定返回地址真的发生过 `dealloc`」（审计发现 1 的身份证）；
//!   · 本件报**进程级**的两个数（存活字节数 / 存活块数），供验收与运维读，**不参与任何判定**。
//! 计数来源是本进程**真实的分配器调用**（`GlobalAlloc` 的 `alloc` / `dealloc`），不另记一本账。
//!
//! # 谁在计数：生产二进制，不是本库
//!
//! `#[global_allocator]` 是 **crate 级语言项**，一个二进制只能有一处。本库**不挂**它：
//! 挂在本库会与「自带计数分配器」的测试二进制撞（实测 `tests/整条HTTP/夹具.rs` 那一处报
//! `the #[global_allocator] in this crate conflicts with global allocator in: v1_adapter`）。
//! 分工因此是：
//!   · **本件**提供分配器类型 + 两个读数函数（「怎么读」）；
//!   · **生产二进制** `examples/启动网关.rs` 挂上它（「谁在计数」）。
//! 发布验收跑的就是那个二进制 ⇒ 读到的正是生产进程的数。

use std::alloc::{GlobalAlloc, Layout, System};
use std::sync::atomic::{AtomicUsize, Ordering};

/// 当前存活字节数（本进程）。
static 存活字节数: AtomicUsize = AtomicUsize::new(0);

/// 当前存活块数（本进程）。
static 存活块数: AtomicUsize = AtomicUsize::new(0);

/// 计数分配器 —— 包一层 `System`，**只加两个计数、不改分配行为**。
///
/// **公开**：生产二进制要把它挂成本进程的 `#[global_allocator]`
/// （`examples/启动网关.rs`），为什么挂那里见本件文件头。
pub struct 进程计数分配器;

unsafe impl GlobalAlloc for 进程计数分配器 {
    unsafe fn alloc(&self, 内存布局: Layout) -> *mut u8 {
        let 块地址 = unsafe { System.alloc(内存布局) };
        if !块地址.is_null() {
            存活字节数.fetch_add(内存布局.size(), Ordering::SeqCst);
            存活块数.fetch_add(1, Ordering::SeqCst);
        }
        块地址
    }

    unsafe fn dealloc(&self, 块地址: *mut u8, 内存布局: Layout) {
        unsafe { System.dealloc(块地址, 内存布局) };
        存活字节数.fetch_sub(内存布局.size(), Ordering::SeqCst);
        存活块数.fetch_sub(1, Ordering::SeqCst);
    }
}

// 这里**不挂** `#[global_allocator]`：它是 crate 级语言项，挂在本库会与自带的测试二进制撞
// （`tests/整条HTTP/夹具.rs` 有它那一处），而本库的测试档那一处归 `边界测试.rs`。
// 「谁在计数」= 生产二进制（`examples/启动网关.rs`）；本件只提供分配器类型与「怎么读」。

/// 读当前存活字节数（生产读数，不参与判定）。
pub fn 读存活字节数() -> usize {
    存活字节数.load(Ordering::SeqCst)
}

/// 读当前存活分配计数 —— 就是发布验收要的那个「跨分配器存活分配计数」。
///
/// 「跨分配器」= 从**分配器外面**读得到：验收在调用前后各读一次，差为 0 才算没有泄漏。
pub fn 读存活分配计数() -> usize {
    存活块数.load(Ordering::SeqCst)
}
