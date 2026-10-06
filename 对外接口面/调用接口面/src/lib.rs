//! 调用接口面 —— 契约的 HTTP 门面（网关）：把 `契约声明/` 的声明装成端点，收请求、发协议值。
//!
//! ★ 本 crate 原先用 `#![doc = include_str!("调用接口面/接口面说明.md")]` 把一份说明散文读进来；
//!   那份 md 在「md 全量入库」批次里**已删**（正文只在 git 历史里 —— `条款` 表是**当前 md 集**的
//!   视图，删了就没了）⇒ 那个 `include_str!` 会让**整个工作区编不过**（实测 `cargo check --workspace`
//!   两处 error：`couldn't read … 接口面说明.md` + `attribute value must be a literal`）⇒ 改成本短述。
//!   形状的机器可读落点在 `契约声明/`；端点的判法落点在 `测试验证/契约一致性/扫实现/`。

#[path = "协议值.rs"]
mod 协议值;
#[path = "协议写出.rs"]
mod 协议写出;
#[path = "协议解析.rs"]
mod 协议解析;
#[path = "线上逻辑值.rs"]
mod 线上逻辑值;
#[path = "分发.rs"]
mod 分发;
#[path = "响应.rs"]
mod 响应;
#[path = "常量.rs"]
mod 常量;
#[path = "槽编码.rs"]
mod 槽编码;
#[path = "网关.rs"]
mod 网关;
// 扫扩展根：从 example 搬进 src（启动装配与运行期装载同读一份，台账 237）。
// **公开**：example（`examples/启动网关/`）也读它 —— 一个实现两处调用，不是第二套。
#[path = "扫扩展根.rs"]
pub mod 扫扩展根;
#[path = "报文读写.rs"]
mod 报文读写;
#[path = "请求.rs"]
mod 请求;
#[path = "端点路由.rs"]
mod 端点路由;
#[path = "静态件.rs"]
mod 静态件;
#[path = "转码.rs"]
mod 转码;
#[path = "错误形状.rs"]
mod 错误形状;
#[path = "工具链.rs"]
mod 工具链;
#[path = "工具响应.rs"]
mod 工具响应;
#[path = "生命周期响应.rs"]
mod 生命周期响应;
#[path = "留痕响应.rs"]
mod 留痕响应;

pub use 分发::{造应答, 拒绝状态码};
pub use 报文读写::报文;
pub use 网关::{默认并发线程数, 服务, 启动失败};
pub use 端点路由::{拒绝, 端点};

#[cfg(test)]
#[path = "接口面测试.rs"]
mod 接口面测试;
#[cfg(test)]
#[path = "接口面工具族测试.rs"]
mod 接口面工具族测试;
#[cfg(test)]
#[path = "并发测试.rs"]
mod 并发测试;
#[cfg(test)]
#[path = "生命周期测试.rs"]
mod 生命周期测试;
#[cfg(test)]
#[path = "槽编码测试.rs"]
mod 槽编码测试;
#[cfg(test)]
#[path = "测试夹具.rs"]
mod 测试夹具;
