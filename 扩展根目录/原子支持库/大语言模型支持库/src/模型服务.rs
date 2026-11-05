//! 模型服务生命周期：拉起 · 就绪等待 · 状态读数 · 释放。
//!
//! # 为什么这口必须在底座里
//!
//! 2026-11-04 现场抓到的问题：调用方直接 `llama-server …` 起模型，进程父是调用方，
//! 既不归空闲回收、也不归任何登记表，空转 22 小时白占内存。根因不是「没人写回收」，
//! 而是**拉起这件事没有唯一入口**。本件就是那个入口：
//! 只有经 `拉起模型服务` 起的进程才进本表，表内进程才有状态读数、才归 `释放模型服务` 收。
//!
//! # 状态机
//!
//! ```text
//! 拉起 ──► 启动中 ──(端口就绪)──► 就绪 ──(释放)──► 已退出
//!            └──(超时/进程退)──► 失败（条目保留，状态里可读出原因）
//! ```
//!
//! # 边界（不做的事）
//!
//! - 不代理推理请求：请求仍走 `连接模型` / `提交生成任务`，本件只管进程。
//! - 不猜端口：`监听端口` 由调用方给，本件只探活，不做「找一个空端口」这种魔法。
//! - 不按端口或进程名盲杀：释放只认本表登记的进程号。

use std::collections::{HashMap, HashSet};
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Mutex, OnceLock};
use std::time::{Duration, Instant};

use crate::编号与码面::错误码;

/// 一条已登记的模型服务。
pub(crate) struct 服务条目 {
    /// 这个服务跑的是哪个模型 —— 由调用方传的标识或绝对路径解析而来（路径会被校验）。
    pub(crate) 模型标识: String,
    pub(crate) 进程号: u32,
    pub(crate) 监听端口: u16,
    /// 模型类型：文本 / 看图 / 向量 / 重排 / 语音。决定默认就绪路径与后续该用哪对能力。
    pub(crate) 模型类型: String,
    pub(crate) 就绪路径: String,
    pub(crate) 启动时刻: Instant,
    pub(crate) 子进程: Child,
}

/// 取表锁：中毒即视为资源受限（不 panic —— 扩展里 panic 会带垮整个调用）。
fn 取锁(
    锁: &'static Mutex<HashMap<u64, 服务条目>>,
) -> Result<std::sync::MutexGuard<'static, HashMap<u64, 服务条目>>, u32> {
    锁.lock().map_err(|_| 错误码::资源受限)
}

fn 服务表() -> &'static Mutex<HashMap<u64, 服务条目>> {
    模型服务表.get_or_init(|| Mutex::new(HashMap::new()))
}

static 模型服务表: OnceLock<Mutex<HashMap<u64, 服务条目>>> = OnceLock::new();
static 下一句柄: AtomicU64 = AtomicU64::new(900_001);

/// 句柄上限：与连接句柄同一量级（64），防止调用方无节制拉起进程。
const 服务上限: usize = 16;

/// 端口就绪探测：连得上即算端口在听（不要求 HTTP 语义，健康口各模型自定）。
fn 端口就绪(端口: u16) -> bool {
    use std::net::{SocketAddr, TcpStream};
    let 地址 = SocketAddr::from(([127, 0, 0, 1], 端口));
    TcpStream::connect_timeout(&地址, Duration::from_millis(200)).is_ok()
}

/// 手写一个 HTTP GET 只取状态码（不引第三方依赖：这是底座，少一个依赖少一份风险）。
fn 探状态码(端口: u16, 路径: &str) -> Option<u16> {
    use std::io::{Read, Write};
    use std::net::{SocketAddr, TcpStream};
    let 地址 = SocketAddr::from(([127, 0, 0, 1], 端口));
    let mut 流 = TcpStream::connect_timeout(&地址, Duration::from_millis(300)).ok()?;
    流.set_read_timeout(Some(Duration::from_millis(800))).ok()?;
    let 请求 = format!("GET {路径} HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n");
    流.write_all(请求.as_bytes()).ok()?;
    let mut 缓冲 = [0u8; 64];
    let 读入 = 流.read(&mut 缓冲).ok()?;
    std::str::from_utf8(&缓冲[..读入]).ok()?.split_whitespace().nth(1)?.parse().ok()
}

