//! 网关 —— **全平台唯一的对外监听**（`全局连接器与网关.md` 第四节判据 1：全仓搜监听调用点，
//! 恰好 1 处；那一处就是本文件的 `TcpListener::bind`）。
//!
//! # 只监听回环
//!
//! `接口面形状.md` §一：判据是「第一次用不需要读文档就能调对」，而「要先拿 token」正好违反
//! 它 ⇒ **不做鉴权**。没有鉴权就必须只对本机开放，故地址是 `127.0.0.1`
//! （`常量.rs` 的 `监听地址`），**不提供改成 0.0.0.0 的口**。
//!
//! # 手写 HTTP/1.1，零第三方依赖
//!
//! 本仓硬规矩：进制品的形态必须零第三方依赖。HTTP 只用到一小块（请求行 · 头 · 定长体 ·
//! 一行响应头），手写比引一个运行时更可判。
//!
//! **明确不做**（都是 `接口面形状.md` §一 判据的直接后果，不是偏好）：
//!
//! - 不做握手 / 会话 / 连接管理：每次应答都带 `Connection: close` 并关闭连接。入口无状态。
//! - 不做 `Transfer-Encoding: chunked`：收到即 400（要支持它就得做流式状态机 = 连接管理）。
//! - 不做 `keep-alive` / `pipelining`：一个连接一个请求，读到定长体为止，余料丢弃。
//! - 不做鉴权 / 不做 CORS：静态文件与前端同源，同源不需要 CORS。
//!
//! # 待办：单线程 accept（缺口，如实登记）
//!
//! 本轮的 accept 循环是**单线程**的：一个连接处理完才 accept 下一个。原因是**唯一腿**那条
//! 规则 —— 适配器公开面没有给 `Send` / `Sync` 保证（`注册表` 持有裸指针的切片，
//! `平台信息` 也是），而网关**不许替下层 `unsafe impl Sync` 担保**：那是替别的 crate 的
//! 类型断言一件自己验证不了的事。多线程共享适配器要适配器先声明线程安全，或给出一个
//! 线程安全的句柄形态。**修法在适配器，不在网关里绕。**
//!
//! 现状的兜底：每个连接设了读写超时（`读超时毫秒`），所以一个挂住的客户端最多挡住
//! 一次超时的时长，不会永久挡住整个门。

use crate::协议解析;
use crate::分发::{应答, 处理, 拒绝状态码};
use crate::路由;
use crate::常量::{监听地址, 接口端口};
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::time::Duration;
use v1_adapter::{平台信息, 适配器};

/// 单次连接的读写超时（毫秒）。**旁路常量**：它不是契约里的数，是本面的防挂死策略。
const 读超时毫秒: u64 = 2_000;
/// 请求头（含请求行）的字节上限。
const 头区上限: usize = 16 * 1024;
/// 请求体的字节上限。**旁路策略**：不设上限就是让一次请求决定进程的内存。
const 体上限: usize = 1 << 20;

/// 绑定失败 —— 结构化，说清是哪一步。
#[derive(Debug)]
pub enum 启动失败 {
    /// 装载失败（原样转出适配器的段位，不吞、不改写）。
    装载(v1_adapter::装载失败),
    /// 端口绑不上（已被占用 / 权限不足）。
    绑定(std::io::Error),
}

/// 已绑定的对外门。**一个实例一套东西**：适配器 + 监听 + 契约来源，**没有任何进程级
/// `static`** ⇒ 同进程开两份就是两个互不干扰的门（多实例安全）。
///
/// `契约来源` 是**注入的声明**（声明根的第一份，适配器约定「底座排在最前」）：
/// 根端点要的 `契约版本` 与 `声明格式号` 从它上面现读。网关**不自己去取声明** ——
/// 「谁把声明递进来」是装配与扩展装载那条腿的事，网关自己去找就是跳层。
pub struct 服务 {
    适配器: 适配器,
    契约来源: &'static 平台信息,
    监听: TcpListener,
    端口: u16,
}

