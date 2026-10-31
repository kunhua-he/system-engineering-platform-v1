use crate::编号与码面::错误码;

#[derive(Debug)]
pub struct 源码块 {
    pub 块类型: &'static str,
    pub 块正文: String,
    pub 行起点: usize,
    pub 行终点: usize,
}

#[derive(Debug)]
pub struct 切块结果 {
    pub 块表: Vec<源码块>,
    pub 单元数: usize,
}

struct 规则面 {
    切分模式: String,
    单元模式表: Vec<regex::Regex>,
}

fn 取规则面(规则对象: &serde_json::Value) -> Result<规则面, u32> {
    let 切分模式 = 规则对象
        .get("切分模式")
        .and_then(serde_json::Value::as_str)
        .unwrap_or("")
        .to_owned();
    let mut 单元模式表 = Vec::new();
    if let Some(模式值表) = 规则对象.get("单元模式表").and_then(serde_json::Value::as_array) {
        for 模式值 in 模式值表 {
            let 模式串 = 模式值.as_str().ok_or(错误码::解析参数不合法)?;
            单元模式表.push(regex::Regex::new(模式串).map_err(|_| 错误码::解析参数不合法)?);
        }
    }
    Ok(规则面 {
        切分模式,
        单元模式表,
    })
}

/// 收集注释行的行号区间，切块时跳过（注释里的 `def` 不算单元）
fn 收集保护区间(行表: &[&str]) -> Vec<(usize, usize)> {
    let mut 区间表: Vec<(usize, usize)> = Vec::new();
    let mut 在块注释 = false;
    let mut 注释结束 = String::new();
    for (行号, 原行) in 行表.iter().enumerate() {
        let 净行 = 原行.trim_start();
        if 在块注释 {
            if 净行.contains(&注释结束) {
                在块注释 = false;
            }
            区间表.push((行号, 行号));
            continue;
        }
        if 净行.starts_with("//") || 净行.starts_with('#') || 净行.starts_with("--") {
            区间表.push((行号, 行号));
            continue;
        }
        if 净行.starts_with("/*") {
            在块注释 = !净行.contains("*/");
            注释结束 = "*/".to_owned();
            区间表.push((行号, 行号));
        }
    }
    区间表
}

fn 在保护区间内(保护区间表: &[(usize, usize)], 行号: usize) -> bool {
    保护区间表
        .iter()
        .any(|(段起点, 段终点)| 行号 >= *段起点 && 行号 <= *段终点)
}

fn 推块(块表: &mut Vec<源码块>, 行表: &[&str], 段起点: usize, 段终点: usize, 块类型: &'static str) {
    if 段起点 > 段终点 || 段终点 > 行表.len() {
        return;
    }
    let 块正文 = 行表[段起点..段终点].join("\n");
    if 块正文.trim().is_empty() {
        return;
    }
    块表.push(源码块 {
        块类型,
        块正文,
        行起点: 段起点 + 1,
        行终点: 段终点,
    });
}

fn 按单元切块(行表: &[&str], 规则面: &规则面) -> 切块结果 {
    let 保护区间表 = 收集保护区间(行表);
    let mut 块表: Vec<源码块> = Vec::new();
    let mut 单元数: usize = 0;
    let mut 段起点: usize = 0;
    for 行号 in 0..行表.len() {
        let 是空行 = 行表[行号].chars().all(|单字符| 单字符.is_whitespace());
        let 命中单元 = !是空行
            && !在保护区间内(&保护区间表, 行号)
            && 规则面
                .单元模式表
                .iter()
                .any(|模式| 模式.is_match(行表[行号]));
        if 命中单元 {
            if 段起点 < 行号 {
                推块(&mut 块表, 行表, 段起点, 行号, "代码块");
            }
            单元数 += 1;
            段起点 = 行号;
        }
    }
    if 段起点 < 行表.len() {
        推块(&mut 块表, 行表, 段起点, 行表.len(), "代码块");
    }
    切块结果 { 块表, 单元数 }
}

fn 按空行切块(行表: &[&str]) -> 切块结果 {
    let mut 块表: Vec<源码块> = Vec::new();
    let mut 段起点: usize = 0;
    for 行号 in 0..行表.len() {
        if 行表[行号].trim().is_empty() {
            if 段起点 < 行号 {
                推块(&mut 块表, 行表, 段起点, 行号, "文本块");
            }
            段起点 = 行号 + 1;
        }
    }
    if 段起点 < 行表.len() {
        推块(&mut 块表, 行表, 段起点, 行表.len(), "文本块");
    }
    let 单元数 = 块表.len();
    切块结果 { 块表, 单元数 }
}