/// 模型类型受控枚举：类型不认识就直接拒（不等到调用时才发现拿错能力）。
///
/// 收口成五个词，不做自由文本 —— 自由文本等于没校验。别名按「去掉空格+小写」比对。
/// 模型类型的**唯一词表**。传参、服务表、状态回执全用这五个词，不许再出现第二套写法。
///
/// 为什么只留五个、不认别名：别名一开口，下游就会各写各的（文本 / LLM / 文本模型 / 大模型…），
/// 最后没人确定该传哪个，反而变成四不像。要加类型就改这张表，别在调用方发明新词。
pub(crate) const 模型类型表: [&str; 5] = [
    "LLM文本模型",
    "VLM看图模型",
    "EM向量模型",
    "Rerank重排模型",
    "ASR语音识别模型",
];

pub(crate) fn 规整模型类型(原文: &str) -> Result<&'static str, u32> {
    let 紧凑: String = 原文.chars().filter(|c| !c.is_whitespace() && *c != '\0').collect();
    for 允许 in 模型类型表 {
        if 紧凑 == 允许 {
            return Ok(允许);
        }
    }
    Err(错误码::参数不合法)
}

/// 默认就绪路径：给空就按类型取。文本/看图/向量/重排都是 llama-server 家族，认 `/health`；
/// 语音常见服务只认根路径。
fn 默认就绪路径(模型类型: &str) -> &'static str {
    match 模型类型 {
        "ASR语音识别模型" => "/",
        _ => "/health",
    }
}

/// 内存预算：按模型文件大小估算需要多少，再看本机还剩多少，不够就回 `资源受限`。
///
/// 估算口径：权重按文件大小（GGUF 基本就是实际占用），再乘 `1.15` 覆盖上下文 KV 与运行时开销。
/// 判定口径：可用内存取 `vm_stat` 的空闲 + 非活跃页，再打八折当安全余量 —— 打得紧一点，
/// 因为 macOS 会拿「空闲」去做缓存，看着还有很多其实一压就换页。
///
/// 模型文件未知（调用方传的是纯名字）就跳过预算：外部模型不在本机，无从估算。
fn 内存预算够吗(模型文件: Option<&str>) -> Result<(), u32> {
    let 路径 = match 模型文件 {
        Some(路径) => 路径,
        None => return Ok(()),
    };
    let 文件字节 = match std::fs::metadata(路径) {
        Ok(元) => 元.len(),
        Err(_) => return Ok(()), // 文件问题由上游解析那一步报，这里不重复判
    };
    let 需求字节 = (文件字节 as f64 * 1.15) as u64 + 512 * 1024 * 1024;
    let 可用字节 = 可用内存字节();
    if 可用字节 == 0 {
        return Ok(()); // 读不到内存就放行，不用「读不到」当拒绝理由
    }
    if 需求字节 > (可用字节 as f64 * 0.8) as u64 {
        return Err(错误码::资源受限);
    }
    Ok(())
}

/// 可用内存 = `vm_stat` 的空闲页 + 非活跃页（非活跃页可以立刻回收，算得上可用）。
/// 读不到返回 0，由调用方决定放行。
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
            // 形如：Mach Virtual Memory Statistics: (page size of 16384 bytes)
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

/// 分配一个空闲端口：40000-49999 里既没在听、也没被服务表占用的第一个。
fn 分配空闲端口(表: &HashMap<u64, 服务条目>, 预占: &HashSet<u16>) -> Option<u16> {
    (40000..50000u16).find(|候选| {
        !端口就绪(*候选)
            && !表.values().any(|条目| 条目.监听端口 == *候选)
            && !预占.contains(候选)
    })
}

/// 预占端口表：「已经分配出去、但进程还没起来」的那一段窗口。
///
/// 为什么需要它：端口释放锁以后到进程真正 listen 之前有一段空窗，这期间 `端口就绪()`
/// 探不到、服务表里也还没登记 —— 并发的第二个请求会算出同一个「第一个空闲端口」。
/// 实测同时拉起 8 个，8 个全分到 `40002`，只有第一个真能服务。
static 预占表: OnceLock<Mutex<HashSet<u16>>> = OnceLock::new();

fn 预占锁() -> Result<std::sync::MutexGuard<'static, HashSet<u16>>, u32> {
    预占表
        .get_or_init(Default::default)
        .lock()
        .map_err(|_| 错误码::资源受限)
}

/// 预占守卫：无论拉起成功、失败还是中途返回，离开作用域都把这个端口还回去，
/// 不靠每条失败路径记得写一次 `remove`（漏一处就等于永久泄漏一个端口）。
struct 预占守卫(u16);

