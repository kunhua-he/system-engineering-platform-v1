#![allow(non_snake_case)]
#[path = "命令声明面.rs"]
mod 命令声明面;
#[path = "文档解析.rs"]
mod 文档解析;
#[path = "格式转换.rs"]
mod 格式转换;
#[path = "业务实现.rs"]
mod 业务实现;
#[path = "执行函数面.rs"]
mod 执行函数面;
#[path = "编号与码面.rs"]
mod 编号与码面;
#[path = "静态声明.rs"]
mod 静态声明;
#[path = "表格边界.rs"] mod 表格边界;
#[path = "表格读取.rs"] mod 表格读取;
#[path = "表格写出.rs"] mod 表格写出;
#[path = "页面结构.rs"] mod 页面结构;
pub use 静态声明::{取平台信息, 扩展声明};
