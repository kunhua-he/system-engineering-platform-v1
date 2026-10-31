//! 执行计划：把校验通过的技能包整理成「可直接提交给 2601 的形态」。
//!
//! 本库不起进程。计划包含：脚本绝对路径、解释器、参数文件、超时秒、工作目录，
//! 以及拼好的 `命令`（2601 的 `命令` 字段是交给 `/bin/sh -c` 的字符串，所以要按 shell 规则转义）。
//! 参数走**文件**而不是 stdin：2601 的子进程 stdin 是 null（实测），
//! 技能脚本按 `sys.argv[1]` 读参数文件即与之对齐。

use std::path::Path;

use crate::编号与码面::错误码;

/// 参数 JSON 上限。
const 参数上限: usize = 1024 * 1024;

/// 单引号包裹，内部单引号按 shell 规矩收尾再拼接。
fn 引号(文本: &str) -> String {
    format!("'{}'", 文本.replace('\'', "'\\''"))
}

/// 解释器：调用方给的绝对路径优先，空串落系统 python3。
fn 定解释器(候选项: &str) -> Result<String, u32> {
    let 文本 = 候选项.trim();
    if 文本.is_empty() {
        return Ok("/usr/bin/python3".to_string());
    }
    if !文本.starts_with('/') || 文本.contains('\0') {
        return Err(错误码::参数不合法);
    }
    if !Path::new(文本).is_file() {
        return Err(错误码::参数不合法);
    }
    Ok(文本.to_string())
}

/// 把参数写成临时文件，返回绝对路径；超过 1MiB 直拒。
pub(crate) fn 写参数文件(负载: &serde_json::Value) -> Result<String, u32> {
    let 文本 = serde_json::to_string(负载).map_err(|_| 错误码::处理失败)?;
    if 文本.len() > 参数上限 {
        return Err(错误码::资源超限);
    }
    let 纳秒 = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|时长| 时长.as_nanos())
        .unwrap_or(0);
    let 路径 = format!("/private/tmp/v1技能参数-{}-{}.json", std::process::id(), 纳秒);
    std::fs::write(&路径, 文本.as_bytes()).map_err(|_| 错误码::处理失败)?;
    Ok(路径)
}

/// 组装计划。`脚本` 与 `技能目录` 必须是已校验过的真实路径。
pub(crate) fn 组装(
    脚本: &Path,
    技能目录: &Path,
    解释器候选: &str,
    参数文件: &str,
    超时秒: f64,
) -> Result<serde_json::Value, u32> {
    if !(0.2..=600.0).contains(&超时秒) {
        return Err(错误码::参数不合法);
    }
    let 解释器 = 定解释器(解释器候选)?;
    let 脚本文本 = 脚本.to_str().ok_or(错误码::参数不合法)?.to_string();
    let 目录文本 = 技能目录.to_str().ok_or(错误码::参数不合法)?.to_string();
    let 命令 = format!("{} {} {}", 引号(&解释器), 引号(&脚本文本), 引号(参数文件));
    Ok(serde_json::json!({
        "脚本路径": 脚本文本,
        "解释器": 解释器,
        "参数文件": 参数文件,
        "技能目录": 目录文本,
        "工作目录": 目录文本,
        "超时秒": 超时秒,
        "命令": 命令,
        "提交参数": {
            "命令": 命令,
            "工作目录": 目录文本,
            "超时秒数": 超时秒,
            "沙箱": "沙箱",
        },
    }))
}