impl 服务 {
    /// 装载声明根 → 绑定 `127.0.0.1:端口`。
    ///
    /// `端口` 传 `0` 让 OS 分配（测试与多实例用；实际端口由 [`服务::端口`] 报出）。
    pub fn 绑定(声明根: &[&'static 平台信息], 端口: u16) -> Result<Self, 启动失败> {
        let 契约来源 = *声明根
            .first()
            .ok_or(启动失败::装载(v1_adapter::装载失败::空声明根))?;
        // 唯一腿：所有请求都转调它（`适配器::装载声明根` 是全平台唯一的那一处 `载入`）。
        let 适配器 = 适配器::装载声明根(声明根).map_err(启动失败::装载)?;
        let 监听 = TcpListener::bind((监听地址, 端口)).map_err(启动失败::绑定)?;
        let 端口 = 监听.local_addr().map_err(启动失败::绑定)?.port();
        Ok(Self {
            适配器,
            契约来源,
            监听,
            端口,
        })
    }

    /// 用契约里的默认端口绑定（`常量.rs` 的 `接口端口`，来源 `契约声明/常量表.json`）。
    pub fn 绑定默认端口(声明根: &[&'static 平台信息]) -> Result<Self, 启动失败> {
        Self::绑定(声明根, 接口端口)
    }

    /// **真正绑上的端口**。根端点的 `实际端口` 报的就是它（不报常量：测试与多实例下
    /// 报常量就是一个假事实）。
    pub fn 端口(&self) -> u16 {
        self.端口
    }

    /// 唯一腿（验证面与装配用）。
    pub fn 适配器(&self) -> &适配器 {
        &self.适配器
    }

    /// 接受一个连接、处理一次、关闭。**一个连接一个请求**（不做连接管理）。
    ///
    /// 单列一个口（而不是只给 `跑`）：它让「真起服务真发请求」的测试不必开线程 ——
    /// 客户端先 `connect`（内核的 accept 队列会接住），再调本函数，再读应答。
    pub fn 处理一个连接(&self) -> std::io::Result<()> {
        let (mut 流, _) = self.监听.accept()?;
        let 超时 = Some(Duration::from_millis(读超时毫秒));
        流.set_read_timeout(超时)?;
        流.set_write_timeout(超时)?;
        let 应答 = match 读报文(&mut 流) {
            Ok(报文) => self.应答(&报文),
            // 请求本身不合法 ⇒ 400（**协议层**失败，不是业务失败）。
            Err(说明) => 应答::协议(400, &说明),
        };
        写响应(&mut 流, &应答)
    }

    /// 一直服务下去（生产入口；`跑` 不返回 `Ok`）。
    pub fn 跑(&self) -> std::io::Result<()> {
        loop {
            self.处理一个连接()?;
        }
    }

    /// 一次请求 → 一次应答。**纯分发**：先认端点，再交给 `端点::处理`。
    fn 应答(&self, 报文: &报文) -> 应答 {
        let 落点 = match 路由::认(&报文.方法, &报文.目标) {
            Ok(落点) => 落点,
            Err(拒绝) => return 应答::协议(拒绝状态码(&拒绝), &拒绝.说明()),
        };
        // 请求体只对**收体的端点**解析：GET 的体与本面无关，不去判它。
        let 体 = match 落点 {
            crate::路由::端点::调用 | crate::路由::端点::声明 => match 协议解析::解析(&报文.体) {
                Ok(体) => Some(体),
                Err(错) => {
                    return 应答::协议(
                        400,
                        &format!("请求体不是合法 JSON：{}（第 {} 字节）", 错.说明, 错.位置),
                    );
                }
            },
            _ => None,
        };
        处理(&self.适配器, self.契约来源, self.端口, 落点, 体.as_ref())
    }
}

/// 一条已读完的 HTTP 请求。**只留形状**：方法 · 目标 · 体。
#[derive(Debug, Clone)]
pub struct 报文 {
    pub 方法: String,
    pub 目标: String,
    pub 体: String,
}

/// 读一条请求。错误是**一句可读说明**（⇒ 400）。
fn 读报文(流: &mut TcpStream) -> Result<报文, String> {
    let mut 缓冲: Vec<u8> = Vec::with_capacity(1024);
    let mut 临时 = [0u8; 4096];
    let 头尾 = loop {
        if let Some(位) = 找头尾(&缓冲) {
            break 位;
        }
        if 缓冲.len() > 头区上限 {
            return Err(format!("请求头超过 {头区上限} 字节"));
        }
        let 读到 = 流.read(&mut 临时).map_err(|错| format!("读请求失败：{错}"))?;
        if 读到 == 0 {
            return Err("连接在请求写完之前就断了".to_owned());
        }
        缓冲.extend_from_slice(&临时[..读到]);
    };

    let 头 = core::str::from_utf8(&缓冲[..头尾])
        .map_err(|_| "请求头不是合法 UTF-8".to_owned())?
        .to_owned();
    let 体起 = 头尾 + 4;
    let 余料 = 缓冲.get(体起..).unwrap_or(&[]).to_vec();

    let mut 行 = 头.split("\r\n");
    let 首行 = 行.next().unwrap_or("");
    let 部件: Vec<&str> = 首行.split(' ').filter(|段| !段.is_empty()).collect();
    if 部件.len() != 3 {
        return Err("请求行必须是「方法 目标 版本」三段".to_owned());
    }
    let (方法, 目标) = (部件[0].to_owned(), 部件[1].to_owned());

    let mut 内容长度 = 0usize;
    for 一行 in 行 {
        let Some((名, 值)) = 一行.split_once(':') else {
            continue;
        };
        let 名 = 名.trim().to_ascii_lowercase();
        let 值 = 值.trim();
        if 名 == "content-length" {
            内容长度 = 值
                .parse::<usize>()
                .map_err(|_| "Content-Length 不是非负整数".to_owned())?;
        }
        if 名 == "transfer-encoding" && !值.eq_ignore_ascii_case("identity") {
            // 分块传输要做流式状态机 = 连接管理，本面明确不做（文件头）。
            return Err("本面不支持 Transfer-Encoding：请用 Content-Length".to_owned());
        }
    }
    if 内容长度 > 体上限 {
        return Err(format!("请求体超过 {体上限} 字节"));
    }

    let mut 体字节 = 余料;
    // 余料可能已经多于 Content-Length（pipelining）：多的部分**丢弃**，本面不做流水线。
    体字节.truncate(内容长度);
    while 体字节.len() < 内容长度 {
        let 还差 = (内容长度 - 体字节.len()).min(临时.len());
        let 读到 = 流
            .read(&mut 临时[..还差])
            .map_err(|错| format!("读请求体失败：{错}"))?;
        if 读到 == 0 {
            return Err("请求体没读完连接就断了".to_owned());
        }
        体字节.extend_from_slice(&临时[..读到]);
    }
    let 体 = String::from_utf8(体字节).map_err(|_| "请求体不是合法 UTF-8".to_owned())?;
    Ok(报文 { 方法, 目标, 体 })
}

/// 找 `\r\n\r\n` 的起始偏移（请求头与体的分界）。
fn 找头尾(缓冲: &[u8]) -> Option<usize> {
    缓冲
        .windows(4)
        .position(|窗| 窗 == b"\r\n\r\n")
}

/// 写一条应答。**恒带 `Connection: close`**（不做连接管理）。
fn 写响应(流: &mut TcpStream, 应答: &应答) -> std::io::Result<()> {
    let 头 = format!(
        "HTTP/1.1 {} {}\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
        应答.状态,
        原因短语(应答.状态),
        应答.体.len()
    );
    流.write_all(头.as_bytes())?;
    流.write_all(应答.体.as_bytes())?;
    流.flush()
}

fn 原因短语(状态: u16) -> &'static str {
    match 状态 {
        200 => "OK",
        400 => "Bad Request",
        404 => "Not Found",
        405 => "Method Not Allowed",
        _ => "Unknown",
    }
}
