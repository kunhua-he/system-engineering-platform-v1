//! 进程池 —— 跨进程执行域的拉起 · 监督 · 崩溃重拉。
//!
//! 依据：`临时件/W01_裁决_架构升级.md` 六项未定项（进程池粒度 · 反复崩溃）·
//! `临时件/派活_W/W04a_进程池与线协议.md`。
//!
//! # 一个执行域一个工作进程
//!
//! 执行域按 `适配器实例 × 扩展标识 × 制品版本` 划分（[`执行域标识`]）：不混装无关扩展，
//! 扩展未声明可并发时**不擅自并发**。**状态按实例持有**（[`进程池`] 的字段），
//! 不落任何进程级 `static` —— 同进程开两份池就是两个互不干扰的执行域表。
//!
//! # 反复崩溃：退避 · 重启预算 · 熔断
//!
//! 阈值属部署配置（[`进程池配置`]）。每查实一次崩溃，连续计数加一、退避按指数推进
//! （[`进程池::退避时长`]），越过重启预算即熔断一段时间；熔断期内不许再拉起。
//!
//! # 重放：只重放装载初始化
//!
//! 工作进程重拉后只重放**装载初始化**（通知号 2000，见 [`进程池::重放装载初始化`]），
//! **不恢复业务任务**（业务是否重试由调用与能力保障决定，内核不替业务重试）。

use std::num::NonZeroU64;
use std::os::fd::OwnedFd;
use std::os::unix::net::UnixStream;
use std::os::unix::process::CommandExt;
use std::process::{Child, Command, Stdio};
use std::time::{Duration, Instant};

/// 单次装载初始化重放的帧预算（毫秒）。**≤ 五秒硬顶**。
const 重放预算毫秒: u64 = 200;

/// 默认退避基数（毫秒）。
pub const 默认退避基数毫秒: u64 = 50;
/// 默认退避上限（毫秒）。
pub const 默认退避上限毫秒: u64 = 1000;
/// 默认重启预算（连续崩溃到这个数即熔断）。
pub const 默认重启预算: u32 = 5;
/// 默认熔断时长（毫秒）。
pub const 默认熔断时长毫秒: u64 = 1000;

unsafe extern "C" {
    fn kill(进程组号: i32, 信号编号: i32) -> i32;
}

/// 按进程组强杀一个执行域的全部进程（含后代）。
fn 击杀进程组(进程组号: i32) {
    // SAFETY: 负进程组号 = 整组；信号 9 = SIGKILL。组号取自被拉起的子进程，必然存在或被回收。
    unsafe {
        kill(-进程组号, 9);
    }
}

/// 执行域标识 —— `适配器实例 × 扩展标识 × 制品版本`。
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct 执行域标识 {
    pub 适配器实例号: u64,
    pub 扩展标识串: String,
    pub 制品版本: (u32, u32, u32),
}

/// 部署配置：退避与熔断阈值（W01：阈值属部署配置）。
#[derive(Clone, Copy)]
pub struct 进程池配置 {
    pub 退避基数毫秒: u64,
    pub 退避上限毫秒: u64,
    pub 重启预算: u32,
    pub 熔断时长毫秒: u64,
}

impl Default for 进程池配置 {
    fn default() -> Self {
        Self {
            退避基数毫秒: 默认退避基数毫秒,
            退避上限毫秒: 默认退避上限毫秒,
            重启预算: 默认重启预算,
            熔断时长毫秒: 默认熔断时长毫秒,
        }
    }
}

/// 池操作的结构化失败。**不 panic**（跨边界不许抛异常）。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum 进程池错误 {
    域不存在,
    熔断中,
    拉起失败,
}

/// 一次监督的判读。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct 监督判读 {
    pub 仍在运行: bool,
    pub 已重拉: bool,
    pub 连续崩溃次数: u32,
    pub 熔断中: bool,
}

/// 一个执行域的工作进程：子进程 + 与它相连的通道 + 退避账。
struct 工作进程 {
    子进程: Child,
    通道: UnixStream,
    进程组号: i32,
    运行中: bool,
    连续崩溃次数: u32,
    下次允许拉起: Instant,
    熔断截至: Option<Instant>,
    装载已重放: bool,
}

/// 进程池：`执行域标识 → 工作进程` 的实例表。**不落 static**。
pub struct 进程池 {
    配置: 进程池配置,
    域表: Vec<(执行域标识, 工作进程)>,
}

