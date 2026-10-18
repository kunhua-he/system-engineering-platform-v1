//! 域登记、调用租约与实例所属空闲回收。
use std::sync::{Arc, Condvar, Mutex, Weak};
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};
use crate::线程安全::取锁;
use crate::进程池::{域句柄, 执行域标识, 进程池, 进程池错误};
use super::{域部署, 跨进程域表};

pub(super) const 空闲保活时长: Duration = Duration::from_secs(30);

pub(super) struct 回收信号 {
    唤醒代次: Mutex<u64>,
    等待: Condvar,
    停止: AtomicBool,
    资源紧张: AtomicBool,
}
impl 回收信号 {
    pub(super) fn 创建() -> Self {
        Self { 唤醒代次: Mutex::new(0), 等待: Condvar::new(), 停止: AtomicBool::new(false), 资源紧张: AtomicBool::new(false) }
    }
    pub(super) fn 唤醒(&self) {
        let mut 唤醒代次 = 取锁(&self.唤醒代次);
        *唤醒代次 = 唤醒代次.wrapping_add(1);
        self.等待.notify_all();
    }
    fn 等变动(&self, 旧唤醒代次: u64, 等待时长: Option<Duration>) {
        let 唤醒代次 = 取锁(&self.唤醒代次);
        let 未变动 = |当前唤醒代次: &mut u64| *当前唤醒代次 == 旧唤醒代次 && !self.停止.load(Ordering::Acquire);
        if let Some(等待时长) = 等待时长 {
            drop(self.等待.wait_timeout_while(唤醒代次, 等待时长, 未变动).unwrap_or_else(|中毒| 中毒.into_inner()));
        } else {
            drop(self.等待.wait_while(唤醒代次, 未变动).unwrap_or_else(|中毒| 中毒.into_inner()));
        }
    }
}

struct 域活动 {
    最近调用: Instant,
    在途数: usize,
    回收中: bool,
    已注销: bool,
}

pub(super) struct 域登记 {
    pub(super) 部署: 域部署,
    标识: 执行域标识,
    执行池: Arc<进程池>,
    启动锁: Mutex<()>,
    活动: Mutex<域活动>,
    等待: Condvar,
    信号: Arc<回收信号>,
}

pub(super) struct 调用租约(Arc<域登记>);
impl Drop for 调用租约 {
    fn drop(&mut self) {
        let mut 活动 = 取锁(&self.0.活动);
        活动.在途数 -= 1;
        let 已空闲 = 活动.在途数 == 0;
        drop(活动);
        if 已空闲 { self.0.信号.唤醒(); }
    }
}

