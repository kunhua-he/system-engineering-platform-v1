use std::fmt;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum 调用节点阶段 {
    等待依赖,
    就绪,
    等资源,
    执行中,
    收尾中,
    成功,
    失败,
    跳过,
    已取消,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum 调用任务阶段 {
    排队中,
    执行中,
    收尾中,
    成功,
    失败,
    已取消,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct 状态转换错误 {
    pub 当前阶段: 调用节点阶段,
    pub 目标: 调用节点阶段,
}
impl fmt::Display for 状态转换错误 {
    fn fmt(&self, 格式输出: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(格式输出, "节点状态不可转换")
    }
}
impl std::error::Error for 状态转换错误 {}
impl 调用节点阶段 {
    pub fn 可转换(self, 目标: Self) -> bool {
        matches!(
            (self, 目标),
            (Self::等待依赖, Self::就绪 | Self::跳过 | Self::已取消)
                | (Self::就绪, Self::等资源 | Self::执行中 | Self::已取消)
                | (Self::等资源, Self::就绪 | Self::执行中 | Self::已取消)
                | (Self::执行中, Self::收尾中 | Self::失败 | Self::已取消)
                | (Self::收尾中, Self::成功 | Self::失败 | Self::已取消)
        )
    }
    pub fn 转换(self, 目标: Self) -> Result<Self, 状态转换错误> {
        if self.可转换(目标) {
            Ok(目标)
        } else {
            Err(状态转换错误 {
                当前阶段: self,
                目标,
            })
        }
    }
}
