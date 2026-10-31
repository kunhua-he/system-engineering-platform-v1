use std::path::Path;

use crate::编号与码面::错误码;
use crate::规则切块::{组装块表载荷, 执行按规则切块};
use crate::规则载入::校验规则文本;
use crate::文本解码::{解码或失败, 输入上限字节};

// 内置支持清单与各格式默认规则（与消费方五组规则同口径的最小子集）
const 支持清单: &[(&str, &str)] = &[
    ("html", r#"{"切分模式":"html","单元模式表":[]}"#),
    ("htm", r#"{"切分模式":"html","单元模式表":[]}"#),
    ("js", r#"{"切分模式":"regex","单元模式表":["(?:export\\s+)?(?:async\\s+)?function\\s+\\w+","(?:export\\s+)?class\\s+\\w+","(?:export\\s+)?(?:const|let|var)\\s+\\w+"]}"#),
    ("ts", r#"{"切分模式":"regex","单元模式表":["(?:export\\s+)?(?:async\\s+)?function\\s+\\w+","(?:export\\s+)?class\\s+\\w+","(?:export\\s+)?(?:const|let|var)\\s+\\w+"]}"#),
    ("jsx", r#"{"切分模式":"regex","单元模式表":["(?:export\\s+)?(?:async\\s+)?function\\s+\\w+","(?:export\\s+)?class\\s+\\w+","(?:export\\s+)?(?:const|let|var)\\s+\\w+"]}"#),
    ("tsx", r#"{"切分模式":"regex","单元模式表":["(?:export\\s+)?(?:async\\s+)?function\\s+\\w+","(?:export\\s+)?class\\s+\\w+","(?:export\\s+)?(?:const|let|var)\\s+\\w+"]}"#),
    ("php", r#"{"切分模式":"regex","单元模式表":["function\\s+\\w+","(?:abstract\\s+|final\\s+)?class\\s+\\w+","interface\\s+\\w+","trait\\s+\\w+"]}"#),
    ("py", r#"{"切分模式":"python_ast","单元模式表":["^(?:async\\s+)?def\\s+\\w+","^class\\s+\\w+"]}"#),
    ("java", r#"{"切分模式":"regex","单元模式表":["(?:public|private|protected)\\s+[\\w<>\\s]+\\s+\\w+\\s*\\(","class\\s+\\w+","interface\\s+\\w+"]}"#),
    ("go", r#"{"切分模式":"regex","单元模式表":["func\\s+(?:\\([^)]*\\)\\s*)?\\w+","type\\s+\\w+\\s+struct","type\\s+\\w+\\s+interface"]}"#),
    ("c", r#"{"切分模式":"regex","单元模式表":["^\\s*(?:static\\s+)?\\w[\\w\\s\\*]*\\s+\\w+\\s*\\([^;]*$"]}"#),
    ("cpp", r#"{"切分模式":"regex","单元模式表":["^\\s*(?:static\\s+)?[\\w:<>,\\s\\*&]+\\s+\\w+::\\w+\\s*\\(","class\\s+\\w+"]}"#),
    ("cs", r#"{"切分模式":"regex","单元模式表":["(?:public|private|protected)\\s+[\\w<>\\s]+\\s+\\w+\\s*\\(","class\\s+\\w+","interface\\s+\\w+"]}"#),
    ("rb", r#"{"切分模式":"regex","单元模式表":["^\\s*def\\s+\\w+","^\\s*class\\s+\\w+","^\\s*module\\s+\\w+"]}"#),
    ("rs", r#"{"切分模式":"regex","单元模式表":["fn\\s+\\w+","struct\\s+\\w+","enum\\s+\\w+","impl\\s+\\w+","trait\\s+\\w+"]}"#),
    ("sh", r#"{"切分模式":"regex","单元模式表":["^\\s*(?:function\\s+)?\\w+\\s*\\(\\)\\s*\\{"]}"#),
    ("sql", r#"{"切分模式":"regex","单元模式表":["(?i)create\\s+(?:or\\s+replace\\s+)?(?:table|view|function|procedure)\\s+\\w+"]}"#),
];

pub fn 规范化扩展名(扩展名文本: &str) -> String {
    扩展名文本
        .trim()
        .trim_start_matches('.')
        .to_ascii_lowercase()
}

pub fn 内置规则(扩展名: &str) -> Result<serde_json::Value, u32> {
    let 规范名 = 规范化扩展名(扩展名);
    for (清单名, 规则文本) in 支持清单 {
        if *清单名 == 规范名 {
            return 校验规则文本(规则文本);
        }
    }
    Err(错误码::解析参数不合法)
}

pub fn 执行解析代码字节(原始字节: &[u8], 文件格式: &str, 编码名: &str) -> Result<String, u32> {
    let 规则对象 = 内置规则(文件格式)?;
    let 解码结果值 = 解码或失败(原始字节, 编码名)?;
    let 切块结果值 = 执行按规则切块(&解码结果值.文本值, &规则对象)?;
    let mut 载荷 = 组装块表载荷(&切块结果值);
    载荷["格式化"] = serde_json::Value::String(规范化扩展名(文件格式));
    载荷["编码"] = serde_json::Value::String(解码结果值.编码名);
    载荷["资源列表"] = serde_json::json!([]);
    serde_json::to_string(&载荷).map_err(|_| 错误码::解析内容不合法)
}

pub fn 执行解析代码文件(文件路径: &str, 扩展名: &str, 编码名: &str) -> Result<String, u32> {
    let 路径 = Path::new(文件路径);
    if !路径.is_absolute() || !路径.is_file() {
        return Err(错误码::解析规则不可读);
    }
    let 元数据 = std::fs::metadata(路径).map_err(|_| 错误码::解析规则不可读)?;
    if 元数据.len() > 输入上限字节 as u64 {
        return Err(错误码::解析资源受限);
    }
    let 字节 = std::fs::read(路径).map_err(|_| 错误码::解析规则不可读)?;
    执行解析代码字节(&字节, 扩展名, 编码名)
}

#[cfg(test)]
mod 测试 {
    use super::*;
    use std::sync::atomic::{AtomicU64, Ordering};

    fn 独立根() -> std::path::PathBuf {
        static 序号: AtomicU64 = AtomicU64::new(0);
        let 清单根 = std::env::temp_dir().join(format!(
            "代码解析业务测试-{}-{}",
            std::process::id(),
            序号.fetch_add(1, Ordering::Relaxed)
        ));
        std::fs::create_dir_all(&清单根).unwrap();
        清单根
    }

    #[test]
    fn 字节解析蟒样返回块列表() {
        let 结果文本 = 执行解析代码字节(
            "def 首函数():\n    速率值 = 1\n\ndef 次函数():\n    负载值 = 2\n".as_bytes(),
            "py",
            "utf-8",
        )
        .unwrap();
        let 载荷: serde_json::Value = serde_json::from_str(&结果文本).unwrap();
        assert_eq!(载荷["格式化"], "py");
        assert!(!载荷["块列表"].as_array().unwrap().is_empty());
    }

    #[test]
    fn 不支持格式拒绝() {
        let 解析结果 = 执行解析代码字节(b"x", "xyz", "utf-8");
        assert_eq!(解析结果.unwrap_err(), 错误码::解析参数不合法);
    }

    #[test]
    fn 带点大写扩展名同认() {
        let 解析结果 = 执行解析代码字节("function 首函数(){}".as_bytes(), ".JS", "utf-8");
        assert!(解析结果.is_ok());
    }

    #[test]
    fn 文件解析同构() {
        let 清单根 = 独立根();
        let 清单文件 = 清单根.join("样例.py");
        std::fs::write(&清单文件, "class 猫族:\n    腿数 = 4\n").unwrap();
        let 结果文本 = 执行解析代码文件(清单文件.to_str().unwrap(), "py", "utf-8").unwrap();
        let 载荷: serde_json::Value = serde_json::from_str(&结果文本).unwrap();
        assert!(!载荷["块列表"].as_array().unwrap().is_empty());
        assert!(载荷["块列表"].as_array().unwrap()[0]["文本"]
            .as_str()
            .unwrap()
            .contains("猫族"));
    }

    #[test]
    fn 文件不存在报规则不可读() {
        let 清单根 = 独立根();
        let 解析结果 = 执行解析代码文件(清单根.join("没有.py").to_str().unwrap(), "py", "utf-8");
        assert_eq!(解析结果.unwrap_err(), 错误码::解析规则不可读);
    }

    #[test]
    fn 资源列表恒空() {
        let 结果文本 = 执行解析代码字节("fn 主流程(){}".as_bytes(), "rs", "utf-8").unwrap();
        let 载荷: serde_json::Value = serde_json::from_str(&结果文本).unwrap();
        assert_eq!(载荷["资源列表"].as_array().unwrap().len(), 0);
    }
}
