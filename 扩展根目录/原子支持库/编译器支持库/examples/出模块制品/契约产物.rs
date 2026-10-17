//! 构建依赖定位：Cargo回执是本次依赖图的事实，不按缓存数量或修改时间选库。
use std::path::{Path, PathBuf};
use super::声明读取::{声明值, 解析声明};

pub fn 找契约产物() -> Result<(PathBuf, PathBuf), String> {
    let 清单路径 = Path::new(env!("CARGO_MANIFEST_DIR")).join("Cargo.toml");
    let 契约清单 = 清单路径.parent().unwrap().join("../../../契约声明/Cargo.toml")
        .canonicalize().map_err(|错误| format!("契约声明路径不可达：{错误}"))?;
    let 输出 = std::process::Command::new(std::env::var_os("CARGO").unwrap_or_else(|| "cargo".into()))
        .args(["build", "--locked", "--offline", "--message-format=json", "-p", "v1-contract", "--manifest-path"])
        .arg(&清单路径).output().map_err(|错误| format!("构建依赖取证失败：{错误}"))?;
    if !输出.status.success() {
        return Err(format!("契约依赖构建失败：{}", String::from_utf8_lossy(&输出.stderr)));
    }
    let 契约产物 = 从构建回执取契约产物(&String::from_utf8_lossy(&输出.stdout), &契约清单)?;
    if !契约产物.is_file() { return Err(format!("构建回执的产物不存在：{}", 契约产物.display())); }
    let 依赖目录 = 契约产物.parent().ok_or_else(|| "契约产物没有父目录".to_owned())?.to_owned();
    Ok((契约产物, 依赖目录))
}

fn 从构建回执取契约产物(回执正文: &str, 契约清单: &Path) -> Result<PathBuf, String> {
    let mut 命中表 = std::collections::BTreeSet::new();
    for 回执行 in 回执正文.lines().filter(|回执行| !回执行.trim().is_empty()) {
        let 回执项 = 解析声明(回执行).map_err(|错误| format!("Cargo回执不是合法JSON：{错误}"))?;
        if 回执项.取键("reason").and_then(声明值::取文本) != Some("compiler-artifact") { continue; }
        let Some(清单文本) = 回执项.取键("manifest_path").and_then(声明值::取文本) else { continue; };
        if Path::new(清单文本).canonicalize().ok().as_deref() != Some(契约清单) { continue; }
        let 产物表 = 回执项.取键("filenames").and_then(声明值::取文本表)
            .ok_or_else(|| "契约构建回执缺产物表".to_owned())?;
        for 产物文本 in 产物表 {
            let 产物路径 = PathBuf::from(产物文本);
            if 产物路径.extension().is_some_and(|扩展名| 扩展名 == "rlib") { 命中表.insert(产物路径); }
        }
    }
    if 命中表.len() != 1 { return Err(format!("本次构建图的契约rlib应为一份，实际{}份", 命中表.len())); }
    Ok(命中表.into_iter().next().unwrap())
}

#[test]
fn 缺契约回执不得扫描缓存补选() {
    assert!(从构建回执取契约产物("{}", Path::new("不存在的声明")).is_err());
    assert!(从构建回执取契约产物("损坏回执", Path::new("不存在的声明")).is_err());
}
