//! 静态件 —— 把**前端自身的件**交给浏览器（`项目文档/设计文档/接口面形状.md` §五）。
//!
//! # 四条口径（每条都能追到冻结件或宪法）
//!
//! 1. **只托管前端自身的件**。托管根是注入的一个目录，请求路径只许落在它里面 ——
//!    **不许把仓根挂出去**（那等于把源码全挂给浏览器）。§五 那句「静态文件由接口面进程托管」
//!    配 §六 第 10 条「接口面托管的是**前端自身的静态件**（`/` → `index.html`），**不含仓根**」
//!    就是这条口径的出处。
//! 2. **一个监听**：托管走网关那一个 `TcpListener`，不为它开第二个口
//!    （判据 ⑪「对外监听恰好 1 处」；独立 dev server 就是第二个监听口）。
//! 3. **不是端点**：`GET /接口` 交出的端点表仍是 §二 那四个，一个不多一个不少 ——
//!    静态件是**托管**，不是能力端点（`常量.rs` 的 `端点表` 一字未动）。
//! 4. **不做目录列表、不做重写**：请求 `/x` 就是文件 `/x`；找不到就是 404。
//!    没有件就去读目录、或替调用方猜一个 `index.html`，都是给同一件事造第二种含义。
//!
//! # 路径安全：**逐段判**，不做字符串前缀匹配
//!
//! `..` / `.` / 空段 / 反斜杠 / 冒号一律拒（`None`），于是拼出来的路径**不可能**离开托管根 ——
//! 这比「拼完再看前缀」稳：前缀匹配在 `根=/a` 与 `/a../x` 这类边界上会判错。
//! 前导斜杠去掉之后 `""` 就是目录请求，回 `index.html`（前端是「无构建步骤」的单目录应用，
//! 没有子目录，故不做「任意目录回首页」那种重写）。

use crate::常量::{目录首页, 内容类型_默认};
use std::path::Path;

/// 一件静态件：内容 + 内容类型（内容类型随扩展名定，见 [`内容类型`]）。
#[derive(Debug, Clone)]
pub struct 静态件 {
    pub 字节: Vec<u8>,
    pub 内容类型: &'static str,
}

/// 请求路径 → 静态件。`None` = 托管根下没有这个件（⇒ 分发侧给 404）。
///
/// `路径` 必须是**已经百分号解码过**的路径 —— 解码在协议层做（`端点路由.rs`），
/// 这里只认解码后的形态，不重复解一次（同一件事两处做，两处会分叉）。
pub fn 取静态件(根目录: &Path, 路径: &str) -> Option<静态件> {
    let 相对 = 安全相对路径(路径)?;
    let 完整路径 = 根目录.join(&相对);
    // 目录与不存在的件一律 `None`（口径 4：不列表、不重写）。
    if !std::fs::metadata(&完整路径).ok()?.is_file() {
        return None;
    }
    let 字节 = std::fs::read(&完整路径).ok()?;
    Some(静态件 {
        内容类型: 内容类型(&相对),
        字节,
    })
}

/// 请求路径 → 托管根下的相对路径。**不安全的一律 `None`**（`..` · `.` · 空段 · 反斜杠 · 冒号 · NUL）。
fn 安全相对路径(路径: &str) -> Option<String> {
    if 路径.contains('\0') {
        return None;
    }
    // 反斜杠不当分隔符用：认了它就等于给同一段路径造两种写法。
    if 路径.contains('\\') {
        return None;
    }
    let 净文本 = 路径.trim_start_matches('/');
    // 目录请求（`/` 或空）⇒ 首页。前端的目录只有这一个，不做通用目录重写。
    if 净文本.is_empty() {
        return Some(目录首页.to_owned());
    }
    let 净文本 = 净文本.trim_end_matches('/');
    if 净文本.is_empty() {
        return None;
    }
    for 路径段 in 净文本.split('/') {
        // 段里带冒号 = Windows 盘符形（`C:` / `C:\\`）。放它过去等于把**绝对路径**拼进托管根，
        // 托管根直接被绕过 —— 与本函数「逐段判、不做前缀匹配」的同一道判定里拦掉，不另开一套。
        if 路径段.is_empty() || 路径段 == "." || 路径段 == ".." || 路径段.contains(':') {
            return None;
        }
    }
    Some(净文本.to_owned())
}

/// 扩展名 → 内容类型。**不认的扩展名一律 `application/octet-stream`**：
/// 猜一个类型就是把浏览器的行为改成猜出来的那样。
fn 内容类型(相对: &str) -> &'static str {
    match 相对.rsplit('.').next().unwrap_or("") {
        "html" => "text/html; charset=utf-8",
        "css" => "text/css; charset=utf-8",
        "js" => "text/javascript; charset=utf-8",
        "json" => "application/json; charset=utf-8",
        "svg" => "image/svg+xml",
        "png" => "image/png",
        "ico" => "image/x-icon",
        _ => 内容类型_默认,
    }
}

#[cfg(test)]
mod 静态件测试 {
    use super::*;
    use std::path::PathBuf;

    /// 前端网页应用的仓内位置：**本 crate 的相对位置**（前端没有构建步骤 ⇒ 它一直在那儿）。
    /// 只在测试里用 `CARGO_MANIFEST_DIR`：制品里不许编进构建机的绝对路径（见 `常量.rs` 的 `静态根`）。
    fn 前端根() -> PathBuf {
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../../前端呈现/网页应用")
    }

    #[test]
    fn 根路径回首页且取得到前端自身的件() {
        let 根目录 = 前端根();
        let 首页 = 取静态件(&根目录, "/").expect("`/` 必须回 index.html");
        assert_eq!(首页.内容类型, "text/html; charset=utf-8");
        assert!(首页.字节.starts_with(b"<!DOCTYPE html>"), "该是真 index.html");

        let 样式件 = 取静态件(&根目录, "/样式资源/页面样式.css").expect("页面样式.css 在托管根下");
        assert_eq!(样式件.内容类型, "text/css; charset=utf-8");
        assert!(!样式件.字节.is_empty());

        let 脚本件 = 取静态件(&根目录, "/接口请求/取接口.js").expect("取接口.js 在托管根下");
        assert_eq!(脚本件.内容类型, "text/javascript; charset=utf-8");
    }

    #[test]
    fn 只托管前端自身的件_仓内别处一律取不到() {
        let 根目录 = 前端根();
        for 路径 in [
            "/Cargo.toml",
            "/项目文档/设计文档/接口面形状.md",
            "/../Cargo.toml",
            "/../../Cargo.toml",
            "/./index.html",
            "//Cargo.toml",
            "/a\\b",
        ] {
            assert!(取静态件(&根目录, 路径).is_none(), "「{路径}」不许取到（托管根之外）");
        }
        // 不存在的件、目录请求（子目录）也不给件 —— 不列表、不重写。
        assert!(取静态件(&根目录, "/没有这个件.txt").is_none());
        assert!(取静态件(&根目录, "/项目文档/").is_none());
    }

    #[test]
    fn 盘符段一律拒() {
        // 段里出现冒号（Windows 盘符形）不是托管根下的合法件名 —— 逐段判定就该拒；
        // 放过去等于把绝对路径拼进托管根，托管根直接被绕过。
        for 路径 in ["/C:/x", "C:/x", "/a/C:/b", "/:/", "/a:b"] {
            assert!(安全相对路径(路径).is_none(), "「{路径}」含盘符段，必须拒");
        }
    }
}
