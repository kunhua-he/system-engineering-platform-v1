//! 诊断 · 测试 · 夹具 —— 三件共用的两样东西：语料读取 · 一行读数的期望写法。
//!
//! 夹具只有一处实现（同一件事不许两套），三件都从这里取。
//! 语料读取与 `src/词法/切分测试/夹具.rs` 同源（同一批 53 份真文本），本件不另立一份语料清单。

use std::path::{Path, PathBuf};

/// 一行**读数的期望写法**：`阶段 {阶段} · 码 {错误码} · {位置}`，位置给不出时写 `位置 无`。
///
/// 判据（为什么期望也走函数而不是各写一遍字面量）：`读数` 的体例只有一处定义（`整理.rs`），
/// 测试里再抄一遍体例就是「同一件事两套」—— 体例改了测试会假绿。这里只把**两个数**喂进去。
pub fn 期望读数(阶段: u32, 错误码: u32, 位置: Option<(u32, u32)>) -> String {
    match 位置 {
        Some((起, 止)) => format!("阶段 {阶段} · 码 {错误码} · 位置 [{起},{止})"),
        None => format!("阶段 {阶段} · 码 {错误码} · 位置 无"),
    }
}

/// 53 份真文本样本（`语料/真文本/*.txt`，UTF-8），按文件名排序。
pub fn 语料文件() -> Vec<PathBuf> {
    let 目录 = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("语料")
        .join("真文本");
    let mut 路s: Vec<PathBuf> = std::fs::read_dir(&目录)
        .unwrap_or_else(|错| panic!("读不到 {}：{错}", 目录.display()))
        .filter_map(|项| 项.ok().map(|项| 项.path()))
        .filter(|路| 路.to_str().is_some_and(|名| 名.ends_with(".txt")))
        .collect();
    路s.sort();
    路s
}

/// 读一份语料（UTF-8）。
pub fn 读语料(路径: &Path) -> String {
    std::fs::read_to_string(路径).unwrap_or_else(|错| panic!("{}：{错}", 路径.display()))
}
