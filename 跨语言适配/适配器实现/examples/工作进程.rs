//! 工作进程 · 真进程入口 —— 接 stdout/stdin 上那条 UnixStream、dlopen 真支持库制品、起收调用循环。
//!
//! 依据：`临时件/落点/307收尾_接口冻结.md`（工作进程形状 · 真进程入口）。
//!
//! # 用法
//!
//! ```text
//! 工作进程 <制品路径> <缓存根目录>
//! ```
//!
//! ★ **装配例子里不许出现任何扩展的名字 / 路径字面**（判据 ⑯）：制品路径**由命令行参数给**。
//! 本件不认任何扩展名、不扫目录、不猜路径 —— 猜一次就把底座绑死在某个扩展上。
//!
//! # 通道怎么来的
//!
//! `进程池.rs::生成进程` 把一条 `UnixStream` 的**子端**接在子进程的 `stdin`（fd 0）上，
//! 再 `try_clone` 一份接在 `stdout`（fd 1）上 —— 同一个 socket 的两个 dup。
//! 故工作进程**读 fd 0、写 fd 1** 就是一条双向通道。
//!
//! # 退出
//!
//! 通道断开（对端关了 / 宿主回收）即正常退出。工作进程**不做自杀 / 重拉**：
//! 崩溃检出与重拉归宿主侧 [`v1_adapter::进程池`]（冻结件 §三 ⑤）。

use std::os::fd::FromRawFd;
use std::os::unix::net::UnixStream;
use std::path::PathBuf;
use std::process::ExitCode;

use v1_adapter::工作进程::工作进程;

fn main() -> ExitCode {
    let 参数表: Vec<String> = std::env::args().skip(1).collect();
    if 参数表.len() != 2 {
        eprintln!("用法：工作进程 <制品路径> <缓存根目录>");
        return ExitCode::from(2);
    }
    let 制品路径 = PathBuf::from(&参数表[0]);
    let 缓存根目录 = PathBuf::from(&参数表[1]);
    // SAFETY: fd 0 由 `进程池::生成进程` 接上 UnixStream 的子端（Stdio::from(OwnedFd)）；
    // 每个进程恰好接管一次 ⇒ 不存在二次接管同一个 fd。
    let 流通道 = unsafe { UnixStream::from_raw_fd(0) };
    let mut 进程 = match 工作进程::创建(流通道, &制品路径, &缓存根目录) {
        Ok(进程) => 进程,
        Err(错误) => {
            eprintln!("工作进程装载失败：{错误:?}");
            return ExitCode::from(3);
        }
    };
    match 进程.起工作循环() {
        Ok(()) => ExitCode::SUCCESS,
        Err(错误) => {
            eprintln!("工作进程循环失败：{错误:?}");
            ExitCode::from(4)
        }
    }
}