impl 域登记 {
    pub(super) fn 创建(标识: 执行域标识, 部署: 域部署, 执行池: Arc<进程池>, 信号: Arc<回收信号>) -> Arc<Self> {
        Arc::new(Self { 标识, 部署, 执行池, 信号, 启动锁: Mutex::new(()), 等待: Condvar::new(),
            活动: Mutex::new(域活动 { 最近调用: Instant::now(), 在途数: 0, 回收中: false, 已注销: false }) })
    }
    pub(super) fn 领用(self: &Arc<Self>, 总期限: Instant) -> Result<调用租约, 进程池错误> {
        let mut 活动 = 取锁(&self.活动);
        while 活动.回收中 && !活动.已注销 {
            let 剩余时长 = 总期限.checked_duration_since(Instant::now()).ok_or(进程池错误::预算耗尽)?;
            活动 = self.等待.wait_timeout(活动, 剩余时长).unwrap_or_else(|中毒| 中毒.into_inner()).0;
        }
        if 活动.已注销 { return Err(进程池错误::域不存在); }
        活动.最近调用 = Instant::now();
        活动.在途数 += 1;
        Ok(调用租约(Arc::clone(self)))
    }
    pub(super) fn 注销(&self) {
        取锁(&self.活动).已注销 = true;
        self.等待.notify_all();
    }
    pub(super) fn 取调用句柄(&self, 总期限: Instant) -> Result<域句柄, 进程池错误> {
        if let Some(句柄) = self.执行池.取域句柄(&self.标识) { return Ok(句柄); }
        let 启动守卫 = 取锁(&self.启动锁);
        let _ = &启动守卫;
        loop {
            if Instant::now() >= 总期限 { return Err(进程池错误::预算耗尽); }
            if let Some(句柄) = self.执行池.取域句柄(&self.标识) { return Ok(句柄); }
            let 启动读数 = {
                let 活动 = 取锁(&self.活动);
                if 活动.已注销 { return Err(进程池错误::域不存在); }
                self.执行池.保证域在(&self.标识, &self.部署.启动程序, &self.部署.启动参数)
            };
            match 启动读数 {
                Ok(()) => {
                    return self.执行池.取域句柄(&self.标识).ok_or(进程池错误::域不存在);
                }
                Err(进程池错误::子进程数已满) => {
                    self.信号.资源紧张.store(true, Ordering::Release);
                    self.信号.唤醒();
                    let 旧唤醒代次 = *取锁(&self.信号.唤醒代次);
                    let 剩余时长 = 总期限.saturating_duration_since(Instant::now()).min(Duration::from_millis(20));
                    self.信号.等变动(旧唤醒代次, Some(剩余时长));
                }
                Err(错误值) => return Err(错误值),
            }
        }
    }
    pub(super) fn 保证调用进程(&self, 句柄: &域句柄) -> Result<(), 进程池错误> {
        let 活动 = 取锁(&self.活动);
        if 活动.已注销 { return Err(进程池错误::域不存在); }
        句柄.保证在(&self.部署.启动程序, &self.部署.启动参数)
    }
    fn 空闲期限(&self) -> Option<Instant> {
        if !self.执行池.取域句柄(&self.标识).is_some_and(|句柄| 句柄.监督().仍在运行) { return None; }
        let 活动 = 取锁(&self.活动);
        if 活动.在途数 != 0 || 活动.回收中 || 活动.已注销 { return None; }
        Some(活动.最近调用 + 空闲保活时长)
    }
    fn 回收空闲(&self, 现在时刻: Instant, 资源紧张: bool) -> bool {
        {
            let mut 活动 = 取锁(&self.活动);
            if 活动.在途数 != 0 || 活动.回收中 || 活动.已注销 { return false; }
            if !资源紧张 && 现在时刻 < 活动.最近调用 + 空闲保活时长 { return false; }
            活动.回收中 = true;
        }
        let 已回收 = self.执行池.回收空闲域(&self.标识);
        取锁(&self.活动).回收中 = false;
        self.等待.notify_all();
        if 已回收 { self.信号.唤醒(); }
        已回收
    }
}

pub(super) fn 启动回收(域表: Weak<Mutex<跨进程域表>>, 信号: Arc<回收信号>) -> std::io::Result<std::thread::JoinHandle<()>> {
    std::thread::Builder::new().name(String::from("扩展空闲回收")).spawn(move || {
        while !信号.停止.load(Ordering::Acquire) {
            let 旧唤醒代次 = *取锁(&信号.唤醒代次);
            let Some(表引用) = 域表.upgrade() else { break };
            let mut 登记表 = 取锁(&表引用).部署表.iter().map(|格子| {
                let 登记 = Arc::clone(&格子.1);
                (登记.空闲期限(), 登记)
            }).collect::<Vec<_>>();
            drop(表引用);
            if 信号.停止.load(Ordering::Acquire) { break; }
            登记表.sort_by_key(|(期限, _)| *期限);
            let mut 下次期限: Option<Instant> = None;
            for (_, 登记) in &登记表 {
                let 资源紧张 = 信号.资源紧张.load(Ordering::Acquire);
                if let Some(期限) = 登记.空闲期限() {
                    if 登记.回收空闲(Instant::now(), 资源紧张) {
                        if 资源紧张 { 信号.资源紧张.store(false, Ordering::Release); }
                    } else {
                        let 期限 = 期限.max(Instant::now() + Duration::from_millis(1));
                        下次期限 = Some(下次期限.map_or(期限, |旧期限| 旧期限.min(期限)));
                    }
                }
            }
            drop(登记表);
            信号.等变动(旧唤醒代次, 下次期限.map(|期限| 期限.saturating_duration_since(Instant::now())));
        }
    })
}

impl Drop for 跨进程域表 {
    fn drop(&mut self) {
        self.回收通知.停止.store(true, Ordering::Release);
        self.回收通知.唤醒();
        if let Some(回收线程) = self.回收线程.take()
            && 回收线程.thread().id() != std::thread::current().id() {
            let _ = 回收线程.join();
        }
        for (_, 登记) in &self.部署表 { 登记.注销(); }
    }
}
