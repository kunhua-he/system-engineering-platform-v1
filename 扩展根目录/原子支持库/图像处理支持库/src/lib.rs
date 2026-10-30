#![allow(non_snake_case)]
#[path = "命令声明面.rs"]
mod 命令声明面;
#[path = "图像处理.rs"]
mod 图像处理;
#[path = "执行函数面.rs"]
mod 执行函数面;
#[path = "编号与码面.rs"]
mod 编号与码面;
#[path = "静态声明.rs"]
mod 静态声明;
pub use 静态声明::{取平台信息, 扩展声明};
