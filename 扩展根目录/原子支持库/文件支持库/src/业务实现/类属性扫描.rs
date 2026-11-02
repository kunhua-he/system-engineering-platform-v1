//! 扫 py 类属性字符串常量（3119）。

use crate::编号与码面::错误码;

use super::路径状态与清理::转义JSON片段;


pub(super) fn 扫描类属性行(
    扫描根: &std::path::Path,
    属性字节: &[u8],
    排除字节: &[u8],
) -> Result<(u32, Vec<u8>), u32> {
    let 目标属性名 = std::str::from_utf8(属性字节)
        .map_err(|_| 错误码::参数不合法)?
        .trim();
    if 目标属性名.is_empty()
        || 目标属性名.len() > 128
        || !目标属性名
            .chars()
            .all(|单字| 单字.is_ascii_alphanumeric() || 单字 == '_')
    {
        return Err(错误码::参数不合法);
    }
    let 排除文本 = std::str::from_utf8(排除字节).map_err(|_| 错误码::参数不合法)?;
    let 排除表: Vec<&str> = 排除文本
        .split(',')
        .map(|单段| 单段.trim())
        .filter(|单段| !单段.is_empty())
        .collect();
    if !扫描根.is_dir() {
        return Err(错误码::文件不存在);
    }
    let mut 结果值表: Vec<String> = Vec::new();
    let mut 待扫目录表: Vec<(std::path::PathBuf, u32)> = vec![(扫描根.to_path_buf(), 0)];
    let mut 已扫件数: usize = 0;
    while let Some((当前目录, 目录层级)) = 待扫目录表.pop() {
        if 目录层级 > 8 {
            continue;
        }
        let 读取目录 = match std::fs::read_dir(&当前目录) {
            Ok(值) => 值,
            Err(_) => continue,
        };
        for 目录条目 in 读取目录.flatten() {
            let 条目路径 = 目录条目.path();
            let 条目名 = match 条目路径.file_name().and_then(|末段| 末段.to_str()) {
                Some(值) => 值.to_string(),
                None => continue,
            };
            if 排除表
                .iter()
                .any(|关键字| 条目路径.to_string_lossy().contains(关键字))
            {
                continue;
            }
            if 条目路径.is_dir() {
                待扫目录表.push((条目路径, 目录层级 + 1));
                continue;
            }
            if !条目名.ends_with(".py") {
                continue;
            }
            已扫件数 += 1;
            if 已扫件数 > 2000 {
                return Err(错误码::资源受限);
            }
            let 文件属性 = match 目录条目.metadata() {
                Ok(值) => 值,
                Err(_) => continue,
            };
            if 文件属性.len() > 4_194_304 {
                continue;
            }
            let 源码文本 = match std::fs::read_to_string(&条目路径) {
                Ok(值) => 值,
                Err(_) => continue,
            };
            for 源码行 in 源码文本.lines() {
                if let Some(类属性值) = 取类属性值(源码行, 目标属性名)
                    && !结果值表.iter().any(|已有值| 已有值 == &类属性值)
                {
                    结果值表.push(类属性值);
                }
            }
        }
    }
    结果值表.sort();
    let 拼接文本 = 结果值表
        .iter()
        .map(|单值| format!("\"{}\"", 转义JSON片段(单值)))
        .collect::<Vec<_>>()
        .join(",");
    Ok((4, format!("[{拼接文本}]").into_bytes()))
}


pub(super) fn 取类属性值(源码行: &str, 目标属性名: &str) -> Option<String> {
    let 去空行 = 源码行.trim_start();
    let 余部文本 = 去空行.strip_prefix(目标属性名)?;
    let 首字符 = 余部文本.chars().next()?;
    if !(首字符.is_whitespace() || 首字符 == ':' || 首字符 == '=') {
        return None;
    }
    let 余部文本 = 余部文本.trim_start();
    let 余部文本 = if let Some(注解段) = 余部文本.strip_prefix(':') {
        &注解段[注解段.find('=')?..]
    } else {
        余部文本
    };
    let 余部文本 = 余部文本.strip_prefix('=')?.trim_start();
    let 引号字符 = 余部文本.chars().next()?;
    if 引号字符 != '"' && 引号字符 != '\'' {
        return None;
    }
    let 引号内文 = &余部文本[引号字符.len_utf8()..];
    let 结束位 = 引号内文.find(引号字符)?;
    Some(引号内文[..结束位].to_string())
}


