//! 实例状态 —— 状态显式持有为句柄，**不落进程级全局**。
//!
//! 两个实例互不污染。状态是句柄：调用方持有，调用方释放。

/// 实例句柄。不透明，跨边界只传这个数。
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct 实例句柄(pub u64);

/// 实例错误。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum 实例错误 {
    /// 句柄不存在或已释放。
    句柄失效,
    /// 句柄不属于本实例。
    句柄越界,
}

/// 实例表：显式持有，无全局。
pub struct 实例表 {
    _私有: (),
}

impl 实例表 {
    pub fn 新建() -> Self {
        Self { _私有: () }
    }

    /// 开一个实例，返回句柄。
    pub fn 开启(&mut self) -> 实例句柄 {
        todo!()
    }

    /// 关一个实例。
    pub fn 关闭(&mut self, 句柄: 实例句柄) -> Result<(), 实例错误> {
        let _ = 句柄;
        todo!()
    }

    /// 校验句柄。**未命中返回错误，不许当成功。**
    pub fn 校验(&self, 句柄: 实例句柄) -> Result<(), 实例错误> {
        let _ = 句柄;
        todo!()
    }
}
