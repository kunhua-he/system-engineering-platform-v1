#![allow(non_snake_case)]
#[path = "命令声明面.rs"]
mod 命令声明面;

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
#[path = "办公资源.rs"] mod 办公资源;
#[path = "文档部件.rs"] mod 文档部件;
#[path = "文档合并解析.rs"] mod 文档合并解析;
#[path = "表格读取.rs"] mod 表格读取;
#[path = "表格写出.rs"] mod 表格写出;
#[path = "页面结构.rs"] mod 页面结构;
#[path = "演示文稿解析.rs"] mod 演示文稿解析;
#[path = "演示文稿部件.rs"] mod 演示文稿部件;
#[path = "演示文稿生成.rs"] mod 演示文稿生成;
#[cfg(test)]
#[path = "表格回归测试.rs"]
mod 表格回归测试;
pub use 静态声明::{取平台信息, 扩展声明};
