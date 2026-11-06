//! 调用任务装配 · 调度实例 —— 一张图一个实例：装配、提交、等结局、停机合流。
//!
//! `装配(素材表, 叶子执行口) → 提交() → 工作线程推图 → 等待任务(时限) → 停止()`
//!
//! 三条不许：① **不强持宿主适配器**（执行侧只拿 [`叶子执行口`]，与适配器不成 `Arc` 环）；
//! ② **锁不跨业务调用持有**（取出工作项即放锁，执行完再取锁记账）；
//! ③ **叶子内禁止再提交**（提交口先问 `叶子执行口::标记().在叶子内()`）。
//!
//! 图怎么一圈圈推、状态怎么落，在 `图驱动.rs`；本件只管对外形状与生命周期。

use std::collections::BTreeMap;
use std::sync::{Arc, Condvar, Mutex};
use std::thread::JoinHandle;
use std::time::{Duration, Instant};

use v1_contract::数据槽;
use v1_dispatch::{
    图校验错误, 调度器错误, 调度错误, 调用任务图, 调用任务节点, 调用任务调度器, 调用任务阶段,
    调用节点阶段,
};

use super::叶子执行::{叶子执行口, 叶子请求};
use super::图驱动::{取锁, 实例状态, 工作循环};
use super::存储::{任务存储, 存储错误};

/// 工作线程条数。**≥ 2** 才有「异键并行」可言；同键仍由资源车道串成先进先出。
pub const 工作线程数: usize = 2;

/// 单次提交的等待上限：内核唯一的单项超时口径 + 装配余量。
pub fn 等待时限() -> Duration {
    Duration::from_millis(v1_dispatch::单项超时毫秒.saturating_add(1_000))
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum 装配错误 {
    空素材表,
    图校验失败(图校验错误),
    调度器错误(调度器错误),
    存储错误(存储错误),
    叶子内重入,
    任务超时,
}

/// 任务结局。**成功与失败都带槽**：执行后失败的槽里可能有半个值，原路怎么留这里怎么留。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum 任务结局 {
    成功(数据槽),
    失败 {
        错误: 调度错误,
        槽: 数据槽,
    },
    已取消,
}

/// 一个节点的素材：图上的位置 + 资源键 + 叶子的自足请求。
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct 节点素材 {
    pub 节点标识: String,
    pub 依赖节点: Vec<String>,
    pub 资源键: Vec<String>,
    pub 请求: 叶子请求,
}

impl 节点素材 {
    /// 单节点图的一格（无依赖）。
    pub fn 单能力(请求: 叶子请求, 资源键: Vec<String>) -> Self {
        Self {
            节点标识: 请求.节点标识.clone(),
            依赖节点: Vec::new(),
            资源键,
            请求,
        }
    }
}

/// 一张图的运行时。**Drop 即停机合流**，不留孤儿线程。
pub struct 调度实例 {
    实例: Arc<(Mutex<实例状态>, Condvar)>,
    线程组: Vec<JoinHandle<()>>,
    /// 执行口留一份：提交前要问它的防递归标记（标记在实例上，不在模块 static）。
    执行口: Arc<dyn 叶子执行口>,
}

impl 调度实例 {
    pub fn 装配(
        素材表: Vec<节点素材>,
        执行口: Arc<dyn 叶子执行口>,
        任务标识: &str,
    ) -> Result<Self, 装配错误> {
        if 素材表.is_empty() {
            return Err(装配错误::空素材表);
        }
        let 节点表: Vec<调用任务节点> = 素材表
            .iter()
            .map(|素材| 调用任务节点::构造(素材.节点标识.clone(), 素材.依赖节点.clone()))
            .collect();
        let 任务图 = 调用任务图::构造图(节点表).map_err(装配错误::图校验失败)?;
        let mut 记录 = 任务存储::新建(任务标识);
        记录
            .登记(素材表.iter().map(|素材| 素材.节点标识.clone()))
            .map_err(装配错误::存储错误)?;
        let 素材索引: BTreeMap<String, 节点素材> = 素材表
            .into_iter()
            .map(|素材| (素材.节点标识.clone(), 素材))
            .collect();
        let 状态 = 实例状态 {
            调度器: 调用任务调度器::构造(任务图),
            素材表: 素材索引,
            待执行: Default::default(),
            槽表: BTreeMap::new(),
            失败表: BTreeMap::new(),
            结局: None,
            停止: false,
            请求取消: false,
            记录,
            跟踪: super::任务跟踪::任务跟踪表::新建(),
        };
        let 实例 = Arc::new((Mutex::new(状态), Condvar::new()));
        let 线程组 = (0..工作线程数)
            .map(|_| {
                let 实例 = Arc::clone(&实例);
                let 执行口 = Arc::clone(&执行口);
                std::thread::spawn(move || 工作循环(&实例, 执行口.as_ref()))
            })
            .collect();
        Ok(Self {
            实例,
            线程组,
            执行口,
        })
    }

