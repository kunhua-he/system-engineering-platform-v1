//! 装载件缓存 · 缓存落盘 —— 「把这段字节落到这条路径上」：路径对象 · 原子写入 · 复核。
//!
//! 从 `装载件缓存.rs` 拆出（单源 ≤ 500 行 · 拆法按关注点）：父件管编排，本件管**落**
//! 这一步的判据 —— 不判来源（已由父件判过）、不重判内容（已由父件判过）。
//!
//! # 脏件当未命中，安全性拒绝才是真停
//!
//! 长度 / 内容不符的缓存件**删掉当未命中**（缓存可丢可重建，装载能自身修好）；
//! 符号链接 / 非普通文件 / 权限位过宽**删了也照样不能落** ⇒ 如实报因，不假装未命中。

use std::fs;
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

pub(super) struct 临时件清理 {
    pub(super) 临时路径: PathBuf,
}

impl Drop for 临时件清理 {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.临时路径);
    }
}

/// **路径对象** —— 只回答「这条**落点**路径链能不能落」。
///
/// **不看内容、不看来源**：链上每一段要么还不存在（可以建），要么是**真目录**且不是符号链接。
/// 判的是路径链这个对象，与要落的字节是什么无关。
pub(super) fn 缓存路径对象(缓存根目录: &Path) -> Result<(), String> {
    for 目录路径 in 缓存根目录.ancestors() {
        if 目录路径.as_os_str().is_empty() {
            continue;
        }
        match fs::symlink_metadata(目录路径) {
            Ok(目录属性) if 目录属性.is_dir() && !目录属性.file_type().is_symlink() => {}
            Ok(_) => return Err(format!("缓存目录链含符号链接或非目录：{}", 目录路径.display())),
            Err(错误) if 错误.kind() == std::io::ErrorKind::NotFound => {}
            Err(错误) => return Err(format!("缓存目录检查失败：{错误}")),
        }
    }
    Ok(())
}

/// **缓存写入** —— 只回答「把这段字节**落到这条路径**上」，且可重入。
///
/// **不判来源**（来源已由 [`判定来源信任`] 判过）、**不重判内容**（内容已由 [`校验内容`] 判过，
/// 字节由调用方交进来）：写临时件 → `hard_link` 原子发布（同名已在即视为已写好）→ 复核落盘件。
pub(super) fn 写入缓存件(缓存根目录: &Path, 键名: &str, 能力码段: &[u8]) -> Result<PathBuf, String> {
    缓存路径对象(缓存根目录)?;
    fs::create_dir_all(缓存根目录).map_err(|错误| format!("建不出缓存目录：{错误}"))?;
    缓存路径对象(缓存根目录)?;
    let 落盘路径 = 缓存根目录.join(键名);
    if 验证缓存件(&落盘路径, 能力码段)? {
        return Ok(落盘路径);
    }
    let (临时清理, mut 临时文件) = 创建缓存临时件(缓存根目录, 键名)?;
    临时文件.write_all(能力码段)
        .and_then(|_| 临时文件.sync_all())
        .map_err(|错误| format!("缓存临时件写入或同步失败：{错误}"))?;
    drop(临时文件);
    缓存路径对象(缓存根目录)?;
    match fs::hard_link(&临时清理.临时路径, &落盘路径) {
        Ok(()) => {}
        Err(错误) if 错误.kind() == std::io::ErrorKind::AlreadyExists => {}
        Err(错误) => return Err(format!("缓存原子发布失败：{错误}")),
    }
    if !验证缓存件(&落盘路径, 能力码段)? {
        return Err("发布后的缓存件不存在".to_owned());
    }
    Ok(落盘路径)
}

/// **脏件当未命中** —— 校验不过的缓存件删掉，交回「没命中」，让调用方按原路重写。
///
/// **为什么删而不报错**：缓存件可丢可重建（文件头），而命中后校验不过只说明这一份坏了
/// （中断写入 / 别人动过）—— 报错就把「清一下再装」变成要人手动干的事，而装载本来能自身修好。
/// 删不掉（权限 / 被占用）才是真停：**如实报因**，不假装未命中（假装会连着失败且看不出为什么）。
fn 删脏件当未命中(落盘路径: &Path, 因由: &str) -> Result<bool, String> {
    fs::remove_file(落盘路径).map_err(|错误| {
        format!("缓存件{因由}（{}），且删不掉它：{错误}", 落盘路径.display())
    })?;
    Ok(false)
}

