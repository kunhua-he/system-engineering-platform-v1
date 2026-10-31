#![allow(clippy::missing_const_for_fn)]

#[path = "代际/契约.rs"]
mod contract_impl;
mod ffi;
#[path = "代际/跨进程租约.rs"]
mod process_lease_impl;

pub use contract_impl::{
    代际令牌, 契约错误, 执行租约, 版本号, 装载单元, 装载单元上下文
};
pub use ffi::{数据库连接, 数据库错误};
pub use process_lease_impl::{跨进程租约, 跨进程租约错误};
