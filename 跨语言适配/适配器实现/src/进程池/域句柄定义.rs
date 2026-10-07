//! 进程池 · 域句柄 —— 一个执行域的短引用（拿到它就不必再持域表锁）。
//!
//! 从 `进程池.rs` 拆出（单源 ≤ 400 行 · `开发规范.md` 第六节）。拆法按**关注点**：
//! 父件管**表与进程**（建格 · 取格 · 退避账 · 重拉），本件管**一个域**（保证在 ·
//! 监督 · 击杀 · 代次）。
//!
//! 件名带「定义」是因为 **Rust 里模块与类型共用一套命名空间**：本件若叫 `域句柄.rs`
//! 就会与它定义的类型撞名 —— 同名时类型反而看不见（`expected type, found module`
//! 就是这么来的）。故此处私有模块 + 父件再导出（`pub use 域句柄定义::域句柄;`）。
//!
//! # 锁收窄的落点就是本件（`临时件/落点/307收尾_接口冻结.md` 末行）
//!
//! 域表锁只用于**取引用**（`进程池::取域句柄`，一次短锁）；长执行（收发）持本件
//! 自带的这把锁 ⇒ **一个慢域阻塞不了健康域**。
//!
//! 子件能读父件的私有项（Rust 隐私：子模块看得见祖先的私项）—— 故本件直接读写
//! `工作进程`，不需要父件为它开任何口子。

use std::sync::{Arc, Mutex, MutexGuard};
use std::time::{Instant, SystemTime, UNIX_EPOCH};

use crate::线程安全::取锁;

use super::{
    工作进程, 判读格子, 监督判读, 生成进程, 装新进程, 查实崩溃, 部署指纹, 进程池错误,
    进程池配置,
};

/// **域句柄** —— 一个执行域的短引用：拿到它之后**不必再持域表锁**就能做长执行。
///
/// 这是「域表锁只用于取引用，长执行锁收窄到该域」（冻结件 §五 末行）的落点：
/// 句柄自持该域的锁（`工作`）与代次源（`代次源`），收发全程只锁**本域这一格**。
#[derive(Clone)]
pub struct 域句柄 {
    pub(crate) 配置: 进程池配置,
    pub(crate) 工作: Arc<Mutex<工作进程>>,
    pub(crate) 代次源: Arc<Mutex<u64>>,
    pub(crate) 事务锁: Arc<Mutex<()>>,
}

impl 域句柄 {
    pub(crate) fn 锁事务(
        &self, 预算: &crate::进程帧::调用帧预算,
    ) -> Result<MutexGuard<'_, ()>, 进程池错误> {
        loop {
            预算.检查剩余().map_err(|_| 进程池错误::预算耗尽)?;
            match self.事务锁.try_lock() {
                Ok(事务守卫) => return Ok(事务守卫),
                Err(std::sync::TryLockError::Poisoned(中毒)) => return Ok(中毒.into_inner()),
                Err(std::sync::TryLockError::WouldBlock) => {
                    std::thread::sleep(std::time::Duration::from_millis(1));
                },
            }
        }
    }

    /// 取该域的锁（**长执行只在它之内**；跨域互不阻塞）。
    pub(crate) fn 锁(&self) -> MutexGuard<'_, 工作进程> {
        取锁(&self.工作)
    }

    /// 取一个**跨重启不复用**的实例代次（墙钟纳秒为源，强制比上次大）。
    pub(crate) fn 取单调代次(&self) -> u64 {
        let 墙钟 = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|时长| 时长.as_nanos() as u64)
            .unwrap_or(0);
        let mut 上次 = 取锁(&self.代次源);
        let 代次 = 墙钟.max(上次.saturating_add(1));
        *上次 = 代次;
        代次
    }

    /// 保证这个域在跑：崩了则按退避 / 熔断决定能不能重拉。**只持该域的锁**。
    ///
    /// **单次语义**：域已拉起且**部署指纹一致**才算「已在」；运行中却给了不同部署参数
    /// ⇒ [`进程池错误::部署参数不符`]（结构化拒）。绝不静默换部署表 —— 旧 worker 继续
    /// 服务、下次重拉才用新参，等于同域两套部署口径。崩溃（不在运行）时按传入参数重拉。
    pub fn 保证在(&self, 启动程序: &str, 启动参数: &[String]) -> Result<(), 进程池错误> {
        let 指纹 = 部署指纹(启动程序, 启动参数);
        let mut 工作 = self.锁();
        查实崩溃(self.配置, &mut 工作);
        let 现在时刻 = Instant::now();
        if 工作.运行中 {
            if 工作.部署指纹 != 指纹 {
                return Err(进程池错误::部署参数不符);
            }
            return Ok(());
        }
        if 工作.熔断截至.map_or(false, |熔断截至| 现在时刻 < 熔断截至) {
            return Err(进程池错误::熔断中);
        }
        if 现在时刻 < 工作.下次允许拉起 {
            return Err(进程池错误::拉起失败);
        }
        let (子进程, 通道) = 生成进程(启动程序, 启动参数)?;
        装新进程(&mut 工作, 子进程, 通道, self.取单调代次(), 指纹)?;
        Ok(())
    }

    /// 这个域的装载初始化重放过没有。
    pub fn 已重放装载(&self) -> bool {
        self.锁().装载已重放
    }

    /// 这个域的**当前实例代次**。
    pub fn 当前代次(&self) -> u64 {
        self.锁().实例代次
    }

    /// 监督一次：查实崩溃、给判读。不重拉。
    pub fn 监督(&self) -> 监督判读 {
        let mut 工作 = self.锁();
        查实崩溃(self.配置, &mut 工作);
        判读格子(&工作, Instant::now())
    }

    /// 击杀本域（整组），并回收它的进程。
    pub fn 击杀(&self) -> Result<(), 进程池错误> {
        let mut 工作 = self.锁();
        super::击杀进程组(工作.进程组号);
        let _ = 工作.子进程.kill();
        let _ = 工作.子进程.wait();
        工作.运行中 = false;
        Ok(())
    }
}
