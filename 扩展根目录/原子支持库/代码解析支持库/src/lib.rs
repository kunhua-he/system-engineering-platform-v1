#![allow(non_snake_case)]
#![allow(uncommon_codepoints)]
#[path = "编号与码面.rs"]
mod 编号与码面;
#[path = "命令声明面.rs"]
mod 命令声明面;
#[path = "执行函数面.rs"]
mod 执行函数面;
#[path = "文本解码.rs"]
mod 文本解码;
#[path = "规则载入.rs"]
mod 规则载入;
#[path = "规则切块.rs"]
mod 规则切块;
#[path = "业务实现.rs"]
mod 业务实现;
#[path = "静态声明.rs"]
mod 静态声明;
pub use 静态声明::{取平台信息, 扩展声明};
