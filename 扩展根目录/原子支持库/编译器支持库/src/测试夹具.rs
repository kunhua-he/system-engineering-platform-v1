//! 测试夹具 —— 各测试件共用的夹具构造：造记号流 · 区间 · 语料读取 · 语料收集 · 首异比对 · 注册表字节。
//!
//! 夹具只有一处实现（同一件事不许两套），各测试件都从这里取。
//! 这些夹具**只在测试模块里用** ⇒ 整个模块挂 `#[cfg(test)]`（在 `lib.rs` 的声明处门控），
//! 不进制品面。

use std::path::{Path, PathBuf};

use crate::语言面::{记号, 记号流, 记号种类};

/// 取证语料根目录（易语言源码树，只读）。**crate 内唯一一处** `/tmp/易语言源码` 字面 ——
/// `记录流` 与 `容器` 的测试件都从这里取，不许各写一份（同一事实两处源）。
/// 目录不存在时相关往返测试跳过（不失败）。
///
/// 为什么不走「运行数据根」：本 crate 是**扩展**，按纪律只依赖底座公布的契约
/// （`Cargo.toml`：不依赖底座任何内部节点）⇒ 取不到 `v1-run-data-root` 的解析口；
/// 直接读 `V1_RUN_DATA_ROOT` 再自拼路径，又是判据 ㉔ 当场报红的形状（自拼运行数据路径）。
pub(crate) const 语料根目录: &str = "/tmp/易语言源码";

/// 按顺序找出片段拼成记号表（夹具构造，**不是词法分析器**：种类由调用方给定）。
pub(crate) fn 造记号流(原文: &str, 项表: &[(记号种类, &str)]) -> 记号流 {
    let 字节 = 原文.as_bytes().to_vec();
    let mut 记号表 = Vec::new();
    let mut 游标 = 0usize;
    for (种类, 片段) in 项表 {
        let 相对 = 原文[游标..].find(片段).expect("夹具片段在原文里找不到");
        let 区间起点 = 游标 + 相对;
        let 区间终点 = 区间起点 + 片段.len();
        记号表.push(记号::新建(*种类, 区间起点 as u32, 区间终点 as u32));
        游标 = 区间终点;
    }
    assert_eq!(游标, 字节.len(), "夹具片段没铺满全文");
    let 长度 = 字节.len() as u32;
    记号表.push(记号::新建(记号种类::文件结束, 长度, 长度));
    记号流::新建(字节, 记号表).expect("夹具造的记号流必须合法")
}

/// 取某片段的字节区间。
pub(crate) fn 区间(原文: &str, 片段: &str) -> (u32, u32) {
    let 区间起点 = 原文.find(片段).expect("夹具片段在原文里找不到");
    (区间起点 as u32, (区间起点 + 片段.len()) as u32)
}

/// 53 份真文本样本（`语料/真文本/*.txt`，UTF-8），按文件名排序。
pub(crate) fn 语料文件() -> Vec<PathBuf> {
    let 目录 = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("语料")
        .join("真文本");
    let mut 路s: Vec<PathBuf> = std::fs::read_dir(&目录)
        .unwrap_or_else(|错误| panic!("读不到 {}：{错误}", 目录.display()))
        .filter_map(|目录项| 目录项.ok().map(|目录项| 目录项.path()))
        .filter(|路径| 路径.to_str().is_some_and(|名称| 名称.ends_with(".txt")))
        .collect();
    路s.sort();
    路s
}

/// 读一份语料（UTF-8）。
pub(crate) fn 读语料(路径: &Path) -> String {
    std::fs::read_to_string(路径).unwrap_or_else(|错误| panic!("{}：{错误}", 路径.display()))
}

/// 首个不一致字节偏移（逐字节比；先到头的那份长度为界）。
pub(crate) fn 首个不一致(原文: &[u8], 产物: &[u8]) -> u64 {
    let 上限 = 原文.len().min(产物.len());
    for 位置 in 0..上限 {
        if 原文[位置] != 产物[位置] {
            return 位置 as u64;
        }
    }
    上限 as u64
}

/// 大小写不敏感地认 `.e` / `.ec`。
pub(crate) fn 是语料文件(路径: &Path) -> bool {
    match 路径.extension().and_then(|扩展| 扩展.to_str()) {
        Some(扩展) => {
            let 小写 = 扩展.to_ascii_lowercase();
            小写 == "e" || 小写 == "ec"
        }
        None => false,
    }
}

/// 递归收集语料。用 `file_type()` 不追符号链接，避免环。
pub(crate) fn 收集语料(根目录: &Path, 输出缓冲: &mut Vec<PathBuf>) {
    let Ok(项集) = std::fs::read_dir(根目录) else {
        return;
    };
    for 目录项 in 项集.flatten() {
        let Ok(类型) = 目录项.file_type() else { continue };
        let 路径 = 目录项.path();
        if 类型.is_dir() {
            收集语料(&路径, 输出缓冲);
        } else if 类型.is_file() && 是语料文件(&路径) {
            输出缓冲.push(路径);
        }
    }
}

/// 造一份名号表字节集（载荷 = 本库的名号表边界编码）。
///
/// **返回 Vec 而不是槽**：`字节集槽` 是「引用」槽，指向的字节必须比槽活得久；
/// 若在函数里返回槽，它指的那份 `Vec` 当场析构 ⇒ 悬垂（实测撞到 `ptr::copy_nonoverlapping`
/// 的 UB 检查）。故本助手只交字节，槽由调用方就地造。
pub(crate) fn 注册表字节(项集: &[(&str, u16)]) -> Vec<u8> {
    crate::语义::名号表::从项(
        项集.iter().map(|(名称, 号值)| (名称.as_bytes().to_vec(), *号值)).collect(),
    )
    .编码()
}