impl 进程池 {
    /// 建一个空池（一份部署配置）。
    pub fn 新建(配置: 进程池配置) -> Self {
        Self { 配置, 域表: Vec::new() }
    }

    /// 已建域数（验证面用）。
    pub fn 已建域数(&self) -> usize {
        self.域表.len()
    }

    /// 这个域建过没有。
    pub fn 含域(&self, 标识: &执行域标识) -> bool {
        self.取域位置(标识).is_some()
    }

    /// 这个域的装载初始化重放过没有。
    pub fn 已重放装载(&self, 标识: &执行域标识) -> bool {
        self.取域位置(标识).map_or(false, |位置| self.域表[位置].1.装载已重放)
    }

    fn 取域位置(&self, 标识: &执行域标识) -> Option<usize> {
        self.域表.iter().position(|格子| &格子.0 == 标识)
    }

    /// 指数退避：`基数 × 2^(次数-1)`，封顶在退避上限。
    fn 退避时长(&self, 连续次数: u32) -> Duration {
        let 位移 = 连续次数.saturating_sub(1).min(20);
        let 毫秒 = self.配置.退避基数毫秒.saturating_mul(1u64 << 位移).min(self.配置.退避上限毫秒);
        Duration::from_millis(毫秒)
    }

    /// 拉起一个工作进程：UnixStream 一对，子端接它自己的 stdin/stdout，宿主端留在池里。
    fn 生成进程(启动程序: &str, 启动参数: &[String]) -> Result<(Child, UnixStream), 进程池错误> {
        let (主机端, 子进程端) = UnixStream::pair().map_err(|_| 进程池错误::拉起失败)?;
        let 子读端 = 子进程端.try_clone().map_err(|_| 进程池错误::拉起失败)?;
        let mut 命令 = Command::new(启动程序);
        命令
            .args(启动参数)
            .stdin(Stdio::from(OwnedFd::from(子进程端)))
            .stdout(Stdio::from(OwnedFd::from(子读端)))
            .stderr(Stdio::null())
            .process_group(0);
        let 子进程 = 命令.spawn().map_err(|_| 进程池错误::拉起失败)?;
        Ok((子进程, 主机端))
    }

    fn 判读格子(工作: &工作进程, 现在时刻: Instant) -> 监督判读 {
        监督判读 {
            仍在运行: 工作.运行中,
            已重拉: false,
            连续崩溃次数: 工作.连续崩溃次数,
            熔断中: 工作.熔断截至.map_or(false, |熔断截至| 现在时刻 < 熔断截至),
        }
    }

    /// 查实一次崩溃：只在「上一次查时还在跑」时计数，**幂等**（连查两次不多记）。
    fn 查实崩溃(&mut self, 位置: usize) {
        if !self.域表[位置].1.运行中 {
            return;
        }
        if let Ok(Some(_)) = self.域表[位置].1.子进程.try_wait() {
            let 现在时刻 = Instant::now();
            let 配置 = self.配置;
            let 工作 = &mut self.域表[位置].1;
            工作.运行中 = false;
            工作.连续崩溃次数 = 工作.连续崩溃次数.saturating_add(1);
            let 位移 = 工作.连续崩溃次数.saturating_sub(1).min(20);
            let 毫秒 = 配置.退避基数毫秒.saturating_mul(1u64 << 位移).min(配置.退避上限毫秒);
            工作.下次允许拉起 = 现在时刻 + Duration::from_millis(毫秒);
            if 工作.连续崩溃次数 >= 配置.重启预算 {
                工作.熔断截至 = Some(现在时刻 + Duration::from_millis(配置.熔断时长毫秒));
            }
            工作.装载已重放 = false;
        }
    }

    /// 保证这个域在跑：没有则拉起；崩了则按退避 / 熔断决定能不能重拉。
    pub fn 保证域在(
        &mut self,
        标识: &执行域标识,
        启动程序: &str,
        启动参数: &[String],
    ) -> Result<(), 进程池错误> {
        if let Some(位置) = self.取域位置(标识) {
            self.查实崩溃(位置);
            let 现在时刻 = Instant::now();
            let 工作 = &self.域表[位置].1;
            if 工作.运行中 {
                return Ok(());
            }
            if 工作.熔断截至.map_or(false, |熔断截至| 现在时刻 < 熔断截至) {
                return Err(进程池错误::熔断中);
            }
            if 现在时刻 < 工作.下次允许拉起 {
                return Err(进程池错误::拉起失败);
            }
        }
        let (子进程, 通道) = Self::生成进程(启动程序, 启动参数)?;
        let 进程组号 = i32::try_from(子进程.id()).map_err(|_| 进程池错误::拉起失败)?;
        match self.取域位置(标识) {
            Some(位置) => {
                let 工作 = &mut self.域表[位置].1;
                工作.子进程 = 子进程;
                工作.通道 = 通道;
                工作.进程组号 = 进程组号;
                工作.运行中 = true;
                工作.装载已重放 = false;
            }
            None => {
                self.域表.push((
                    标识.clone(),
                    工作进程 {
                        子进程,
                        通道,
                        进程组号,
                        运行中: true,
                        连续崩溃次数: 0,
                        下次允许拉起: Instant::now(),
                        熔断截至: None,
                        装载已重放: false,
                    },
                ));
            }
        }
        Ok(())
    }