impl Drop for 预占守卫 {
    fn drop(&mut self) {
        if let Ok(mut 占) = 预占锁() {
            占.remove(&self.0);
        }
    }
}

/// 真就绪 = 端口在听 + 就绪路径回 200 + （服务若有 `/health`，它也必须是 200）。
///
/// 为什么不能只看端口、也不能只看 `/v1/models`：llama-server 在**模型还没加载完**时
/// `/v1/models` 就回 200，但 `/v1/chat/completions` 直接 **503** —— 表现是「显示已就绪、
/// 一问就挂」（2026-11-04 实测）。`/health` 才是真判据：加载中 503、加载完 200。
/// 对没有 `/health` 的服务（回 404 或连不上），退回到只看就绪路径，不误判。
fn 真就绪(端口: u16, 就绪路径: &str) -> bool {
    if !端口就绪(端口) {
        return false;
    }
    if 探状态码(端口, 就绪路径) != Some(200) {
        return false;
    }
    match 探状态码(端口, "/health") {
        Some(200) => true,
        Some(503) => false,
        _ => true,
    }
}

/// 进程是否**还在跑**。
///
/// 为什么不用 `kill(pid, 0)`：那个对**僵尸进程**返回成功（僵尸仍占着进程号），
/// 会让我们把「已经死了、只是还没被回收」判成存活 —— 实测症状是释放一直等到超时、
/// 状态永远显示「启动中」。`try_wait` 顺便把僵尸回收掉，语义是「还在跑」而非「进程表里有这行」。
fn 判存活(子进程: &mut Child) -> bool {
    match 子进程.try_wait() {
        Ok(None) => true,
        Ok(Some(_)) => false,
        Err(_) => false,
    }
}

/// 进程累计 CPU 时间（毫秒）：读 `ps -o time=`，取不到回 `None`（不猜 0）。
///
/// 为什么不走 `proc_pid_rusage`：那是 macOS 私有结构，字段随系统版本变；
/// `ps` 的输出稳定、代价约 5 毫秒，而本口只在**主动查状态**时调一次，不在高频路径上。
pub(crate) fn 取CPU毫秒(进程号: u32) -> Option<u64> {
    // 绝对路径：扩展进程的环境不一定带 PATH（实测用裸 `ps` 取不到读数，CPU毫秒 恒为 null）。
    let 输出 = Command::new("/bin/ps")
        .args(["-o", "time=", "-p", &进程号.to_string()])
        .output()
        .ok()?;
    if !输出.status.success() {
        return None;
    }
    let 文本 = String::from_utf8_lossy(&输出.stdout);
    解析CPU时间(文本.trim())
}

/// `[[日-]时:]分:秒[.厘秒]` → 毫秒。
///
/// `ps -o time=` 的真形状（macOS 实测）：`105:27.90` / `0:04.11` / `1:02:03.45` / `1-02:03:04.56`。
/// **秒段带两位小数**（厘秒），按整数解析会一律失败 —— 那正是「CPU毫秒 恒为 null」的真因。
pub(crate) fn 解析CPU时间(文本: &str) -> Option<u64> {
    let 文本 = 文本.trim();
    if 文本.is_empty() {
        return None;
    }
    let (天数, 剩余) = match 文本.split_once('-') {
        Some((天数字, 尾部)) => (天数字.parse::<u64>().ok()?, 尾部),
        None => (0, 文本),
    };
    let 段: Vec<&str> = 剩余.split(':').collect();
    let 秒段: f64 = 段.last()?.parse().ok()?;
    let 毫秒 = match 段.len() {
        2 => 段[0].parse::<u64>().ok()? * 60_000 + (秒段 * 1_000.0).round() as u64,
        3 => {
            段[0].parse::<u64>().ok()? * 3_600_000
                + 段[1].parse::<u64>().ok()? * 60_000
                + (秒段 * 1_000.0).round() as u64
        }
        _ => return None,
    };
    Some(天数 * 86_400_000 + 毫秒)
}

