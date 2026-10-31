use crate::ffi::{数据库连接, 数据库错误};
use std::fmt;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct 版本号 {
    pub 主版本: u16,
    pub 次版本: u16,
}

impl 版本号 {
    pub const fn 构造(主版本: u16, 次版本: u16) -> Self {
        Self {
            主版本, 次版本
        }
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Hash)]
pub struct 代际令牌(u128);

impl 代际令牌 {
    fn 生成(序号: u64) -> Self {
        let 当前纳秒 = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos();
        let 进程号 = u128::from(std::process::id());
        Self(当前纳秒 ^ (进程号 << 64) ^ u128::from(序号))
    }

    pub fn 十六进制(&self) -> String {
        format!("{:032x}", self.0)
    }

    pub fn 从十六进制(文本: &str) -> Result<Self, 契约错误> {
        if 文本.len() != 32 {
            return Err(契约错误::令牌格式不符);
        }
        u128::from_str_radix(文本, 16)
            .map(Self)
            .map_err(|_| 契约错误::令牌格式不符)
    }
}

impl fmt::Debug for 代际令牌 {
    fn fmt(&self, 格式: &mut fmt::Formatter<'_>) -> fmt::Result {
        格式
            .debug_tuple("代际令牌")
            .field(&self.十六进制())
            .finish()
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct 装载单元上下文 {
    pub 装载单元标识: String,
    pub 实现版本: 版本号,
    pub 代际序号: u64,
    pub 代际令牌: 代际令牌,
    pub 宿主进程号: u32,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum 契约错误 {
    令牌格式不符,
    代际不符,
    装载单元已退出,
    已取消,
    已超时,
    数据库(数据库错误),
}

impl fmt::Display for 契约错误 {
    fn fmt(&self, 格式: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::令牌格式不符 => 格式.write_str("代际令牌格式不符"),
            Self::代际不符 => 格式.write_str("执行租约代际令牌不再是当前装载代"),
            Self::装载单元已退出 => 格式.write_str("装载单元已经退出"),
            Self::已取消 => 格式.write_str("执行已取消"),
            Self::已超时 => 格式.write_str("执行已超时"),
            Self::数据库(错误) => 错误.fmt(格式),
        }
    }
}

impl std::error::Error for 契约错误 {}

impl From<数据库错误> for 契约错误 {
    fn from(错误: 数据库错误) -> Self {
        Self::数据库(错误)
    }
}

struct 装载单元状态 {
    当前上下文: Option<Arc<装载单元上下文>>,
    序号: AtomicU64,
}

pub struct 装载单元 {
    状态: Mutex<装载单元状态>,
}

impl 装载单元 {
    pub fn 装载(装载单元标识: impl Into<String>, 实现版本: 版本号) -> Self {
        let 上下文 = Arc::new(装载单元上下文 {
            装载单元标识: 装载单元标识.into(),
            实现版本,
            代际序号: 1,
            代际令牌: 代际令牌::生成(1),
            宿主进程号: std::process::id(),
        });
        Self {
            状态: Mutex::new(装载单元状态 {
                当前上下文: Some(上下文),
                序号: AtomicU64::new(1),
            }),
        }
    }

    pub fn 当前上下文(&self) -> Result<Arc<装载单元上下文>, 契约错误> {
        let 状态 = self.状态.lock().unwrap_or_else(|中毒| 中毒.into_inner());
        状态.当前上下文.clone().ok_or(契约错误::装载单元已退出)
    }

    pub fn 重装(
        &self, 实现版本: 版本号
    ) -> Result<Arc<装载单元上下文>, 契约错误> {
        let mut 状态 = self.状态.lock().unwrap_or_else(|中毒| 中毒.into_inner());
        let 代际序号 = 状态.序号.fetch_add(1, Ordering::AcqRel) + 1;
        let 旧上下文 = 状态.当前上下文.as_ref().ok_or(契约错误::装载单元已退出)?;
        let 新上下文 = Arc::new(装载单元上下文 {
            装载单元标识: 旧上下文.装载单元标识.clone(),
            实现版本,
            代际序号,
            代际令牌: 代际令牌::生成(代际序号),
            宿主进程号: std::process::id(),
        });
        状态.当前上下文 = Some(新上下文.clone());
        Ok(新上下文)
    }

    pub fn 退出(&self) {
        let mut 状态 = self.状态.lock().unwrap_or_else(|中毒| 中毒.into_inner());
        状态.当前上下文 = None;
    }

    pub fn 申请执行租约(&self, 连接信息: &str) -> Result<执行租约, 契约错误> {
        let 上下文 = self.当前上下文()?;
        let 连接 = 数据库连接::建立(连接信息)?;
        Ok(执行租约 {
            上下文,
            连接: Some(连接),
            释放状态: 释放状态::未释放,
        })
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum 释放状态 {
    未释放,
    已释放,
}

pub struct 执行租约 {
    上下文: Arc<装载单元上下文>,
    连接: Option<数据库连接>,
    释放状态: 释放状态,
}

impl 执行租约 {
    pub fn 上下文(&self) -> &装载单元上下文 {
        &self.上下文
    }

    pub fn 代际令牌(&self) -> 代际令牌 {
        self.上下文.代际令牌
    }

    pub fn 后端进程号(&self) -> Result<i32, 契约错误> {
        self.连接
            .as_ref()
            .map(数据库连接::后端进程号)
            .ok_or(契约错误::装载单元已退出)
    }

    pub fn 验证当前代际(&self, 装载单元: &装载单元) -> Result<(), 契约错误> {
        let 当前上下文 = 装载单元.当前上下文()?;
        if 当前上下文.代际令牌 == self.上下文.代际令牌 {
            Ok(())
        } else {
            Err(契约错误::代际不符)
        }
    }

    pub fn 执行受控<F, 返回值>(
        &mut self,
        装载单元: &装载单元,
        取消标志: &std::sync::atomic::AtomicBool,
        截止时刻: std::time::Instant,
        操作: F,
    ) -> Result<返回值, 契约错误>
    where
        F: FnOnce(&mut 数据库连接) -> Result<返回值, 契约错误>,
    {
        self.验证当前代际(装载单元)?;
        if 取消标志.load(Ordering::Acquire) {
            return Err(契约错误::已取消);
        }
        if std::time::Instant::now() >= 截止时刻 {
            return Err(契约错误::已超时);
        }
        let 连接 = self.连接.as_mut().ok_or(契约错误::装载单元已退出)?;
        let 返回值 = 操作(连接)?;
        if 取消标志.load(Ordering::Acquire) {
            return Err(契约错误::已取消);
        }
        if std::time::Instant::now() >= 截止时刻 {
            return Err(契约错误::已超时);
        }
        Ok(返回值)
    }

    pub fn 释放(&mut self) {
        self.连接.take();
        self.释放状态 = 释放状态::已释放;
    }

    pub fn 是否已释放(&self) -> bool {
        self.释放状态 == 释放状态::已释放
    }
}

impl Drop for 执行租约 {
    fn drop(&mut self) {
        self.连接.take();
        self.释放状态 = 释放状态::已释放;
    }
}
