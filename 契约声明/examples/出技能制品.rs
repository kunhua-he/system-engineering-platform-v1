//! 出技能制品 —— 把一份技能本体 md 装进 `.技能制品`（技能本体段 `19`）。
//!
//! 怎么跑（在仓根）：
//!
//! ```sh
//! cargo run --quiet --locked -p v1-contract --example 出技能制品 -- <技能目录>
//! ```
//!
//! `<技能目录>` 由调用方给（含 `说明.md`）；**本 bin 不认识任何扩展名**（README §五 硬边界 1）。
//!
//! # 它走的链就是「技能」那一条
//!
//! 1. 读 `<技能目录>/说明.md`（技能本体，UTF-8）；
//! 2. 六字段（接口说明段）字面写死 —— 与 `能力声明/8200.json` 逐条同名同序；
//! 3. `容器::装包技能`（唯一 codec）装包：接口说明段 `16` + 技能本体段 `19` + 指纹段 `18`；
//! 4. **往返断言**：`容器::取技能本体文本` 取回 == 原 md（**只取文、不执行**）。
//!
//! # 技能无码段（如实登记，不是偷工）
//!
//! 技能**不含实现**（`扩展装载/开发标准/必备件.json` 的「技能」行：码段=无）⇒ 没有能力码段，
//! 本 bin 不编任何机器码，也不进 `dlopen`。

use std::fs;
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use v1_contract::容器;
use v1_contract::接口说明段::{self, 接口说明};

fn main() -> ExitCode {
    let 命令行参数: Vec<String> = std::env::args().skip(1).collect();
    let 技能目录 = match 命令行参数.first() {
        Some(目录参数) => PathBuf::from(目录参数),
        None => {
            eprintln!("用法：出技能制品 -- <技能目录>（含 说明.md）");
            return ExitCode::from(2);
        }
    };
    match 出制品(&技能目录) {
        Ok(编号) => {
            println!("出技能制品：{} · 能力 {}", 技能目录.display(), 编号);
            ExitCode::SUCCESS
        }
        Err(失败原因) => {
            eprintln!("出技能制品失败：{失败原因}");
            ExitCode::FAILURE
        }
    }
}

/// 一个技能目录 → 写出 `.技能制品`，返回它自述的能力号。
fn 出制品(技能目录: &Path) -> Result<u32, String> {
    let 技能名 = 技能目录
        .file_name()
        .and_then(|名称| 名称.to_str())
        .ok_or_else(|| format!("从 {} 取不出技能名", 技能目录.display()))?
        .to_owned();
    let 本体件 = 技能目录.join("说明.md");
    let 技能文本 = fs::read_to_string(&本体件)
        .map_err(|错误| format!("读不到 {}：{错误}", 本体件.display()))?;

    // 六字段（与 能力声明/8200.json 逐条同名同序；技能返回类型 = 文本 4，无参数、无错误码）。
    let 说明 = 接口说明 {
        编号: 8200,
        名称: "取技能说明".to_owned(),
        说明: "取回本技能（8200–8249）的本体文本 —— 即 `说明.md` 的 md 正文。**只取文、不执行**：技能不含实现、无码段，底座解析 `.技能制品` 的**技能本体段 19** 并返回 UTF-8 文本。".to_owned(),
        参数表: Vec::new(),
        返回类型: 4,
        可抛错误码: Vec::new(),
    };
    let 接口说明段字节 = 接口说明段::编码(&说明);

    // 装包（唯一 codec）：接口说明 16 + 技能本体 19 + 指纹 18。
    let 包件字节 = 容器::装包技能(&接口说明段字节, &技能文本)
        .map_err(|错误| format!("装包失败：{错误:?}"))?;

    // 往返断言：只取文 == 原 md；接口说明段逐字段比一次；指纹自校。
    let 回读文本 = 容器::取技能本体文本(&包件字节).map_err(|错误| format!("取文失败：{错误:?}"))?;
    if 回读文本 != 技能文本 {
        return Err("往返不一致：取回的文本与 说明.md 对不上".to_owned());
    }
    let 解出包件 = 容器::解包类型化(&包件字节).map_err(|错误| format!("装出来的包拆不开：{错误:?}"))?;
    if 解出包件.本体段类别 != 容器::本体段类别::技能本体 {
        return Err("本体段类别不是技能本体".to_owned());
    }
    if 解出包件.接口说明段 != 接口说明段字节 {
        return Err("接口说明段往返不一致".to_owned());
    }
    if 容器::校验段指纹(&包件字节) != Some(true) {
        return Err("指纹段自校验不过".to_owned());
    }

    let 制品件 = 技能目录.join(format!("{技能名}.技能制品"));
    fs::write(&制品件, &包件字节).map_err(|错误| format!("写不到 {}：{错误}", 制品件.display()))?;
    println!(
        "  本体 {} → 制品 {}（{} 字节）",
        本体件.display(),
        制品件.display(),
        包件字节.len()
    );
    Ok(说明.编号)
}
