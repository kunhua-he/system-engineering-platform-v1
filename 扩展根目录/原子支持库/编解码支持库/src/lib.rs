#![allow(non_snake_case)]
#[path = "Base64编解码/mod.rs"]
mod Base64编解码;
#[path = "十六进制编解码/mod.rs"]
mod 十六进制编解码;
#[path = "字符编解码/mod.rs"]
mod 字符编解码;
#[path = "URI组件编解码/mod.rs"]
mod URI组件编解码;
#[path = "命令声明面.rs"]
mod 命令声明面;
#[path = "执行函数面.rs"]
mod 执行函数面;
#[path = "编号与码面.rs"]
mod 编号与码面;
#[path = "静态声明.rs"]
mod 静态声明;
pub use 静态声明::{取平台信息, 扩展声明};
