#[path = "本机生成/生成形状.rs"]
mod 生成形状;
#[path = "本机生成/生成实现.rs"]
mod 生成实现;
#[path = "本机生成/表达式生成.rs"]
mod 表达式生成;

pub(crate) use 生成形状::{本机依赖, 本机生成请求, 本机源码产物, 本机生成错误};
pub(crate) use 生成实现::生成本机源码;

#[cfg(test)]
#[path = "本机生成/验证样本.rs"]
mod 验证样本;
