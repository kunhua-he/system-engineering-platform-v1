//! 路径元信息 · 暂存残留清理（3117 · 3118）。

use crate::编号与码面::错误码;

use super::基础件::映射读错;


pub(super) fn 转义JSON片段(原文本: &str) -> String {
    原文本
        .replace('\\', "\\\\")
        .replace('"', "\\\"")
        .replace('\n', "\\n")
}


pub(super) fn 取路径元信息行(目标路径: &std::path::Path) -> Result<(u32, Vec<u8>), u32> {
    let 路径元信息 = std::fs::symlink_metadata(目标路径).map_err(映射读错)?;
    let 文件类型 = 路径元信息.file_type();
    let 类型文本 = if 文件类型.is_symlink() {
        "符号链接"
    } else if 文件类型.is_dir() {
        "目录"
    } else if 文件类型.is_file() {
        "文件"
    } else {
        "其他"
    };
    let 修改毫秒 = 路径元信息
        .modified()
        .ok()
        .and_then(|时点| 时点.duration_since(std::time::UNIX_EPOCH).ok())
        .map(|时长| 时长.as_millis() as i64)
        .unwrap_or(-1);
    #[cfg(unix)]
    let 权限八进制 = {
        use std::os::unix::fs::PermissionsExt as _;
        format!("{:o}", 路径元信息.permissions().mode() & 0o777)
    };
    #[cfg(not(unix))]
    let 权限八进制 = String::new();
    let 元信息文本 = format!(
        "{{\"类型\":\"{类型文本}\",\"字节数\":{},\"修改时间毫秒\":{修改毫秒},\"权限\":\"{权限八进制}\",\"是否符号链接\":\"{}\"}}",
        路径元信息.len(),
        if 文件类型.is_symlink() {
            "真"
        } else {
            "假"
        }
    );
    Ok((4, 元信息文本.into_bytes()))
}


pub(super) fn 清理暂存行(
    受控根: &std::path::Path,
    相对字节: &[u8],
    过期字节: &[u8],
) -> Result<(u32, Vec<u8>), u32> {
    let 目录文本 = std::str::from_utf8(相对字节).map_err(|_| 错误码::参数不合法)?;
    if 目录文本.contains('\0') {
        return Err(错误码::参数不合法);
    }
    let 目标目录 = if 目录文本.is_empty() {
        受控根.to_path_buf()
    } else {
        if 目录文本.split('/').any(|路径段| 路径段 == "..") {
            return Err(错误码::参数不合法);
        }
        受控根.join(目录文本)
    };
    let 过期文本 = std::str::from_utf8(过期字节)
        .map_err(|_| 错误码::参数不合法)?
        .trim();
    let 过期秒数 = if 过期文本.is_empty() || 过期文本 == "0" {
        300u64
    } else {
        过期文本.parse::<u64>().map_err(|_| 错误码::参数不合法)?
    };
    if 过期秒数 < 60 {
        return Err(错误码::参数不合法);
    }
    let 记录时刻 = std::time::SystemTime::now();
    let mut 清理件数: u64 = 0;
    for 目录条目 in std::fs::read_dir(&目标目录).map_err(映射读错)?.flatten() {
        let 条目名 = match 目录条目.file_name().to_str() {
            Some(值) => 值.to_string(),
            None => continue,
        };
        let 暂存余部 = match 条目名.strip_prefix(".原子写入-") {
            Some(值) => 值,
            None => continue,
        };
        let mut 字段段 = 暂存余部.split('-');
        let 暂存进程号 = 字段段.next();
        if 暂存进程号.is_none() || 字段段.next().is_none() {
            continue;
        }
        let 改动时刻 = match 目录条目.metadata().and_then(|元信息| 元信息.modified()) {
            Ok(值) => 值,
            Err(_) => continue,
        };
        if 记录时刻
            .duration_since(改动时刻)
            .map(|时长| 时长.as_secs())
            .unwrap_or(0)
            < 过期秒数
        {
            continue;
        }
        if std::fs::remove_file(目录条目.path()).is_ok() {
            清理件数 += 1;
        }
    }
    Ok((1, 清理件数.to_le_bytes().to_vec()))
}