/// 拉起：起进程 → 登记 → 返回句柄。**就绪要另调 `等待模型就绪`**（拉起不干等）。
pub(crate) fn 拉起(
    模型标识: &str,
    模型文件: Option<&str>,
    可执行文件: &str,
    启动参数: &str,
    监听端口: u16,
    就绪路径: &str,
    模型类型: &str,
) -> Result<u64, u32> {
    if 模型标识.trim().is_empty() || 可执行文件.trim().is_empty() {
        return Err(错误码::参数不合法);
    }
    let 模型类型 = 规整模型类型(模型类型)?;
    // 内存预算先过一遍：不够就当场拒，不「先拉起再说」。
    // 撑爆内存的后果是整机变卡、别人正在跑的模型一起遭殃，而且事后查不出是谁拉起来的。
    内存预算够吗(模型文件)?;
    // 端口 0 = 由底座分配：调用方不必先找空端口，也就不会撞。（服务表已登记的端口一并避开）
    let (端口, 就绪路径) = {
        let 表 = 取锁(服务表()).map_err(|_| 错误码::资源受限)?;
        // 这里提前查一次只为「省得起进程」，不是最终判据 —— 真正的上限在登记那把锁里判，
        // 因为这两次查表之间进程可能已经被别人登记进去了。
        if 表.len() >= 服务上限 {
            return Err(错误码::资源受限);
        }
        // 分配和预占必须在同一把锁内做完：先算再占，中间不能让别的请求插进来。
        let mut 占 = 预占锁()?;
        let 端口 = if 监听端口 == 0 {
            分配空闲端口(&表, &占).ok_or(错误码::资源受限)?
        } else {
            监听端口
        };
        if 占.contains(&端口) {
            return Err(错误码::端口已被占用);
        }
        if 表.values().any(|条目| 条目.监听端口 == 端口) {
            return Err(错误码::端口已被占用);
        }
        占.insert(端口);
        drop(占);
        let 路径 = if 就绪路径.trim().is_empty() {
            默认就绪路径(&模型类型)
        } else {
            就绪路径
        };
        (端口, 路径)
    };
    // 从这一刻起端口被预占；拉起结束（成功或失败）守卫销毁时自动还回去。
    let _端口守卫 = 预占守卫(端口);
    let 监听端口 = 端口;
    if 端口就绪(监听端口) {
        // 端口已被占：不许再起一个同端口的进程（那是典型的孤儿来源）。
        return Err(错误码::端口已被占用);
    }
    // `{端口}` 占位符换成实际端口：端口 0 自动分配时，模型进程也必须知道落到哪个端口，
    // 否则模型监听它内置的默认端口、和底座登记的对不上。不猜各家的端口参数名，只做占位替换。
    // `{模型文件}` 同理：模型文件路径已经在入参里给过一次，启动参数里不该再抄一遍
    // （抄两遍就会两边不一致，改了一处忘了另一处）。没给路径却用了占位符，当场报参数不合法。
    let 带文件 = match 模型文件 {
        Some(路径) => 启动参数.replace("{模型文件}", 路径),
        None if 启动参数.contains("{模型文件}") => return Err(错误码::参数不合法),
        None => 启动参数.to_owned(),
    };
    let 实际参数 = 带文件.replace("{端口}", &监听端口.to_string());
    let 参数向量: Vec<String> = 实际参数.split_whitespace().map(str::to_owned).collect();
    let 子进程 = Command::new(可执行文件)
        .args(参数向量.iter())
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|_| 错误码::拉起失败)?;
    let 进程号 = 子进程.id();
    let 句柄 = 下一句柄.fetch_add(1, Ordering::AcqRel);
    let mut 表 = 取锁(服务表()).map_err(|_| 错误码::资源受限)?;
    // 上限的最终判据在这里：进程已经起来了，再拒就必须先把它收干净，
    // 否则留下一个不归任何句柄管的孤儿进程，端口也一直被它占着。
    if 表.len() >= 服务上限 {
        unsafe extern "C" {
            fn kill(进程号: i32, 信号: i32) -> i32;
        }
        let mut 待收 = 子进程;
        unsafe { kill(进程号 as i32, 9) };
        let _ = 待收.wait();
        return Err(错误码::资源受限);
    }
    表.insert(
        句柄,
        服务条目 {
            模型标识: 模型标识.to_owned(),
            进程号,
            监听端口,
            模型类型: 模型类型.to_owned(),
            就绪路径: 就绪路径.to_owned(),
            启动时刻: Instant::now(),
            子进程,
        },
    );
    Ok(句柄)
}

/// 该服务句柄是否仍在表内（许可申请前用它挡住「已释放的服务」）。
pub(crate) fn 服务存在(句柄: u64) -> bool {
    match 服务表().lock() {
        Ok(表) => 表.contains_key(&句柄),
        Err(_) => false,
    }
}

