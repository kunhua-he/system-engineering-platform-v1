//! 调用任务装配 · 图驱动 —— 实例内部状态与工作线程循环（调度器就住在这里）。
//!
//! `调度实例.rs` 答「怎么装配、怎么等、怎么停」（对外形状），本件答「线程怎么把图推到底」
//! （对内状态）。混在一件会超 200 行，长文件会把「锁在哪、谁改阶段」埋进噪声里。

use std::collections::{BTreeMap, VecDeque};
use std::sync::{Arc, Condvar, Mutex, MutexGuard};

use v1_contract::数据槽;
use v1_dispatch::{
    节点完成事件, 调度决策, 调度错误, 调用任务调度器, 调用任务阶段, 调用状态存储回调, 调用节点阶段,
};

use super::任务跟踪::任务跟踪表;
use super::叶子执行::{叶子产出, 叶子执行口, 叶子请求};
use super::存储::任务存储;
use super::实例::{任务结局, 节点素材, 装配错误};

pub(super) struct 工作项 {
    节点标识: String,
    执行批号: u64,
    请求: 叶子请求,
}

pub(super) struct 实例状态 {
    pub(super) 调度器: 调用任务调度器,
    pub(super) 素材表: BTreeMap<String, 节点素材>,
    pub(super) 待执行: VecDeque<工作项>,
    pub(super) 槽表: BTreeMap<String, 数据槽>,
    pub(super) 失败表: BTreeMap<String, 调度错误>,
    pub(super) 结局: Option<任务结局>,
    pub(super) 停止: bool,
    /// 取消请求：**挂在实例上**（不落模块 static —— 同进程两张图必须互不可见）。
    pub(super) 请求取消: bool,
    pub(super) 记录: 任务存储,
    pub(super) 跟踪: 任务跟踪表,
}

impl 实例状态 {
    /// 把可启动的节点各试启动一次；启动成功的进待执行队。
    ///
    /// **同键先在闸外排队**：内核 `启动节点` 只认「就绪」，冲突递进去会被置成「等资源」，
    /// 而内核没有「等资源 → 就绪」的口（冻结件不补）⇒ 那个节点永远起不来。故驱动按
    /// 「执行中节点所占的键」挡一道，冲突的留在**就绪**，占用者收口后按图序再来 ——
    /// 这就是同键先进先出。闸只是执行面的**视图**（由阶段现算），不是第二份占用表。
    pub(super) fn 冲刷(&mut self) -> Result<(), 装配错误> {
        // 取消挡板：收到取消请求后**一个节点都不再启动**。
        //
        // 为什么挡在这里而不是逐节点拦：内核 `启动节点` 只认「就绪」，本驱动是唯一启动口
        // （`冲刷` 覆盖提交与每次完成后的重试）⇒ 一个判断就够，不会漏启动路径。
        // 已经在「执行中」的节点（含已进待执行队的那批）照实跑完并照实收口 ——
        // 取消只**标记**它们，不伪造「已取消」（跃迁表里执行中 → 已取消虽合法，
        // 但那是执行体真退场之后的事，不是驱动能替它宣布的）。
        if self.请求取消 {
            return Ok(());
        }
        let 标识表: Vec<String> = self.素材表.keys().cloned().collect();
        let mut 占用键: BTreeMap<String, usize> = BTreeMap::new();
        for 标识 in &标识表 {
            if self.调度器.节点阶段(标识) != Some(调用节点阶段::执行中) {
                continue;
            }
            for 键 in &self.素材表[标识].资源键 {
                *占用键.entry(键.clone()).or_insert(0) += 1;
            }
        }
        for 标识 in 标识表 {
            if self.调度器.节点阶段(&标识) != Some(调用节点阶段::就绪) {
                continue;
            }
            let 资源键 = self.素材表[&标识].资源键.clone();
            if 资源键.iter().any(|键| 占用键.contains_key(键)) {
                continue;
            }
            for 键 in &资源键 {
                *占用键.entry(键.clone()).or_insert(0) += 1;
            }
            let 决策 = self
                .调度器
                .启动节点(&标识, 资源键)
                .map_err(装配错误::调度器错误)?;
            let Some(调度决策::启动 { 执行批号, .. }) = 决策 else {
                continue;
            };
            let 请求 = self.素材表[&标识].请求.clone();
            self.跟踪.登记生成中(&标识, 执行批号);
            self.待执行.push_back(工作项 {
                节点标识: 标识.clone(),
                执行批号,
                请求,
            });
            let _ = self
                .记录
                .保存节点状态(&标识, 调用节点阶段::执行中, 执行批号);
        }
        Ok(())
    }

