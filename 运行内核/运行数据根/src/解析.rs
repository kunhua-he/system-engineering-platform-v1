//! 解析 —— **唯一解析器**：把「外部事实」定成运行数据根。
//!
//! # 为什么外部事实要**注入**而不是从全局读
//!
//! 解析的每条分支（覆盖 · macOS · Linux+XDG · Linux 无 XDG · Windows · 全缺）都必须**判得了**。
//! 从 `std::env` 直接读的话，测试只能靠改进程环境变量，分支之间会互相污染
//! （本项目已有的教训：两个测试共用一个进程级 `static` ⇒ 并行跑互相污染）。
//! ⇒ 解析器**只吃参数**；读真实环境是 [`解析当前`] 那一层薄壳的事。

use std::path::PathBuf;

/// 解析要的全部外部事实。**注入**，不从全局读。
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct 环境<'a> {
    /// 覆盖：环境变量 `V1_RUN_DATA_ROOT`。**部署事实**（可配、可换、可清空）。
    ///
    /// 为什么变量名是 ASCII：`macOS` 的 `/bin/sh` 是 bash 3.2，**不认中文变量名**
    /// （`.git/hooks/pre-commit` 顶部同一条理由）—— 环境变量名一律 ASCII，值可以是任何路径。
    pub 覆盖: Option<&'a str>,
    /// 家目录（`HOME`；Windows 上也有）。
    pub 家目录: Option<&'a str>,
    /// `XDG_DATA_HOME`（Linux 的 XDG 基线；**未设时按 XDG 规范退回 `~/.local/share`**）。
    pub xdg数据目录: Option<&'a str>,
    /// `APPDATA`（Windows 的应用数据目录；**不是**家目录）。
    pub 应用数据目录: Option<&'a str>,
}

/// 目标平台。决定默认位置走哪条规则。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum 平台 {
    MacOS,
    Linux,
    Windows,
}

/// 解析失败。**结构化，不编一个路径**（编路径 = 把「没有位置」藏起来）。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum 解析失败 {
    /// 既没有覆盖，也推不出默认位置（家目录 / XDG / APPDATA 全缺）。
    无位置,
}

/// 平台数据目录下那一层的名字。**唯一来源** —— 别处要这个名字就引用它，不许再写一份。
pub const 默认目录名: &str = "系统工程平台V1";

/// 覆盖用的环境变量名。**ASCII**（见 [`环境::覆盖`] 的理由）。
pub const 覆盖变量名: &str = "V1_RUN_DATA_ROOT";

/// **唯一解析器**：`覆盖 > 平台默认`。
///
/// - 覆盖非空 ⇒ 原样用它（**不再拼 [`默认目录名`]** —— 覆盖就是完整根，部署方说了算）；
/// - 覆盖为空 / 缺 ⇒ 平台数据目录 + [`默认目录名`]；
/// - 两条都拿不到 ⇒ [`解析失败::无位置`]。
pub fn 解析(环境: &环境, 平台: 平台) -> Result<PathBuf, 解析失败> {
    if let Some(覆盖) = 环境.覆盖
        && !覆盖.is_empty()
    {
        return Ok(PathBuf::from(覆盖));
    }
    let 基准目录 = 默认基(环境, 平台).ok_or(解析失败::无位置)?;
    Ok(基准目录.join(默认目录名))
}

/// 平台数据目录（**不含** [`默认目录名`] 那一层）。
///
/// 三条规则互不重叠，且**没有一条**落在当前目录或它的祖先 —— 这正是
/// 「运行数据不在源码树内」这条纪律在解析层的落点。
fn 默认基(环境: &环境, 平台: 平台) -> Option<PathBuf> {
    match 平台 {
        // macOS：`~/Library/Application Support`
        平台::MacOS => 环境
            .家目录
            .filter(|家| !家.is_empty())
            .map(|家| PathBuf::from(家).join("Library").join("Application Support")),
        // Linux：`$XDG_DATA_HOME`，未设则按 XDG 规范退回 `~/.local/share`
        平台::Linux => {
            if let Some(数据) = 环境.xdg数据目录.filter(|目录| !目录.is_empty()) {
                return Some(PathBuf::from(数据));
            }
            环境
                .家目录
                .filter(|家| !家.is_empty())
                .map(|家| PathBuf::from(家).join(".local").join("share"))
        }
        // Windows：`%APPDATA%`（家目录不是它 —— 两者别混）
        平台::Windows => 环境
            .应用数据目录
            .filter(|目录| !目录.is_empty())
            .map(PathBuf::from),
    }
}

/// 从**真实环境**解析：读四个环境变量 + 判目标平台。**只做这两件事，零判断**。
pub fn 解析当前() -> Result<PathBuf, 解析失败> {
    let 覆盖 = std::env::var(覆盖变量名).ok();
    let 家目录 = std::env::var("HOME").ok();
    let xdg = std::env::var("XDG_DATA_HOME").ok();
    let 应用 = std::env::var("APPDATA").ok();
    let 环境 = 环境 {
        覆盖: 覆盖.as_deref(),
        家目录: 家目录.as_deref(),
        xdg数据目录: xdg.as_deref(),
        应用数据目录: 应用.as_deref(),
    };
    解析(&环境, 当前平台())
}

/// 编译期定死的目标平台。**不查环境、不猜** —— 平台由构建目标决定。
pub const fn 当前平台() -> 平台 {
    if cfg!(target_os = "macos") {
        平台::MacOS
    } else if cfg!(target_os = "windows") {
        平台::Windows
    } else {
        平台::Linux
    }
}
