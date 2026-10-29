#![allow(non_snake_case)]
#[path = "命令声明面.rs"]
mod 命令声明面;
#[path = "业务实现.rs"]
mod 业务实现;
#[path = "执行函数面.rs"]
mod 执行函数面;
#[path = "编号与码面.rs"]
mod 编号与码面;
#[path = "静态声明.rs"]
mod 静态声明;
pub use 静态声明::{取平台信息, 扩展声明};

#[cfg(test)]
#[path = "异步请求样本.rs"]
mod 异步请求样本;

#[path="异步请求执行.rs"] mod 异步请求执行;
#[path="网络任务管理.rs"] mod 网络任务管理;
#[path="异步请求接口.rs"] mod 异步请求接口;
