use std::collections::HashMap;
use std::path::Path;
use std::sync::Mutex;
use std::time::SystemTime;

use crate::编号与码面::错误码;

// 缓存条目同口径 1 MiB 上限；同一路径缓存规则文本与校验时刻
const 规则文件上限字节: u64 = 1048576;

struct 缓存条目 {
    内容文本: String,
    校验时刻: SystemTime,
}

static 规则表缓存: Mutex<Option<HashMap<String, 缓存条目>>> = Mutex::new(None);

fn 读文件与时刻(路径文本: &str) -> Result<(String, SystemTime), u32> {
    let 路径 = Path::new(路径文本);
    if !路径.is_absolute() || !路径.is_file() {
        return Err(错误码::解析规则不可读);
    }
    let 元数据 = std::fs::metadata(路径).map_err(|_| 错误码::解析规则不可读)?;
    if 元数据.len() > 规则文件上限字节 {
        return Err(错误码::解析资源受限);
    }
    let 修改时刻 = 元数据.modified().unwrap_or(SystemTime::UNIX_EPOCH);
    let 字节 = std::fs::read(路径).map_err(|_| 错误码::解析规则不可读)?;
    let 规则文本 = String::from_utf8(字节).map_err(|_| 错误码::解析内容不合法)?;
    Ok((规则文本, 修改时刻))
}

pub fn 校验规则文本(规则文本: &str) -> Result<serde_json::Value, u32> {
    let 规则对象: serde_json::Value =
        serde_json::from_str(规则文本).map_err(|_| 错误码::解析参数不合法)?;
    if !规则对象.is_object() {
        return Err(错误码::解析参数不合法);
    }
    let 切分模式 = 规则对象
        .get("切分模式")
        .and_then(serde_json::Value::as_str)
        .unwrap_or("");
    match 切分模式 {
        "regex" | "python_ast" => {
            let 模式值表 = 规则对象
                .get("单元模式表")
                .and_then(serde_json::Value::as_array)
                .ok_or(错误码::解析参数不合法)?;
            for 模式值 in 模式值表 {
                let 模式串 = 模式值.as_str().ok_or(错误码::解析参数不合法)?;
                regex::Regex::new(模式串).map_err(|_| 错误码::解析参数不合法)?;
            }
        }
        "html" => {}
        _ => return Err(错误码::解析参数不合法),
    }
    Ok(规则对象)
}

pub fn 执行载入切块规则(路径文本: &str, 强制重载: bool) -> Result<String, u32> {
    if 路径文本.is_empty() {
        return Err(错误码::解析参数不合法);
    }
    let mut 缓存守卫 = 规则表缓存
        .lock()
        .map_err(|_| 错误码::解析资源受限)?;
    let 缓存表 = 缓存守卫.get_or_insert_with(HashMap::new);
    if !强制重载
        && 缓存表
            .get(路径文本)
            .is_some_and(|条目| matches!(读文件与时刻(路径文本), Ok((_, 最新时刻)) if 最新时刻 == 条目.校验时刻))
    {
        // 缓存命中且文件未变（mtime 一致）才直接回
        return Ok(缓存表[路径文本].内容文本.clone());
    }
    let (规则文本, 修改时刻) = 读文件与时刻(路径文本)?;
    校验规则文本(&规则文本)?;
    缓存表.insert(
        路径文本.to_owned(),
        缓存条目 {
            内容文本: 规则文本.clone(),
            校验时刻: 修改时刻,
        },
    );
    Ok(规则文本)
}

pub fn 执行重载切块规则(路径文本: &str) -> Result<String, u32> {
    执行载入切块规则(路径文本, true)
}

#[cfg(test)]
mod 测试 {
    use super::*;
    use std::sync::atomic::{AtomicU64, Ordering};

    fn 独立根() -> std::path::PathBuf {
        static 序号: AtomicU64 = AtomicU64::new(0);
        let 清单根 = std::env::temp_dir().join(format!(
            "代码解析规则测试-{}-{}",
            std::process::id(),
            序号.fetch_add(1, Ordering::Relaxed)
        ));
        std::fs::create_dir_all(&清单根).unwrap();
        清单根
    }

    #[test]
    fn 载入合法规则回原文() {
        let 清单根 = 独立根();
        let 清单文件 = 清单根.join("规则.json");
        std::fs::write(&清单文件, r#"{"切分模式":"regex","单元模式表":["^def "]} "#).unwrap();
        let 载入结果 = 执行载入切块规则(清单文件.to_str().unwrap(), false).unwrap();
        assert!(载入结果.contains("单元模式表"));
    }

    #[test]
    fn 缺失路径报规则不可读() {
        let 清单根 = 独立根();
        let 载入结果 = 执行载入切块规则(清单根.join("没有.json").to_str().unwrap(), false);
        assert_eq!(载入结果.unwrap_err(), 错误码::解析规则不可读);
    }

    #[test]
    fn 相对路径报规则不可读() {
        let 载入结果 = 执行载入切块规则("相对/规则.json", false);
        assert_eq!(载入结果.unwrap_err(), 错误码::解析规则不可读);
    }

    #[test]
    fn 校验拒绝坏正则与未知模式() {
        assert_eq!(
            校验规则文本(r#"{"切分模式":"regex","单元模式表":["("]}"#).unwrap_err(),
            错误码::解析参数不合法
        );
        assert_eq!(
            校验规则文本(r#"{"切分模式":"未知"}"#).unwrap_err(),
            错误码::解析参数不合法
        );
    }

    #[test]
    fn 校验放行空单元模式的超文本模式() {
        校验规则文本(r#"{"切分模式":"html","单元模式表":[]}"#).unwrap();
    }

    #[test]
    fn 缓存命中与强制重载同回() {
        let 清单根 = 独立根();
        let 清单文件 = 清单根.join("规则.json");
        std::fs::write(&清单文件, r#"{"切分模式":"html"}"#).unwrap();
        let 路径文本 = 清单文件.to_str().unwrap().to_owned();
        let 首次 = 执行载入切块规则(&路径文本, false).unwrap();
        let 再取 = 执行载入切块规则(&路径文本, false).unwrap();
        let 强制 = 执行重载切块规则(&路径文本).unwrap();
        assert_eq!(首次, 再取);
        assert_eq!(首次, 强制);
    }
}
