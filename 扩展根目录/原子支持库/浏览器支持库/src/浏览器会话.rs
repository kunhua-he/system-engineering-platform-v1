//! 浏览器会话：起 Chrome 无头进程、开标签、维护底座进程内的会话表。
//!
//! 会话生命周期归底座 —— 句柄是底座进程内的一个整数，关掉句柄就杀掉对应的
//! Chrome 与标签，进程退出也不留孤儿（Chrome 以 `kill_on_drop` 语义收尾）。

use std::collections::HashMap;
use std::io::{BufRead, BufReader, Read};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex, OnceLock};

use serde_json::{Value, json};

use crate::浏览器通道::{请求调试口, 调试连接};
use crate::编号与码面::错误码;

/// 一条活着的浏览器会话。
///
/// 会话表只保存 `Arc`，命令取出引用后立即释放表锁；CDP 收发由会话专属的
/// 状态锁串行，因此不同会话可以同时收发，同一会话仍保持报文与序号一致。
pub(crate) struct 会话 {
    进程: Mutex<Child>,
    状态: Mutex<会话状态>,
    临时目录: String,
}

struct 会话状态 {
    标签连接: Option<调试连接>,
    指令序: u64,
    已关闭: bool,
    /// **通道已失步**：收发曾失败过 ⇒ 这条 CDP 连接不再可信。
    ///
    /// 为什么必须记下来：连接读写出错后直接抛错，会话在表里仍是「未关闭」，
    /// 下一条指令还会往同一根死管里写、再在 10 秒预算里空等一轮 —— 调用方看到的是
    /// 一串「处理超时」，既不是「会话没了」也不是「指令失败」。失步一旦成立，后续
    /// 指令立刻报连接失败，会话仍占着归属（Chrome 进程与临时目录都还在），
    /// 只能靠 [`关闭会话`] 显式收掉再重建 —— 未知不等于已回收，不静默换新会话。
    失步: bool,
}

struct 会话表容器 {
    会话表: HashMap<u32, Arc<会话>>,
    创建中: usize,
    已停止: bool,
}

static 会话表: OnceLock<Mutex<会话表容器>> = OnceLock::new();

fn 会话登记表() -> &'static Mutex<会话表容器> {
    会话表.get_or_init(|| {
        Mutex::new(会话表容器 {
            会话表: HashMap::new(),
            创建中: 0,
            已停止: false,
        })
    })
}

const 会话下限: usize = 8;
/// 单会话内存预算基准；容量公式与既有运行口径保持不变。
const 单会话预估字节: u64 = 632 * 1024 * 1024;

/// 上限只吃可用内存的 60%，留 40% 给系统本身和其他程序。
const 可用额度百分比: u64 = 60;

/// 会话上限按本机真实可用内存算，**不写死、也不设人为封顶**。
///
/// 为什么去掉封顶：封顶本身就是把「按机器自适应」又变回「按代码写死」。
/// 之前 clamp(8, 64) 把 256 GB 机器算出来的 220 个又砍回 64，等于没改。
/// 这里只保一个下限 8 兜住小机器，上限由可用内存自动决定。
fn 算会话上限() -> usize {
    let 可用 = 可用内存字节();
    if 可用 == 0 {
        return 会话下限; // 读不到内存就退回保守值，不用「读不到」当拒绝理由
    }
    let 额度 = 可用 / 100 * 可用额度百分比;
    let 算得出 = (额度 / 单会话预估字节) as usize;
    算得出.max(会话下限)
}

/// 可用内存 = `vm_stat` 的空闲页 + 非活跃页（非活跃页可立刻回收，算得上可用）。
///
/// 与大语言模型支持库 `模型服务.rs` 的同名函数同源。契约层 `v1_contract` 要求
/// 零依赖、签名冻结，放不进去；两边都是 20 行纯读，逻辑必须保持一致，
/// 改动时两边一起改。
fn 可用内存字节() -> u64 {
    let 输出 = match std::process::Command::new("/usr/bin/vm_stat").output() {
        Ok(输出) => 输出,
        Err(_) => return 0,
    };
    let 文本 = String::from_utf8_lossy(&输出.stdout);
    let mut 空闲页 = 0u64;
    let mut 非活跃页 = 0u64;
    let mut 页大小 = 4096u64;
    for 行 in 文本.lines() {
        if 行.contains("page size of") {
            if let Some(起) = 行.find("page size of") {
                let 剩余 = &行[起 + 12..];
                页大小 = 剩余
                    .split_whitespace()
                    .next()
                    .and_then(|数| 数.parse::<u64>().ok())
                    .unwrap_or(4096);
            }
            continue;
        }
        let 取数 = |键: &str| -> u64 {
            if !行.starts_with(键) {
                return 0;
            }
            行.split(':')
                .nth(1)
                .map(|尾| 尾.trim().trim_end_matches('.').to_owned())
                .and_then(|数| 数.parse::<u64>().ok())
                .unwrap_or(0)
        };
        空闲页 += 取数("Pages free");
        非活跃页 += 取数("Pages inactive");
    }
    (空闲页 + 非活跃页) * 页大小
}

