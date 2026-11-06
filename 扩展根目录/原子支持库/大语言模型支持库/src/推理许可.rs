//! 服务与远程端点分开寻址；显式许可按唯一申请号 FIFO 等待。
//! 活生成持有任务守卫，租约只回收尚未交给生成任务的预留。
use crate::{模型服务, 编号与码面::错误码};
use std::collections::{HashMap, VecDeque};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Condvar, Mutex, OnceLock};
use std::time::{Duration, Instant};

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub(crate) enum 许可资源 {
    服务(u64),
    端点(String),
}
struct 持有记录 {
    许可句柄: u64,
    授予时刻: Instant,
    租约毫秒: u64,
    活生成: bool,
}
#[derive(Default)]
struct 许可状态 {
    持有表: HashMap<许可资源, 持有记录>,
    排队表: HashMap<许可资源, VecDeque<(u64, Instant)>>,
    累计授予: u64,
    累计超租约回收: u64,
}
static 状态表实例: OnceLock<Mutex<许可状态>> = OnceLock::new();
static 下一许可句柄: AtomicU64 = AtomicU64::new(800_001);
static 下一申请编号: AtomicU64 = AtomicU64::new(1);
static 许可通知: Condvar = Condvar::new();
const 等待上限毫秒: u64 = 3000;
const 默认租约毫秒: u64 = 5000;
fn 状态表() -> &'static Mutex<许可状态> {
    状态表实例.get_or_init(Default::default)
}
pub(crate) fn 唤醒等待() {
    // 与等待方同锁通知，避免取消发生在检查与休眠之间而丢失唤醒。
    let _通知锁 = 状态表()
        .lock()
        .unwrap_or_else(|中毒错误| 中毒错误.into_inner());
    许可通知.notify_all();
}
fn 回收预留(状态值: &mut 许可状态, 资源键: &许可资源) {
    let 已过期 = 状态值.持有表.get(资源键).is_some_and(|持有值| {
        !持有值.活生成 && 持有值.授予时刻.elapsed().as_millis() >= 持有值.租约毫秒 as u128
    });
    if 已过期 {
        状态值.持有表.remove(资源键);
        状态值.累计超租约回收 += 1;
    }
}
fn 发放许可(
    状态值: &mut 许可状态, 资源键: 许可资源, 租约毫秒: u64, 活生成: bool
) -> u64 {
    let 许可编号 = 下一许可句柄.fetch_add(1, Ordering::AcqRel);
    状态值.持有表.insert(
        资源键,
        持有记录 {
            许可句柄: 许可编号,
            授予时刻: Instant::now(),
            租约毫秒: if 租约毫秒 == 0 {
                默认租约毫秒
            } else {
                租约毫秒.min(默认租约毫秒)
            },
            活生成,
        },
    );
    状态值.累计授予 += 1;
    许可编号
}
/// 非阻塞准入只观察空闲与队首，不绕过已等待的申请者。
pub(crate) fn 试取资源(资源键: 许可资源, 租约毫秒: u64) -> Result<Option<u64>, u32> {
    let mut 状态值 = 状态表().lock().map_err(|_| 错误码::资源受限)?;
    回收预留(&mut 状态值, &资源键);
    if 状态值.持有表.contains_key(&资源键)
        || 状态值
            .排队表
            .get(&资源键)
            .is_some_and(|等待队列| !等待队列.is_empty())
    {
        return Ok(None);
    }
    Ok(Some(发放许可(&mut 状态值, 资源键, 租约毫秒, false)))
}
fn 移除申请(状态值: &mut 许可状态, 资源键: &许可资源, 申请编号: u64) {
    if let Some(等待队列) = 状态值.排队表.get_mut(资源键) {
        等待队列.retain(|(等待编号, _)| *等待编号 != 申请编号);
        if 等待队列.is_empty() {
            状态值.排队表.remove(资源键);
        }
    }
}
fn 等待资源(
    资源键: 许可资源,
    等待毫秒: Option<u64>,
    租约毫秒: u64,
    活生成: bool,
    取消标志: &AtomicBool,
) -> Result<u64, u32> {
    let 截止时刻 = 等待毫秒.map(|等待时长| Instant::now() + Duration::from_millis(等待时长));
    let 申请编号 = 下一申请编号.fetch_add(1, Ordering::AcqRel);
    let mut 状态值 = 状态表().lock().map_err(|_| 错误码::资源受限)?;
    // 显式 2516 的预留在首次生成时移交，不再重复申请同一服务。
    if 活生成
        && let Some(持有值) = 状态值.持有表.get_mut(&资源键)
        && !持有值.活生成
    {
        持有值.活生成 = true;
        return Ok(持有值.许可句柄);
    }
    状态值
        .排队表
        .entry(资源键.clone())
        .or_default()
        .push_back((申请编号, Instant::now()));
    loop {
        回收预留(&mut 状态值, &资源键);
        if 取消标志.load(Ordering::Acquire) {
            移除申请(&mut 状态值, &资源键, 申请编号);
            许可通知.notify_all();
            return Err(错误码::上游失败);
        }
        let 位于队首 = 状态值
            .排队表
            .get(&资源键)
            .and_then(|等待队列| 等待队列.front())
            .is_some_and(|(等待编号, _)| *等待编号 == 申请编号);
        if 位于队首 && !状态值.持有表.contains_key(&资源键) {
            移除申请(&mut 状态值, &资源键, 申请编号);
            return Ok(发放许可(&mut 状态值, 资源键, 租约毫秒, 活生成));
        }
        if 截止时刻.is_some_and(|截止值| Instant::now() >= 截止值) {
            移除申请(&mut 状态值, &资源键, 申请编号);
            许可通知.notify_all();
            return Err(错误码::排队超时);
        }
        let 预留余量 = 状态值
            .持有表
            .get(&资源键)
            .filter(|持有值| !持有值.活生成)
            .map(|持有值| {
                Duration::from_millis(持有值.租约毫秒).saturating_sub(持有值.授予时刻.elapsed())
            });
        let 剩余时间 = 截止时刻.map(|截止值| 截止值.saturating_duration_since(Instant::now()));
        状态值 = match (预留余量, 剩余时间) {
            (None, None) => 许可通知.wait(状态值).map_err(|_| 错误码::资源受限)?,
            (预留时长, 等待时长) => {
                let 睡眠时长 = match (预留时长, 等待时长) {
                    (Some(预留值), Some(等待值)) => 预留值.min(等待值),
                    (Some(时长值), None) | (None, Some(时长值)) => 时长值,
                    _ => unreachable!(),
                };
                许可通知
                    .wait_timeout(状态值, 睡眠时长)
                    .map_err(|_| 错误码::资源受限)?
                    .0
            }
        };
    }
}
pub(crate) fn 申请(服务句柄: u64, 等待毫秒: u64, 租约毫秒: u64) -> Result<u64, u32> {
    if !模型服务::服务存在(服务句柄) {
        return Err(错误码::服务无效);
    }
    if let Some(许可编号) = 试取资源(许可资源::服务(服务句柄), 租约毫秒)? {
        return Ok(许可编号);
    }
    等待资源(
        许可资源::服务(服务句柄),
        Some(等待毫秒.min(等待上限毫秒)),
        租约毫秒,
        false,
        &AtomicBool::new(false),
    )
}
pub(crate) fn 归还(许可句柄: u64) -> Result<bool, u32> {
    let mut 状态值 = 状态表().lock().map_err(|_| 错误码::资源受限)?;
    let 资源键 = 状态值
        .持有表
        .iter()
        .find(|(_, 持有值)| 持有值.许可句柄 == 许可句柄)
        .map(|(资源键, 持有值)| (资源键.clone(), 持有值.活生成))
        .ok_or(错误码::许可无效)?;
    if 资源键.1 {
        return Err(错误码::许可无效);
    }
    状态值.持有表.remove(&资源键.0);
    许可通知.notify_all();
    Ok(true)
}
pub(crate) struct 任务许可 {
    资源键: 许可资源,
    许可句柄: u64,
}
impl Drop for 任务许可 {
    fn drop(&mut self) {
        let mut 状态值 = 状态表()
            .lock()
            .unwrap_or_else(|中毒错误| 中毒错误.into_inner());
        if 状态值
            .持有表
            .get(&self.资源键)
            .is_some_and(|持有值| 持有值.许可句柄 == self.许可句柄)
        {
            状态值.持有表.remove(&self.资源键);
        }
        许可通知.notify_all();
    }
}
pub(crate) fn 取得可取消任务许可(
    资源键: 许可资源,
    取消标志: &AtomicBool,
) -> Result<任务许可, u32> {
    let 许可句柄 = 等待资源(资源键.clone(), None, 默认租约毫秒, true, 取消标志)?;
    Ok(任务许可 {
        资源键, 许可句柄
    })
}
#[cfg(test)]
fn 取得任务许可(资源键: 许可资源) -> Result<任务许可, u32> {
    取得可取消任务许可(资源键, &AtomicBool::new(false))
}
pub(crate) fn 快照() -> serde_json::Value {
    let 状态值 = match 状态表().lock() {
        Ok(状态值) => 状态值,
        Err(_) => return serde_json::json!({"读不到":"许可表锁中毒"}),
    };
    let 持有列表: Vec<_> = 状态值.持有表.iter().map(|(资源键, 持有值)| serde_json::json!({
        "许可句柄":持有值.许可句柄, "服务句柄":match 资源键 { 许可资源::服务(服务句柄) => Some(*服务句柄), _ => None },
        "已持有毫秒":持有值.授予时刻.elapsed().as_millis() as u64, "租约毫秒":持有值.租约毫秒
    })).collect();
    let 排队列表: Vec<_> = 状态值.排队表.iter().filter(|(_, 等待队列)| !等待队列.is_empty()).map(|(资源键, 等待队列)| serde_json::json!({
        "服务句柄":match 资源键 { 许可资源::服务(服务句柄) => Some(*服务句柄), _ => None }, "排队数":等待队列.len(),
        "最长等待毫秒":等待队列.iter().map(|(_, 入队时刻)| 入队时刻.elapsed().as_millis() as u64).max().unwrap_or(0)
    })).collect();
    serde_json::json!({"持有":持有列表,"持有数":持有列表.len(),"排队":排队列表,"总排队数":状态值.排队表.values().map(VecDeque::len).sum::<usize>(),"累计授予":状态值.累计授予,"累计超租约回收":状态值.累计超租约回收})
}

