//! 任务对外 · 任务表 —— 发号 · 幂等 · 快照 · 取消 · 释放 · 收口清扫。
//!
//! # 上限与清扫（不许跑一晚就漏内存）
//!
//! 表有容量（[`默认任务容量`]）。超容量时**只淘汰终态任务**，按最近最少用丢记录；
//! 在跑的任务一条都不动（丢它的记录等于把还在执行的图变成孤儿：没有口能查到、也停不掉）。
//! 淘汰**只丢记录不丢正在跑的实例**：条目一丢，实例 `Drop` 即停机合流，而那条路只有终态才走。
//!
//! # 阶段的唯一来源
//!
//! 未取消时读****调度器那份**状态机（`调用任务阶段` 那份，不在本件重写一份）；取消时读本面的
//! 取消旗 —— 取消是**调用方的意志**，不是图的状态机事件，两者不能混成一份。
//!
//! # 取消语义（三句）
//!
//! 1. 等待中 / 就绪 / 等资源的节点 ⇒ 报「已取消」；任务阶段 ⇒「已取消」。
//! 2. 执行中 / 收尾中的节点**只标记**：阶段照实报执行中，真实收口后才回收资源。
//! 3. 释放只对**已终态且无在跑节点**的任务开口。

use std::collections::BTreeMap;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};

use v1_dispatch::{调用任务阶段, 调用节点阶段};

use crate::数据槽;

use crate::调用任务装配::调度实例;

use super::形状::{任务快照, 取消读数, 节点失败读数};

/// 任务表容量（超了按最近最少用淘汰**终态**任务）。
pub(crate) const 默认任务容量: usize = 128;

/// 一条任务记录。**只有任务表持有它**：丢了就再没有口能查到这张图。
pub(crate) struct 任务条目 {
    pub 任务标识: u64,
    pub 请求标识: Option<String>,
    /// 图摘要（判「同请求标识是不是同一张图」）。
    pub 摘要: u64,
    pub 实例: Arc<调度实例>,
    pub 节点标识表: Vec<String>,
    pub 取消: bool,
    pub 末次访问: u64,
    pub 失败表: Arc<Mutex<BTreeMap<String, String>>>,
    /// 逐节点产出槽：引用补位从这里取，也是「上图结果」的唯一来源。
    pub 产出表: Arc<Mutex<BTreeMap<String, 数据槽>>>,
}

/// 任务表本体（**按适配器实例持有**，跨执行快照共享）。
pub(crate) struct 任务表 {
    条目: BTreeMap<u64, 任务条目>,
    幂等: BTreeMap<String, u64>,
    下一号: AtomicU64,
    访问序: u64,
    容量: usize,
}

impl 任务表 {
    pub(crate) fn 新建(容量: usize) -> Self {
        Self {
            条目: BTreeMap::new(),
            幂等: BTreeMap::new(),
            下一号: AtomicU64::new(1),
            访问序: 0,
            容量: 容量.max(1),
        }
    }

    /// 发号：**实例内单调**（原子量，跨快照共享同一条序列）。
    pub(crate) fn 发号(&self) -> u64 {
        self.下一号.fetch_add(1, Ordering::Relaxed)
    }

    pub(crate) fn 按请求标识(&self, 请求标识: &str) -> Option<u64> {
        self.幂等.get(请求标识).copied()
    }

    pub(crate) fn 摘要(&self, 任务标识: u64) -> Option<u64> {
        self.条目.get(&任务标识).map(|条目| 条目.摘要)
    }

    pub(crate) fn 插入(&mut self, 条目: 任务条目) {
        if let Some(请求标识) = 条目.请求标识.clone() {
            self.幂等.insert(请求标识, 条目.任务标识);
        }
        self.条目.insert(条目.任务标识, 条目);
    }

    /// 取条目并刷新末次访问（淘汰按它排）。
    pub(crate) fn 取(&mut self, 任务标识: u64) -> Option<&mut 任务条目> {
        self.访问序 += 1;
        let 序 = self.访问序;
        let 条目 = self.条目.get_mut(&任务标识)?;
        条目.末次访问 = 序;
        Some(条目)
    }

    /// 释放一条记录（连同它的幂等键）：返回「原本在不在」。
    pub(crate) fn 移除(&mut self, 任务标识: u64) -> bool {
        let Some(条目) = self.条目.remove(&任务标识) else {
            return false;
        };
        if let Some(请求标识) = 条目.请求标识 {
            self.幂等.remove(&请求标识);
        }
        true
    }

    pub(crate) fn 条数(&self) -> usize {
        self.条目.len()
    }

