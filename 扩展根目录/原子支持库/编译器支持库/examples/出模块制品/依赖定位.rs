//! 依赖定位与语义表：按标识串找包目录 · 类型表 · 命令表 · 锁定依赖 · 列声明目录 · 找仓根。
//!
//! 全部 fail-closed：命中 0 份 / 多份、声明缺键、版本不满足一律拒，不猜、不静默补。

use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};

use v1_compiler::执行函数面::本机生成::本机依赖;
use v1_compiler::语义;

use super::依赖要求::{依赖要求, 取实现版本};
use super::声明取值::取整数;
use super::声明读取::{声明值, 读声明件};

/// 标识串 → 包目录（扫 `扩展根目录/` 下全部 `包声明.json`，按标识串精确命中），
/// 并**当场按装载依赖校验的同一合同**核被选包的 `实现版本` 是否满足版本门槛。
///
/// fail-closed：命中 0 份 = 缺依赖；命中多份 = 分不清用哪份；被选包缺 `标识串` / `实现版本`
/// 或版本不满足（含「要求未来版本」）= 拒。不让要求未来不兼容版本也生成。
pub(super) fn 定位依赖包(
    仓根: &Path, 要求表: &[依赖要求]
) -> Result<Vec<PathBuf>, String> {
    let mut 目录表 = Vec::with_capacity(要求表.len());
    for 要求项 in 要求表 {
        let 命中表: Vec<PathBuf> = 扫包目录(&仓根.join("扩展根目录"))
            .into_iter()
            .filter(|包目录| {
                读声明件(&包目录.join("包声明.json"))
                    .ok()
                    .and_then(|声明| {
                        声明
                            .取键("标识串")
                            .and_then(声明值::取文本)
                            .map(str::to_owned)
                    })
                    .is_some_and(|自身标识| 自身标识 == 要求项.标识串)
            })
            .collect();
        let [包目录] = 命中表.as_slice() else {
            return Err(match 命中表.len() {
                0 => format!("依赖 {} 在 扩展根目录/ 下找不到同标识串的包", 要求项.标识串),
                _ => format!(
                    "依赖 {} 在 扩展根目录/ 下命中 {} 份包，分不清用哪份",
                    要求项.标识串,
                    命中表.len()
                ),
            });
        };
        let 包声明 = 读声明件(&包目录.join("包声明.json"))?;
        let 实际版本 = 取实现版本(&包声明, &要求项.标识串)?;
        if !实际版本.满足(&要求项.版本门槛) {
            return Err(format!(
                "依赖 {} 的版本不满足要求：要求 {}.{}，被选包实现版本 {}.{}.{}",
                要求项.标识串,
                要求项.版本门槛.主版本,
                要求项.版本门槛.次版本号,
                实际版本.主版本,
                实际版本.次版本号,
                实际版本.构建
            ));
        }
        目录表.push(包目录.clone());
    }
    Ok(目录表)
}

/// 递归扫出含 `包声明.json` 的目录（有界：只看 `扩展根目录/` 这棵树）。
pub(super) fn 扫包目录(扫描根: &Path) -> Vec<PathBuf> {
    let mut 结果表 = Vec::new();
    let mut 待扫 = vec![扫描根.to_path_buf()];
    while let Some(当前目录) = 待扫.pop() {
        if 当前目录.join("包声明.json").is_file() {
            结果表.push(当前目录.clone());
        }
        let Ok(目录项) = fs::read_dir(&当前目录) else {
            continue;
        };
        for 目录条目 in 目录项.flatten() {
            let 条目路径 = 目录条目.path();
            if 条目路径.is_dir()
                && 条目路径
                    .file_name()
                    .is_some_and(|目录名| 目录名 != "target" && 目录名 != ".git")
            {
                待扫.push(条目路径);
            }
        }
    }
    结果表
}

/// 类型表：仓根契约类型声明 ＋ 各依赖包的类型声明（名 → 号）。
///
/// **两种写法同号**：声明里的 `名称`（如 `整数`）与易语言式 `名称`＋`型`（如 `整数型`）——
/// 模块程序文本按后者写（既有样本就这么写），构建侧不能因为差一个「型」字就拒。
/// 标签超出 `u16` 的声明（`4294967295` 这类占位号）不进表：名号表的号是 `u16`。
pub(super) fn 收集类型表(
    仓根: &Path,
    依赖目录表: &[PathBuf],
) -> Result<语义::名号表, String> {
    let mut 声明目录表 = vec![仓根.join("契约声明/类型声明")];
    for 依赖目录 in 依赖目录表 {
        let 声明目录 = 依赖目录.join("类型声明");
        if 声明目录
            .try_exists()
            .map_err(|错误| format!("类型声明目录无法检查：{错误}"))?
        {
            声明目录表.push(声明目录);
        }
    }
    let mut 类型表项: BTreeMap<Vec<u8>, u16> = BTreeMap::new();
    for 声明目录 in 声明目录表 {
        for 声明件 in 列声明目录(&声明目录)? {
            let Ok(类型号) = 取整数(&声明件, "类型标签") else {
                continue;
            };
            let Ok(u16标签) = u16::try_from(类型号) else {
                continue;
            };
            let Some(名称) = 声明件.取键("名称").and_then(声明值::取文本) else {
                continue;
            };
            类型表项.insert(名称.as_bytes().to_vec(), u16标签);
            类型表项.insert(format!("{名称}型").into_bytes(), u16标签);
        }
    }
    if 类型表项.is_empty() {
        return Err("类型表是空的：契约与依赖的类型声明都没读到".to_owned());
    }
    Ok(语义::名号表::从项(类型表项.into_iter().collect()))
}