#[cfg(test)]
mod 类属性扫描验证样本 {
    use super::*;
    use std::fs;

    fn 造扫描根(唯一名: &str) -> std::path::PathBuf {
        let 样本根 =
            std::env::temp_dir().join(format!("v1类属性样本-{唯一名}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&样本根);
        fs::create_dir_all(&样本根).unwrap();
        样本根
    }

    fn 写模型(样本根: &std::path::Path, 相对路径: &str, 样本源码: &str) {
        let 目标 = 样本根.join(相对路径);
        if let Some(父目录) = 目标.parent() {
            fs::create_dir_all(父目录).unwrap();
        }
        fs::write(目标, 样本源码.as_bytes()).unwrap();
    }

    #[test]
    fn 扫描类属性收集与去重() {
        let 样本根 = 造扫描根("收集");
        写模型(
            &样本根,
            "主模块/后端/模型.py",
            "class 主类(Base):\n    __tablename__ = \"业务表\"\n",
        );
        写模型(
            &样本根,
            "副模块/后端/模型.py",
            "class 副类(Base):\n    __tablename__ = \"另一表\"\n    __tablename__ = \"业务表\"\n",
        );
        let (标签值, 返回字节) =
            扫描类属性行(&样本根, "__tablename__".as_bytes(), "".as_bytes()).unwrap();
        assert_eq!(标签值, 4);
        let 扫描结果文本 = std::str::from_utf8(&返回字节).unwrap();
        assert_eq!(扫描结果文本, "[\"业务表\",\"另一表\"]");
        let _ = fs::remove_dir_all(&样本根);
    }

    #[test]
    fn 扫描类属性排除关键字() {
        let 样本根 = 造扫描根("排除");
        写模型(
            &样本根,
            "正式模块/后端/模型.py",
            "    __tablename__ = \"正式表\"\n",
        );
        写模型(
            &样本根,
            "正式模块/后端/测试_模型.py",
            "    __tablename__ = \"测试表\"\n",
        );
        let (_, 返回字节) =
            扫描类属性行(&样本根, "__tablename__".as_bytes(), "测试".as_bytes()).unwrap();
        assert_eq!(std::str::from_utf8(&返回字节).unwrap(), "[\"正式表\"]");
        let _ = fs::remove_dir_all(&样本根);
    }

    #[test]
    fn 扫描类属性注解与边界() {
        let 样本根 = 造扫描根("注解");
        写模型(
            &样本根,
            "模型包/后端/模型.py",
            "    __tablename__: str = '注解表'\n    __tablename__片段 = \"不该收\"\n    __tablename__ = 12345\n",
        );
        let (_, 返回字节) =
            扫描类属性行(&样本根, "__tablename__".as_bytes(), "".as_bytes()).unwrap();
        assert_eq!(std::str::from_utf8(&返回字节).unwrap(), "[\"注解表\"]");
        let _ = fs::remove_dir_all(&样本根);
    }

    #[test]
    fn 扫描类属性目录不存在被拒() {
        let 样本根 = 造扫描根("缺目录");
        assert_eq!(
            扫描类属性行(
                &样本根.join("没有这层"),
                "__tablename__".as_bytes(),
                "".as_bytes()
            )
            .unwrap_err(),
            错误码::文件不存在
        );
        let _ = fs::remove_dir_all(&样本根);
    }

    #[test]
    fn 扫描类属性空属性名被拒() {
        let 样本根 = 造扫描根("空名");
        assert_eq!(
            扫描类属性行(&样本根, "".as_bytes(), "".as_bytes()).unwrap_err(),
            错误码::参数不合法
        );
        assert_eq!(
            扫描类属性行(&样本根, "__表格__".as_bytes(), "".as_bytes()).unwrap_err(),
            错误码::参数不合法
        );
        let _ = fs::remove_dir_all(&样本根);
    }
}