    /// 提交：启动所有就绪节点（含等资源的重试），唤醒工作线程。
    pub fn 提交(&self) -> Result<(), 装配错误> {
        if self.执行口.标记().在叶子内() {
            return Err(装配错误::叶子内重入);
        }
        {
            let mut 状态 = 取锁(&self.实例);
            状态.冲刷()?;
            状态.收口();
        }
        self.实例.1.notify_all();
        Ok(())
    }

    /// 等结局。到时限还没收口 ⇒ `None`（调用方报超时，不编一个结局）。
    pub fn 等待任务(&self, 时限: Duration) -> Option<任务结局> {
        let 起点 = Instant::now();
        let mut 状态 = 取锁(&self.实例);
        loop {
            if let Some(结局) = 状态.结局 {
                return Some(结局);
            }
            let 剩余 = 时限.checked_sub(起点.elapsed())?;
            let (收下, 等超时) = self
                .实例
                .1
                .wait_timeout(状态, 剩余)
                .unwrap_or_else(|中毒| 中毒.into_inner());
            状态 = 收下;
            if 等超时.timed_out() && 状态.结局.is_none() {
                return None;
            }
        }
    }

    pub fn 节点阶段(&self, 标识: &str) -> Option<调用节点阶段> {
        取锁(&self.实例).调度器.节点阶段(标识)
    }

    /// 取任务记录的阶段（「到哪一步了」从这里读，不反查调度器）。
    pub fn 记录阶段(&self) -> Option<调用任务阶段> {
        取锁(&self.实例).记录.取().map(|记录| 记录.阶段)
    }

    /// 调度器给出的任务阶段（排队中 / 执行中 / 终态）。**不另写一份状态机**：
    /// 它就是内核那份，本口只是把它读出来（图任务对外面报阶段用）。
    pub fn 调度器阶段(&self) -> 调用任务阶段 {
        取锁(&self.实例).调度器.任务阶段()
    }

    /// 请求取消：置实例上的取消旗（**状态挂实例，不落模块 static**），并唤醒工作线程。
    ///
    /// 效果只有一条：**此后一个节点都不再启动**（挡板在 `图驱动::冲刷` 的入口）。
    /// 已在「执行中」的节点照实跑完、照实收口 —— 取消只标记它们，不替执行体宣布已取消。
    /// 反复调用幂等：旗本来就是 true。
    pub fn 请求取消(&self) {
        {
            let mut 状态 = 取锁(&self.实例);
            状态.请求取消 = true;
        }
        self.实例.1.notify_all();
    }

    /// 停机并汇合。返回「线程是否全部退出」。
    pub fn 停止(&mut self) -> bool {
        {
            let mut 状态 = 取锁(&self.实例);
            状态.停止 = true;
        }
        self.实例.1.notify_all();
        self.线程组.drain(..).all(|线程| 线程.join().is_ok())
    }
}

impl Drop for 调度实例 {
    fn drop(&mut self) {
        let _ = self.停止();
    }
}

/// 一次性提交：装配 → 提交 → 等结局 → 停机合流。
pub fn 执行单次(
    素材表: Vec<节点素材>,
    执行口: Arc<dyn 叶子执行口>,
    任务标识: &str,
    时限: Duration,
) -> Result<任务结局, 装配错误> {
    let mut 实例 = 调度实例::装配(素材表, 执行口, 任务标识)?;
    实例.提交()?;
    let 结局 = 实例.等待任务(时限).ok_or(装配错误::任务超时)?;
    let _ = 实例.停止();
    Ok(结局)
}