    /// 监督一次：查实崩溃、给判读。不重拉。
    pub fn 监督一域(&mut self, 标识: &执行域标识) -> Result<监督判读, 进程池错误> {
        let 位置 = self.取域位置(标识).ok_or(进程池错误::域不存在)?;
        self.查实崩溃(位置);
        Ok(Self::判读格子(&self.域表[位置].1, Instant::now()))
    }

    /// 崩溃重拉：查实崩溃后，按退避 / 重启预算 / 熔断决定能否再拉一个。
    pub fn 崩溃重拉(
        &mut self,
        标识: &执行域标识,
        启动程序: &str,
        启动参数: &[String],
    ) -> Result<监督判读, 进程池错误> {
        let 位置 = self.取域位置(标识).ok_or(进程池错误::域不存在)?;
        self.查实崩溃(位置);
        {
            let 现在时刻 = Instant::now();
            let 工作 = &self.域表[位置].1;
            if 工作.运行中 {
                return Ok(Self::判读格子(工作, 现在时刻));
            }
            if 工作.熔断截至.map_or(false, |熔断截至| 现在时刻 < 熔断截至) {
                return Err(进程池错误::熔断中);
            }
            if 现在时刻 < 工作.下次允许拉起 {
                return Err(进程池错误::拉起失败);
            }
        }
        let (子进程, 通道) = Self::生成进程(启动程序, 启动参数)?;
        let 进程组号 = i32::try_from(子进程.id()).map_err(|_| 进程池错误::拉起失败)?;
        let 工作 = &mut self.域表[位置].1;
        工作.子进程 = 子进程;
        工作.通道 = 通道;
        工作.进程组号 = 进程组号;
        工作.运行中 = true;
        let mut 判读 = Self::判读格子(工作, Instant::now());
        判读.已重拉 = true;
        Ok(判读)
    }

    /// 重放装载初始化：向这个域发一条**通知号 2000** 的帧（不恢复业务任务）。
    pub fn 重放装载初始化(
        &mut self,
        标识: &执行域标识,
        请求标识: NonZeroU64,
    ) -> Result<(), 进程池错误> {
        let 位置 = self.取域位置(标识).ok_or(进程池错误::域不存在)?;
        let 截止 = Instant::now() + Duration::from_millis(重放预算毫秒);
        let mut 预算 =
            crate::进程帧::调用帧预算::创建(截止).map_err(|_| 进程池错误::拉起失败)?;
        let 通知帧 = crate::进程帧::消息帧 {
            消息类型: crate::进程帧::消息类别::通知,
            请求标识,
            载荷: v1_contract::声明数据::通知号_2000.to_le_bytes().to_vec(),
        };
        let 工作 = &mut self.域表[位置].1;
        crate::进程帧::发送帧(&mut 工作.通道, &通知帧, &mut 预算)
            .map_err(|_| 进程池错误::拉起失败)?;
        工作.装载已重放 = true;
        Ok(())
    }

    /// 击杀一个域（整组），并回收它的进程。
    pub fn 击杀一域(&mut self, 标识: &执行域标识) -> Result<(), 进程池错误> {
        let 位置 = self.取域位置(标识).ok_or(进程池错误::域不存在)?;
        let 工作 = &mut self.域表[位置].1;
        击杀进程组(工作.进程组号);
        let _ = 工作.子进程.kill();
        let _ = 工作.子进程.wait();
        工作.运行中 = false;
        Ok(())
    }
}

impl Drop for 进程池 {
    /// 池析构即回收全部工作进程组（不留孤儿）。
    fn drop(&mut self) {
        for (_标识, 工作) in self.域表.iter_mut() {
            击杀进程组(工作.进程组号);
            let _ = 工作.子进程.kill();
            let _ = 工作.子进程.wait();
        }
    }
}
