use crate::{
    任务图模块::调用任务图,
    调用节点状态::{调用任务阶段, 调用节点阶段},
    资源车道模块::{调用资源车道, 资源租约},
};
use std::collections::BTreeMap;
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct 节点完成事件 {
    pub 节点标识: String,
    pub 执行批号: u64,
    pub 成功: bool,
}
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum 调度决策 {
    启动 {
        节点标识: String,
        执行批号: u64,
    },
    节点就绪 {
        节点标识: String,
    },
    节点跳过 {
        节点标识: String,
    },
    节点失败 {
        节点标识: String,
    },
}
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum 调度器错误 {
    未知节点(String),
    非法启动(调用节点阶段),
    依赖未就绪,
}
#[derive(Debug)]
pub struct 调用节点记录 {
    pub 阶段: 调用节点阶段,
    pub 执行批号: u64,
    pub 前驱剩余: usize,
    pub 资源租约: Option<资源租约>,
}
pub struct 调用任务调度器 {
    任务图: 调用任务图,
    节点状态: BTreeMap<String, 调用节点记录>,
    资源车道: 调用资源车道,
    下一批号: u64,
}
impl 调用任务调度器 {
    pub fn 构造(任务图: 调用任务图) -> Self {
        let mut 节点状态 = BTreeMap::new();
        for 节点 in 任务图.节点列表() {
            节点状态.insert(
                节点.节点标识.clone(),
                调用节点记录 {
                    阶段: 调用节点阶段::等待依赖,
                    执行批号: 0,
                    前驱剩余: 节点.依赖节点.len(),
                    资源租约: None,
                },
            );
        }
        let mut 调度器 = Self {
            任务图,
            节点状态,
            资源车道: 调用资源车道::构造(),
            下一批号: 0,
        };
        调度器.刷新就绪();
        调度器
    }
    pub fn 任务阶段(&self) -> 调用任务阶段 {
        if self
            .节点状态
            .values()
            .any(|节点状态| matches!(节点状态.阶段, 调用节点阶段::执行中 | 调用节点阶段::收尾中))
        {
            调用任务阶段::执行中
        } else if self.节点状态.values().all(|节点状态| {
            matches!(
                节点状态.阶段,
                调用节点阶段::成功 | 调用节点阶段::跳过 | 调用节点阶段::已取消
            )
        }) {
            if self
                .节点状态
                .values()
                .any(|节点状态| matches!(节点状态.阶段, 调用节点阶段::跳过 | 调用节点阶段::已取消))
            {
                调用任务阶段::已取消
            } else {
                调用任务阶段::成功
            }
        } else {
            调用任务阶段::排队中
        }
    }
    pub fn 节点阶段(&self, 标识: &str) -> Option<调用节点阶段> {
        self.节点状态.get(标识).map(|节点状态| 节点状态.阶段)
    }
    pub fn 启动节点(
        &mut self,
        标识: &str,
        资源键: impl IntoIterator<Item = impl Into<String>>,
    ) -> Result<Option<调度决策>, 调度器错误> {
        let 当前阶段 = self
            .节点状态
            .get(标识)
            .ok_or_else(|| 调度器错误::未知节点(标识.to_owned()))?
            .阶段;
        if 当前阶段 != 调用节点阶段::就绪 {
            return Err(调度器错误::非法启动(当前阶段));
        }
        let Some(租约) = self.资源车道.尝试预留(标识.to_owned(), 资源键) else {
            self.节点状态.get_mut(标识).expect("节点已确认").阶段 = 调用节点阶段::等资源;
            return Ok(None);
        };
        self.下一批号 += 1;
        let 执行批号 = self.下一批号;
        let 节点状态 = self.节点状态.get_mut(标识).expect("节点已确认");
        节点状态.执行批号 = 执行批号;
        节点状态.资源租约 = Some(租约);
        节点状态.阶段 = 调用节点阶段::执行中;
        Ok(Some(调度决策::启动 {
            节点标识: 标识.to_owned(),
            执行批号,
        }))
    }
    pub fn 处理完成(
        &mut self,
        事件: 节点完成事件,
    ) -> Result<Vec<调度决策>, 调度器错误> {
        let 节点状态 = self
            .节点状态
            .get(&事件.节点标识)
            .ok_or_else(|| 调度器错误::未知节点(事件.节点标识.clone()))?;
        if 节点状态.阶段 != 调用节点阶段::执行中 || 节点状态.执行批号 != 事件.执行批号
        {
            return Ok(Vec::new());
        }
        let 租约 = self
            .节点状态
            .get_mut(&事件.节点标识)
            .and_then(|节点状态| 节点状态.资源租约.take());
        if let Some(租约) = 租约 {
            self.资源车道.释放(&租约);
        }
        self.节点状态
            .get_mut(&事件.节点标识)
            .expect("节点已确认")
            .阶段 = if 事件.成功 {
            调用节点阶段::成功
        } else {
            调用节点阶段::失败
        };
        let mut 决策 = Vec::new();
        let 后代: Vec<String> = self
            .任务图
            .后继节点(&事件.节点标识)
            .into_iter()
            .flatten()
            .map(str::to_owned)
            .collect();
        for 后置 in 后代 {
            if 事件.成功 {
                self.刷新单节点(&后置, &mut 决策);
            } else {
                self.跳过后代(&后置, &mut 决策);
            }
        }
        决策.push(if 事件.成功 {
            调度决策::节点就绪 {
                节点标识: 事件.节点标识,
            }
        } else {
            调度决策::节点失败 {
                节点标识: 事件.节点标识,
            }
        });
        self.刷新就绪();
        Ok(决策)
    }
    fn 跳过后代(&mut self, 标识: &str, 决策: &mut Vec<调度决策>) {
        let 可跳过 = self.节点状态.get(标识).is_some_and(|节点状态| {
            matches!(
                节点状态.阶段,
                调用节点阶段::等待依赖 | 调用节点阶段::就绪 | 调用节点阶段::等资源
            )
        });
        if !可跳过 {
            return;
        }
        self.节点状态.get_mut(标识).expect("节点已确认").阶段 = 调用节点阶段::跳过;
        决策.push(调度决策::节点跳过 {
            节点标识: 标识.to_owned(),
        });
        let 后代: Vec<String> = self
            .任务图
            .后继节点(标识)
            .into_iter()
            .flatten()
            .map(str::to_owned)
            .collect();
        for 后置 in 后代 {
            self.跳过后代(&后置, 决策)
        }
    }
    fn 刷新单节点(&mut self, 标识: &str, 决策: &mut Vec<调度决策>) {
        let 可就绪 = self
            .节点状态
            .get(标识)
            .is_some_and(|节点状态| 节点状态.阶段 == 调用节点阶段::等待依赖);
        if !可就绪 {
            return;
        }
        let 全成功 = self.任务图.节点(标识).is_some_and(|节点| {
            节点.依赖节点.iter().all(|依赖| {
                self.节点状态
                    .get(依赖)
                    .is_some_and(|前置| 前置.阶段 == 调用节点阶段::成功)
            })
        });
        if 全成功 {
            self.节点状态.get_mut(标识).expect("节点已确认").阶段 = 调用节点阶段::就绪;
            决策.push(调度决策::节点就绪 {
                节点标识: 标识.to_owned(),
            });
        }
    }
    fn 刷新就绪(&mut self) {
        let 标识列表: Vec<String> = self.节点状态.keys().cloned().collect();
        for 标识 in 标识列表 {
            let mut 丢弃 = Vec::new();
            self.刷新单节点(&标识, &mut 丢弃);
        }
    }
}
pub trait 调用参数回调 {
    type 参数;
    type 错误;
    fn 获取参数(&self, 节点标识: &str) -> Result<Self::参数, Self::错误>;
}
pub trait 调用执行回调 {
    type 参数;
    type 输出;
    type 错误;
    fn 执行(
        &mut self,
        节点标识: &str,
        执行批号: u64,
        参数: Self::参数,
    ) -> Result<Self::输出, Self::错误>;
}
pub trait 调用状态存储回调 {
    type 错误;
    fn 保存节点状态(
        &mut self,
        节点标识: &str,
        阶段: 调用节点阶段,
        执行批号: u64,
    ) -> Result<(), Self::错误>;
}
pub trait 异步跟踪回调 {
    type 错误;
    fn 登记执行(&mut self, 节点标识: &str, 执行批号: u64) -> Result<(), Self::错误>;
    fn 登记完成(&mut self, 事件: &节点完成事件) -> Result<(), Self::错误>;
}