#[cfg(test)]
mod 生命周期回归 {
    use super::*;
    #[test]
    fn 活生成不能随租约到期转授() {
        let 资源键 = 许可资源::端点("模拟长生成".to_owned());
        let 任务守卫 = 取得任务许可(资源键.clone()).unwrap();
        {
            let mut 状态值 = 状态表().lock().unwrap();
            let 持有值 = 状态值.持有表.get_mut(&资源键).unwrap();
            持有值.授予时刻 = Instant::now() - Duration::from_secs(6);
        }
        assert_eq!(试取资源(资源键.clone(), 5000).unwrap(), None);
        assert!(归还(任务守卫.许可句柄).is_err());
        drop(任务守卫);
        let 许可编号 = 试取资源(资源键, 5000).unwrap().unwrap();
        assert_eq!(归还(许可编号), Ok(true));
    }
}

#[cfg(test)]
mod 公平性回归 {
    use super::*;
    fn 等待队长(资源键: &许可资源, 预期数量: usize) {
        let 截止时刻 = Instant::now() + Duration::from_secs(2);
        loop {
            let 实际数量 = 状态表()
                .lock()
                .unwrap()
                .排队表
                .get(资源键)
                .map_or(0, VecDeque::len);
            if 实际数量 == 预期数量 {
                return;
            }
            assert!(Instant::now() < 截止时刻, "排队数量不符");
            std::thread::yield_now();
        }
    }
    #[test]
    fn 超时只删本申请且队首优先并通知后继() {
        let 资源键 = 许可资源::端点("公平队列验收".to_owned());
        let 任务守卫 = 取得任务许可(资源键.clone()).unwrap();
        let 超时资源 = 资源键.clone();
        let 超时线程 = std::thread::spawn(move || {
            等待资源(超时资源, Some(200), 5000, false, &AtomicBool::new(false))
        });
        等待队长(&资源键, 1);
        let (顺序发送器, 顺序接收器) = std::sync::mpsc::channel();
        let mut 等待线程列表 = Vec::new();
        for 申请顺序 in [10, 20] {
            let 等待资源键 = 资源键.clone();
            let 线程发送器 = 顺序发送器.clone();
            等待线程列表.push(std::thread::spawn(move || {
                let 许可编号 =
                    等待资源(等待资源键, Some(2000), 5000, false, &AtomicBool::new(false)).unwrap();
                线程发送器.send(申请顺序).unwrap();
                归还(许可编号).unwrap();
            }));
            等待队长(&资源键, if 申请顺序 == 10 { 2 } else { 3 });
        }
        assert_eq!(超时线程.join().unwrap(), Err(错误码::排队超时));
        等待队长(&资源键, 2);
        assert_eq!(试取资源(资源键.clone(), 5000).unwrap(), None);
        let 独立许可 = 取得任务许可(许可资源::端点("独立服务验收".into())).unwrap();
        drop(独立许可);
        drop(任务守卫);
        assert_eq!(顺序接收器.recv_timeout(Duration::from_secs(2)).unwrap(), 10);
        assert_eq!(顺序接收器.recv_timeout(Duration::from_secs(2)).unwrap(), 20);
        for 等待线程 in 等待线程列表 {
            等待线程.join().unwrap();
        }
        等待队长(&资源键, 0);
    }
    #[test]
    fn 嵌套生成复用预留且异常展开归还() {
        let 资源键 = 许可资源::端点("嵌套复用验收".into());
        let 预留编号 = 试取资源(资源键.clone(), 5000).unwrap().unwrap();
        let 展开结果 = std::panic::catch_unwind(|| {
            let 任务守卫 = 取得任务许可(资源键.clone()).unwrap();
            assert_eq!(任务守卫.许可句柄, 预留编号);
            panic!("验收异常退场");
        });
        assert!(展开结果.is_err());
        let 后继编号 = 试取资源(资源键, 5000).unwrap().unwrap();
        归还(后继编号).unwrap();
    }
    #[test]
    fn 排队取消通知退出但不归还前任() {
        let 资源键 = 许可资源::端点("取消排队验收".into());
        let 任务守卫 = 取得任务许可(资源键.clone()).unwrap();
        let 取消标志 = std::sync::Arc::new(AtomicBool::new(false));
        let 线程取消标志 = 取消标志.clone();
        let 等待资源键 = 资源键.clone();
        let 等待线程 =
            std::thread::spawn(move || 取得可取消任务许可(等待资源键, &线程取消标志).is_err());
        等待队长(&资源键, 1);
        取消标志.store(true, Ordering::Release);
        唤醒等待();
        assert!(等待线程.join().unwrap());
        等待队长(&资源键, 0);
        assert_eq!(试取资源(资源键, 5000).unwrap(), None);
        drop(任务守卫);
    }
}
