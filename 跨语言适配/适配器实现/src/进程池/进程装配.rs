//! 进程池 · 进程装配 —— 拉起 / 换进程 / 查实崩溃 / 判读 这几个自由函数。
//!
//! 从 `进程池.rs` 拆出（单源 ≤ 400 行 · `开发规范.md` 第六节）。拆法按**关注点**：
//! 父件管**表与账**（建格 · 取格 · 退避账 · 重拉），本件管**一个工作进程的装配与判读**
//! （怎么拉起 · 怎么换进去 · 怎么查实崩溃 · 怎么给判读）。
//!
//! 子件能读父件的私有项（Rust 隐私：子模块看得见祖先的私项）。

use std::os::fd::OwnedFd;
use std::os::unix::net::UnixStream;
use std::os::unix::process::CommandExt;
use std::process::{Child, Command, Stdio};
use std::time::{Duration, Instant};

use super::{子进程前提, 工作进程, 监督判读, 进程池错误, 进程池配置};

/// 一份部署参数（启动程序 + 启动参数）的**指纹**：同域重复登记时据此判「参数变没变」。
///
/// 为什么用指纹而不是直接比 `域部署`：域格只存一个可比的标量，且指纹不必跨进程稳定
/// （只在本实例的域格里比）。FNV-1a 64 位：零依赖、确定、够用（不做安全哈希）。
pub fn 部署指纹(启动程序: &str, 启动参数: &[String]) -> u64 {
    const 质数: u64 = 0x0000_0100_0000_01b3;
    // FNV-1a 64 位偏移基准（内联，不另起名）。
    let mut 指纹 = 0xcbf2_9ce4_8422_2325u64;
    for 字节 in 启动程序.as_bytes().iter().copied().chain(core::iter::once(0u8)) {
        指纹 ^= u64::from(字节);
        指纹 = 指纹.wrapping_mul(质数);
    }
    for 参数项 in 启动参数 {
        for 字节 in 参数项.as_bytes().iter().copied().chain(core::iter::once(0u8)) {
            指纹 ^= u64::from(字节);
            指纹 = 指纹.wrapping_mul(质数);
        }
    }
    指纹
}

/// 拉起一个工作进程：UnixStream 一对，子端接它自身的 stdin/stdout，宿主端留在池里。
///
/// **默认前提**（只授权派生进程 + 空环境）—— 与 [`生成进程按前提`] 同一份实现，
/// 不给调用方留第二套口径。要透传变量 / 投秘密走那个口。
pub(crate) fn 生成进程(
    启动程序: &str,
    启动参数: &[String],
) -> Result<(Child, UnixStream), 进程池错误> {
    生成进程按前提(启动程序, 启动参数, &子进程前提::默认前提())
}

/// 拉起一个工作进程（**按前提**）：先判授权，再按名单装环境，最后才 `spawn`。
///
/// # 顺序不是随手定的
///
/// ① [`子进程前提::校验派生`] —— 没授权派生进程就**当场拒、一个进程都不拉**
/// （「不拉起进程」是本条的验收口径）；② [`子进程前提::把环境装进命令`] ——
/// 要全放行 / 带秘密却没授权同样当场拒，且**不写半个变量**；③ 前两步都过了才 `spawn`。
///
/// **本函数不 `env_clear` 的那条旧行为已消失**：装环境那一步无条件先 `env_clear`
/// ⇒ 子进程拿到的是**前提算出来的那份环境**，不是父进程的全环境。
pub(crate) fn 生成进程按前提(
    启动程序: &str,
    启动参数: &[String],
    前提: &子进程前提,
) -> Result<(Child, UnixStream), 进程池错误> {
    前提.校验派生()?;
    let (主机端, 子进程端) = UnixStream::pair().map_err(|_| 进程池错误::拉起失败)?;
    let 子读端 = 子进程端.try_clone().map_err(|_| 进程池错误::拉起失败)?;
    let mut 命令 = Command::new(启动程序);
    命令
        .args(启动参数)
        .stdin(Stdio::from(OwnedFd::from(子进程端)))
        .stdout(Stdio::from(OwnedFd::from(子读端)))
        .stderr(Stdio::null())
        .process_group(0);
    // 授权与装环境都在 `spawn` 之前 —— 判定不过就一个进程都不起。
    前提.把环境装进命令(&mut 命令)?;
    let 子进程 = 命令.spawn().map_err(|_| 进程池错误::拉起失败)?;
    Ok((子进程, 主机端))
}

/// 往一个已有格子里装一个新拉起的进程（拉起 / 重拉共用）。
pub(crate) fn 装新进程(
    工作: &mut 工作进程,
    子进程: Child,
    通信通道: UnixStream,
    实例代次: u64,
    指纹: u64,
    前提指纹: u64,
) -> Result<(), 进程池错误> {
    let 进程组号 = i32::try_from(子进程.id()).map_err(|_| 进程池错误::拉起失败)?;
    工作.子进程 = 子进程;
    工作.流通道 = 通信通道;
    工作.进程组号 = 进程组号;
    工作.实例代次 = 实例代次;
    工作.部署指纹 = 指纹;
    工作.前提指纹 = 前提指纹;
    工作.运行中 = true;
    工作.装载已重放 = false;
    Ok(())
}

/// 查实一次崩溃：只在「上一次查时还在跑」时计数，**幂等**（连查两次不多记）。
pub(crate) fn 查实崩溃(配置: 进程池配置, 工作: &mut 工作进程) {
    if !工作.运行中 {
        return;
    }
    if let Ok(Some(_)) = 工作.子进程.try_wait() {
        let 现在时刻 = Instant::now();
        工作.运行中 = false;
        工作.连续崩溃次数 = 工作.连续崩溃次数.saturating_add(1);
        let 位移 = 工作.连续崩溃次数.saturating_sub(1).min(20);
        let 退避毫秒 = 配置.退避基数毫秒.saturating_mul(1u64 << 位移).min(配置.退避上限毫秒);
        工作.下次允许拉起 = 现在时刻 + Duration::from_millis(退避毫秒);
        if 工作.连续崩溃次数 >= 配置.重启预算 {
            工作.熔断截至 = Some(现在时刻 + Duration::from_millis(配置.熔断时长毫秒));
        }
        工作.装载已重放 = false;
    }
}

/// 给一次判读（不改状态）。
pub(crate) fn 判读格子(工作: &工作进程, 现在时刻: Instant) -> 监督判读 {
    监督判读 {
        仍在运行: 工作.运行中,
        已重拉: false,
        连续崩溃次数: 工作.连续崩溃次数,
        熔断中: 工作.熔断截至.is_some_and(|熔断截至| 现在时刻 < 熔断截至),
    }
}
