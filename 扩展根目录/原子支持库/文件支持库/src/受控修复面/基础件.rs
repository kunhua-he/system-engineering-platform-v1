//! 基础件 —— JSON 文本转义与对象拼装 · git 命令封装 · 工作区标识与归属验证。
//!
//! 三个受控作业（替换 · 验证 · 回滚）与 `受控提交面` 共用这一份：只此一套转义、
//! 只此一条 git 调用腿、只此一处「工作区是不是我建的」判定。

use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

use crate::错误码;

pub(crate) fn 转义JSON(文本: &str) -> String {
    文本
        .chars()
        .flat_map(|字| match 字 {
            '"' => "\\\"".chars().collect::<Vec<_>>(),
            '\\' => "\\\\".chars().collect(),
            '\n' => "\\n".chars().collect(),
            '\r' => "\\r".chars().collect(),
            '\t' => "\\t".chars().collect(),
            c if c.is_control() => format!("\\u{:04x}", c as u32).chars().collect(),
            c => vec![c],
        })
        .collect()
}
pub(super) fn 对象JSON(字段: &[(&str, String)]) -> Vec<u8> {
    format!(
        "{{{}}}",
        字段
            .iter()
            .map(|(键, 值)| format!("\"{}\":\"{}\"", 转义JSON(键), 转义JSON(值)))
            .collect::<Vec<_>>()
            .join(",")
    )
    .into_bytes()
}
pub(super) fn 规范仓库(文本: &str) -> Result<PathBuf, u32> {
    let 路径 = Path::new(文本);
    if !路径.is_absolute() {
        return Err(错误码::受控边界不合法);
    }
    let 绝对 = fs::canonicalize(路径).map_err(|_| 错误码::文件不存在)?;
    if !绝对.is_dir()
        || 命令(&绝对, ["rev-parse", "--is-inside-work-tree"])
            .ok()
            .as_deref()
            != Some("true")
    {
        return Err(错误码::受控边界不合法);
    }
    Ok(绝对)
}
pub(crate) fn 命令<'a>(
    仓库: &Path,
    参数: impl IntoIterator<Item = &'a str>,
) -> Result<String, u32> {
    let 输出 = Command::new("git")
        .arg("-C")
        .arg(仓库)
        .args(参数)
        .output()
        .map_err(|_| 错误码::写入失败)?;
    let 文本 = String::from_utf8_lossy(&输出.stdout).trim().to_owned();
    if 输出.status.success() {
        Ok(文本)
    } else {
        Err(错误码::写入失败)
    }
}
fn 安全标识(标识: &str) -> bool {
    !标识.is_empty()
        && 标识.len() <= 64
        && 标识
            .chars()
            .all(|字| 字.is_ascii_alphanumeric() || 字 == '-' || 字 == '_')
}
pub(crate) fn 工作区路径(根: &Path, 标识: &str) -> Result<PathBuf, u32> {
    if !安全标识(标识) {
        return Err(错误码::受控边界不合法);
    }
    let 目标 = 根.join(format!("v1-d4-{标识}"));
    if !目标.starts_with(根) {
        return Err(错误码::受控边界不合法);
    }
    Ok(目标)
}
pub(crate) fn 验证工作区(路径: &Path) -> Result<PathBuf, u32> {
    if !路径.is_absolute() {
        return Err(错误码::受控边界不合法);
    }
    let 根 = fs::canonicalize(路径).map_err(|_| 错误码::文件不存在)?;
    let 父目录 = 根.parent().ok_or(错误码::受控边界不合法)?;
    let 名称 = 根
        .file_name()
        .and_then(|项| 项.to_str())
        .ok_or(错误码::受控边界不合法)?;
    let 标识 = 名称
        .strip_prefix("v1-d4-")
        .filter(|项| 安全标识(项))
        .ok_or(错误码::受控边界不合法)?;
    let 标记 = 父目录.join(".v1-d4-state").join(format!("{标识}.owner"));
    let 仓库归属记录 = fs::read(标记).map_err(|_| 错误码::受控边界不合法)?;
    if !根.is_dir()
        || 命令(&根, ["rev-parse", "--is-inside-work-tree"])
            .ok()
            .as_deref()
            != Some("true")
    {
        return Err(错误码::受控边界不合法);
    }
    let 顶层 = 命令(&根, ["rev-parse", "--show-toplevel"])
        .map_err(|_| 错误码::受控边界不合法)?;
    let 顶层 = fs::canonicalize(顶层).map_err(|_| 错误码::受控边界不合法)?;
    let 仓库文本 =
        std::str::from_utf8(&仓库归属记录).map_err(|_| 错误码::受控边界不合法)?;
    let 仓库根 = fs::canonicalize(仓库文本).map_err(|_| 错误码::受控边界不合法)?;
    let 实际共用目录 = 命令(
        &根,
        ["rev-parse", "--path-format=absolute", "--git-common-dir"],
    )
    .map_err(|_| 错误码::受控边界不合法)?;
    let 实际共用目录 =
        fs::canonicalize(实际共用目录).map_err(|_| 错误码::受控边界不合法)?;
    let 预期共用目录 =
        fs::canonicalize(仓库根.join(".git")).map_err(|_| 错误码::受控边界不合法)?;
    if 顶层 != 根 || 实际共用目录 != 预期共用目录 {
        return Err(错误码::受控边界不合法);
    }
    Ok(根)
}
