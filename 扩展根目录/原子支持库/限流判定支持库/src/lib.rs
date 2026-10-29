//! 限流判定支持库，调用方传状态，返回新状态；无常驻资源。
#![allow(uncommon_codepoints)]
#![allow(non_snake_case)]
#[path = "令牌判定面.rs"]
mod 令牌判定面;
#[path = "声明接口面.rs"]
mod 声明接口面;
pub use 声明接口面::取平台信息;
#[cfg(test)]
#[path = "令牌判定样本.rs"]
mod 令牌判定样本;
