//! 编译本机源码 —— 把 `本机源码产物.执行源码` 编成**本机机器码**（段 20 的载荷）。
//!
//! 依据 `项目文档/决策记录/2026-10-12_模块执行体承载与编译裁决.md`：
//! 执行体放段 20 · **构建侧编译**（运行侧不现编）· 制品带平台身份。
//!
//! # 形态：`cdylib` + 固定 C-ABI 入口
//!
//! 本件裁（原裁决 §六 遗留「平台身份字段形状」之外的形态项，收口方自裁并记入该件 §七）：
//!
//! - **产物形态**：`--crate-type cdylib`。理由：运行侧走已裁的「子进程 + IPC」路，
//!   宿主进程用一次 `dlopen` 取入口，不必每个模块各带一份 `main`（避免 IPC 代码在
//!   每个制品里重复实现 —— 那是第二实现）。
//! - **入口符号**：`v1_模块执行`。宿主回调**由调用方以 C-ABI 函数指针传入**，
//!   故制品内**不含任何 IPC 代码** —— IPC 只在平台侧那一份宿主进程里。
//! - **段 20 载荷**：`[平台身份长度 u16 大端][平台身份 UTF-8][执行体机器码]`。
//!   理由：原裁决要求「随执行体段带平台身份」，且 §六 建议「直接用平台身份字符串」。
//!
//! # 为什么不在这里判平台身份
//!
//! 本件只管编；**判**在装载侧（裁决 §三：不匹配即拒，不静默降级）。本件把平台身份
//! 原样写进载荷，判据面按载荷前缀比。

use super::本机源码产物;
use std::path::Path;
use std::process::Command;

/// 入口符号名（C-ABI）。装载侧按此名取入口。
///
/// **为什么用 ASCII**：`#[no_mangle]` 要求标识符是 ASCII（`error[E0754]`）——
/// 这是工具链硬约束，不是命名偏好。C-ABI 符号名是**跨语言边界的标识符**，
/// 同 `ID`/`PPT` 一类缩写，保留原文。
pub const 入口符号: &str = "v1_module_exec";

/// 生成 C-ABI 入口包装 —— 把 `模块执行`（Rust 闭包签名）接到宿主传进来的函数指针上。
///
/// 包装是**平台级生成物**（不是每个模块各写一份），故各模块制品形状一致。
fn 生成入口包装(编号: u32) -> String {
    format!(
        r#"
#[unsafe(no_mangle)]
pub extern "C" fn {入口符号}(
    宿主: extern "C" fn(u32, *const 数据槽, usize, *mut 数据槽) -> i32,
    入参: *const 数据槽,
    入参个数: usize,
    返回槽: *mut 数据槽,
) -> i32 {{
    let 入参切片: &[数据槽] = unsafe {{ std::slice::from_raw_parts(入参, 入参个数) }};
    let 返回槽引用: &mut 数据槽 = unsafe {{ &mut *返回槽 }};
    let mut 宿主调用 = |能力号: u32, 参数: &[数据槽], 返回: &mut 数据槽| -> Result<(), u32> {{
        let 码 = 宿主(能力号, 参数.as_ptr(), 参数.len(), 返回);
        if 码 == 0 {{ Ok(()) }} else {{ Err(码 as u32) }}
    }};
    let _ = {编号};
    match 模块执行(&mut 宿主调用, 入参切片) {{
        Ok(值) => {{
            *返回槽引用 = 数据槽::内联槽(1u32.into(), 值 as u64, 8);
            0
        }}
        Err(_) => 1,
    }}
}}
"#,
        入口符号 = 入口符号,
        编号 = 编号
    )
}

/// 编译：`执行源码` + 入口包装 → `cdylib`。`输出路径` 是编出来的机器码文件。
///
/// 工具链命令 / 契约产物（`libv1_contract-*.rlib`）/ 依赖目录由**调用方给**——
/// 本件不猜环境（换机器、换 target 目录都只是换参数）。
pub fn 编译本机源码(
    产物: &本机源码产物,
    编号: u32,
    工具链命令: &Path,
    契约产物: &Path,
    依赖目录: &Path,
    输出路径: &Path,
) -> Result<(), String> {
    let 源码路径 = 输出路径.with_extension("rs");
    let 全源 = format!("{}\n{}", 产物.执行源码, 生成入口包装(编号));
    std::fs::write(&源码路径, 全源).map_err(|错| format!("写源码失败：{错}"))?;
    let 编译输出 = Command::new(工具链命令)
        .arg("--edition=2024")
        .arg("--crate-type").arg("cdylib")
        .arg("--crate-name").arg("v1_模块执行体")
        .arg("--target").arg(&产物.平台身份)
        .arg("--extern").arg(format!("v1_contract={}", 契约产物.display()))
        .arg("-L").arg(format!("dependency={}", 依赖目录.display()))
        .arg(&源码路径)
        .arg("-o").arg(输出路径)
        .output()
        .map_err(|错| format!("拉不起工具链：{错}"))?;
    if !编译输出.status.success() {
        return Err(format!("编译失败：{}", String::from_utf8_lossy(&编译输出.stderr)));
    }
    Ok(())
}

/// 把平台身份与执行体打成段 20 的载荷：`[长度 u16 大端][平台身份][执行体]`。
pub fn 打包执行体载荷(平台身份: &str, 执行体: &[u8]) -> Vec<u8> {
    let 身份字节 = 平台身份.as_bytes();
    let mut 载荷 = Vec::with_capacity(2 + 身份字节.len() + 执行体.len());
    载荷.extend_from_slice(&(身份字节.len() as u16).to_be_bytes());
    载荷.extend_from_slice(身份字节);
    载荷.extend_from_slice(执行体);
    载荷
}

/// 反向：从段 20 载荷里取回 `(平台身份, 执行体)`。长度越界给 `None`（不 panic）。
pub fn 拆执行体载荷(载荷: &[u8]) -> Option<(String, Vec<u8>)> {
    if 载荷.len() < 2 {
        return None;
    }
    let 长度 = u16::from_be_bytes([载荷[0], 载荷[1]]) as usize;
    let 身份段 = 载荷.get(2..2 + 长度)?;
    let 执行体 = 载荷.get(2 + 长度..)?.to_vec();
    Some((String::from_utf8(身份段.to_vec()).ok()?, 执行体))
}