/// 取走已退出会话；真正的进程与目录清理在表锁外完成。
fn 取出死会话(会话表锁: &mut 会话表容器) -> Vec<Arc<会话>> {
    let 死号: Vec<u32> = 会话表锁
        .会话表
        .iter()
        .filter_map(|(号, 会话项)| {
            let 已退出 = 会话项
                .进程
                .lock()
                .ok()
                .and_then(|mut 浏览器进程| 浏览器进程.try_wait().ok())
                .flatten()
                .is_some();
            已退出.then_some(*号)
        })
        .collect();
    死号
        .into_iter()
        .filter_map(|号| 会话表锁.会话表.remove(&号))
        .collect()
}

fn 清理浏览器资源(mut 浏览器进程: Child, 临时目录: &str) {
    let _ = 浏览器进程.kill();
    let _ = 浏览器进程.wait();
    let _ = std::fs::remove_dir_all(临时目录);
}

fn 清理会话资源(会话项: &Arc<会话>) {
    if let Ok(mut 会话状态) = 会话项.状态.lock() {
        会话状态.已关闭 = true;
        let _ = 会话状态.标签连接.take();
    }
    if let Ok(mut 浏览器进程) = 会话项.进程.lock() {
        let _ = 浏览器进程.kill();
        let _ = 浏览器进程.wait();
    }
    let _ = std::fs::remove_dir_all(&会话项.临时目录);
}

fn 结束创建失败() {
    if let Ok(mut 会话表锁) = 会话登记表().lock() {
        会话表锁.创建中 = 会话表锁.创建中.saturating_sub(1);
    }
}

fn 登记创建会话(会话项: Arc<会话>) -> Result<u32, u32> {
    let mut 会话表锁 = match 会话登记表().lock() {
        Ok(会话表锁) => 会话表锁,
        Err(_) => {
            清理会话资源(&会话项);
            return Err(错误码::处理失败);
        }
    };
    会话表锁.创建中 = 会话表锁.创建中.saturating_sub(1);
    if 会话表锁.已停止 {
        drop(会话表锁);
        清理会话资源(&会话项);
        return Err(错误码::启动失败);
    }
    let 句柄 = 下一个句柄(&会话表锁.会话表);
    会话表锁.会话表.insert(句柄, 会话项);
    Ok(句柄)
}

/// 造一个新会话，返回句柄。表锁只负责预约与登记，不包住浏览器启动。
pub(crate) fn 创建会话(临时根: &str) -> Result<u32, u32> {
    let 上限 = 算会话上限();
    let (死会话, 允许创建) = {
        let mut 会话表锁 = 会话登记表().lock().map_err(|_| 错误码::处理失败)?;
        if 会话表锁.已停止 {
            return Err(错误码::启动失败);
        }
        let 死会话 = 取出死会话(&mut 会话表锁);
        let 允许创建 = 会话表锁.会话表.len() + 会话表锁.创建中 < 上限;
        if 允许创建 {
            会话表锁.创建中 += 1;
        }
        (死会话, 允许创建)
    };
    for 会话项 in 死会话 {
        清理会话资源(&会话项);
    }
    if !允许创建 {
        return Err(错误码::资源超限);
    }

    let 目录 = format!("{}/v1-browser-{}", 临时根, 时间戳());
    if std::fs::create_dir_all(&目录).is_err() {
        结束创建失败();
        return Err(错误码::启动失败);
    }
    let (进程, 端口) = match 起浏览器(&目录) {
        Ok(启动返回) => 启动返回,
        Err(码) => {
            let _ = std::fs::remove_dir_all(&目录);
            结束创建失败();
            return Err(码);
        }
    };
    let 标签路径 = match 开标签(端口) {
        Ok(路径) => 路径,
        Err(码) => {
            清理浏览器资源(进程, &目录);
            结束创建失败();
            return Err(码);
        }
    };
    let 连接 = match 调试连接::建连(端口, &标签路径) {
        Ok(连接) => 连接,
        Err(码) => {
            清理浏览器资源(进程, &目录);
            结束创建失败();
            return Err(码);
        }
    };
    let 会话项 = Arc::new(会话 {
        进程: Mutex::new(进程),
        状态: Mutex::new(会话状态 {
            标签连接: Some(连接),
            指令序: 0,
            已关闭: false,
            失步: false,
        }),
        临时目录: 目录,
    });
    登记创建会话(会话项)
}

