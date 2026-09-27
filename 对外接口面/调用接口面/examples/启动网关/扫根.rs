//! 启动网关 · 扫根 —— 「一个扩展根目录里有哪些可装载库」的判据。
//!
//! 从 `examples/启动网关.rs` 搬来（那是装配入口，本件是它的一个关注点；**纯搬家**）。
//! 这里**不写死任何扩展名**：扫到谁就是谁（README 第五节「底座不认识任何扩展」）。

use std::fs;
use std::path::{Path, PathBuf};

/// 可装载库文件的后缀：**按后缀找，不按名字找**（名字里会有扩展名，底座不许认名字）。
pub(crate) const 库后缀: [&str; 3] = [".dylib", ".so", ".dll"];

/// 取一个目录下的直接子目录，**按名字排序**（装载顺序即依赖序，不许随文件系统飘）。
pub(crate) fn 子目录(目录: &Path) -> Vec<PathBuf> {
    let Ok(读) = fs::read_dir(目录) else { return Vec::new() };
    let mut 输出缓冲: Vec<PathBuf> = 读
        .filter_map(|项| 项.ok())
        .map(|项| 项.path())
        .filter(|路| 路.is_dir())
        .collect();
    输出缓冲.sort();
    输出缓冲
}

/// 是不是可装载库文件（按后缀找，不按名字找）。
pub(crate) fn 是可装载库(路径: &Path) -> bool {
    let 名称 = 路径.file_name().and_then(|名| 名.to_str());
    路径.is_file() && 名称.is_some_and(|名| 库后缀.iter().any(|尾| 名.ends_with(尾)))
}