#[cfg(test)]
mod 元信息与清理验证样本 {
    use super::*;
    use std::fs;

    fn 造清理根(唯一名: &str) -> std::path::PathBuf {
        let 样本根 =
            std::env::temp_dir().join(format!("v1清理样本-{唯一名}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&样本根);
        fs::create_dir_all(样本根.join("写入层")).unwrap();
        样本根
    }

    #[test]
    fn 取路径元信息字段完整() {
        let 样本根 = 造清理根("元信息");
        let 件路径 = 样本根.join("样本文本.txt");
        fs::write(&件路径, "五个汉字表".as_bytes()).unwrap();
        let (标签值, 返回字节) = 取路径元信息行(&件路径).unwrap();
        assert_eq!(标签值, 4);
        let 全文文本 = std::str::from_utf8(&返回字节).unwrap();
        assert!(全文文本.contains("\"类型\":\"文件\""), "{全文文本}");
        assert!(全文文本.contains("\"字节数\":15"), "{全文文本}");
        assert!(全文文本.contains("\"是否符号链接\":\"假\""), "{全文文本}");
        assert!(!全文文本.contains("\"权限\":\"\""), "{全文文本}");
        let _ = fs::remove_dir_all(&样本根);
    }

    #[test]
    fn 取路径元信息目录类型() {
        let 样本根 = 造清理根("目录型");
        let (_, 返回字节) = 取路径元信息行(&样本根.join("写入层")).unwrap();
        assert!(
            std::str::from_utf8(&返回字节)
                .unwrap()
                .contains("\"类型\":\"目录\"")
        );
        let _ = fs::remove_dir_all(&样本根);
    }

    #[test]
    fn 取路径元信息不存在被拒() {
        let 样本根 = 造清理根("缺失");
        assert_eq!(
            取路径元信息行(&样本根.join("没有这层")).unwrap_err(),
            错误码::文件不存在
        );
        let _ = fs::remove_dir_all(&样本根);
    }

    #[test]
    fn 清理暂存不动活跃件() {
        let 样本根 = 造清理根("活跃");
        let 写入层 = 样本根.join("写入层");
        let 暂存件 = 写入层.join(".原子写入-999999-0");
        fs::write(&暂存件, "半截".as_bytes()).unwrap();
        fs::write(写入层.join("正常件.txt"), "内容".as_bytes()).unwrap();
        let (标签值, 返回字节) =
            清理暂存行(&样本根, "写入层".as_bytes(), 空标记().as_bytes()).unwrap();
        assert_eq!(标签值, 1);
        assert_eq!(
            u64::from_le_bytes(返回字节.as_slice().try_into().unwrap()),
            0
        );
        assert!(暂存件.exists(), "新暂存件不该被删");
        assert!(写入层.join("正常件.txt").exists());
        let _ = fs::remove_dir_all(&样本根);
    }

    #[test]
    fn 清理暂存过期秒数过小被拒() {
        let 样本根 = 造清理根("秒数");
        assert_eq!(
            清理暂存行(&样本根, "".as_bytes(), "30".as_bytes()).unwrap_err(),
            错误码::参数不合法
        );
        assert_eq!(
            清理暂存行(&样本根, "".as_bytes(), "不是数字".as_bytes()).unwrap_err(),
            错误码::参数不合法
        );
        let _ = fs::remove_dir_all(&样本根);
    }

    #[test]
    fn 清理暂存上跳被拒() {
        let 样本根 = 造清理根("上跳");
        assert_eq!(
            清理暂存行(&样本根, "../上级".as_bytes(), "".as_bytes()).unwrap_err(),
            错误码::参数不合法
        );
        let _ = fs::remove_dir_all(&样本根);
    }

    #[test]
    fn 原子写放宽后可写大文本() {
        let 样本根 = 造清理根("大文本");
        let 大文本 = "字".repeat(70000);
        assert!(大文本.len() > 131072, "样本必须超过旧上界");
        let 写入字节 = crate::受控写入面::原子写入文本(
            样本根.to_str().unwrap(),
            "大文本.txt",
            &大文本,
        )
        .unwrap();
        assert_eq!(写入字节, 大文本.len() as i64);
        let _ = fs::remove_dir_all(&样本根);
    }

    fn 空标记() -> &'static str {
        ""
    }
}