fn 按超文本切块(行表: &[&str]) -> 切块结果 {
    // 标签行（以 < 开头、以 > 结尾的独立行）单独成标题块；其余按空行聚合
    let mut 块表: Vec<源码块> = Vec::new();
    let mut 段起点: usize = 0;
    for 行号 in 0..行表.len() {
        let 净行 = 行表[行号].trim();
        let 是标签行 = 净行.starts_with('<') && 净行.ends_with('>');
        if 是标签行 {
            if 段起点 < 行号 {
                推块(&mut 块表, 行表, 段起点, 行号, "文本块");
            }
            推块(&mut 块表, 行表, 行号, 行号 + 1, "标题块");
            段起点 = 行号 + 1;
        }
    }
    if 段起点 < 行表.len() {
        推块(&mut 块表, 行表, 段起点, 行表.len(), "文本块");
    }
    if 块表.is_empty() {
        return 按空行切块(行表);
    }
    let 单元数 = 块表.iter().filter(|块序号| 块序号.块类型 == "标题块").count();
    切块结果 { 块表, 单元数 }
}

pub fn 执行按规则切块(源码全文: &str, 规则对象: &serde_json::Value) -> Result<切块结果, u32> {
    let 规则面 = 取规则面(规则对象)?;
    let 行表: Vec<&str> = 源码全文.lines().collect();
    let 切块结果值 = match 规则面.切分模式.as_str() {
        "regex" | "python_ast" => 按单元切块(&行表, &规则面),
        "html" => 按超文本切块(&行表),
        _ => return Err(错误码::解析参数不合法),
    };
    if 切块结果值.块表.is_empty() && !源码全文.trim().is_empty() {
        // 保底：任何非空内容至少回一块，不静默丢内容
        let mut 块表: Vec<源码块> = Vec::new();
        推块(&mut 块表, &行表, 0, 行表.len(), "代码块");
        return Ok(切块结果 {
            块表,
            单元数: 0,
        });
    }
    Ok(切块结果值)
}

pub fn 组装块表载荷(切块结果值: &切块结果) -> serde_json::Value {
    let 块值表: Vec<serde_json::Value> = 切块结果值
        .块表
        .iter()
        .map(|块序号| {
            serde_json::json!({
                "块类型": 块序号.块类型,
                "文本": 块序号.块正文,
                "行起始": 块序号.行起点,
                "行结束": 块序号.行终点,
            })
        })
        .collect();
    serde_json::json!({
        "块列表": 块值表,
        "单元数": 切块结果值.单元数,
    })
}

#[cfg(test)]
mod 测试 {
    use super::*;

    fn 正则规则(模式表: &[&str]) -> serde_json::Value {
        serde_json::json!({"切分模式":"regex","单元模式表":模式表})
    }

    #[test]
    fn 函数单元切成多块() {
        let 源码全文 = "def 首函数():\n    return 1\n\ndef 次函数():\n    return 2\n";
        let 切块结果值 =
            执行按规则切块(源码全文, &正则规则(&["^(async\\s+)?def\\s+\\w+"])).unwrap();
        assert_eq!(切块结果值.单元数, 2);
        assert_eq!(切块结果值.块表.len(), 2);
        assert!(切块结果值.块表[0].块正文.contains("首函数"));
        assert!(切块结果值.块表[1].块正文.contains("次函数"));
        assert_eq!(切块结果值.块表[1].行起点, 4);
    }

    #[test]
    fn 注释里的伪单元不切() {
        let 源码全文 = "# def 伪单元():\n实际值 = 1\n";
        let 切块结果值 = 执行按规则切块(源码全文, &正则规则(&["^def\\s+\\w+"])).unwrap();
        // '#' 起始行按保护区间跳过 ⇒ 全文一块、单元数 0
        assert_eq!(切块结果值.单元数, 0);
    }

    #[test]
    fn 超文本标签行成标题块() {
        let 源码全文 = "<div>\n正文一段\n</div>\n";
        let 切块结果值 = 执行按规则切块(源码全文, &serde_json::json!({"切分模式":"html"})).unwrap();
        assert!(切块结果值.块表.iter().any(|块序号| 块序号.块类型 == "标题块"));
    }

    #[test]
    fn 未知模式拒绝() {
        let 切块结果值 = 执行按规则切块("x", &serde_json::json!({"切分模式":"猜"}));
        assert_eq!(切块结果值.unwrap_err(), 错误码::解析参数不合法);
    }

    #[test]
    fn 块正文拼接还原原文() {
        let 源码全文 = "首值 = 1\n\n次值 = 2\n";
        let 切块结果值 = 执行按规则切块(源码全文, &正则规则(&[])).unwrap();
        let 还原 = 切块结果值
            .块表
            .iter()
            .map(|块序号| 块序号.块正文.as_str())
            .collect::<Vec<_>>()
            .join("\n\n");
        assert_eq!(还原.trim_end(), 源码全文.trim_end());
    }
}