/// 等待就绪：轮询「端口在听」，超时即假（不把超时说成成功）。
pub(crate) fn 等待就绪(句柄: u64, 超时毫秒: u64) -> Result<bool, u32> {
    let (端口, 就绪路径) = {
        let 表 = 取锁(服务表()).map_err(|_| 错误码::资源受限)?;
        let 条目 = 表.get(&句柄).ok_or(错误码::服务无效)?;
        (条目.监听端口, 条目.就绪路径.clone())
    };
    // 单次等待封顶 3 秒：顶到 5 秒会先撞内核调用预算，调用方拿到的是内核 `4 超时`
    // 而不是本能力的判定（实测踩过）。模型加载慢就多次调用，不靠一次长等。
    let 截止 = Instant::now() + Duration::from_millis(超时毫秒.min(3_000));
    loop {
        if 真就绪(端口, &就绪路径) {
            return Ok(true);
        }
        let 仍在跑 = {
            let mut 表 = 取锁(服务表()).map_err(|_| 错误码::资源受限)?;
            let 条目 = 表.get_mut(&句柄).ok_or(错误码::服务无效)?;
            判存活(&mut 条目.子进程)
        };
        if !仍在跑 {
            // 进程已退：不是「还没起来」，是起不来 —— 明确报失败。
            return Err(错误码::拉起失败);
        }
        if Instant::now() >= 截止 {
            return Ok(false);
        }
        std::thread::sleep(Duration::from_millis(200));
    }
}

/// 取状态：存活 / 端口就绪 / CPU 毫秒 / 运行秒数。读数取不到给 `null`，不给 0。
pub(crate) fn 取状态(句柄: u64) -> Result<serde_json::Value, u32> {
    let mut 表 = 取锁(服务表()).map_err(|_| 错误码::资源受限)?;
    let 条目 = 表.get_mut(&句柄).ok_or(错误码::服务无效)?;
    let 存活 = 判存活(&mut 条目.子进程);
    let 就绪 = 存活 && 端口就绪(条目.监听端口);
    let CPU毫秒 = if 存活 {
        serde_json::json!(取CPU毫秒(条目.进程号))
    } else {
        serde_json::json!(null)
    };
    Ok(serde_json::json!({
        "服务句柄": 句柄,
        "进程号": 条目.进程号,
        "监听端口": 条目.监听端口,
        "存活": 存活,
        "端口就绪": 就绪,
        "运行秒": 条目.启动时刻.elapsed().as_secs(),
        // 底座把「模型标识 / 绝对路径」翻译成了哪个 model 名 —— 得让人看得见，
        // 否则调用方没法确认传进来那条路径到底被认成了什么。
        "模型标识": 条目.模型标识,
        "模型类型": 条目.模型类型,
        "就绪路径": 条目.就绪路径,
        "CPU毫秒": CPU毫秒,
        "状态": if 就绪 { "就绪" } else if 存活 { "启动中" } else { "已退出" },
    }))
}

