//! 装支持库制品 —— 构建期小 bin：把编出的 cdylib 字节与接口说明段字节包成一份 `.支持库制品`。
//!
//! 用法：
//!
//! ```text
//! cargo run -p v1-contract --example 装支持库制品 -- \
//!     --能力码 <cdylib 路径> --接口说明 <接口说明段路径> --输出 <制品路径>
//! ```
//!
//! **它只做一件事**：吃「cdylib 字节 + 接口说明段字节」⇒ 吐一份 `.支持库制品`。
//! 容器格式的**唯一实现在 `v1_contract::容器`**（本 bin 只转调，一条格式知识也不重写）。
//!
//! # 它不知道的
//!
//! - **不认识任何扩展名**：`--能力码` / `--接口说明` / `--输出` 都是调用方（装配侧）给的路径。
//! - **不生成机器码**：能力码就是调用方给的 cdylib 字节，本 bin 一个字节都不替它编。
//! - **不编接口说明段**：接口说明段是调用方给的已编码段数据（六字段 = `接口面形状.md` §三
//!   的返回体；编码在扩展侧 `接口段编码.rs`）。
//!
//! 后缀与落点见 `扩展装载/后缀表.json`（唯一权威）：`<扩展目录>/<扩展名>.支持库制品`。

use std::fs;
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use v1_contract::容器;

fn main() -> ExitCode {
    let 命令行参数 = match 解析命令行参数() {
        Ok(命令行参数) => 命令行参数,
        Err(说明文字) => {
            eprintln!("装支持库制品：{说明文字}");
            eprintln!("用法：--能力码 <cdylib> --接口说明 <段文件> --输出 <制品>");
            return ExitCode::from(2);
        }
    };
    let 能力码 = match 读输入件(&命令行参数.能力码, "能力码（cdylib）") {
        Ok(字节) => 字节,
        Err(退出码) => return 退出码,
    };
    let 接口说明段 = match 读输入件(&命令行参数.接口说明, "接口说明段") {
        Ok(字节) => 字节,
        Err(退出码) => return 退出码,
    };

    let 制品字节 = 容器::装包(&接口说明段, &能力码);
    // 当场自检往返：冻结容器无段长字段，段数据里碰巧出现段头特征就会被多切一刀。
    // 不许把这种包交给调用方（否则错会漂到很久以后的读侧）。
    match 容器::解包(&制品字节) {
        Ok(解出包件) if 解出包件.接口说明段 == 接口说明段 && 解出包件.能力码段 == 能力码 => {}
        _ => {
            eprintln!("装包往返不一致（能力码段里出现了段头特征？）—— 拒绝写出制品");
            return ExitCode::FAILURE;
        }
    }

    // 两个嵌套 `if` 合成一个（Clippy `collapsible_if`）：`if let … && !…` 是同一分支，
    // 分开写只是多一层缩进（附② 零成本可修那类）。
    if let Some(父目录) = 命令行参数.输出.parent()
        && !父目录.as_os_str().is_empty()
        && let Err(错误) = fs::create_dir_all(父目录)
    {
        eprintln!("建不出输出目录 {}：{错误}", 父目录.display());
        return ExitCode::FAILURE;
    }
    match fs::write(&命令行参数.输出, &制品字节) {
        Ok(()) => {
            println!(
                "装支持库制品：{} ｜ 接口说明段 {} 字节 · 能力码段 {} 字节 · 制品 {} 字节",
                命令行参数.输出.display(),
                接口说明段.len(),
                能力码.len(),
                制品字节.len()
            );
            ExitCode::SUCCESS
        }
        Err(错误) => {
            eprintln!("写不出制品 {}：{错误}", 命令行参数.输出.display());
            ExitCode::FAILURE
        }
    }
}

/// 读一个输入件。失败即指路（不回退、不猜）。
fn 读输入件(路径: &Path, 是什么: &str) -> Result<Vec<u8>, ExitCode> {
    match fs::read(路径) {
        Ok(字节) => Ok(字节),
        Err(错误) => {
            eprintln!("读不出{是什么}：{} —— {错误}", 路径.display());
            Err(ExitCode::FAILURE)
        }
    }
}

/// 三个入参路径。
struct 入参路径集 {
    能力码: PathBuf,
    接口说明: PathBuf,
    输出: PathBuf,
}

/// 解命令行。缺参数 / 有不认识的参数一律拒（不猜）。
fn 解析命令行参数() -> Result<入参路径集, String> {
    let 实参: Vec<String> = std::env::args().skip(1).collect();
    let mut 能力码 = None;
    let mut 接口说明 = None;
    let mut 输出 = None;
    let mut 迭代 = 实参.iter();
    while let Some(参数项) = 迭代.next() {
        match 参数项.as_str() {
            "--能力码" => 能力码 = 迭代.next().map(PathBuf::from),
            "--接口说明" => 接口说明 = 迭代.next().map(PathBuf::from),
            "--输出" => 输出 = 迭代.next().map(PathBuf::from),
            其余值 => return Err(format!("不认识的参数：{其余值}")),
        }
    }
    Ok(入参路径集 {
        能力码: 能力码.ok_or("缺 --能力码")?,
        接口说明: 接口说明.ok_or("缺 --接口说明")?,
        输出: 输出.ok_or("缺 --输出")?,
    })
}
