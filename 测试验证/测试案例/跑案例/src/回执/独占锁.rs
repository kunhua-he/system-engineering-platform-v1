//! `flock(2)` 的唯一 FFI —— **有界等待**的独占锁。
//!
//! # 为什么在本件能写 `extern "C"`
//!
//! 本仓底座**不许引第三方 crate**（`Cargo.toml` 的冻结注释），而 `flock` 是 libc 里的内核原语、
//! 不是第三方件 —— 这里只声明一个符号，不新增依赖。
//!
//! # 为什么锁得住
//!
//! `flock` 挂在**打开文件描述**上，同进程的两个 `File` 也各是一个描述 ⇒ 同进程多线程同样互斥
//! （不像 `fcntl` 的 POSIX 锁按进程算）；跨进程同样互斥 ⇒ 回执的多进程追加与收敛共用这一把锁。
//!
//! # 两条硬口径（2026-10-29 定）
//!
//! 1. **等待有界**：`LOCK_NB` 轮询到截止时刻，超时就回明确错误（带等了多久、哪个锁件）。
//!    早先直接 `flock(LOCK_EX)` 会**无限期挂住**整个跑案例进程 —— 持有者崩在临界区时没人兜。
//! 2. **拿不到锁就是失败**：本模块**只回 `Result`**，调用方不许退回「无锁追加」。
//!    两个写者同时写同一份回执 = 拼坏行，那是这条链上唯一不可接受的结局。

use std::fs::{File, OpenOptions};
use std::io;
use std::os::raw::c_int;
use std::os::unix::io::AsRawFd;
use std::path::Path;
use std::time::{Duration, Instant};

/// `LOCK_EX`：独占锁。
const 独占: c_int = 2;
/// `LOCK_NB`：不阻塞（配 `LOCK_EX` 用轮询实现有界等待）。
const 非阻塞: c_int = 4;
/// `LOCK_UN`：解锁。
const 解锁: c_int = 8;
/// 轮询间隔：2 毫秒 —— 回执的临界区是「读全文 + 一次 rename」，量级在毫秒，无需更密。
const 重试间隔毫秒: u64 = 2;

unsafe extern "C" {
    /// `flock(2)`：0 = 成，非 0 = 败（`errno` 说明原因，例如文件系统不支持）。
    ///
    /// ★ 标识符只能是 ASCII 原名：`rustc` 明确拒 —— *items in `extern` blocks cannot use
    /// non-ascii identifiers*（rust-lang/rust#83942，本仓工具链 1.95 实测仍拒）。它是 libc
    /// 强加的名字，不走命名纪律那条路；外面一律经 [`文件加锁`] 用它，不直接碰 FFI。
    fn flock(句柄号: c_int, 操作值: c_int) -> c_int;
}

/// FFI 的安全封装：把「非 ASCII 标识符」这条限制关在本模块里。
///
/// `flock` 只读这两个整数（一个是打开的文件描述符、一个是锁操作位），不碰任何指针
/// ⇒ 包一层之后外面拿到的是普通安全函数，调用点不必再写 `unsafe`。
fn 文件加锁(句柄号: c_int, 操作值: c_int) -> io::Result<()> {
    // SAFETY：见上 —— 两个入参都是纯值，没有指针、没有生命周期可言。
    if unsafe { flock(句柄号, 操作值) } == 0 {
        Ok(())
    } else {
        Err(io::Error::last_os_error())
    }
}

/// 持锁凭据：**作用域结束即放锁**（`Drop` 里显式解一次，关描述符再兜一次）。
pub struct 锁件(File);

impl Drop for 锁件 {
    fn drop(&mut self) {
        文件加锁(self.0.as_raw_fd(), 解锁).ok();
    }
}

/// 取独占锁：**最多等 `等待毫秒`** ⇒ `Ok(凭据)`；锁被占满等待 / 锁件打不开 / `flock` 不支持 ⇒ `Err`。
///
/// 错误里带三件事：锁件路径、等了多少毫秒、底层 errno 说法 —— 调用方据此回拒，不再有无锁退路。
pub fn 取锁(路径: &Path, 等待毫秒: u64) -> Result<锁件, String> {
    let 锁节点 = OpenOptions::new()
        .create(true)
        .append(true)
        .open(路径)
        .map_err(|错误| format!("打不开锁件 {}：{错误}", 路径.display()))?;
    let 截止时刻 = Instant::now() + Duration::from_millis(等待毫秒);
    loop {
        match 文件加锁(锁节点.as_raw_fd(), 独占 | 非阻塞) {
            Ok(()) => return Ok(锁件(锁节点)),
            Err(错误) => {
                // EAGAIN / EWOULDBLOCK ⇒ 有人持锁；其余（含 ENOTSUP）⇒ 这条路根本走不通。
                if 错误.kind() != io::ErrorKind::WouldBlock {
                    return Err(format!(
                        "flock 不走这条路（{} 不支持独占锁？errno 说法：{错误}）⇒ 拒绝无锁写",
                        路径.display()
                    ));
                }
                if Instant::now() >= 截止时刻 {
                    return Err(format!(
                        "锁被占用：等满 {等待毫秒} 毫秒仍没拿到 {} ⇒ 明确失败（不退回无锁写）",
                        路径.display()
                    ));
                }
                std::thread::sleep(Duration::from_millis(重试间隔毫秒));
            }
        }
    }
}
