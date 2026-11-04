//! 推理许可：**按模型服务分槽**，同一个模型内串行、不同模型之间并行。
//!
//! # 为什么这口在底座里
//!
//! GPU 利用率不是判据 —— 正常推理瞬间冲到 100% 很正常。要管的是**同一个模型**上
//! 别同时压两个推理：同一进程共享一份 GPU 上下文与 KV 缓存，两个请求挤进去只会互相
//! 拖慢，读数也没法归因到谁。
//!
//! 但**不同模型必须能同时跑**：它们是各自独立的进程，显存与算力由驱动调度，
//! 底座不该替驱动做串行决定 —— 全局一把锁会把整台机器的并行能力废掉
//! （实测：13B 在推理时，26B / 32B 全都排队超时）。
//!
//! # 状态机
//!
//! ```text
//! 申请 ──(无人持有)──────────────► 授予 ──(归还)──► 空闲
//!        ├─(有人持有)──► 排队 ──(等待超时)──► 排队超时
//!        └─(持有者超租约)──► 强制回收后授予（计入超租约回收次数）
//! ```
//!
//! # 边界（不做的事）
//!
//! - 只颁发许可：不代理推理、不读 GPU 利用率；**常驻服务待命不占许可**（许可是推理级独占）。
//! - 不按端口/进程名判归属；租约到期只在下一次申请时回收，不做后台定时器。

use std::collections::{HashMap, VecDeque};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Mutex, OnceLock};
use std::time::{Duration, Instant};

use crate::编号与码面::错误码;
use crate::模型服务;

/// 一次被授予的许可。
struct 持有记录 {
    许可句柄: u64,
    服务句柄: u64,
    授予时刻: Instant,
    租约毫秒: u64,
}

struct 许可状态 {
    /// 服务句柄 → 当前持有者。每个模型服务各自一格，互不遮挡。
    持有表: HashMap<u64, 持有记录>,
    /// 服务句柄 → 该服务专属的排队队列（元素 = 申请者标记 + 入队时刻）。
    排队表: HashMap<u64, VecDeque<(u64, Instant)>>,
    累计授予: u64,
    累计超租约回收: u64,
}

fn 状态表() -> &'static Mutex<许可状态> {
    状态表实例.get_or_init(|| {
        Mutex::new(许可状态 {
            持有表: HashMap::new(),
            排队表: HashMap::new(),
            累计授予: 0,
            累计超租约回收: 0,
        })
    })
}

static 状态表实例: OnceLock<Mutex<许可状态>> = OnceLock::new();
static 下一许可句柄: AtomicU64 = AtomicU64::new(800_001);

/// 排队轮询间隔：50 毫秒足够快，又不至于空转烧 CPU。
const 轮询间隔毫秒: u64 = 50;
/// 等待上限 3 秒 —— **不能顶到 5 秒**：内核调用预算本身就是 5 秒，等满 5 秒会被内核
/// 先判 `4 超时`，调用方拿到的就不是本能力的 `2511 排队超时`（实测踩过）。留 2 秒余量。
const 等待上限毫秒: u64 = 3_000;
/// 默认租约 5 秒（全仓超时硬顶）：单次推理超 5 秒时若有别人来申请，本许可会被当成超租约回收。
const 默认租约毫秒: u64 = 5_000;
const 租约上限毫秒: u64 = 5_000;

