//! 模块执行体装载 —— 段 `20` 里的**本机机器码** → `dlopen` → 取入口 → 调用。
//!
//! 依据 `项目文档/决策记录/2026-10-12_模块执行体承载与编译裁决.md`：
//! 执行体放段 `20` · 构建侧编译 · 制品带平台身份（**不匹配即拒**）。
//! 入口**形状与符号名**住契约层（`v1_contract::容器::执行体载荷`）—— 构建侧按它导出、
//! 本件按它取，只此一份。
//!
//! # 本件只做「制品 → 能调的入口」
//!
//! 「子进程里怎么跑这条调用」是**跨进程执行域**的事（`进程池.rs` / `工作进程.rs`）。
//! 本件把「制品 → 能调的入口」做成一个可复用的口，执行域按需取用。
//!
//! # 平台身份从哪来
//!
//! [`本机平台身份`] 由 `std::env::consts` 的 `ARCH` / `OS` 拼出目标三元组。
//! **认不出的 OS ⇒ 明确失败**（不猜、不回落）—— 判错的代价是「本该拒的装上了」。

use std::ffi::CString;
use std::path::Path;

use v1_contract::容器::入口符号;
use v1_contract::数据槽;

use crate::动态库口::{RTLD_NOW, dlopen, dlsym, 最近装载错误};

/// 宿主回调 —— 模块执行体向平台要别的能力时走这里（C-ABI，形状由构建侧生成的入口包装冻结）。
pub type 宿主回调 = extern "C" fn(u32, *const 数据槽, usize, *mut 数据槽) -> i32;

/// 模块装载的结构化失败。**不 panic**（跨边界不许抛异常）。
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum 模块装载错误 {
    /// 制品读不到 / 不是能力包件 / 段指纹不符 / 平台身份不符（`装载件缓存` 的原因串）。
    制品不可用(String),
    /// `dlopen` 失败。
    装载失败(String),
    /// 取不到入口符号。
    入口缺失(String),
    /// 调用返回非零 —— 执行体回报的失败码。
    执行失败(i32),
}

/// 已装载的模块执行体 —— 拿着入口函数指针。
///
/// # 库的生命周期
///
/// **不 `dlclose`**：入口要活到调用方用完；卸载走生命周期通知，不是卸载动态库
/// （与 `工作进程.rs` · `扫扩展根.rs` 同一条处置）。
pub struct 已装载执行体 {
    执行: extern "C" fn(宿主回调, *const 数据槽, usize, *mut 数据槽) -> i32,
}

impl 已装载执行体 {
    /// 调一次：入参槽进、返回槽出。返回码 `0` = 成功；非零 = 执行体回报的失败码。
    pub fn 调用(&self, 入参: &[数据槽], 宿主函数: 宿主回调) -> Result<i64, 模块装载错误> {
        let mut 返回槽 = 数据槽::空槽();
        let 返回码 = (self.执行)(宿主函数, 入参.as_ptr(), 入参.len(), &mut 返回槽);
        if 返回码 != 0 {
            return Err(模块装载错误::执行失败(返回码));
        }
        Ok(返回槽.槽值 as i64)
    }
}

/// 装载：模块制品 → 段 `20` → 判平台身份 → 落缓存 → `dlopen` → 取入口。
///
/// 前三步走本 crate 既有的 [`crate::装载件缓存::解包模块执行体到缓存`]（**唯一实现**）。
pub fn 装载模块执行体(
    制品路径: &Path,
    缓存根目录: &Path,
    当前平台身份: &str,
) -> Result<已装载执行体, 模块装载错误> {
    let 落盘路径 = crate::装载件缓存::解包模块执行体到缓存(制品路径, 缓存根目录, 当前平台身份)
        .map_err(模块装载错误::制品不可用)?;
    let 路径串 = CString::new(落盘路径.as_os_str().as_encoded_bytes())
        .map_err(|_| 模块装载错误::装载失败(String::from("库路径含 NUL")))?;
    // SAFETY: 路径串是 NUL 结尾的合法 C 串；句柄只装载不释放（活到进程结束）。
    let 句柄 = unsafe { dlopen(路径串.as_ptr(), RTLD_NOW) };
    if 句柄.is_null() {
        return Err(模块装载错误::装载失败(最近装载错误()));
    }
    let 符号名 = CString::new(入口符号)
        .map_err(|_| 模块装载错误::入口缺失(String::from("符号名含 NUL")))?;
    // SAFETY: 句柄非空（上面已挡）；符号名是合法 C 串。
    let 符号指针 = unsafe { dlsym(句柄, 符号名.as_ptr()) };
    if 符号指针.is_null() {
        return Err(模块装载错误::入口缺失(最近装载错误()));
    }
    // SAFETY: 入口形状由构建侧生成的包装冻结（见 `编译本机源码.rs`）——
    // 四个参数：宿主回调、入参槽指针、入参个数、返回槽指针；返回 `i32`。
    let 执行: extern "C" fn(宿主回调, *const 数据槽, usize, *mut 数据槽) -> i32 =
        unsafe { core::mem::transmute(符号指针) };
    Ok(已装载执行体 { 执行 })
}

/// 本机平台身份 —— 目标三元组，由 `std::env::consts` 的 `ARCH` / `OS` 拼出。
///
/// **认不出的 OS ⇒ 明确失败**（不猜、不回落）：判错的代价是「本该拒的装上了」。
pub fn 本机平台身份() -> Result<String, String> {
    let 架构 = std::env::consts::ARCH;
    let 系统 = std::env::consts::OS;
    let 系统尾段 = match 系统 {
        "macos" => "apple-darwin",
        "linux" => "unknown-linux-gnu",
        "windows" => "pc-windows-msvc",
        _ => return Err(format!("认不出本机 OS：{系统}")),
    };
    Ok(format!("{架构}-{系统尾段}"))
}
