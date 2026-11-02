//! 工作区事务 —— 3120 创建/关闭仓外临时 Git 工作区，关闭前要求干净。
//!
//! 边界：临时根与仓库互不包含、工作区名固定 `v1-d4-<标识>`、归属记在临时根
//! `.v1-d4-state/<标识>.owner` —— 不是本组件建的工作区一律不碰。

use std::fs;
use std::path::Path;

use crate::错误码;

use super::基础件::{对象JSON, 工作区路径, 命令, 规范仓库, 验证工作区};

pub(crate) fn 工作区事务(参数: &[&str]) -> Result<Vec<u8>, u32> {
    let 操作 = 参数[0];
    let 仓库 = 规范仓库(参数[1])?;
    let 标识 = 参数[2];
    let 临时根 = Path::new(参数[3]);
    if !临时根.is_absolute() {
        return Err(错误码::受控边界不合法);
    }
    fs::create_dir_all(临时根).map_err(|_| 错误码::写入失败)?;
    let 临时根 = fs::canonicalize(临时根).map_err(|_| 错误码::写入失败)?;
    if 临时根.starts_with(&仓库) || 仓库.starts_with(&临时根) {
        eprintln!(
            "D4边界:根相交 仓库={} 临时根={}",
            仓库.display(),
            临时根.display()
        );
        return Err(错误码::受控边界不合法);
    }
    let 目标 = 工作区路径(&临时根, 标识)?;
    let 状态根 = 临时根.join(".v1-d4-state");
    let 标记 = 状态根.join(format!("{标识}.owner"));
    match 操作 {
        "创建" => {
            fs::create_dir_all(&状态根).map_err(|_| 错误码::写入失败)?;
            if 目标.exists() {
                return Err(错误码::文件已存在);
            }
            fs::create_dir_all(&目标).map_err(|_| 错误码::写入失败)?;
            if let Err(失败) = 命令(
                &仓库,
                [
                    "worktree",
                    "add",
                    "--detach",
                    目标.to_str().ok_or(错误码::受控边界不合法)?,
                    "HEAD",
                ],
            ) {
                let _ = fs::remove_dir_all(&目标);
                return Err(失败);
            }
            fs::write(&标记, 仓库.as_os_str().as_encoded_bytes()).map_err(|_| {
                let _ = fs::remove_dir_all(&目标);
                错误码::写入失败
            })?;
            Ok(对象JSON(&[
                ("状态", "已创建".into()),
                ("工作区", 目标.to_string_lossy().into_owned()),
                ("仓库", 仓库.to_string_lossy().into_owned()),
            ]))
        }
        "关闭" => {
            let 根 = 验证工作区(&目标)?;
            let 登记 = fs::read(&标记).map_err(|_| 错误码::受控边界不合法)?;
            if 登记 != 仓库.as_os_str().as_encoded_bytes() {
                return Err(错误码::受控边界不合法);
            }
            if !命令(&根, ["status", "--porcelain"])
                .map_err(|_| 错误码::回滚冲突或状态不干净)?
                .is_empty()
            {
                return Err(错误码::回滚冲突或状态不干净);
            }
            命令(
                &仓库,
                [
                    "worktree",
                    "remove",
                    "--force",
                    目标.to_str().ok_or(错误码::受控边界不合法)?,
                ],
            )
            .map_err(|_| 错误码::写入失败)?;
            let _ = fs::remove_file(&标记);
            let _ = fs::remove_dir_all(&状态根);
            let _ = fs::remove_dir_all(&目标);
            Ok(对象JSON(&[
                ("状态", "已关闭并清理".into()),
                ("工作区", 目标.to_string_lossy().into_owned()),
            ]))
        }
        _ => Err(错误码::参数不合法),
    }
}
