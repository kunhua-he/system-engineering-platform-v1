//! 进程内显式句柄；不导出PGconn地址，不承诺原池IPC长期资源。
use crate::{
    引擎封装::{引擎连接, 核语句},
    编号与码面::错误码,
};
use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};
use std::time::{Duration, Instant};
struct 句柄状态 {
    接收连接: bool,
    连接序号: u64,
    连接表: HashMap<u64, 引擎连接>,
}
static 句柄存储: OnceLock<Mutex<句柄状态>> = OnceLock::new();
fn 句柄锁() -> Result<std::sync::MutexGuard<'static, 句柄状态>, u32> {
    句柄存储
        .get_or_init(|| {
            Mutex::new(句柄状态 {
                接收连接: true,
                连接序号: 初始句柄号(),
                连接表: HashMap::new(),
            })
        })
        .try_lock()
        .map_err(|_| 错误码::连接资源受限)
}
fn 初始句柄号() -> u64 {
    use std::io::Read;
    let mut 随机字节 = [0u8; 8];
    std::fs::File::open("/dev/urandom")
        .and_then(|mut 随机源| 随机源.read_exact(&mut 随机字节))
        .expect("OS random required");
    (u64::from_ne_bytes(随机字节) & 0x0007_ffff_ffff_0000) | 1
}
pub(crate) fn 打开连接(连接文本: &str) -> Result<u64, u32> {
    let mut 句柄表 = 句柄锁()?;
    if !句柄表.接收连接 || 句柄表.连接表.len() >= 32 {
        return Err(错误码::连接资源受限);
    }
    let 连接对象 = 引擎连接::打开(连接文本)?;
    let 连接编号 = 句柄表.连接序号.checked_add(1).ok_or(错误码::连接资源受限)?;
    句柄表.连接序号 = 连接编号;
    句柄表.连接表.insert(连接编号, 连接对象);
    Ok(连接编号)
}
pub(crate) fn 查询(连接编号: u64, 语句文本: &str) -> Result<String, u32> {
    核语句(语句文本, true)?;
    let mut 句柄表 = 句柄锁()?;
    let 连接对象 = 句柄表
        .连接表
        .get_mut(&连接编号)
        .ok_or(错误码::连接句柄无效)?;
    let 截止时刻 = Instant::now() + Duration::from_millis(800);
    let 查询返回 = (|| {
        连接对象.执行("BEGIN READ ONLY", 截止时刻)?;
        let 结果值 = 连接对象.执行(语句文本, 截止时刻)?;
        连接对象.执行("COMMIT", 截止时刻)?;
        serde_json::to_string(&结果值).map_err(|_| 错误码::查询结果越界)
    })();
    收敛失败(&mut 句柄表, 连接编号, 查询返回)
}
pub(crate) fn 事务(连接编号: u64, 语句列表: &[String]) -> Result<i64, u32> {
    if 语句列表.is_empty()
        || 语句列表.len() > 32
        || 语句列表.iter().map(String::len).sum::<usize>() > 65536
    {
        return Err(错误码::连接参数不合法);
    }
    for 语句文本 in 语句列表 {
        核语句(语句文本, false)?;
    }
    let mut 句柄表 = 句柄锁()?;
    let 连接对象 = 句柄表
        .连接表
        .get_mut(&连接编号)
        .ok_or(错误码::连接句柄无效)?;
    let 截止时刻 = Instant::now() + Duration::from_millis(800);
    let 事务返回 = (|| {
        连接对象.执行("BEGIN", 截止时刻)?;
        for 语句文本 in 语句列表 {
            连接对象.执行(语句文本, 截止时刻)?;
        }
        连接对象.执行("COMMIT", 截止时刻)?;
        Ok(语句列表.len() as i64)
    })();
    收敛失败(&mut 句柄表, 连接编号, 事务返回)
}
fn 收敛失败<返回类型>(
    句柄表: &mut 句柄状态,
    连接编号: u64,
    执行返回: Result<返回类型, u32>,
) -> Result<返回类型, u32> {
    if let Err(失败码) = 执行返回 {
        if 失败码 == 错误码::连接不可继续 {
            句柄表.连接表.remove(&连接编号);
            return Err(失败码);
        }
        let 连接对象 = 句柄表
            .连接表
            .get_mut(&连接编号)
            .ok_or(错误码::连接句柄无效)?;
        if !连接对象.空闲()
            && (连接对象
                .执行("ROLLBACK", Instant::now() + Duration::from_millis(200))
                .is_err()
                || !连接对象.空闲())
        {
            句柄表.连接表.remove(&连接编号);
            return Err(错误码::连接不可继续);
        }
        return Err(失败码);
    }
    执行返回
}
pub(crate) fn 释放连接(连接编号: u64) -> Result<i64, u32> {
    let 连接对象 = 句柄锁()?
        .连接表
        .remove(&连接编号)
        .ok_or(错误码::连接句柄无效)?;
    drop(连接对象);
    Ok(1)
}
pub(crate) unsafe extern "C" fn 生命周期通知(
    通知编号: v1_contract::通知号,
    _通知参数: usize,
    _附加参数: usize,
) -> isize {
    let Ok(mut 句柄表) = 句柄锁() else {
        return v1_contract::通知返回::延迟释放;
    };
    match 通知编号.取号值() {
        2000 => {
            句柄表.接收连接 = true;
            0
        }
        2001..=2003 => {
            句柄表.接收连接 = false;
            句柄表.连接表.clear();
            0
        }
        _ => 0,
    }
}
