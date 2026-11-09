//! 进程内显式句柄；表锁只寻址，连接锁覆盖整段事务与失败收敛。
use crate::{
    引擎封装::{引擎连接, 核语句},
    编号与码面::错误码,
};
use std::collections::HashMap;
use std::sync::{Arc, Mutex, OnceLock};
use std::time::{Duration, Instant};
type 连接条目 = Arc<Mutex<Option<引擎连接>>>;
struct 句柄状态 {
    接收连接: bool,
    连接序号: u64,
    连接表: HashMap<u64, 连接条目>,
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
        .lock()
        .map_err(|_| 错误码::连接不可继续)
}
fn 初始句柄号() -> u64 {
    use std::io::Read;
    let mut 随机字节 = [0u8; 8];
    std::fs::File::open("/dev/urandom")
        .and_then(|mut 随机源| 随机源.read_exact(&mut 随机字节))
        .expect("OS random required");
    (u64::from_ne_bytes(随机字节) & 0x0007_ffff_ffff_0000) | 1
}
/// 句柄上限**由环境定、不写死**：写死一个数字会在机器资源充足时照样报「连接资源受限」，
/// 而调用方看到 CPU、内存都没满，问的就是这件事。`V1_PG最大连接` 覆盖；未设或非法 ⇒ 默认 256。
/// 硬顶 4096 只防手滑把上限写成天文数字、一次耗光文件描述符，不是业务封顶。
const 默认上限: usize = 256;
const 硬顶上限: usize = 4096;
const 上限环境变量名: &str = "V1_PG最大连接";
pub(crate) fn 连接上限() -> usize {
    std::env::var(上限环境变量名)
        .ok()
        .and_then(|原文| 原文.trim().parse::<usize>().ok())
        .filter(|上限读数| (1..=硬顶上限).contains(上限读数))
        .unwrap_or(默认上限)
}
pub(crate) fn 打开连接(连接文本: &str) -> Result<u64, u32> {
    {
        let 句柄表 = 句柄锁()?;
        if !句柄表.接收连接 || 句柄表.连接表.len() >= 连接上限() {
            return Err(错误码::连接资源受限);
        }
    }
    // 建连也不占全表锁；完成后重新核准入，拒绝时复用Drop收尾。
    let 连接对象 = 引擎连接::打开(连接文本)?;
    let mut 句柄表 = 句柄锁()?;
    if !句柄表.接收连接 || 句柄表.连接表.len() >= 连接上限() {
        return Err(错误码::连接资源受限);
    }
    let 连接编号 = 句柄表.连接序号.checked_add(1).ok_or(错误码::连接资源受限)?;
    句柄表.连接序号 = 连接编号;
    句柄表
        .连接表
        .insert(连接编号, Arc::new(Mutex::new(Some(连接对象))));
    Ok(连接编号)
}
fn 取连接条目(连接编号: u64) -> Result<连接条目, u32> {
    句柄锁()?
        .连接表
        .get(&连接编号)
        .cloned()
        .ok_or(错误码::连接句柄无效)
}
fn 执行连接<返回类型>(
    连接编号: u64,
    执行过程: impl FnOnce(&mut 引擎连接) -> Result<返回类型, u32>,
) -> Result<返回类型, u32> {
    let 连接条目 = 取连接条目(连接编号)?;
    let mut 连接守卫 = match 连接条目.lock() {
        Ok(连接守卫) => 连接守卫,
        Err(中毒错误) => {
            中毒错误.into_inner().take();
            句柄锁()?.连接表.remove(&连接编号);
            return Err(错误码::连接不可继续);
        }
    };
    let 连接对象 = 连接守卫.as_mut().ok_or(错误码::连接句柄无效)?;
    let 执行返回 = 执行过程(连接对象);
    收敛失败(&mut 连接守卫, 连接编号, 执行返回)
}
pub(crate) fn 查询(连接编号: u64, 语句文本: &str) -> Result<String, u32> {
    核语句(语句文本, true)?;
    执行连接(连接编号, |连接对象| {
        let 截止时刻 = Instant::now() + Duration::from_millis(800);
        连接对象.执行("BEGIN READ ONLY", 截止时刻)?;
        let 结果值 = 连接对象.执行(语句文本, 截止时刻)?;
        连接对象.执行("COMMIT", 截止时刻)?;
        serde_json::to_string(&结果值).map_err(|_| 错误码::查询结果越界)
    })
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
    执行连接(连接编号, |连接对象| {
        let 截止时刻 = Instant::now() + Duration::from_millis(800);
        连接对象.执行("BEGIN", 截止时刻)?;
        for 语句文本 in 语句列表 {
            连接对象.执行(语句文本, 截止时刻)?;
        }
        连接对象.执行("COMMIT", 截止时刻)?;
        Ok(语句列表.len() as i64)
    })
}
fn 收敛失败<返回类型>(
    连接存位: &mut Option<引擎连接>,
    连接编号: u64,
    执行返回: Result<返回类型, u32>,
) -> Result<返回类型, u32> {
    if let Err(失败码) = 执行返回 {
        let 连接对象 = 连接存位.as_mut().ok_or(错误码::连接句柄无效)?;
        let 连接损坏 = 失败码 == 错误码::连接不可继续
            || (!连接对象.空闲()
                && (连接对象
                    .执行("ROLLBACK", Instant::now() + Duration::from_millis(200))
                    .is_err()
                    || !连接对象.空闲()));
        if 连接损坏 {
            // 在连接锁内失效，已取Arc的等待者也不能再进入该连接。
            连接存位.take();
            句柄锁()?.连接表.remove(&连接编号);
            return Err(错误码::连接不可继续);
        }
        return Err(失败码);
    }
    执行返回
}
pub(crate) fn 释放连接(连接编号: u64) -> Result<i64, u32> {
    let 连接条目 = 句柄锁()?
        .连接表
        .remove(&连接编号)
        .ok_or(错误码::连接句柄无效)?;
    关闭条目(&连接条目)?;
    Ok(1)
}
fn 关闭条目(连接条目: &连接条目) -> Result<(), u32> {
    match 连接条目.lock() {
        Ok(mut 连接守卫) => {
            连接守卫.take();
            Ok(())
        }
        Err(中毒错误) => {
            中毒错误.into_inner().take();
            Err(错误码::连接不可继续)
        }
    }
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
            let 待关闭列表: Vec<_> = 句柄表
                .连接表
                .drain()
                .map(|(_, 连接条目)| 连接条目)
                .collect();
            drop(句柄表);
            let mut 关闭失败 = false;
            for 连接条目 in 待关闭列表 {
                if 关闭条目(&连接条目).is_err() {
                    关闭失败 = true;
                }
            }
            if 关闭失败 {
                v1_contract::通知返回::延迟释放
            } else {
                0
            }
        }
        _ => 0,
    }
}

#[cfg(test)]
mod 并发测试 {
    use super::*;
    #[test]
    fn 表锁繁忙应等待而非拒绝() {
        let 句柄守卫 = 句柄锁().unwrap();
        let (开始发送, 开始接收) = std::sync::mpsc::channel();
        let (完成发送, 完成接收) = std::sync::mpsc::channel();
        let 等待线程 = std::thread::spawn(move || {
            开始发送.send(()).unwrap();
            let 获取结果 = 句柄锁().map(|_| ());
            完成发送.send(获取结果).unwrap();
        });
        开始接收.recv().unwrap();
        let 提前返回 = 完成接收.recv_timeout(Duration::from_millis(50));
        drop(句柄守卫);
        等待线程.join().unwrap();
        assert!(提前返回.is_err(), "表锁繁忙不应立即返回错误");
        assert_eq!(完成接收.recv().unwrap(), Ok(()));
    }
}