    /// 一次完成：登记跟踪 → 报调度器 → 落记录 → 重试启动 → 收口。
    pub(super) fn 记账完成(&mut self, 工作: &工作项, 产出: 叶子产出) {
        let 事件 = 节点完成事件 {
            节点标识: 工作.节点标识.clone(),
            执行批号: 工作.执行批号,
            成功: 产出.成功(),
        };
        self.跟踪.登记完成(&事件);
        let _ = self.调度器.处理完成(事件);
        if let Some(错误) = 产出.错误() {
            self.失败表.insert(工作.节点标识.clone(), 错误);
        }
        self.槽表.insert(工作.节点标识.clone(), 产出.槽);
        if let Some(阶段) = self.调度器.节点阶段(&工作.节点标识) {
            let _ = self.记录.保存节点状态(&工作.节点标识, 阶段, 工作.执行批号);
        }
        let _ = self.冲刷();
        self.收口();
    }

    /// 收口：跟踪表没有「生成中」且任务到终态 ⇒ 定结局（生成中一律不算成功）。
    pub(super) fn 收口(&mut self) {
        if self.结局.is_some() || !self.跟踪.全部已收口() {
            return;
        }
        let 任务阶段 = self.调度器.任务阶段();
        let 结局 = if let Some((_, 错误)) = self.失败表.iter().next() {
            任务结局::失败 {
                错误: *错误,
                槽: self.首个槽(),
            }
        } else if 任务阶段 == 调用任务阶段::成功 {
            任务结局::成功(self.首个槽())
        } else if 任务阶段 == 调用任务阶段::已取消 {
            任务结局::已取消
        } else {
            return;
        };
        let 阶段 = match 结局 {
            任务结局::成功(_) => 调用任务阶段::成功,
            任务结局::失败 { .. } => 调用任务阶段::失败,
            任务结局::已取消 => 调用任务阶段::已取消,
        };
        let _ = self.记录.设置任务阶段(阶段);
        self.结局 = Some(结局);
    }

    fn 首个槽(&self) -> 数据槽 {
        self.槽表
            .values()
            .next()
            .copied()
            .unwrap_or_else(数据槽::空槽)
    }
}

/// 工作线程循环：取项 → 执行叶子（锁外）→ 记账 → 唤醒。
pub(super) fn 工作循环(
    实例: &Arc<(Mutex<实例状态>, Condvar)>, 执行口: &dyn 叶子执行口
) {
    loop {
        let Some(工作) = 取出一项(实例) else {
            return;
        };
        // 锁已放：叶子在锁外跑（一个慢叶子不阻塞别的线程登记）。
        let 产出 = match 执行口.标记().进入() {
            Some(_守卫) => 执行口.执行(&工作.请求),
            None => 叶子产出 {
                结果: crate::转发结果::失败(调度错误::扩展执行崩溃),
                槽: 数据槽::空槽(),
            },
        };
        {
            let mut 状态 = 取锁(实例);
            状态.记账完成(&工作, 产出);
        }
        实例.1.notify_all();
    }
}

/// 停下时取出一项：没有工作即是「停机」信号。
fn 取出一项(实例: &Arc<(Mutex<实例状态>, Condvar)>) -> Option<工作项> {
    let mut 状态 = 取锁(实例);
    while 状态.待执行.is_empty() && !状态.停止 {
        状态 = 实例.1.wait(状态).unwrap_or_else(|中毒| 中毒.into_inner());
    }
    状态.待执行.pop_front()
}

/// 取锁：锁中毒也拿回来（调度路径不因一次 panic 永久不可用）。
pub(super) fn 取锁(实例: &Arc<(Mutex<实例状态>, Condvar)>) -> MutexGuard<'_, 实例状态> {
    实例.0.lock().unwrap_or_else(|中毒| 中毒.into_inner())
}