/// **复核落盘件** —— 只回答「这条路上现在那份字节是不是我要的那份」，`true` = 命中。
///
/// 校验不过的三类（长度不符 / 读不出 / 内容不符）**删该件当未命中**（缓存可重建）；
/// 符号链接 / 非普通文件 / 权限位过宽不在这三类里 —— 那是安全性拒绝，删了也照样不能落。
fn 验证缓存件(落盘路径: &Path, 能力码段: &[u8]) -> Result<bool, String> {
    let 缓存属性 = match fs::symlink_metadata(落盘路径) {
        Ok(缓存属性) => 缓存属性,
        Err(错误) if 错误.kind() == std::io::ErrorKind::NotFound => return Ok(false),
        Err(错误) => return Err(format!("缓存件检查失败：{错误}")),
    };
    if !缓存属性.is_file() || 缓存属性.file_type().is_symlink() {
        return Err("缓存目标是符号链接或非普通文件".to_owned());
    }
    // **权限位**：缓存件不许组/他人可写（`0o022` 位不为零即拒）。
    //
    // **为什么**：缓存件是 `dlopen` 的对象，而校验（指纹 / 长度 / 字节比对）与 `dlopen` 不是
    // 同一个瞬间 —— 别人能在中间改它，那校验过的就不是同一份字节（与「来源是符号链接即拒」
    // 同一条理由：**校验的对象必须是不可被第三方替换的那个东西**）。只在 unix 上判。
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let 模式位 = 缓存属性.permissions().mode();
        if 模式位 & 0o022 != 0 {
            return Err(format!(
                "缓存件权限位过宽：{} 的模式位是 {模式位:o}（组或他人可写）⇒ 拒",
                落盘路径.display()
            ));
        }
    }
    if 缓存属性.len() != 能力码段.len() as u64 {
        return 删脏件当未命中(落盘路径, "长度与能力码不符");
    }
    let mut 打开选项 = fs::OpenOptions::new();
    打开选项.read(true);
    #[cfg(any(target_os = "linux", target_os = "android"))]
    {
        use std::os::unix::fs::OpenOptionsExt;
        打开选项.custom_flags(0x20000);
    }
    #[cfg(target_vendor = "apple")]
    {
        use std::os::unix::fs::OpenOptionsExt;
        打开选项.custom_flags(0x100);
    }
    #[cfg(windows)]
    {
        use std::os::windows::fs::OpenOptionsExt;
        打开选项.custom_flags(0x00200000);
    }
    let 缓存文件 = match 打开选项.open(落盘路径) {
        Ok(缓存文件) => 缓存文件,
        Err(错误) => return 删脏件当未命中(落盘路径, &format!("读不出：{错误}")),
    };
    let 打开属性 = 缓存文件.metadata().map_err(|错误| format!("缓存句柄检查失败：{错误}"))?;
    if !打开属性.is_file() {
        return Err("缓存句柄不是普通文件".to_owned());
    }
    let mut 缓存字节 = Vec::new();
    if let Err(错误) = 缓存文件
        .take(能力码段.len() as u64 + 1)
        .read_to_end(&mut 缓存字节)
    {
        return 删脏件当未命中(落盘路径, &format!("读不出：{错误}"));
    }
    let 复核属性 = fs::symlink_metadata(落盘路径)
        .map_err(|错误| format!("缓存件复核失败：{错误}"))?;
    if !复核属性.is_file() || 复核属性.file_type().is_symlink() || 缓存字节 != 能力码段 {
        return 删脏件当未命中(落盘路径, "内容不符或目标被替换");
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        if 打开属性.dev() != 复核属性.dev() || 打开属性.ino() != 复核属性.ino() {
            return Err("缓存件读取期间目标被替换".to_owned());
        }
    }
    Ok(true)
}

pub(super) fn 创建缓存临时件(缓存根目录: &Path, 键名: &str) -> Result<(临时件清理, fs::File), String> {
    let 时间戳 = SystemTime::now().duration_since(UNIX_EPOCH)
        .map_err(|错误| format!("临时件时钟读取失败：{错误}"))?.as_nanos();
    for 临时序号 in 0..128 {
        let 临时路径 = 缓存根目录.join(format!(
            ".{键名}.{}.{时间戳}.{临时序号}.临时", std::process::id()
        ));
        match fs::OpenOptions::new().write(true).create_new(true).open(&临时路径) {
            Ok(临时文件) => return Ok((临时件清理 { 临时路径 }, 临时文件)),
            Err(错误) if 错误.kind() == std::io::ErrorKind::AlreadyExists => continue,
            Err(错误) => return Err(format!("缓存临时件创建失败：{错误}")),
        }
    }
    Err("缓存临时件名称竞争次数超限".to_owned())
}
