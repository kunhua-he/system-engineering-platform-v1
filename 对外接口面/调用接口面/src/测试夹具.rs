//! 测试夹具 —— **真起服务、真发原始请求**要用的最小客户端。
//!
//! 用 `std::net::TcpStream` 手写请求，不引任何 HTTP 客户端库（本仓硬规矩：零第三方依赖）。
//! 为什么不用一个现成的客户端：那样测的就是「客户端库 + 我的服务」，而不是**我的服务的
//! 协议层**——请求行怎么写、头怎么给、体长度怎么算，正是本面要负责的事。
//!
//! # 为什么不必开线程
//!
//! `TcpStream::connect` 只要监听套接字已经 `bind`+`listen` 就会成功（内核的 accept 队列
//! 接住它），**不需要服务端已经 `accept`**。所以测试可以：先连上、先写请求，
//! 再调 `服务::处理一个连接()`，最后读应答 —— 全在一个线程里。
//! 这样也就不需要把 `服务` 搬进线程（它搬不进去：适配器不是 `Send`，见 `网关.rs` 文件头）。

use crate::协议值::协议值;
use crate::常量::监听地址;
use crate::网关::服务;
use std::io::{Read, Write};
use std::net::TcpStream;

/// 错误体必须齐的六项（`接口面形状.md` §三 冻结）。
pub const 错误体六项: [&str; 6] = ["码", "段位", "名称", "可重试", "可自愈", "需人工"];

/// 收到的一条应答：状态码 + 头 + 体。
pub struct 收到应答 {
    pub 状态: u16,
    pub 报文头: String,
    pub 报文体: String,
}

impl 收到应答 {
    /// 体解析成 JSON。**应答体必须是合法 JSON** —— 不是就当场挂（那是本面的缺陷）。
    pub fn 取协议值(&self) -> 协议值 {
        crate::协议解析::解析协议值(&self.报文体).unwrap_or_else(|错误| {
            panic!(
                "应答体必须是合法 JSON，却在第 {} 字节报「{}」：\n{}",
                错误.出错位置, 错误.说明文字, self.报文体
            )
        })
    }

    /// 取一个顶层键；**没有就挂**（要判「没有」请用 `找成员`）。
    pub fn 取成员(&self, 键名: &str) -> 协议值 {
        self.找成员(键名)
            .unwrap_or_else(|| panic!("应答里没有「{键名}」：\n{}", self.报文体))
    }

    /// 找一个顶层键；没有给 `None`。
    pub fn 找成员(&self, 键名: &str) -> Option<协议值> {
        self.取协议值().取成员(键名).cloned()
    }

    /// 取顶层的一个逻辑型键。
    pub fn 取逻辑值(&self, 键名: &str) -> bool {
        match self.取成员(键名) {
            协议值::真值 => true,
            协议值::假值 => false,
            其余值 => panic!("「{键名}」应当是逻辑型，实际 {其余值:?}：\n{}", self.报文体),
        }
    }

    /// 取顶层的一个文本键。
    pub fn 取文本(&self, 键名: &str) -> String {
        self.取成员(键名)
            .取文本()
            .map(str::to_owned)
            .unwrap_or_else(|| panic!("「{键名}」应当是文本：\n{}", self.报文体))
    }

    /// 取顶层的一个数组键。
    pub fn 取数组(&self, 键名: &str) -> Vec<协议值> {
        self.取成员(键名)
            .取数组()
            .map(<[协议值]>::to_vec)
            .unwrap_or_else(|| panic!("「{键名}」应当是数组：\n{}", self.报文体))
    }
}

/// 取一个逻辑型成员。**不是逻辑型就挂**：形状不对当场暴露，不静默当 `false`。
pub fn 取逻辑值(待处理值: &协议值, 键名: &str) -> bool {
    match 待处理值.取成员(键名) {
        Some(协议值::真值) => true,
        Some(协议值::假值) => false,
        其余值 => panic!("「{键名}」应当是逻辑型，实际 {其余值:?}"),
    }
}

/// 取一个非负整数成员。
pub fn 无符号值(待处理值: &协议值, 键名: &str) -> u64 {
    待处理值.取成员(键名)
        .and_then(协议值::取无符号)
        .unwrap_or_else(|| panic!("「{键名}」应当是非负整数，实际 {:?}", 待处理值.取成员(键名)))
}

/// 取一个文本成员。
pub fn 源文本(待处理值: &协议值, 键名: &str) -> String {
    待处理值.取成员(键名)
        .and_then(协议值::取文本)
        .map(str::to_owned)
        .unwrap_or_else(|| panic!("「{键名}」应当是文本，实际 {:?}", 待处理值.取成员(键名)))
}

/// 取一个数组成员。
pub fn 取成员数组(待处理值: &协议值, 键名: &str) -> Vec<协议值> {
    待处理值.取成员(键名)
        .and_then(协议值::取数组)
        .map(<[协议值]>::to_vec)
        .unwrap_or_else(|| panic!("「{键名}」应当是数组，实际 {:?}", 待处理值.取成员(键名)))
}

