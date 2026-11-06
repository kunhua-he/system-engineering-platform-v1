//! 调用任务装配 · 任务存储 —— 内存任务记录 + 可注入存储回调。
//!
//! # 本腿只到接口面
//!
//! 记录先落内存（`BTreeMap`），真正的库（SQLite 等）**经 [`任务存储回调`] 注入**：
//! 本腿不拉数据库、不新增端口、不起服务。注入位空着时就是纯内存，行为不退化。
//!
//! 内核的 [`调用状态存储回调`] 由本件实现 —— 节点阶段一变就落一条，所以
//! 「节点走到哪一步」在任务记录里读得到，不必反查调度器。

use std::collections::BTreeMap;

use v1_dispatch::{调用任务阶段, 调用状态存储回调, 调用节点阶段};

/// 存储写入失败。**结构化**：说清是哪一步写的，不是 `false`。
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum 存储错误 {
    未登记任务(String),
}

/// 一条任务记录：任务阶段 + 逐节点阶段。**没有第三个字段**（记录只答「到哪一步了」）。
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct 任务记录 {
    pub 任务标识: String,
    pub 阶段: 调用任务阶段,
    pub 节点阶段: BTreeMap<String, 调用节点阶段>,
}

/// 可注入的存储回调（真库走这里；本腿只定义形状）。
pub trait 任务存储回调: Send {
    fn 写入(&mut self, 记录: &任务记录) -> Result<(), 存储错误>;
}

/// 内存任务记录表。**按实例持有**，不落进程级全局。
#[derive(Debug, Default)]
pub struct 内存任务存储 {
    记录表: BTreeMap<String, 任务记录>,
}

impl 内存任务存储 {
    pub fn 新建() -> Self {
        Self::default()
    }

    pub fn 写入(&mut self, 记录: 任务记录) {
        self.记录表.insert(记录.任务标识.clone(), 记录);
    }

    pub fn 取(&self, 任务标识: &str) -> Option<&任务记录> {
        self.记录表.get(任务标识)
    }

    pub fn 全部(&self) -> Vec<&任务记录> {
        self.记录表.values().collect()
    }

    pub fn 移除(&mut self, 任务标识: &str) -> bool {
        self.记录表.remove(任务标识).is_some()
    }

    pub fn 条数(&self) -> usize {
        self.记录表.len()
    }
}

/// 任务存储：内存记录 + 可选注入回调。**写内存成功才算写过**，注入失败原样报出去。
pub struct 任务存储 {
    任务标识: String,
    内存: 内存任务存储,
    注入: Option<Box<dyn 任务存储回调>>,
}

impl 任务存储 {
    pub fn 新建(任务标识: impl Into<String>) -> Self {
        Self {
            任务标识: 任务标识.into(),
            内存: 内存任务存储::新建(),
            注入: None,
        }
    }

    /// 带注入回调的构造：真库从这里进来。
    pub fn 带注入(任务标识: impl Into<String>, 注入: Box<dyn 任务存储回调>) -> Self {
        Self {
            注入: Some(注入),
            ..Self::新建(任务标识)
        }
    }

    /// 登记一条任务（阶段起步 = 排队中，节点阶段表按调用方给的填）。
    pub fn 登记(
        &mut self,
        节点标识表: impl IntoIterator<Item = String>,
    ) -> Result<(), 存储错误> {
        let 节点阶段 = 节点标识表
            .into_iter()
            .map(|节点标识| (节点标识, 调用节点阶段::等待依赖))
            .collect();
        self.写入记录(任务记录 {
            任务标识: self.任务标识.clone(),
            阶段: 调用任务阶段::排队中,
            节点阶段,
        })
    }

    /// 落一条完整记录（内存 + 注入）。
    pub fn 写入记录(&mut self, 记录: 任务记录) -> Result<(), 存储错误> {
        if let Some(注入) = self.注入.as_mut() {
            注入.写入(&记录)?;
        }
        self.内存.写入(记录);
        Ok(())
    }

    /// 改任务阶段（不动节点阶段表）。
    pub fn 设置任务阶段(&mut self, 阶段: 调用任务阶段) -> Result<(), 存储错误> {
        let Some(记录) = self.内存.取(&self.任务标识).cloned() else {
            return Err(存储错误::未登记任务(self.任务标识.clone()));
        };
        self.写入记录(任务记录 { 阶段, ..记录 })
    }

    pub fn 取(&self) -> Option<&任务记录> {
        self.内存.取(&self.任务标识)
    }

    /// 落一个节点阶段（节点状态回调走这里）。
    pub fn 保存阶段(
        &mut self, 节点标识: &str, 阶段: 调用节点阶段
    ) -> Result<(), 存储错误> {
        self.写节点阶段(节点标识, 阶段, 0)
    }

    fn 写节点阶段(
        &mut self,
        节点标识: &str,
        阶段: 调用节点阶段,
        _执行批号: u64,
    ) -> Result<(), 存储错误> {
        let Some(记录) = self.内存.取(&self.任务标识).cloned() else {
            return Err(存储错误::未登记任务(self.任务标识.clone()));
        };
        let mut 节点阶段 = 记录.节点阶段;
        节点阶段.insert(节点标识.to_owned(), 阶段);
        self.写入记录(任务记录 {
            节点阶段, ..记录
        })
    }
}

impl 调用状态存储回调 for 任务存储 {
    type 错误 = 存储错误;

    fn 保存节点状态(
        &mut self,
        节点标识: &str,
        阶段: 调用节点阶段,
        执行批号: u64,
    ) -> Result<(), Self::错误> {
        self.写节点阶段(节点标识, 阶段, 执行批号)
    }
}
