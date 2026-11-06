//! 任务对外 · 图任务叶子 —— 唯一执行口：执行时补引用、执行后登记产出与失败。
//!
//! # 为什么要包一层
//!
//! [`叶子执行口`](crate::调用任务装配::叶子执行口) 收到的是**自足请求**（入参已在请求里）。
//! 图任务的下游节点入参来自上游节点的**运行产出**，提交时还不存在 ⇒ 本层在「执行前一刻」
//! 把补位填进行序。填不进去就节点失败，并把原因记进失败表（查询回执要说清是执行崩溃，
//! 不是参数不符契约 —— 后者在提交时就拒了）。
//!
//! # 产出表与失败表是**实例级**的
//!
//! 两者都由任务条目持有（`Arc<Mutex<..>>`），叶子只借一份 —— 任务释放时随条目一起丢。
//! 不落模块 static：同进程两份适配器就是两套互不可见的任务。

use std::collections::BTreeMap;
use std::sync::{Arc, Mutex};

use v1_dispatch::调度错误;

use crate::{数据槽, 转发结果, 适配器};

use super::计划::节点计划;
use crate::调用任务装配::{
    叶子产出, 叶子执行口, 叶子标记, 叶子请求, 适配器叶子
};

/// 图任务的真叶子。
pub(crate) struct 图任务叶子 {
    内层: 适配器叶子,
    计划表: Arc<BTreeMap<String, 节点计划>>,
    产出表: Arc<Mutex<BTreeMap<String, 数据槽>>>,
    失败表: Arc<Mutex<BTreeMap<String, String>>>,
}

impl 图任务叶子 {
    pub(crate) fn 新建(
        快照: 适配器,
        标记: 叶子标记,
        计划表: Arc<BTreeMap<String, 节点计划>>,
        产出表: Arc<Mutex<BTreeMap<String, 数据槽>>>,
        失败表: Arc<Mutex<BTreeMap<String, String>>>,
    ) -> Self {
        Self {
            内层: 适配器叶子::由快照(快照, 标记),
            计划表,
            产出表,
            失败表,
        }
    }

    fn 记失败(&self, 节点标识: &str, 说明: String) -> 叶子产出 {
        if let Ok(mut 表) = self.失败表.lock() {
            表.insert(节点标识.to_owned(), 说明);
        }
        叶子产出 {
            结果: 转发结果::失败(调度错误::扩展执行崩溃),
            槽: 数据槽::空槽(),
        }
    }

    /// 按计划成槽并补引用。**取不到就失败**（不编一个值：编出来的值就是第二个语义源）。
    fn 组装入参(&self, 节点标识: &str) -> Result<叶子请求, 叶子产出> {
        let Some(计划) = self.计划表.get(节点标识) else {
            return Err(self.记失败(节点标识, "执行计划里没有这个节点".to_owned()));
        };
        let mut 槽表: Vec<数据槽> = 计划.入参.iter().map(|值| 值.取槽()).collect();
        for 补 in &计划.补位 {
            let 源槽 = self
                .产出表
                .lock()
                .ok()
                .and_then(|表| 表.get(&补.来源节点).copied());
            let Some(源槽) = 源槽 else {
                return Err(self.记失败(
                    节点标识,
                    format!(
                        "输入引用取不到：上游节点「{}」没有留下产出槽（未成功收口即不供值）",
                        补.来源节点
                    ),
                ));
            };
            if 补.行序 >= 槽表.len() {
                return Err(self.记失败(节点标识, format!("输入引用的行序 {} 越过参数表", 补.行序)));
            }
            槽表[补.行序] = 源槽;
        }
        Ok(叶子请求 {
            节点标识: 节点标识.to_owned(),
            执行批号: 0,
            编号: 计划.编号,
            入参: 槽表,
        })
    }
}

impl 叶子执行口 for 图任务叶子 {
    fn 执行(&self, 请求: &叶子请求) -> 叶子产出 {
        let 改写 = match self.组装入参(&请求.节点标识) {
            Ok(改写) => 改写,
            Err(产出) => return 产出,
        };
        let 产出 = self.内层.执行(&改写);
        if 产出.成功() {
            if let Ok(mut 表) = self.产出表.lock() {
                表.insert(请求.节点标识.clone(), 产出.槽);
            }
        } else {
            let 说明 = match 产出.错误() {
                Some(错误) => format!("执行失败：{错误:?}"),
                None => "执行失败：结果不可信".to_owned(),
            };
            if let Ok(mut 表) = self.失败表.lock() {
                表.insert(请求.节点标识.clone(), 说明);
            }
        }
        产出
    }

    fn 标记(&self) -> &叶子标记 {
        self.内层.标记()
    }
}
