use crate::{能力号, 错误码};
use std::{
    fs,
    io::Write,
    path::{Component, Path, PathBuf},
    process::{Command, Stdio},
    time::{Duration, Instant},
};
use v1_contract::{数据槽, 类型标签};

fn 转义JSON(文本: &str) -> String {
    文本
        .chars()
        .flat_map(|字| match 字 {
            '"' => "\\\"".chars().collect::<Vec<_>>(),
            '\\' => "\\\\".chars().collect(),
            '\n' => "\\n".chars().collect(),
            '\r' => "\\r".chars().collect(),
            '\t' => "\\t".chars().collect(),
            c if c.is_control() => format!("\\u{:04x}", c as u32).chars().collect(),
            c => vec![c],
        })
        .collect()
}
fn 对象JSON(字段: &[(&str, String)]) -> Vec<u8> {
    format!(
        "{{{}}}",
        字段
            .iter()
            .map(|(键, 值)| format!("\"{}\":\"{}\"", 转义JSON(键), 转义JSON(值)))
            .collect::<Vec<_>>()
            .join(",")
    )
    .into_bytes()
}
fn 规范仓库(文本: &str) -> Result<PathBuf, u32> {
    let 路径 = Path::new(文本);
    if !路径.is_absolute() {
        return Err(错误码::受控边界不合法);
    }
    let 绝对 = fs::canonicalize(路径).map_err(|_| 错误码::文件不存在)?;
    if !绝对.is_dir()
        || 命令(&绝对, ["rev-parse", "--is-inside-work-tree"])
            .ok()
            .as_deref()
            != Some("true")
    {
        return Err(错误码::受控边界不合法);
    }
    Ok(绝对)
}
fn 命令<'a>(仓库: &Path, 参数: impl IntoIterator<Item = &'a str>) -> Result<String, u32> {
    let 输出 = Command::new("git")
        .arg("-C")
        .arg(仓库)
        .args(参数)
        .output()
        .map_err(|_| 错误码::写入失败)?;
    let 文本 = String::from_utf8_lossy(&输出.stdout).trim().to_owned();
    if 输出.status.success() {
        Ok(文本)
    } else {
        Err(错误码::写入失败)
    }
}
fn 安全标识(标识: &str) -> bool {
    !标识.is_empty()
        && 标识.len() <= 64
        && 标识
            .chars()
            .all(|字| 字.is_ascii_alphanumeric() || 字 == '-' || 字 == '_')
}
fn 工作区路径(根: &Path, 标识: &str) -> Result<PathBuf, u32> {
    if !安全标识(标识) {
        return Err(错误码::受控边界不合法);
    }
    let 目标 = 根.join(format!("v1-d4-{标识}"));
    if !目标.starts_with(根) {
        return Err(错误码::受控边界不合法);
    }
    Ok(目标)
}
fn 验证工作区(路径: &Path) -> Result<PathBuf, u32> {
    if !路径.is_absolute() {
        return Err(错误码::受控边界不合法);
    }
    let 根 = fs::canonicalize(路径).map_err(|_| 错误码::文件不存在)?;
    let 父目录 = 根.parent().ok_or(错误码::受控边界不合法)?;
    let 名称 = 根
        .file_name()
        .and_then(|项| 项.to_str())
        .ok_or(错误码::受控边界不合法)?;
    let 标识 = 名称
        .strip_prefix("v1-d4-")
        .filter(|项| 安全标识(项))
        .ok_or(错误码::受控边界不合法)?;
    let 标记 = 父目录.join(".v1-d4-state").join(format!("{标识}.owner"));
    let 仓库归属记录 = fs::read(标记).map_err(|_| 错误码::受控边界不合法)?;
    if !根.is_dir()
        || 命令(&根, ["rev-parse", "--is-inside-work-tree"])
            .ok()
            .as_deref()
            != Some("true")
    {
        return Err(错误码::受控边界不合法);
    }
    let 顶层 = 命令(&根, ["rev-parse", "--show-toplevel"])
        .map_err(|_| 错误码::受控边界不合法)?;
    let 顶层 = fs::canonicalize(顶层).map_err(|_| 错误码::受控边界不合法)?;
    let 仓库文本 =
        std::str::from_utf8(&仓库归属记录).map_err(|_| 错误码::受控边界不合法)?;
    let 仓库根 = fs::canonicalize(仓库文本).map_err(|_| 错误码::受控边界不合法)?;
    let 实际共用目录 = 命令(
        &根,
        ["rev-parse", "--path-format=absolute", "--git-common-dir"],
    )
    .map_err(|_| 错误码::受控边界不合法)?;
    let 实际共用目录 =
        fs::canonicalize(实际共用目录).map_err(|_| 错误码::受控边界不合法)?;
    let 预期共用目录 =
        fs::canonicalize(仓库根.join(".git")).map_err(|_| 错误码::受控边界不合法)?;
    if 顶层 != 根 || 实际共用目录 != 预期共用目录 {
        return Err(错误码::受控边界不合法);
    }
    Ok(根)
}
fn 标准槽(
    返回槽: *mut 数据槽,
    参数数: u32,
    参数槽: *const 数据槽,
    编号: u32,
    参数预期: usize,
) -> Result<Vec<Vec<u8>>, u32> {
    if 参数数 as usize != 参数预期 || 参数槽.is_null() || 返回槽.is_null() {
        return Err(错误码::参数不合法);
    }
    let 槽表 = unsafe { std::slice::from_raw_parts(参数槽, 参数数 as usize) };
    let mut 值表 = Vec::with_capacity(参数预期);
    for 槽 in 槽表 {
        if 槽.类型标签.取号值() != 4
            || !槽.是否引用()
            || 槽.槽字节长度 == 0
            || 槽.槽字节长度 > 65536
        {
            return Err(错误码::参数不合法);
        }
        let 字节 = unsafe {
            std::slice::from_raw_parts(槽.槽值 as *const u8, 槽.槽字节长度 as usize)
        };
        std::str::from_utf8(字节).map_err(|_| 错误码::参数不合法)?;
        值表.push(字节.to_vec());
    }
    let _ = 编号;
    Ok(值表)
}
unsafe fn 调用处理(
    返回槽: *mut 数据槽, 参数数: u32, 参数槽: *const 数据槽, 编号: u32
) {
    if 返回槽.is_null() {
        return;
    }
    let 结果 = (|| -> Result<Vec<u8>, u32> {
        let 个数 = match 编号 {
            3120 => 4,
            3121 => 4,
            3122 => 3,
            3123 => 3,
            _ => return Err(错误码::参数不合法),
        };
        let 入参 = 标准槽(返回槽, 参数数, 参数槽, 编号, 个数)?;
        let 文本表 = 入参
            .iter()
            .map(|项| std::str::from_utf8(项).map_err(|_| 错误码::参数不合法))
            .collect::<Result<Vec<_>, _>>()?;
        执行业务口(编号, &文本表)
    })();
    match 结果 {
        Ok(字节) => {
            let 长度 = 字节.len() as u64;
            let 指针 = Box::into_raw(字节.into_boxed_slice()) as *const u8;
            unsafe {
                *返回槽 = 数据槽::指针(类型标签::构造(4), 指针 as u64, 长度, true)
            };
        }
        Err(码) => unsafe {
            *返回槽 = 数据槽::内联槽(类型标签::构造(u32::MAX), 码 as u64, 4)
        },
    }
}
pub fn 执行业务口(编号: u32, 参数: &[&str]) -> Result<Vec<u8>, u32> {
    match 编号 {
        3120 => 工作区事务(参数),
        3121 => 唯一文本替换(参数),
        3122 => 受控验证(参数),
        3123 => 受控回滚(参数),
        _ => Err(错误码::参数不合法),
    }
}
fn 工作区事务(参数: &[&str]) -> Result<Vec<u8>, u32> {
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
fn 路径内文件(根: &Path, 相对: &str) -> Result<PathBuf, u32> {
    let 候选 = Path::new(相对);
    if 候选.is_absolute()
        || 候选.components().any(|片段| {
            matches!(
                片段,
                Component::ParentDir | Component::RootDir | Component::Prefix(_)
            )
        })
    {
        return Err(错误码::受控边界不合法);
    }
    let 根 = fs::canonicalize(根).map_err(|_| 错误码::文件不存在)?;
    let 完整 = 根.join(候选);
    let 父 = 完整.parent().ok_or(错误码::受控边界不合法)?;
    let 规范父 = fs::canonicalize(父).map_err(|_| 错误码::文件不存在)?;
    if !规范父.starts_with(&根)
        || fs::symlink_metadata(&完整)
            .map(|元| 元.file_type().is_symlink())
            .unwrap_or(false)
    {
        return Err(错误码::受控边界不合法);
    }
    let 元 = 完整.metadata().map_err(|_| 错误码::文件不存在)?;
    if !元.is_file() {
        return Err(错误码::不是普通文件);
    }
    Ok(完整)
}
fn 唯一文本替换(参数: &[&str]) -> Result<Vec<u8>, u32> {
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
fn 解析参数数组(文本: &str) -> Result<Vec<String>, u32> {
    let 字节 = 文本.as_bytes();
    let mut 位置 = 0;
    fn 空白(字节: &[u8], 位置: &mut usize) {
        while *位置 < 字节.len() && 字节[*位置].is_ascii_whitespace() {
            *位置 += 1
        }
    }
    空白(字节, &mut 位置);
    if 字节.get(位置) != Some(&b'[') {
        return Err(错误码::参数不合法);
    }
    位置 += 1;
    let mut 结果 = Vec::new();
    loop {
        空白(字节, &mut 位置);
        if 字节.get(位置) == Some(&b']') {
            位置 += 1;
            break;
        }
        if 字节.get(位置) != Some(&b'"') {
            return Err(错误码::参数不合法);
        }
        位置 += 1;
        let mut 当前 = String::new();
        let mut 完成 = false;
        while 位置 < 字节.len() {
            let 字 = 字节[位置];
            位置 += 1;
            match 字 {
                b'"' => {
                    完成 = true;
                    break;
                }
                b'\\' => {
                    let 转义 = *字节.get(位置).ok_or(错误码::参数不合法)?;
                    位置 += 1;
                    match 转义 {
                        b'"' => 当前.push('"'),
                        b'\\' => 当前.push('\\'),
                        b'n' => 当前.push('\n'),
                        b'r' => 当前.push('\r'),
                        b't' => 当前.push('\t'),
                        _ => return Err(错误码::参数不合法),
                    }
                }
                值 if 值 < 0x20 => return Err(错误码::参数不合法),
                值 if 值 >= 0x80 => {
                    let 起点 = 位置 - 1;
                    let 剩余文本 = std::str::from_utf8(&字节[起点..])
                        .map_err(|_| 错误码::参数不合法)?;
                    let 待解析字符 = 剩余文本.chars().next().ok_or(错误码::参数不合法)?;
                    当前.push(待解析字符);
                    位置 = 起点 + 待解析字符.len_utf8();
                }
                值 => 当前.push(值 as char),
            }
        }
        if !完成 {
            return Err(错误码::参数不合法);
        }
        结果.push(当前);
        空白(字节, &mut 位置);
        match 字节.get(位置) {
            Some(b',') => 位置 += 1,
            Some(b']') => {}
            _ => return Err(错误码::参数不合法),
        }
        if 字节.get(位置) == Some(&b']') {
            continue;
        }
    }
    空白(字节, &mut 位置);
    if 位置 != 字节.len()
        || 结果.is_empty()
        || 结果.len() > 128
        || 结果.iter().any(|项| 项.len() > 4096)
    {
        return Err(错误码::参数不合法);
    }
    Ok(结果)
}
fn 受控验证(参数: &[&str]) -> Result<Vec<u8>, u32> {
    let 根 = 验证工作区(Path::new(参数[0]))?;
    let 参数表 = 解析参数数组(参数[1])?;
    let 超时 = 参数[2].parse::<u64>().map_err(|_| 错误码::参数不合法)?;
    if !(1..=5000).contains(&超时) {
        return Err(错误码::参数不合法);
    }
    let mut 子进程 = Command::new(&参数表[0])
        .args(&参数表[1..])
        .current_dir(&根)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|_| 错误码::受控验证失败)?;
    let 开始 = Instant::now();
    let 状态 = loop {
        if let Some(退出) = 子进程.try_wait().map_err(|_| 错误码::受控验证失败)? {
            break Some(退出);
        }
        if 开始.elapsed() >= Duration::from_millis(超时) {
            let _ = 子进程.kill();
            break None;
        }
        std::thread::sleep(Duration::from_millis(10));
    };
    let 输出 = 子进程
        .wait_with_output()
        .map_err(|_| 错误码::受控验证失败)?;
    let 代码 = 状态.as_ref().and_then(|值| 值.code()).unwrap_or(-1);
    let 结果 = 对象JSON(&[
        ("退出码", 代码.to_string()),
        ("超时", 状态.is_none().to_string()),
        (
            "标准输出",
            String::from_utf8_lossy(&输出.stdout).into_owned(),
        ),
        (
            "标准错误",
            String::from_utf8_lossy(&输出.stderr).into_owned(),
        ),
        (
            "工作区状态",
            命令(&根, ["status", "--short"]).unwrap_or_else(|_| "状态读取失败".into()),
        ),
    ]);
    if 状态.is_none() || 代码 != 0 {
        Err(错误码::受控验证失败)
    } else {
        Ok(结果)
    }
}
fn 受控回滚(参数: &[&str]) -> Result<Vec<u8>, u32> {
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
pub unsafe extern "C-unwind" fn 受控工作区入口(
    返回槽: *mut 数据槽,
    参数数: u32,
    参数槽: *const 数据槽,
) {
    unsafe { 调用处理(返回槽, 参数数, 参数槽, 能力号::受控工作区) }
}
pub unsafe extern "C-unwind" fn 唯一文本替换入口(
    返回槽: *mut 数据槽,
    参数数: u32,
    参数槽: *const 数据槽,
) {
    unsafe { 调用处理(返回槽, 参数数, 参数槽, 能力号::唯一文本替换) }
}
pub unsafe extern "C-unwind" fn 受控验证入口(
    返回槽: *mut 数据槽,
    参数数: u32,
    参数槽: *const 数据槽,
) {
    unsafe { 调用处理(返回槽, 参数数, 参数槽, 能力号::受控验证) }
}
pub unsafe extern "C-unwind" fn 受控回滚入口(
    返回槽: *mut 数据槽,
    参数数: u32,
    参数槽: *const 数据槽,
) {
    unsafe { 调用处理(返回槽, 参数数, 参数槽, 能力号::受控回滚) }
}
#[cfg(test)]
mod 验证样本 {
    use super::*;
    use std::sync::atomic::{AtomicU64, Ordering};

    #[test]
    fn 参数数组分项解析() {
        assert_eq!(
            解析参数数组("[\"git\",\"status\",\"--short\"]").unwrap(),
            vec!["git", "status", "--short"]
        );
    }
    #[test]
    fn 参数数组拒绝命令拼接() {
        assert!(解析参数数组("git status").is_err());
    }

    #[test]
    fn 真实Git四原子正反验收() {
        static 序号: AtomicU64 = AtomicU64::new(0);
        let 根 = std::env::temp_dir().join(format!(
            "v1-d4-{}-{}",
            std::process::id(),
            序号.fetch_add(1, Ordering::Relaxed)
        ));
        let 仓库 = 根.join("仓库");
        let 临时根 = 根.join("仓外");
        std::fs::create_dir_all(&仓库).unwrap();
        fn 跑(目录: &Path, 参数: &[&str]) {
            assert!(
                Command::new("git")
                    .current_dir(目录)
                    .args(参数)
                    .status()
                    .unwrap()
                    .success(),
                "git {:?}",
                参数
            )
        }
        跑(&仓库, &["init", "-q"]);
        跑(&仓库, &["config", "user.email", "d4@example.test"]);
        跑(&仓库, &["config", "user.name", "D4 Test"]);
        std::fs::write(仓库.join("样本.txt"), "原始内容\n").unwrap();
        跑(&仓库, &["add", "样本.txt"]);
        跑(&仓库, &["commit", "-qm", "初始"]);
        let 仓库文本 = 仓库.to_str().unwrap();
        let 临时文本 = 临时根.to_str().unwrap();
        let 返回 = 工作区事务(&["创建", 仓库文本, "acceptance", 临时文本]).unwrap();
        let 返回文本 = String::from_utf8(返回).unwrap();
        assert!(返回文本.contains("已创建"));
        let 工作区 = std::fs::canonicalize(&临时根)
            .unwrap()
            .join("v1-d4-acceptance");
        let 工作区文本 = 工作区.to_str().unwrap();
        assert!(唯一文本替换(&[工作区文本, "样本.txt", "原始内容", "第一版内容"]).is_ok());
        assert_eq!(
            std::fs::read_to_string(工作区.join("样本.txt")).unwrap(),
            "第一版内容\n"
        );
        let 原件 = std::fs::read_to_string(工作区.join("样本.txt")).unwrap();
        assert_eq!(
            唯一文本替换(&[工作区文本, "样本.txt", "不存在", "第二版"]).unwrap_err(),
            错误码::精确替换不唯一
        );
        assert_eq!(
            std::fs::read_to_string(工作区.join("样本.txt")).unwrap(),
            原件
        );
        assert!(受控验证(&[工作区文本, "[\"git\",\"status\",\"--short\"]", "1000"]).is_ok());
        assert_eq!(
            受控验证(&[工作区文本, "[\"git\",\"status\",\"--short\"]", "0"]).unwrap_err(),
            错误码::参数不合法
        );
        assert_eq!(
            受控验证(&[工作区文本, "[\"sh\",\"-c\",\"exit 7\"]", "1000"]).unwrap_err(),
            错误码::受控验证失败
        );
        跑(&工作区, &["add", "样本.txt"]);
        跑(&工作区, &["commit", "-qm", "第一版"]);
        let 提交 = 命令(&工作区, ["rev-parse", "HEAD"]).unwrap();
        assert!(受控回滚(&[工作区文本, "回滚", &提交]).is_ok());
        std::fs::write(工作区.join("样本.txt"), "工作区冲突\n").unwrap();
        跑(&工作区, &["add", "样本.txt"]);
        跑(&工作区, &["commit", "-qm", "工作区改动"]);
        跑(&仓库, &["checkout", "-qb", "冲突目标"]);
        std::fs::write(仓库.join("样本.txt"), "目标冲突\n").unwrap();
        跑(&仓库, &["add", "样本.txt"]);
        跑(&仓库, &["commit", "-qm", "目标改动"]);
        let 目标 = 命令(&仓库, ["rev-parse", "HEAD"]).unwrap();
        assert_eq!(
            受控回滚(&[工作区文本, "挑拣合入", &目标]).unwrap_err(),
            错误码::回滚冲突或状态不干净
        );
        assert!(命令(&工作区, ["status", "--porcelain"]).unwrap().is_empty());
        assert!(工作区事务(&["关闭", 仓库文本, "acceptance", 临时文本]).is_ok());
        assert!(!工作区.exists());
        let _ = std::fs::remove_dir_all(&根);
    }
}