/// 申请许可：只看**本服务对应的那一格**。拿不到就排本服务专属的队，超时明确报「排队超时」。
///
/// 跨模型不互相等待：13B 在跑不影响 26B 拿许可 —— 各自独立进程，各走各的。
pub(crate) fn 申请(服务句柄: u64, 等待毫秒: u64, 租约毫秒: u64) -> Result<u64, u32> {
    if !模型服务::服务存在(服务句柄) {
        return Err(错误码::服务无效);
    }
    let 租约 = if 租约毫秒 == 0 {
        默认租约毫秒
    } else {
        租约毫秒.min(租约上限毫秒)
    };
    let 截止 = Instant::now() + Duration::from_millis(等待毫秒.min(等待上限毫秒));
    let mut 已入队 = false;
    loop {
        {
            let mut 表 = 状态表().lock().map_err(|_| 错误码::资源受限)?;
            let 超租约 = 表
                .持有表
                .get(&服务句柄)
                .map(|h| h.授予时刻.elapsed().as_millis() as u64 >= h.租约毫秒)
                .unwrap_or(false);
            if !表.持有表.contains_key(&服务句柄) || 超租约 {
                if 超租约 {
                    表.累计超租约回收 += 1;
                }
                let 句柄 = 下一许可句柄.fetch_add(1, Ordering::AcqRel);
                表.持有表.insert(
                    服务句柄,
                    持有记录 {
                        许可句柄: 句柄,
                        服务句柄,
                        授予时刻: Instant::now(),
                        租约毫秒: 租约,
                    },
                );
                表.累计授予 += 1;
                if 已入队 {
                    if let Some(队) = 表.排队表.get_mut(&服务句柄) {
                        队.retain(|(标记, _)| *标记 != 服务句柄);
                    }
                }
                return Ok(句柄);
            }
            if !已入队 {
                表.排队表
                    .entry(服务句柄)
                    .or_default()
                    .push_back((服务句柄, Instant::now()));
                已入队 = true;
            }
        }
        if Instant::now() >= 截止 {
            if let Ok(mut 表) = 状态表().lock() {
                if let Some(队) = 表.排队表.get_mut(&服务句柄) {
                    队.retain(|(标记, _)| *标记 != 服务句柄);
                }
            }
            return Err(错误码::排队超时);
        }
        std::thread::sleep(Duration::from_millis(轮询间隔毫秒));
    }
}

/// 归还许可：真 = 已释放并唤醒队首；假不会被返回（失败一律报错，不吞）。
pub(crate) fn 归还(许可句柄: u64) -> Result<bool, u32> {
    let mut 表 = 状态表().lock().map_err(|_| 错误码::资源受限)?;
    let 命中 = 表
        .持有表
        .iter()
        .find(|(_, 记录)| 记录.许可句柄 == 许可句柄)
        .map(|(服务, _)| *服务);
    match 命中 {
        Some(服务) => {
            表.持有表.remove(&服务);
            Ok(true)
        }
        None => Err(错误码::许可无效),
    }
}

/// 排队快照：每个模型各自持有什么、各自排了几个。跨模型的并行看得见。
pub(crate) fn 快照() -> serde_json::Value {
    let 表 = match 状态表().lock() {
        Ok(表) => 表,
        Err(_) => return serde_json::json!({ "读不到": "许可表锁中毒" }),
    };
    let 持有: Vec<serde_json::Value> = 表
        .持有表
        .values()
        .map(|h| {
            serde_json::json!({
                "许可句柄": h.许可句柄,
                "服务句柄": h.服务句柄,
                "已持有毫秒": h.授予时刻.elapsed().as_millis() as u64,
                "租约毫秒": h.租约毫秒,
            })
        })
        .collect();
    let 排队: Vec<serde_json::Value> = 表
        .排队表
        .iter()
        .filter(|(_, 队)| !队.is_empty())
        .map(|(服务, 队)| {
            serde_json::json!({
                "服务句柄": 服务,
                "排队数": 队.len(),
                "最长等待毫秒": 队.iter().map(|(_, 时)| 时.elapsed().as_millis() as u64).max().unwrap_or(0),
            })
        })
        .collect();
    let 总排队 = 表.排队表.values().map(|队| 队.len()).sum::<usize>();
    serde_json::json!({
        "持有": 持有,
        "持有数": 持有.len(),
        "排队": 排队,
        "总排队数": 总排队,
        "累计授予": 表.累计授予,
        "累计超租约回收": 表.累计超租约回收,
    })
}
