//! 装载模块执行体 —— 拿一份真 `.模块制品`，走底座**装载侧**，真调一次。
//!
//! 怎么跑（在仓根）：
//!
//! ```sh
//! cargo run --locked -p v1-adapter --example 装载模块执行体 -- \
//!   <模块目录>/<模块名>.模块制品 2 3
//! ```
//!
//! 头一个参数是制品路径；之后的整数是入参（不传就默认 `2 3`）。
//!
//! 想验「平台身份不符即拒」，在制品路径后面插 `--身份 <一个别的身份>`：
//!
//! ```sh
//! cargo run --locked -p v1-adapter --example 装载模块执行体 -- \
//!   <模块目录>/<模块名>.模块制品 --身份 x86_64-unknown-linux-gnu 2 3
//! ```
//!
//! # 这条链与「构建侧」的分工
//!
//! 制品由**构建侧**出（构建侧的例子 `出模块制品`）；本例子只走**装载侧**：
//! 取段 `20` → 判平台身份 → 落缓存 → `dlopen` → 取入口 → 调用。
//! 两条腿共用同一份形状与符号名（`v1_contract::容器::执行体载荷`）。

use std::path::Path;
use std::process::ExitCode;

use v1_adapter::数据槽;
use v1_adapter::模块执行体装载::{本机平台身份, 装载模块执行体};
use v1_adapter::装载件缓存;

fn main() -> ExitCode {
    let 命令行参数: Vec<String> = std::env::args().skip(1).collect();
    if 命令行参数.is_empty() {
        eprintln!("用法：装载模块执行体 <制品路径> [入参…]");
        return ExitCode::FAILURE;
    }
    match 跑一次(&命令行参数) {
        Ok(说明) => {
            println!("{说明}");
            ExitCode::SUCCESS
        }
        Err(失败原因) => {
            eprintln!("装载失败：{失败原因}");
            ExitCode::FAILURE
        }
    }
}

/// 装载 + 调一次，返回一句人读的读数。
fn 跑一次(命令行参数: &[String]) -> Result<String, String> {
    let 制品路径 = 命令行参数
        .first()
        .ok_or_else(|| String::from("缺制品路径"))?
        .clone();
    // 默认用**本机身份**；给了 `--身份` 就用替身 —— 专门用来验「不符即拒」。
    let (平台身份, 入参文本表) = match 命令行参数.get(1).map(String::as_str) {
        Some("--身份") => (
            命令行参数
                .get(2)
                .cloned()
                .ok_or_else(|| String::from("--身份 后面要跟一个身份串"))?,
            命令行参数.get(3..).unwrap_or(&[]).to_vec(),
        ),
        _ => (本机平台身份()?, 命令行参数.get(1..).unwrap_or(&[]).to_vec()),
    };
    let 缓存根目录 = 装载件缓存::默认缓存根目录()
        .ok_or_else(|| String::from("解析不出运行数据根 ⇒ 缓存根目录拿不到"))?;
    let 执行体 = 装载模块执行体(Path::new(&制品路径), &缓存根目录, &平台身份)
        .map_err(|错误| format!("{错误:?}"))?;
    let 入参整数表: Vec<i64> = if 入参文本表.is_empty() {
        vec![2, 3]
    } else {
        入参文本表.iter().map(|入参文本| 入参文本.parse::<i64>().unwrap_or(0)).collect()
    };
    let 入参槽表: Vec<数据槽> = 入参整数表
        .iter()
        .map(|&整数值| 数据槽::内联槽(1u32.into(), 整数值 as u64, 8))
        .collect();
    let 返回整数 = 执行体.调用(&入参槽表, 宿主桩).map_err(|错误| format!("{错误:?}"))?;
    Ok(format!("平台身份 {平台身份} · 入参 {入参整数表:?} → 返回 {返回整数}"))
}

/// 宿主回调桩：本样本模块不调别的能力 ⇒ 真被调到就是**不该发生**（给非零，让它失败）。
extern "C" fn 宿主桩(_: u32, _: *const 数据槽, _: usize, _: *mut 数据槽) -> i32 {
    1
}
