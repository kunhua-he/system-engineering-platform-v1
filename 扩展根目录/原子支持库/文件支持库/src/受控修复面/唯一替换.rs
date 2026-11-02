//! 唯一替换 —— 3121 受控工作区内唯一旧文本原子替换。
//!
//! 旧文本必须**恰好出现一次**，否则 `精确替换不唯一` 且原件不动；
//! 落盘走同目录暂存 + 同步 + 改名，保留旧权限。

use std::fs;
use std::io::Write;
use std::path::Path;

use crate::错误码;

use super::基础件::{对象JSON, 验证工作区};
use super::路径与参数解析::路径内文件;

pub(super) fn 唯一文本替换(参数: &[&str]) -> Result<Vec<u8>, u32> {
    let 根 = 验证工作区(Path::new(参数[0]))?;
    let 文件 = 路径内文件(&根, 参数[1])?;
    let 原字节 = fs::read(&文件).map_err(|_| 错误码::读取被拒)?;
    let 原文 = std::str::from_utf8(&原字节).map_err(|_| 错误码::内容不合法)?;
    if 参数[2].is_empty() {
        return Err(错误码::精确替换不唯一);
    }
    let 次数 = 原文.match_indices(参数[2]).count();
    if 次数 != 1 {
        return Err(错误码::精确替换不唯一);
    }
    let 新文 = 原文.replacen(参数[2], 参数[3], 1);
    let 父 = 文件.parent().ok_or(错误码::写入失败)?;
    let 暂存 = 父.join(format!(
        ".v1-d4-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos()
    ));
    let 元 = 文件.metadata().map_err(|_| 错误码::读取被拒)?;
    let 结果 = (|| {
        let mut 项 = fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&暂存)?;
        项.write_all(新文.as_bytes())?;
        项.sync_all()?;
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            fs::set_permissions(
                &暂存,
                fs::Permissions::from_mode({
                    use std::os::unix::fs::MetadataExt;
                    元.mode() & 0o777
                }),
            )?;
        }
        fs::rename(&暂存, &文件)?;
        Ok::<(), std::io::Error>(())
    })();
    if 结果.is_err() {
        let _ = fs::remove_file(暂存);
        return Err(错误码::写入失败);
    }
    Ok(对象JSON(&[
        ("状态", "已唯一替换".into()),
        ("相对路径", 参数[1].into()),
        ("字节数", 新文.len().to_string()),
    ]))
}