/// 前端网页应用的仓内位置（**本 crate 的相对位置**）：静态托管的根（`接口面形状.md` §五）。
///
/// 只在测试里用 `CARGO_MANIFEST_DIR`：制品里不许编进构建机的绝对路径
/// （见 `常量.rs` 的 `静态根`）—— 生产走 `服务::绑定` 的默认根或 `--静态根`。
pub fn 前端根() -> std::path::PathBuf {
    std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../前端呈现/网页应用")
}

/// 起一个服务：声明根只有底座自身那一份，端口让 OS 分配（避免测试互相撞）；
/// 静态托管根显式指到仓内的 `前端呈现/网页应用/`（测试的 cwd 是 crate 目录，
/// 默认根是「相对进程工作目录」的仓根口径，故这里显式注入）。
pub fn 起服务() -> 服务 {
    起服务带工具根(仓根())
}

/// 仓根（**本 crate 的相对位置**：`对外接口面/调用接口面/` 上两级）。
///
/// 与 `前端根` 同一条口径：**只在测试里**用 `CARGO_MANIFEST_DIR` —— 制品里不许编进
/// 构建机的绝对路径（见 `常量.rs` 的 `静态根` 与 `工具根默认`）。生产走 `服务::绑定`
/// 的默认工具根（进程工作目录 = 仓根）。
pub fn 仓根() -> std::path::PathBuf {
    std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../..")
}

/// 起一个服务并**显式指定 §七 的工具根**（工具族的部署事实：案例库 · 扩展根 · 外部 CLI）。
pub fn 起服务带工具根(工具根: impl Into<std::path::PathBuf>) -> 服务 {
    服务::绑定并托管(&[v1_adapter::底座声明()], 0, 前端根())
        .expect("底座自身的声明必须载得进来")
        .工具根(工具根)
}

/// 唯一腿上的第一个能力号（**不写死 0**：编号是适配器报出来的，测试跟着它走）。
pub fn 第一个能力号(服务: &服务) -> u32 {
    服务.适配器().能力清单()[0].编号
}

/// 一条 GET 请求（原始文本）。
pub fn 取请求(路径: &str) -> String {
    format!("GET {路径} HTTP/1.1\r\nHost: 127.0.0.1\r\nAccept: application/json\r\n\r\n")
}

/// 一条 POST 请求（原始文本）。`Content-Length` 按**字节数**算，与冻结件一致。
pub fn 交POST请求(路径: &str, 请求体: &str) -> String {
    format!(
        "POST {路径} HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: {}\r\n\r\n{请求体}",
        请求体.len()
    )
}

/// 发一条原始请求并收回应答。
///
/// 顺序固定：连上 → 写请求 → **服务处理一次** → 读应答。见文件头「为什么不必开线程」。
pub fn 发请求(服务: &服务, 请求: &str) -> 收到应答 {
    let mut 输出流 = TcpStream::connect((监听地址, 服务.监听端口())).expect("必须连得上（监听已 bind）");
    输出流.write_all(请求.as_bytes()).expect("写请求");
    输出流.flush().expect("刷请求");
    服务.处理一个连接().expect("服务必须处理一次");
    let mut 缓冲 = Vec::new();
    输出流.read_to_end(&mut 缓冲).expect("读应答");
    解析应答(&缓冲)
}

/// **纯客户端**：连上 → 写请求 → 读应答。**不碰服务端**（不调 `处理一个连接`）。
///
/// 给并发测试用：服务端由 `服务::跑并发` 的工作线程收连接，测试这一侧只能当客户端。
/// 不能拿 [`发请求`] 代替 —— 它自带一次 `处理一个连接`，会与并发的服务端**抢同一个连接**。
pub fn 发到端口(监听端口: u16, 请求: &str) -> 收到应答 {
    let mut 输出流 = TcpStream::connect((监听地址, 监听端口)).expect("必须连得上（监听已 bind）");
    输出流.write_all(请求.as_bytes()).expect("写请求");
    输出流.flush().expect("刷请求");
    let mut 缓冲 = Vec::new();
    输出流.read_to_end(&mut 缓冲).expect("读应答");
    解析应答(&缓冲)
}

/// 解析原始应答文本。
fn 解析应答(字节: &[u8]) -> 收到应答 {
    let 源文本 = String::from_utf8(字节.to_vec()).expect("应答必须是 UTF-8");
    let (头部, 应答体) = 源文本
        .split_once("\r\n\r\n")
        .unwrap_or_else(|| panic!("应答必须有头体分界：\n{源文本}"));
    let 状态 = 头部
        .lines()
        .next()
        .and_then(|源码行| 源码行.split(' ').nth(1))
        .and_then(|状态码| 状态码.parse::<u16>().ok())
        .unwrap_or_else(|| panic!("应答首行必须是「HTTP/1.1 码 短语」：\n{源文本}"));
    收到应答 {
        状态,
        报文头: 头部.to_owned(),
        报文体: 应答体.to_owned(),
    }
}
