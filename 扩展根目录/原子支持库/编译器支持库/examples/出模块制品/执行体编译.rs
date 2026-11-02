//! 执行体段（段 20）：产物组 → 构建侧 `rustc` 编译 → `[平台身份长度 u16 大端][平台身份][机器码]`；
//! 暂存目录只从环境变量来（未设即明确失败），本机工具链取 `RUSTC`。

use std::fs;
use std::path::{Path, PathBuf};

use v1_compiler::执行函数面::本机生成;

use super::契约产物;

/// 程序文本 → 段 20 载荷（`平台身份` + 本机机器码）。
///
/// 依据 `项目文档/决策记录/2026-10-12_模块执行体承载与编译裁决.md`：
/// 执行体放段 20 · **构建侧编译**（运行侧不现编）· 制品带平台身份。
pub(super) fn 出执行体(产物组: &[(u32, 本机生成::本机源码产物)], 工具链命令: &Path, 平台身份: &str) -> Result<Vec<u8>, String> {
    let (契约产物, 依赖目录) = 找契约产物()?;
    let 暂存根目录 = 取暂存目录()?;
    let 调用暂存目录 = 暂存根目录.join(format!(
        "模块执行体-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map_err(|错误| format!("取暂存时间失败：{错误}"))?
            .as_nanos()
    ));
    fs::create_dir(&调用暂存目录).map_err(|错误| format!("建独立暂存目录失败：{错误}"))?;
    let 输出路径 = 调用暂存目录.join("模块执行体.dylib");
    let 编译结果 = 本机生成::编译模块源码组(产物组, 工具链命令, &契约产物, &依赖目录, &输出路径);
    if let Err(错误) = 编译结果 {
        let _清理结果 = fs::remove_dir_all(&调用暂存目录);
        return Err(错误);
    }
    let 执行体 = match fs::read(&输出路径) {
        Ok(执行体) => 执行体,
        Err(错误) => {
            let _清理结果 = fs::remove_dir_all(&调用暂存目录);
            return Err(format!("读不出执行体：{错误}"));
        }
    };
    let 清理结果 = fs::remove_dir_all(&调用暂存目录);
    if let Err(错误) = 清理结果 { return Err(format!("执行体已读出，但暂存目录清理失败：{错误}")); }
    if 执行体.is_empty() { return Err("编出来的执行体是空的".to_owned()); }
    Ok(v1_contract::容器::打包执行体载荷(平台身份, &执行体))
}

/// 编执行体用的暂存目录：**只从环境变量来，没有默认值**。
///
/// 同 `src/测试夹具.rs::取语料根目录` 的理由：本 crate 是**扩展**，按纪律只依赖底座公布的契约
/// ⇒ 取不到 `运行内核/运行数据根` 的解析口；而直接读 `V1_RUN_DATA_ROOT` 再自拼路径，
/// 又是判据 ㉕ 当场报红的形状（自拼运行数据路径）。⇒ 暂存目录由**调用方**显式给，
/// 未设即**明确失败**（不静默回落到某个写死的路径 —— 那是「无执行假绿」的老病）。
///
/// **变量名用 ASCII**：同 `测试夹具.rs` 的 `V1_CORPUS_ROOT` —— 环境变量名要能在 shell 里
/// 直接赋值；zsh/bash 都不吃中文变量名（`V1_模块编译暂存目录=x cmd` 会被当成命令执行）。
const 暂存目录变量名: &str = "V1_MODULE_SCRATCH_DIR";

pub(super) fn 取暂存目录() -> Result<PathBuf, String> {
    let 取值 = std::env::var(暂存目录变量名).unwrap_or_default();
    if 取值.trim().is_empty() {
        return Err(format!(
            "未设 {暂存目录变量名}（编执行体要一个暂存目录，本件不自造路径）\
             —— 例：{暂存目录变量名}=\"$HOME/Library/Application Support/系统工程平台V1/临时件/模块编译\""
        ));
    }
    Ok(PathBuf::from(取值))
}

/// 本机工具链：`RUSTC` 环境变量（缺省 `rustc`）→ `(工具链身份, 平台身份, 命令路径)`。
pub(super) fn 取工具链() -> (String, String, PathBuf) {
    let 工具链命令 = PathBuf::from(std::env::var_os("RUSTC").unwrap_or_else(|| "rustc".into()));
    let 输出 = std::process::Command::new(&工具链命令).arg("-vV").output();
    let Ok(输出) = 输出 else { return (String::new(), String::new(), 工具链命令) };
    let 工具链身份 = String::from_utf8_lossy(&输出.stdout).to_string();
    let 平台身份 = 工具链身份
        .lines()
        .find_map(|记录行| 记录行.strip_prefix("host: "))
        .unwrap_or_default()
        .to_owned();
    (工具链身份, 平台身份, 工具链命令)
}

/// 由当前构建图定位契约产物，不扫描缓存目录猜测。
pub(super) fn 找契约产物() -> Result<(PathBuf, PathBuf), String> {
    契约产物::找契约产物()
}
