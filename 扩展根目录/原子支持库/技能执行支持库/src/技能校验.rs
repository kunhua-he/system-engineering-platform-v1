//! 技能包校验：能力标识、六件套、工作流、脚本范围与静态安全审计。
//!
//! 全部 fail-closed：任何一条不清楚就报错，不「大概放行」。

use std::path::{Component, Path, PathBuf};

use crate::编号与码面::错误码;

/// 六件套里必须是文件的那五件。
const 必备文件: [&str; 5] = ["SKILL.md", "契约.json", "工作流.json", "验证声明.json", "依赖.json"];

/// 脚本里出现即拒的片段（任意命令执行与动态加载）。
const 禁项片段: [&str; 16] = [
    "subprocess",
    "os.system",
    "os.popen",
    "os.spawn",
    "os.exec",
    "os.fork",
    "pty.spawn",
    "shell=True",
    "eval(",
    "exec(",
    "__import__",
    "importlib",
    "ctypes",
    "sys.modules",
    "runpy",
    "pickle.loads",
];

/// 解析「分类.技能名」，逐段拒绝穿越、绝对路径、空段与反斜杠。
pub(crate) fn 拆能力标识(标识: &str) -> Result<Vec<String>, u32> {
    let 标识 = 标识.trim();
    if 标识.is_empty() || 标识.contains('\\') || 标识.contains('/') {
        return Err(错误码::能力标识不合法);
    }
    let 段表: Vec<String> = 标识.split('.').map(|段| 段.trim().to_string()).collect();
    if 段表.len() != 2 {
        return Err(错误码::能力标识不合法);
    }
    for 段 in &段表 {
        if 段.is_empty() || 段 == "." || 段 == ".." || 段.contains(':') {
            return Err(错误码::能力标识不合法);
        }
        if Path::new(段).components().any(|项| !matches!(项, Component::Normal(_))) {
            return Err(错误码::能力标识不合法);
        }
    }
    Ok(段表)
}

/// 六件套完整性检查。
pub(crate) fn 查六件套(技能目录: &Path) -> Result<(), u32> {
    if !技能目录.is_dir() {
        return Err(错误码::技能目录不存在);
    }
    for 件 in 必备文件 {
        if !技能目录.join(件).is_file() {
            return Err(错误码::技能包不完整);
        }
    }
    if !技能目录.join("scripts").is_dir() {
        return Err(错误码::技能包不完整);
    }
    Ok(())
}

/// 从工作流.json 取入口脚本名，并保证它落在 scripts/ 内。
pub(crate) fn 查工作流(技能目录: &Path) -> Result<PathBuf, u32> {
    let 文本 = std::fs::read_to_string(技能目录.join("工作流.json")).map_err(|_| 错误码::工作流不合法)?;
    let 值: serde_json::Value = serde_json::from_str(&文本).map_err(|_| 错误码::工作流不合法)?;
    let 入口 = 值
        .get("入口脚本")
        .and_then(|项| 项.as_str())
        .map(|项| 项.trim().to_string())
        .filter(|项| !项.is_empty())
        .ok_or(错误码::工作流不合法)?;
    if 入口.contains('/') || 入口.contains('\\') || 入口 == ".." {
        return Err(错误码::工作流不合法);
    }
    if !入口.ends_with(".py") {
        return Err(错误码::工作流不合法);
    }
    let 脚本 = 技能目录.join("scripts").join(&入口);
    if !脚本.is_file() {
        return Err(错误码::工作流不合法);
    }
    Ok(脚本)
}

/// 解析真实路径后必须仍在该技能 scripts/ 目录内（防符号链接逃逸）。
pub(crate) fn 查脚本范围(技能目录: &Path, 脚本: &Path) -> Result<PathBuf, u32> {
    let 根 = 技能目录
        .join("scripts")
        .canonicalize()
        .map_err(|_| 错误码::技能目录不存在)?;
    let 真 = 脚本.canonicalize().map_err(|_| 错误码::脚本越界)?;
    if !真.starts_with(&根) {
        return Err(错误码::脚本越界);
    }
    Ok(真)
}

/// 读脚本源码做静态审计；源码超过 2MiB 直接判超限。
pub(crate) fn 查脚本内容(脚本: &Path) -> Result<String, u32> {
    let 元 = std::fs::metadata(脚本).map_err(|_| 错误码::脚本越界)?;
    if 元.len() > 2 * 1024 * 1024 {
        return Err(错误码::资源超限);
    }
    let 源码 = std::fs::read_to_string(脚本).map_err(|_| 错误码::脚本审计不通过)?;
    for 片段 in 禁项片段 {
        if 源码.contains(片段) {
            return Err(错误码::脚本审计不通过);
        }
    }
    Ok(源码)
}

/// 按调用方给的禁止导入前缀查 import / from 语句。
pub(crate) fn 查导入(源码: &str, 禁止前缀: &[String]) -> Result<(), u32> {
    if 禁止前缀.is_empty() {
        return Ok(());
    }
    for 行 in 源码.lines() {
        let 净 = 行.trim();
        let 模块 = if let Some(尾巴) = 净.strip_prefix("from ") {
            尾巴.split_whitespace().next().unwrap_or("")
        } else if let Some(尾巴) = 净.strip_prefix("import ") {
            尾巴.split_whitespace()
                .next()
                .unwrap_or("")
                .split(',')
                .next()
                .unwrap_or("")
        } else {
            continue;
        };
        let 模块 = 模块.trim_start_matches('.');
        if 模块.is_empty() {
            continue;
        }
        for 前缀 in 禁止前缀 {
            let 前缀 = 前缀.trim();
            if 前缀.is_empty() {
                continue;
            }
            if 模块 == 前缀 || 模块.starts_with(&format!("{前缀}.")) {
                return Err(错误码::依赖越界);
            }
        }
    }
    Ok(())
}
