//! 图片文字识别支持库：仅声明与导出，识别实现只在本扩展。
#![allow(non_snake_case)]
#[path = "编号与码面.rs"]
mod 编号与码面;
#[path = "命令声明面.rs"]
mod 命令声明面;
#[path = "执行函数面.rs"]
mod 执行函数面;
#[path = "识别提供者.rs"]
mod 识别提供者;
#[path = "静态声明.rs"]
mod 静态声明;
pub use 编号与码面::{能力号, 错误码};
pub use 静态声明::{取平台信息, 扩展声明};