/// 命令表：依赖包全部能力声明（名称 → 编号）。
pub(super) fn 收集命令表(依赖目录表: &[PathBuf]) -> Result<语义::名号表, String> {
    let mut 类型表项: BTreeMap<Vec<u8>, u16> = BTreeMap::new();
    for 依赖目录 in 依赖目录表 {
        for 能力声明 in 列声明目录(&依赖目录.join("能力声明"))? {
            let (Ok(编号), Some(名称)) = (
                取整数(&能力声明, "编号"),
                能力声明.取键("名称").and_then(声明值::取文本),
            ) else {
                return Err(format!(
                    "依赖 {} 的能力声明缺 编号/名称",
                    依赖目录.display()
                ));
            };
            let u16编号 = u16::try_from(编号).map_err(|_| format!("能力号 {编号} 超出 u16"))?;
            类型表项.insert(名称.as_bytes().to_vec(), u16编号);
        }
    }
    Ok(语义::名号表::从项(类型表项.into_iter().collect()))
}

/// 锁定依赖：命令表里**在本模块程序文本中出现过**的能力，签名逐项取自该能力的声明。
///
/// 为什么先按出现过滤：锁定依赖是「本模块真实调用了谁」的签名集合。把依赖包的全部能力
/// 都锁进来，会让本子集不支持的类型（如双精度入参）把整次生成拖红 —— 那不是模块的问题。
/// 少锁则当场红（表达式生成按名查不到签名即拒），故这是**宁可红不静默**的过滤。
pub(super) fn 收集锁定依赖(
    命令表: &语义::名号表,
    源文本: &str,
    依赖目录表: &[PathBuf],
) -> Result<Vec<本机依赖>, String> {
    let mut 锁定表 = Vec::new();
    for 依赖目录 in 依赖目录表 {
        for 能力声明 in 列声明目录(&依赖目录.join("能力声明"))? {
            let Some(名称) = 能力声明.取键("名称").and_then(声明值::取文本) else {
                continue;
            };
            if !源文本.contains(名称) {
                continue;
            }
            let 编号 = 命令表
                .按名取号(名称.as_bytes())
                .ok_or_else(|| format!("命令表里没有 {名称}"))?;
            let 入参类型表 = 能力声明
                .取键("参数表")
                .and_then(声明值::取表)
                .unwrap_or_default()
                .iter()
                .map(|参数项| 取整数(参数项, "类型标签").map(|标签| 标签 as u32))
                .collect::<Result<Vec<_>, String>>()?;
            锁定表.push(本机依赖 {
                名称: 名称.as_bytes().to_vec(),
                能力号: 编号,
                入参类型表,
                返回类型: 取整数(&能力声明, "返回类型")? as u32,
            });
        }
    }
    Ok(锁定表)
}

/// 列一个声明目录里的全部 `*.json`（按文件名升序，读不动即拒）。
pub(super) fn 列声明目录(声明目录: &Path) -> Result<Vec<声明值>, String> {
    let 目录项 =
        fs::read_dir(声明目录).map_err(|错误| format!("读不到 {}：{错误}", 声明目录.display()))?;
    let mut 路径表: Vec<PathBuf> = 目录项
        .flatten()
        .map(|目录条目| 目录条目.path())
        .filter(|条目路径| 条目路径.extension().is_some_and(|扩展名| 扩展名 == "json"))
        .collect();
    路径表.sort();
    路径表.iter().map(|路径| 读声明件(路径)).collect()
}

/// 从给定目录往上找仓根（含 `契约声明/` 的那一级）。
pub(super) fn 找仓根(起点: &Path) -> Result<PathBuf, String> {
    let 绝对起点 = fs::canonicalize(起点)
        .map_err(|错误| format!("取不到 {} 的真实路径：{错误}", 起点.display()))?;
    for 候选目录 in 绝对起点.ancestors() {
        if 候选目录.join("契约声明").is_dir() {
            return Ok(候选目录.to_path_buf());
        }
    }
    Err(format!(
        "从 {} 往上找不到含 契约声明/ 的仓根",
        起点.display()
    ))
}
