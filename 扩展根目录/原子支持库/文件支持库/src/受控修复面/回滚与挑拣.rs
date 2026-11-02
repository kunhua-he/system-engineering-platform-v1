//! 回滚与挑拣 —— 3123 干净状态下回滚或挑拣合入，冲突自动中止并回读状态。
//!
//! 进来先要求干净、目标提交必须真实存在；git 失败就先 abort 再回 `回滚冲突或状态不干净`，
//! 不留半个冲突在现场。

use std::path::Path;

use crate::错误码;

use super::基础件::{命令, 对象JSON, 验证工作区};

pub(super) fn 受控回滚(参数: &[&str]) -> Result<Vec<u8>, u32> {
    let 根 = 验证工作区(Path::new(参数[0]))?;
    let 操作 = 参数[1];
    let 提交 = 参数[2];
    if 提交.is_empty() || 提交.starts_with('-') || !提交.chars().all(|字| 字.is_ascii_hexdigit())
    {
        return Err(错误码::参数不合法);
    }
    if !命令(&根, ["status", "--porcelain"])
        .map_err(|_| 错误码::回滚冲突或状态不干净)?
        .is_empty()
    {
        return Err(错误码::回滚冲突或状态不干净);
    }
    let 验证提交 = 命令(&根, ["cat-file", "-e", &format!("{提交}^{{commit}}")]);
    if 验证提交.is_err() {
        return Err(错误码::参数不合法);
    }
    let 调用结果 = match 操作 {
        "回滚" => 命令(&根, ["revert", "--no-edit", 提交]),
        "挑拣合入" => 命令(&根, ["cherry-pick", 提交]),
        _ => return Err(错误码::参数不合法),
    };
    if 调用结果.is_err() {
        match 操作 {
            "回滚" => {
                let _ = 命令(&根, ["revert", "--abort"]);
            }
            _ => {
                let _ = 命令(&根, ["cherry-pick", "--abort"]);
            }
        }
        let _状态 = 命令(&根, ["status", "--short"]).unwrap_or_else(|_| "状态读取失败".into());
        return Err(错误码::回滚冲突或状态不干净);
    }
    Ok(对象JSON(&[
        ("状态", "已完成".into()),
        ("操作", 操作.into()),
        ("提交", 提交.into()),
        (
            "工作区状态",
            命令(&根, ["status", "--short"]).unwrap_or_default(),
        ),
    ]))
}