    /// 收口清扫：超容量时淘汰**终态且无在跑节点**的任务，按最近最少用先丢。
    pub(crate) fn 清扫(&mut self) {
        while self.条目.len() > self.容量 {
            let 候选 = self
                .条目
                .values()
                .filter(|条目| 可淘汰(条目))
                .min_by_key(|条目| 条目.末次访问)
                .map(|条目| 条目.任务标识);
            let Some(候选) = 候选 else {
                // 一条都不可淘汰（全在跑）：不再硬塞 —— 宁可超容量也不丢在跑的图。
                return;
            };
            self.移除(候选);
        }
    }
}

/// 能不能淘汰：终态**且**没有执行中 / 收尾中的节点。
fn 可淘汰(条目: &任务条目) -> bool {
    let 阶段 = 阶段(条目);
    matches!(
        阶段,
        调用任务阶段::成功 | 调用任务阶段::失败 | 调用任务阶段::已取消
    ) && 在跑节点(条目).is_empty()
}

/// 执行中 / 收尾中的节点（取消只标记它们，真实收口后才算停）。
pub(crate) fn 在跑节点(条目: &任务条目) -> Vec<String> {
    条目
        .节点标识表
        .iter()
        .filter(|标识| {
            matches!(
                条目.实例.节点阶段(标识),
                Some(调用节点阶段::执行中 | 调用节点阶段::收尾中)
            )
        })
        .cloned()
        .collect()
}

/// 任务阶段：取消旗优先，其余读调度器那份状态机。
pub(crate) fn 阶段(条目: &任务条目) -> 调用任务阶段 {
    if 条目.取消 {
        return 调用任务阶段::已取消;
    }
    match 条目.实例.记录阶段() {
        Some(阶段)
            if matches!(
                阶段,
                调用任务阶段::成功 | 调用任务阶段::失败 | 调用任务阶段::已取消
            ) =>
        {
            阶段
        }
        _ => 条目.实例.调度器阶段(),
    }
}

/// 造一张快照。`收窄` 给了就只留那个节点；节点不在本任务 ⇒ `None`（不是空表）。
pub(crate) fn 造快照(条目: &任务条目, 收窄: Option<&str>) -> Option<任务快照> {
    let 阶段 = 阶段(条目);
    let mut 节点阶段表 = Vec::with_capacity(条目.节点标识表.len());
    for 标识 in &条目.节点标识表 {
        let 实报 = 条目.实例.节点阶段(标识);
        let 报 = match (条目.取消, 实报) {
            // 取消后：只有真在跑 / 已收口的节点照实报，其余一律「已取消」（不伪造执行中）。
            (true, Some(阶段))
                if matches!(
                    阶段,
                    调用节点阶段::执行中
                        | 调用节点阶段::收尾中
                        | 调用节点阶段::成功
                        | 调用节点阶段::失败
                ) =>
            {
                阶段
            }
            (true, _) => 调用节点阶段::已取消,
            (false, Some(阶段)) => 阶段,
            (false, None) => 调用节点阶段::等待依赖,
        };
        if 收窄.is_some_and(|要| 要 != 标识) {
            continue;
        }
        节点阶段表.push((标识.clone(), 报));
    }
    if 节点阶段表.is_empty() {
        return None;
    }
    Some(任务快照 {
        任务标识: 条目.任务标识,
        阶段,
        节点阶段表,
        错误: 失败读数(条目, 收窄),
    })
}

/// 失败读数：有失败节点才给（成功与失败不能同时为真）。
fn 失败读数(条目: &任务条目, 收窄: Option<&str>) -> Option<节点失败读数> {
    let 表 = 条目.失败表.lock().ok()?;
    let (节点标识, 说明) = 表
        .iter()
        .find(|(标识, _)| 收窄.is_none_or(|要| 要 == 标识.as_str()))?;
    Some(节点失败读数 {
        节点标识: 节点标识.clone(),
        说明: 说明.clone(),
    })
}

/// 取消一条任务：置取消旗，返回哪些节点被置成「已取消」、哪些还在跑。
pub(crate) fn 取消(条目: &mut 任务条目) -> 取消读数 {
    条目.取消 = true;
    let 在跑 = 在跑节点(条目);
    let 已取消节点 = 条目
        .节点标识表
        .iter()
        .filter(|标识| {
            !在跑.contains(标识)
                && !matches!(
                    条目.实例.节点阶段(标识),
                    Some(调用节点阶段::成功 | 调用节点阶段::失败)
                )
        })
        .cloned()
        .collect::<Vec<String>>();
    取消读数 {
        任务标识: 条目.任务标识,
        任务存在: true,
        阶段: 调用任务阶段::已取消,
        已取消节点,
        在跑节点: 在跑,
    }
}
