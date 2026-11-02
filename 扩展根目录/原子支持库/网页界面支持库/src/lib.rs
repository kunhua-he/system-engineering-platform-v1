#![allow(non_snake_case)]
#[path = "业务实现.rs"]
mod 业务实现;
#[path = "交互运行时.rs"]
mod 交互运行时;
#[path = "命令声明面.rs"]
mod 命令声明面;
#[path = "执行函数面.rs"]
mod 执行函数面;
#[path = "组件树.rs"]
mod 组件树;

#[path = "编号与码面.rs"]
mod 编号与码面;
#[path = "视觉基准.rs"]
mod 视觉基准;
#[path = "静态声明.rs"]
mod 静态声明;
pub use 静态声明::{取平台信息, 扩展声明};