/// Chrome 可执行文件位置；找不到就如实报平台不支持
fn 查浏览器路径() -> Result<String, u32> {
    let 候选 = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ];
    for 路径 in 候选 {
        if std::path::Path::new(路径).is_file() {
            return Ok(路径.to_string());
        }
    }
    Err(错误码::平台不支持)
}

/// 起 Chrome 并从它的输出里取调试端口。
///
/// **两条流都要读**：Chrome 把「DevTools listening on ws://…」打在 stderr，
/// 但某些构建/参数组合会走 stdout（实测踩过：只读一条永远等不到，进程挂到超时）。
fn 起浏览器(临时目录: &str) -> Result<(Child, u16), u32> {
    let 路径 = 查浏览器路径()?;
    let mut 子进程 = Command::new(&路径)
        .args([
            "--headless=new",
            "--remote-debugging-port=0",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-gpu",
            "--disable-extensions",
            "--mute-audio",
            &format!("--user-data-dir={}", 临时目录),
            "about:blank",
        ])
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|_| 错误码::启动失败)?;
    let (发送端, 接收端) = std::sync::mpsc::channel::<u16>();
    for 管道 in [
        子进程
            .stdout
            .take()
            .map(|流| Box::new(流) as Box<dyn Read + Send>),
        子进程
            .stderr
            .take()
            .map(|流| Box::new(流) as Box<dyn Read + Send>),
    ]
    .into_iter()
    .flatten()
    {
        let 发送副本 = 发送端.clone();
        std::thread::spawn(move || {
            let mut 读取器 = BufReader::new(管道);
            let mut 行缓冲 = String::new();
            loop {
                行缓冲.clear();
                if 读取器.read_line(&mut 行缓冲).unwrap_or(0) == 0 {
                    break;
                }
                const 前缀: &str = "DevTools listening on ws://";
                if let Some(位) = 行缓冲.find(前缀) {
                    let 尾巴 = &行缓冲[位 + 前缀.len()..];
                    let 主机段 = 尾巴.split('/').next().unwrap_or("");
                    if let Some(端口) = 主机段
                        .rsplit(':')
                        .next()
                        .and_then(|文| 文.trim().parse::<u16>().ok())
                    {
                        let _ = 发送副本.send(端口);
                        break;
                    }
                }
            }
            // 之后继续把剩余输出读空，避免管道写满把 Chrome 卡住
            let mut 丢弃 = String::new();
            while 读取器.read_line(&mut 丢弃).unwrap_or(0) > 0 {
                丢弃.clear();
            }
        });
    }
    match 接收端.recv_timeout(std::time::Duration::from_secs(10)) {
        Ok(端口) => Ok((子进程, 端口)),
        Err(_) => {
            let _ = 子进程.kill();
            let _ = 子进程.wait();
            Err(错误码::启动失败)
        }
    }
}

/// 开一个新标签，返回对应标签的调试地址路径
fn 开标签(端口: u16) -> Result<String, u32> {
    let 响应体 = 请求调试口(端口, "PUT", "/json/new?about:blank")?;
    let 值: Value = serde_json::from_str(&响应体).map_err(|_| 错误码::协议不符)?;
    let 地址 = 值
        .get("webSocketDebuggerUrl")
        .and_then(|项| 项.as_str())
        .ok_or(错误码::协议不符)?;
    // ws://127.0.0.1:PORT/devtools/page/XXX → 取路径部分
    let 路径 = 地址.splitn(4, '/').nth(3).ok_or(错误码::协议不符)?;
    Ok(format!("/{}", 路径))
}

fn 下一个句柄(会话表映射: &HashMap<u32, Arc<会话>>) -> u32 {
    let mut 候选 = 1u32;
    while 会话表映射.contains_key(&候选) {
        候选 += 1;
    }
    候选
}

