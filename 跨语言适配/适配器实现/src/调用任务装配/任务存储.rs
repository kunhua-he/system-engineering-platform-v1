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
    持久故障(String),
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
    故障: Option<存储错误>,
}

impl 任务存储 {
    pub fn 新建(任务标识: impl Into<String>) -> Self {
        Self {
            任务标识: 任务标识.into(),
            内存: 内存任务存储::新建(),
            注入: None,
            故障: None,
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
        self.内存.写入(记录.clone());
        if let Some(错误) = &self.故障 { return Err(错误.clone()); }
        if let Some(注入) = self.注入.as_mut()
            && let Err(错误) = 注入.写入(&记录)
        {
            self.故障 = Some(错误.clone());
            return Err(错误);
        }
        Ok(())
    }

    /// 改任务阶段（不动节点阶段表）。
    pub fn 设置任务阶段(&mut self, 阶段: 调用任务阶段) -> Result<(), 存储错误> {
        let Some(记录) = self.内存.取(&self.任务标识).cloned() else {
            return Err(存储错误::未登记任务(self.任务标识.clone()));
        };
        self.写入记录(任务记录 { 阶段, ..记录 })
    }

    pub fn 故障(&self) -> Option<存储错误> { self.故障.clone() }

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

#[cfg(test)]
mod 可靠存储反证 {
    use super::*;
    use std::sync::{Arc, atomic::{AtomicUsize, Ordering}};
    use crate::调用任务装配::{叶子执行口, 叶子标记, 叶子请求, 叶子产出, 调度实例, 节点素材, 任务结局};
    struct 故障存储 { 写入次数: usize, 拒绝次数: usize }
    impl 任务存储回调 for 故障存储 {
        fn 写入(&mut self, _任务记录: &任务记录) -> Result<(), 存储错误> {
            self.写入次数 += 1;
            if self.写入次数 == self.拒绝次数 { return Err(存储错误::持久故障("定向保存故障".to_owned())); }
            Ok(())
        }
    }
    #[derive(Default)]
    struct 计数执行口 { 叶子次数: AtomicUsize, 执行标记: 叶子标记 }
    impl 叶子执行口 for 计数执行口 {
        fn 标记(&self) -> &叶子标记 { &self.执行标记 }
        fn 执行(&self, _请求: &叶子请求) -> 叶子产出 {
            self.叶子次数.fetch_add(1, Ordering::SeqCst);
            叶子产出 { 结果: crate::转发结果::成功(crate::数据槽::空槽()), 槽: crate::数据槽::空槽(), 业务错误码: None }
        }
    }
    fn 反证素材() -> Vec<节点素材> {
        vec![节点素材::单能力(叶子请求 { 节点标识: "存储节点".to_owned(), 执行批号: 0, 编号: 1000, 入参: Vec::new() }, Vec::new())]
    }
    #[test]
    fn 登记及执行意图失败不执行叶子() {
        for 拒绝次数 in [1, 2] {
            let 执行计数 = Arc::new(计数执行口::default());
            let 装配结果 = 调度实例::装配带注入(反证素材(), 执行计数.clone(), "900", Some(Box::new(故障存储 { 写入次数: 0, 拒绝次数 })));
            if 拒绝次数 == 1 { assert!(装配结果.is_err()); }
            else {
                let mut 调度实体 = 装配结果.unwrap();
                assert!(调度实体.提交().is_err());
                assert!(调度实体.存储故障().is_some());
                assert_eq!(调度实体.节点阶段("存储节点"), Some(调用节点阶段::失败));
                assert!(调度实体.节点时刻("存储节点").is_none(), "保存执行意图失败，工作线程不得编起跑时刻");
                let 实际结局 = 调度实体.等待任务(std::time::Duration::from_millis(50));
                println!("启动保存故障后的任务结局：{实际结局:?}");
                assert!(实际结局.is_some(), "确定未执行的节点必须闭合任务");
                assert!(调度实体.停止());
            }
            assert_eq!(执行计数.叶子次数.load(Ordering::SeqCst), 0);
        }
    }
    #[test]
    fn 完成保存失败保留事实且不假成功() {
        let 执行计数 = Arc::new(计数执行口::default());
        let mut 调度实体 = 调度实例::装配带注入(反证素材(), 执行计数.clone(), "901", Some(Box::new(故障存储 { 写入次数: 0, 拒绝次数: 3 }))).unwrap();
        调度实体.提交().unwrap();
        assert!(matches!(调度实体.等待任务(std::time::Duration::from_secs(2)), Some(任务结局::未确认 { .. })));
        assert_eq!(调度实体.记录节点阶段("存储节点"), Some(调用节点阶段::成功));
        assert!(调度实体.存储故障().is_some());
        assert!(调度实体.提交().is_err());
        调度实体.停止();
        assert_eq!(执行计数.叶子次数.load(Ordering::SeqCst), 1);
    }

    #[test]
    fn 第二根启动保存失败时全队列收口且不编起跑() {
        let 执行计数 = Arc::new(计数执行口::default());
        let 先行就绪任务 = 节点素材::单能力(叶子请求 { 节点标识: "先行就绪任务".to_owned(), 执行批号: 0, 编号: 1000, 入参: Vec::new() }, Vec::new());
        let 写入受阻任务 = 节点素材::单能力(叶子请求 { 节点标识: "写入受阻任务".to_owned(), 执行批号: 0, 编号: 1000, 入参: Vec::new() }, Vec::new());
        let 依赖后继任务 = 节点素材 { 节点标识: "依赖后继任务".to_owned(), 依赖节点: vec!["写入受阻任务".to_owned()], 资源键: Vec::new(), 请求: 叶子请求 { 节点标识: "依赖后继任务".to_owned(), 执行批号: 0, 编号: 1000, 入参: Vec::new() } };
        let mut 调度实体 = 调度实例::装配带注入(vec![先行就绪任务, 写入受阻任务, 依赖后继任务], 执行计数.clone(), "902", Some(Box::new(故障存储 { 写入次数: 0, 拒绝次数: 3 }))).unwrap();
        assert!(调度实体.提交().is_err());
        assert!(matches!(调度实体.等待任务(std::time::Duration::from_millis(50)), Some(任务结局::未确认 { .. })));
        assert_eq!(执行计数.叶子次数.load(Ordering::SeqCst), 0);
        assert_eq!(调度实体.记录节点阶段("先行就绪任务"), Some(调用节点阶段::执行中));
        assert_eq!(调度实体.记录节点阶段("写入受阻任务"), Some(调用节点阶段::执行中));
        assert_eq!(调度实体.节点阶段("依赖后继任务"), Some(调用节点阶段::跳过));
        assert!(调度实体.节点时刻("先行就绪任务").is_none());
        assert!(调度实体.节点时刻("写入受阻任务").is_none());
        assert!(调度实体.节点时刻("依赖后继任务").is_none());
        assert!(调度实体.停止());
    }
}