/// 释放：先 SIGTERM，短暂等待，仍不退再 SIGKILL；条目出表。
///
/// 返回真 = 确认进程已不在（不是「信号已发送」）；假 = 进程仍在跑，条目保留待重试。
/// 释放：**幂等**，且给得出「进程真不退」时的逃生口。
///
/// * 句柄本来就不在表里 ⇒ 回真。目标状态是「这个进程不在」，已经达成了，重复释放不算错。
/// * `强制` = 假：SIGTERM → 等 → SIGKILL → 仍不退就**保留条目**（回假，等下次重试）。
/// * `强制` = 真：不管进程退没退，一律从表里摘除并回真。用于进程彻底卡死（D 状态）时
///   解封句柄与端口 —— 代价是可能留下一个孤儿进程，所以要调用方明确选择才做。
pub(crate) fn 释放(句柄: u64, 强制: bool) -> Result<bool, u32> {
    unsafe extern "C" {
        fn kill(进程号: i32, 信号: i32) -> i32;
    }
    const 终止信号: i32 = 15;
    const 强杀信号: i32 = 9;
    // 第一阶段只发信号、不持锁（等进程退出期间别的调用还要读状态）。
    let (进程号, 仍在跑) = {
        let mut 表 = 取锁(服务表()).map_err(|_| 错误码::资源受限)?;
        // 幂等：句柄不在表里（从没起过 / 已经被别人释放掉）都回真。
        // 报「服务无效」会让并发释放的后到者以为失败，实际上目标状态早就达成了。
        let 条目 = match 表.get_mut(&句柄) {
            Some(条目) => 条目,
            None => return Ok(true),
        };
        let 仍在跑 = 判存活(&mut 条目.子进程);
        (条目.进程号, 仍在跑)
    };
    if 仍在跑 {
        // SAFETY: 只向本表登记的进程号发信号。
        unsafe { kill(进程号 as i32, 终止信号) };
    }
    // 第二阶段：轮询「真的退出了没有」（try_wait 会顺手回收僵尸，不会被僵尸骗成存活）。
    let mut 已退 = !仍在跑;
    for _ in 0..25 {
        if 已退 {
            break;
        }
        std::thread::sleep(Duration::from_millis(200));
        let mut 表 = 取锁(服务表()).map_err(|_| 错误码::资源受限)?;
        match 表.get_mut(&句柄) {
            Some(条目) => 已退 = !判存活(&mut 条目.子进程),
            // 别人先释放掉了：同样算已退，不报错。
            None => {
                已退 = true;
                break;
            }
        }
    }
    if !已退 {
        // SAFETY: 同上；此时已确认是本表登记的、仍在运行的进程。
        unsafe { kill(进程号 as i32, 强杀信号) };
        std::thread::sleep(Duration::from_millis(400));
        let mut 表 = 取锁(服务表()).map_err(|_| 错误码::资源受限)?;
        match 表.get_mut(&句柄) {
            Some(条目) => 已退 = !判存活(&mut 条目.子进程),
            None => 已退 = true,
        }
    }
    let mut 表 = 取锁(服务表()).map_err(|_| 错误码::资源受限)?;
    if 已退 || 强制 {
        表.remove(&句柄);
    }
    Ok(已退 || 强制)
}

#[cfg(test)]
#[test]
fn CPU时间解析认得厘秒与天段() {
    // macOS `ps -o time=` 的真实形状（带两位小数）。
    assert_eq!(解析CPU时间("105:27.90"), Some(6_327_900));
    assert_eq!(解析CPU时间("0:04.11"), Some(4_110));
    assert_eq!(解析CPU时间("1:02:03.45"), Some(3_723_450));
    assert_eq!(解析CPU时间("1-02:03:04.56"), Some(93_784_560));
    // 取不到就给 None，不猜 0。
    assert_eq!(解析CPU时间(""), None);
    assert_eq!(解析CPU时间("   "), None);
    assert_eq!(解析CPU时间("abc"), None);
}

/// 模型的「引用」解析结果：调用方给什么都能认，最后落到一个确定的标识上。
pub(crate) struct 模型引用 {
    /// 请求体里该写的 model 名（由路径或名字解析出来的）
    pub(crate) 标识: String,
    /// 当引用是绝对路径时带回原路径，供拉起时用
    pub(crate) 文件路径: Option<String>,
}

/// 把「模型引用」翻译成确定标识 —— 这就是那个转化器。
///
/// * 传纯名字（`qwen3`）：原样返回，无从校验（外部模型本来就不在本机）。
/// * 传绝对路径（`/…/Qwen3-8B-Q4_K_M.gguf`）：**先校验文件真的在**，再把文件名
///   （去扩展名）当作 model 名。
///
/// 为什么非要校验：把模型名当自由文本传，模型在不在本机没人知道，要等推理时才炸；
/// 传路径则当场炸，错得早、错得准。
pub(crate) fn 解析模型引用(引用: &str) -> Result<模型引用, u32> {
    let 去空 = 引用.trim();
    if 去空.is_empty() {
        return Err(错误码::参数不合法);
    }
    let 看着像路径 = 去空.contains('/')
        || 去空.contains('\\')
        || 去空.to_lowercase().ends_with(".gguf")
        || 去空.to_lowercase().ends_with(".ggml")
        || 去空.to_lowercase().ends_with(".bin");
    if !看着像路径 {
        return Ok(模型引用 {
            标识: 去空.to_owned(),
            文件路径: None,
        });
    }
    match std::fs::metadata(去空) {
        Ok(元) if 元.is_file() && 元.len() > 0 => {}
        _ => return Err(错误码::模型文件不存在),
    }
    let 文件名 = 去空.rsplit(['/', '\\']).next().unwrap_or(去空);
    let 基名 = 文件名.rsplit_once('.').map(|(前, _)| 前).unwrap_or(文件名);
    if 基名.trim().is_empty() {
        return Err(错误码::参数不合法);
    }
    Ok(模型引用 {
        标识: 基名.to_owned(),
        文件路径: Some(去空.to_owned()),
    })
}