fn 时间戳() -> u128 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|时长| 时长.as_millis())
        .unwrap_or(0)
}

/// 在指定会话上执行一条 CDP 指令，等对应回执（id 对得上才算）。
/// 表锁只保护句柄查找；后续收发只锁当前会话。
pub(crate) fn 发指令(句柄: u32, 方法: &str, 参数: Value) -> Result<Value, u32> {
    let 会话项 = {
        let 会话表锁 = 会话登记表().lock().map_err(|_| 错误码::处理失败)?;
        Arc::clone(会话表锁.会话表.get(&句柄).ok_or(错误码::会话不存在)?)
    };
    let mut 会话状态 = 会话项.状态.lock().map_err(|_| 错误码::处理失败)?;
    if 会话状态.已关闭 {
        return Err(错误码::会话不存在);
    }
    if 会话状态.失步 {
        // 已经失步的会话不再发：见 `会话状态::失步` 的说明。
        return Err(错误码::连接失败);
    }
    会话状态.指令序 += 1;
    let 本次序 = 会话状态.指令序;
    let 报文 = json!({"id": 本次序, "method": 方法, "params": 参数}).to_string();
    let 发失败 = 会话状态
        .标签连接
        .as_mut()
        .ok_or(错误码::会话不存在)?
        .发文本(&报文)
        .is_err();
    if 发失败 {
        let _ = 会话状态.标签连接.take();
        会话状态.失步 = true;
        return Err(错误码::连接失败);
    }
    let 截止 = std::time::Instant::now() + std::time::Duration::from_secs(10);
    while std::time::Instant::now() < 截止 {
        let 回 = match 会话状态
            .标签连接
            .as_mut()
            .ok_or(错误码::会话不存在)?
            .收文本()
        {
            Ok(回) => 回,
            Err(_) => {
                let _ = 会话状态.标签连接.take();
                会话状态.失步 = true;
                return Err(错误码::连接失败);
            }
        };
        let 值: Value = serde_json::from_str(&回).map_err(|_| 错误码::协议不符)?;
        if 值.get("id").and_then(|序| 序.as_u64()) == Some(本次序) {
            if 值.get("error").is_some() {
                return Err(错误码::指令失败);
            }
            return Ok(值.get("result").cloned().unwrap_or(Value::Null));
        }
    }
    Err(错误码::处理超时)
}

/// 关会话：先摘掉归属，再等待在途指令收尾，最后杀浏览器并清目录。
pub(crate) fn 关闭会话(句柄: u32) -> Result<bool, u32> {
    let 会话项 = {
        let mut 会话表锁 = 会话登记表().lock().map_err(|_| 错误码::处理失败)?;
        会话表锁.会话表.remove(&句柄).ok_or(错误码::会话不存在)?
    };
    清理会话资源(&会话项);
    Ok(true)
}

/// 允许生命周期装载通知重新接收会话创建。
pub(crate) fn 开始接收会话() {
    if let Ok(mut 会话表锁) = 会话登记表().lock() {
        会话表锁.已停止 = false;
    }
}

/// 进程退出前把还会话全收掉（避免留孤儿 Chrome）。
pub(crate) fn 全部关闭() {
    loop {
        let (会话项, 创建中) = {
            let Ok(mut 会话表锁) = 会话登记表().lock() else {
                return;
            };
            会话表锁.已停止 = true;
            let 会话项 = 会话表锁
                .会话表
                .drain()
                .map(|(_, 会话项)| 会话项)
                .collect::<Vec<_>>();
            (会话项, 会话表锁.创建中)
        };
        for 会话项 in 会话项 {
            清理会话资源(&会话项);
        }
        if 创建中 == 0 {
            return;
        }
        std::thread::sleep(std::time::Duration::from_millis(10));
    }
}

#[cfg(test)]
mod 测试 {
    use super::*;

    #[test]
    fn 失败资源清理可回收受控子进程() {
        let 临时目录 = std::env::temp_dir().join(format!("v1-browser-cleanup-{}", 时间戳()));
        std::fs::create_dir_all(&临时目录).expect("创建测试目录失败");
        let 子进程 = Command::new("/bin/sh")
            .args(["-c", "sleep 10"])
            .spawn()
            .expect("启动受控测试进程失败");
        清理浏览器资源(子进程, 临时目录.to_string_lossy().as_ref());
        assert!(!临时目录.exists(), "失败路径必须清理临时目录");
    }
}
