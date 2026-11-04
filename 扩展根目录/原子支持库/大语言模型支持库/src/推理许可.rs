//! 推理许可：多个模型共用一块 GPU 时**内置排队**，同一时刻只放一个推理进去。
//!
//! # 为什么这口在底座里
//!
//! GPU 利用率不是判据 —— 正常推理瞬间冲到 100% 很正常。真正要管的是
//! **同一时刻只该有一个推理在跑**：两个模型同时抢 GPU，结果是两边都变慢，
//! 读数也没法归因到谁。把许可做进底座，调用方不必各自写锁，排队与超时统一在这里裁决。
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
//! - 只颁发许可：不代理推理请求、不读 GPU 利用率、不判断模型是否在干活。
//! - **常驻服务待命不占许可**：许可是「一次推理」独占，不是「一个进程」独占。
//! - 不按端口/进程名判归属；租约到期只在下一次申请时回收，不做后台定时器。

use std::collections::VecDeque;
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
    持有: Option<持有记录>,
    排队: VecDeque<(u64, Instant)>,
    累计授予: u64,
    累计超租约回收: u64,
}

fn 状态表() -> &'static Mutex<许可状态> {
    状态表实例.get_or_init(|| {
        Mutex::new(许可状态 {
            持有: None,
            排队: VecDeque::new(),
            累计授予: 0,
            累计超租约回收: 0,
        })
    })
}

static 状态表实例: OnceLock<Mutex<许可状态>> = OnceLock::new();
static 下一许可句柄: AtomicU64 = AtomicU64::new(800_001);

/// 排队轮询间隔：50 毫秒足够快，又不至于空转烧 CPU。
const 轮询间隔毫秒: u64 = 50;
/// 等待上限：调用方给再大也不超过这个数（防止无限等占住线程）。
const 等待上限毫秒: u64 = 600_000;
/// 默认租约：调用方传 0 时用它。超时不归还的许可会在下一次申请时被回收。
const 默认租约毫秒: u64 = 30_000;
const 租约上限毫秒: u64 = 600_000;

/// 申请许可：拿不到就排队，超时明确报「排队超时」（不静默降级成「没排队」）。
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
                .持有
                .as_ref()
                .map(|h| h.授予时刻.elapsed().as_millis() as u64 >= h.租约毫秒)
                .unwrap_or(false);
            if 表.持有.is_none() || 超租约 {
                if 超租约 {
                    表.累计超租约回收 += 1;
                }
                let 句柄 = 下一许可句柄.fetch_add(1, Ordering::AcqRel);
                表.持有 = Some(持有记录 {
                    许可句柄: 句柄,
                    服务句柄,
                    授予时刻: Instant::now(),
                    租约毫秒: 租约,
                });
                表.累计授予 += 1;
                if 已入队 {
                    表.排队.retain(|(服务, _)| *服务 != 服务句柄);
                }
                return Ok(句柄);
            }
            if !已入队 {
                表.排队.push_back((服务句柄, Instant::now()));
                已入队 = true;
            }
        }
        if Instant::now() >= 截止 {
            if let Ok(mut 表) = 状态表().lock() {
                表.排队.retain(|(服务, _)| *服务 != 服务句柄);
            }
            return Err(错误码::排队超时);
        }
        std::thread::sleep(Duration::from_millis(轮询间隔毫秒));
    }
}

/// 归还许可：真 = 已释放并唤醒队首；假不会被返回（失败一律报错，不吞）。
pub(crate) fn 归还(许可句柄: u64) -> Result<bool, u32> {
    let mut 表 = 状态表().lock().map_err(|_| 错误码::资源受限)?;
    match &表.持有 {
        Some(记录) if 记录.许可句柄 == 许可句柄 => {
            表.持有 = None;
            Ok(true)
        }
        _ => Err(错误码::许可无效),
    }
}

/// 排队快照：谁拿着、后面排了几个、等了多久、累计授予与超租约回收各几次。
pub(crate) fn 快照() -> serde_json::Value {
    let 表 = match 状态表().lock() {
        Ok(表) => 表,
        Err(_) => return serde_json::json!({ "读不到": "许可表锁中毒" }),
    };
    let 持有 = 表.持有.as_ref().map(|h| {
        serde_json::json!({
            "许可句柄": h.许可句柄,
            "服务句柄": h.服务句柄,
            "已持有毫秒": h.授予时刻.elapsed().as_millis() as u64,
            "租约毫秒": h.租约毫秒,
        })
    });
    let 最长等待毫秒 = 表
        .排队
        .iter()
        .map(|(_, 入队时刻)| 入队时刻.elapsed().as_millis() as u64)
        .max()
        .unwrap_or(0);
    serde_json::json!({
        "持有": 持有,
        "排队数": 表.排队.len(),
        "排队序号": 表.排队.iter().map(|(服务, _)| *服务).collect::<Vec<u64>>(),
        "最长等待毫秒": 最长等待毫秒,
        "累计授予": 表.累计授予,
        "累计超租约回收": 表.累计超租约回收,
    })
}
