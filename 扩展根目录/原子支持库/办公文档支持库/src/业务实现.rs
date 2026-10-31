use std::io::{Read, Write};

use crate::编号与码面::{能力号, 错误码};

const 最大公式长度: usize = 4096;
const 最大变量个数: usize = 256;
const 最大标记长度: usize = 262144;

pub fn 执行文本操作(编号: u32, 参数表: &[&str]) -> Result<(u32, Vec<u8>), u32> {
    if 编号 == 能力号::求值公式 {
        let 公式文本 = 取第几项文本(参数表, 0)?;
        let 变量文本 = 取第几项文本(参数表, 1)?;
        if 公式文本.chars().count() > 最大公式长度 {
            return Err(错误码::内容不合法);
        }
        let 变量表 = 解析变量表(变量文本)?;
        let 算式结果 = 求值(公式文本, &变量表)?;
        return Ok((4, 数值转文本(算式结果).into_bytes()));
    }
    if 编号 == 能力号::检查转换提供者 {
        return Ok((4, crate::格式转换::检查提供者实现(取第几项文本(参数表, 0)?)?.into_bytes()));
    }
    if 编号 == 能力号::转换办公文件 {
        return Ok((4, crate::格式转换::转换办公实现(
            取第几项文本(参数表, 0)?,
            取第几项文本(参数表, 1)?,
            取第几项文本(参数表, 2)?,
            取第几项文本(参数表, 3)?,
        )?.into_bytes()));
    }
    if 编号 == 能力号::转换文本文件 {
        return Ok((4, crate::格式转换::转换文本实现(
            取第几项文本(参数表, 0)?,
            取第几项文本(参数表, 1)?,
            取第几项文本(参数表, 2)?,
            取第几项文本(参数表, 3)?,
        )?.into_bytes()));
    }
    if 编号 == 能力号::解析标记块 {
        let 源文本 = 取第几项文本(参数表, 0)?;
        if 源文本.len() > 最大标记长度 {
            return Err(错误码::内容不合法);
        }
        let 块列表 = 切分块(源文本);
        return Ok((4, 组装块JSON(&块列表).into_bytes()));
    }
    if 编号 == 能力号::解析纯文本 { let 源文本 = 取第几项文本(参数表, 0)?; return Ok((4, crate::表格地址解析::解析纯文本(源文本)?.into_bytes())); }
    if 编号 == 能力号::解析表格单元格地址 { let 地址文本 = 取第几项文本(参数表, 0)?; return Ok((4, crate::表格地址解析::解析地址文本(地址文本)?.into_bytes())); }
    if 编号 == 能力号::格式化表格单元格地址 { let 结构文本 = 取第几项文本(参数表, 0)?; return Ok((4, crate::表格地址解析::格式化地址文本(结构文本)?.into_bytes())); }
    if 编号 == 能力号::解析DOCX {
        let 文件路径 = 取第几项文本(参数表, 0)?;
        return Ok((4, 解析DOCX文档(文件路径)?.into_bytes()));
    }
    if 编号 == 能力号::生成DOCX {
        let 内容文本 = 取第几项文本(参数表, 0)?;
        let 输出路径 = 取第几项文本(参数表, 1)?;
        return Ok((4, 生成DOCX文档(内容文本, 输出路径)?.into_bytes()));
    }
    if 编号 == 能力号::生成PPTX {
        let 演示内容 = 取第几项文本(参数表, 0)?;
        let 输出路径 = 取第几项文本(参数表, 1)?;
        return Ok((4, 生成PPTX文档(演示内容, 输出路径)?.into_bytes()));
    }
    if 编号 == 能力号::解析PPTX {
        let 文件路径 = 取第几项文本(参数表, 0)?;
        return Ok((4, 解析PPTX文档(文件路径)?.into_bytes()));
    }
    if 编号 == 能力号::检查页面结构 {
        let 文件路径 = 取第几项文本(参数表, 0)?;
        return Ok((4, crate::页面结构::检查页面结构(文件路径)?.into_bytes()));
    }
    Err(错误码::参数不合法)
}

fn 取第几项文本<'a>(参数表: &'a [&'a str], 序位: usize) -> Result<&'a str, u32> {
    match 参数表.get(序位) {
        Some(候选文本) => Ok(*候选文本),
        None => Err(错误码::参数不合法),
    }
}

// ── 公式求值：四则运算 + 括号 + 变量名 ──────────────────────────

fn 求值(公式文本: &str, 变量表: &[(String, f64)]) -> Result<f64, u32> {
    let 字序: Vec<char> = 公式文本.chars().filter(|单字元| !单字元.is_whitespace()).collect();
    if 字序.is_empty() {
        return Err(错误码::计算失败);
    }
    let mut 游标 = 0usize;
    let 结果值 = 解析加减(&字序, &mut 游标, 变量表)?;
    if 游标 != 字序.len() {
        return Err(错误码::计算失败);
    }
    if !结果值.is_finite() {
        return Err(错误码::计算失败);
    }
    Ok(结果值)
}

fn 解析加减(字序: &[char], 游标: &mut usize, 变量表: &[(String, f64)]) -> Result<f64, u32> {
    let mut 累积值 = 解析乘除(字序, 游标, 变量表)?;
    while *游标 < 字序.len() {
        let 运算符 = 字序[*游标];
        if 运算符 != '+' && 运算符 != '-' {
            break;
        }
        *游标 += 1;
        let 右值 = 解析乘除(字序, 游标, 变量表)?;
        累积值 = if 运算符 == '+' { 累积值 + 右值 } else { 累积值 - 右值 };
    }
    Ok(累积值)
}

fn 解析乘除(字序: &[char], 游标: &mut usize, 变量表: &[(String, f64)]) -> Result<f64, u32> {
    let mut 累积值 = 解析单元(字序, 游标, 变量表)?;
    while *游标 < 字序.len() {
        let 运算符 = 字序[*游标];
        if 运算符 != '*' && 运算符 != '/' {
            break;
        }
        *游标 += 1;
        let 右值 = 解析单元(字序, 游标, 变量表)?;
        if 运算符 == '*' {
            累积值 *= 右值;
        } else {
            if 右值 == 0.0 {
                return Err(错误码::计算失败);
            }
            累积值 /= 右值;
        }
    }
    Ok(累积值)
}

fn 解析单元(字序: &[char], 游标: &mut usize, 变量表: &[(String, f64)]) -> Result<f64, u32> {
    if *游标 >= 字序.len() {
        return Err(错误码::计算失败);
    }
    let 当前字元 = 字序[*游标];
    if 当前字元 == '-' {
        *游标 += 1;
        return Ok(-解析单元(字序, 游标, 变量表)?);
    }
    if 当前字元 == '+' {
        *游标 += 1;
        return 解析单元(字序, 游标, 变量表);
    }
    if 当前字元 == '(' {
        *游标 += 1;
        let 内部值 = 解析加减(字序, 游标, 变量表)?;
        if *游标 >= 字序.len() || 字序[*游标] != ')' {
            return Err(错误码::计算失败);
        }
        *游标 += 1;
        return Ok(内部值);
    }
    if 当前字元.is_ascii_digit() || 当前字元 == '.' {
        return 解析数字(字序, 游标);
    }
    if 当前字元.is_alphabetic() || 当前字元 == '_' {
        let 起始位 = *游标;
        while *游标 < 字序.len()
            && (字序[*游标].is_alphanumeric() || 字序[*游标] == '_')
        {
            *游标 += 1;
        }
        let 变量名: String = 字序[起始位..*游标].iter().collect();
        return 查变量(变量表, &变量名);
    }
    Err(错误码::计算失败)
}

fn 解析数字(字序: &[char], 游标: &mut usize) -> Result<f64, u32> {
    let 起始位 = *游标;
    let mut 见到小数点 = false;
    while *游标 < 字序.len() {
        let 当前字元 = 字序[*游标];
        if 当前字元.is_ascii_digit() {
            *游标 += 1;
            continue;
        }
        if 当前字元 == '.' && !见到小数点 {
            见到小数点 = true;
            *游标 += 1;
            continue;
        }
        break;
    }
    let 数字文本: String = 字序[起始位..*游标].iter().collect();
    数字文本.parse::<f64>().map_err(|_| 错误码::计算失败)
}

fn 查变量(变量表: &[(String, f64)], 变量名: &str) -> Result<f64, u32> {
    for (名字, 取值) in 变量表 {
        if 名字 == 变量名 {
            return Ok(*取值);
        }
    }
    Err(错误码::计算失败)
}

fn 数值转文本(算式结果: f64) -> String {
    if 算式结果 == 算式结果.trunc() && 算式结果.abs() < 1e15 {
        return format!("{}", 算式结果 as i64);
    }
    let 粗文本 = format!("{}", 算式结果);
    粗文本
}

// ── 变量表解析：只接受 JSON 对象，值必须是数值 ──────────────────

fn 解析变量表(变量文本: &str) -> Result<Vec<(String, f64)>, u32> {
    let 字序: Vec<char> = 变量文本.chars().collect();
    let mut 游标 = 0usize;
    let mut 变量表: Vec<(String, f64)> = Vec::new();
    跳过空白(&字序, &mut 游标);
    if 游标 >= 字序.len() || 字序[游标] != '{' {
        return Err(错误码::参数不合法);
    }
    游标 += 1;
    跳过空白(&字序, &mut 游标);
    if 游标 < 字序.len() && 字序[游标] == '}' {
        return Ok(变量表);
    }
    loop {
        if 变量表.len() >= 最大变量个数 {
            return Err(错误码::内容不合法);
        }
        跳过空白(&字序, &mut 游标);
        let 名字 = 读名字(&字序, &mut 游标)?;
        跳过空白(&字序, &mut 游标);
        if 游标 >= 字序.len() || 字序[游标] != ':' {
            return Err(错误码::参数不合法);
        }
        游标 += 1;
        跳过空白(&字序, &mut 游标);
        let 取值 = 读数值(&字序, &mut 游标)?;
        变量表.push((名字, 取值));
        跳过空白(&字序, &mut 游标);
        if 游标 >= 字序.len() {
            return Err(错误码::参数不合法);
        }
        if 字序[游标] == ',' {
            游标 += 1;
            continue;
        }
        if 字序[游标] == '}' {
            return Ok(变量表);
        }
        return Err(错误码::参数不合法);
    }
}

fn 跳过空白(字序: &[char], 游标: &mut usize) {
    while *游标 < 字序.len() && 字序[*游标].is_whitespace() {
        *游标 += 1;
    }
}

fn 读名字(字序: &[char], 游标: &mut usize) -> Result<String, u32> {
    if *游标 >= 字序.len() || 字序[*游标] != '"' {
        return Err(错误码::参数不合法);
    }
    *游标 += 1;
    let mut 名字 = String::new();
    while *游标 < 字序.len() {
        let 当前字元 = 字序[*游标];
        if 当前字元 == '\\' {
            *游标 += 1;
            if *游标 >= 字序.len() {
                return Err(错误码::参数不合法);
            }
            名字.push(字序[*游标]);
            *游标 += 1;
            continue;
        }
        if 当前字元 == '"' {
            *游标 += 1;
            return Ok(名字);
        }
        名字.push(当前字元);
        *游标 += 1;
    }
    Err(错误码::参数不合法)
}

fn 读数值(字序: &[char], 游标: &mut usize) -> Result<f64, u32> {
    let 起始位 = *游标;
    while *游标 < 字序.len() {
        let 当前字元 = 字序[*游标];
        if 当前字元.is_ascii_digit()
            || 当前字元 == '-'
            || 当前字元 == '+'
            || 当前字元 == '.'
            || 当前字元 == 'e'
            || 当前字元 == 'E'
        {
            *游标 += 1;
            continue;
        }
        break;
    }
    if *游标 == 起始位 {
        return Err(错误码::参数不合法);
    }
    let 数字文本: String = 字序[起始位..*游标].iter().collect();
    数字文本.parse::<f64>().map_err(|_| 错误码::参数不合法)
}

// ── Markdown 切块 ──────────────────────────────────────────────

struct 文本块 {
    类型: &'static str,
    层级: u32,
    正文: String,
    语言: Option<String>,
}

fn 切分块(源文本: &str) -> Vec<文本块> {
    let mut 块列表: Vec<文本块> = Vec::new();
    let mut 代码行表: Vec<String> = Vec::new();
    let mut 代码语言: Option<String> = None;
    let mut 代码中 = false;
    for 行文本 in 源文本.split('\n') {
        let 原行 = 行文本.trim_end();
        let 整行 = 原行.trim();
        if 整行.starts_with("```") {
            if 代码中 {
                块列表.push(文本块 {
                    类型: "代码块",
                    层级: 0,
                    正文: 代码行表.join("\n"),
                    语言: 代码语言.clone(),
                });
                代码行表.clear();
                代码语言 = None;
                代码中 = false;
            } else {
                代码中 = true;
                let 尾段 = 整行.trim_start_matches("```").trim();
                代码语言 = if 尾段.is_empty() {
                    None
                } else {
                    Some(尾段.to_string())
                };
            }
            continue;
        }
        if 代码中 {
            代码行表.push(原行.to_string());
            continue;
        }
        if 整行.is_empty() {
            continue;
        }
        if 整行 == "---" || 整行 == "***" || 整行 == "___" {
            块列表.push(文本块 { 类型: "分隔线", 层级: 0, 正文: String::new(), 语言: None });
            continue;
        }
        if 整行.starts_with('#') {
            let 井号数 = 整行.chars().take_while(|单字元| *单字元 == '#').count();
            let 余下 = 整行[井号数..].trim_start();
            if 井号数 <= 6 && 整行.chars().count() > 井号数 {
                块列表.push(文本块 {
                    类型: "标题",
                    层级: 井号数 as u32,
                    正文: 余下.trim_end_matches('#').trim().to_string(),
                    语言: None,
                });
                continue;
            }
        }
        if 整行.starts_with("> ") || 整行 == ">" {
            let 余下 = 整行.trim_start_matches('>').trim();
            块列表.push(文本块 { 类型: "引用", 层级: 0, 正文: 余下.to_string(), 语言: None });
            continue;
        }
        if 整行.starts_with("- ") || 整行.starts_with("* ") || 整行.starts_with("+ ") {
            块列表.push(文本块 {
                类型: "列表项",
                层级: 0,
                正文: 整行[2..].trim().to_string(),
                语言: None,
            });
            continue;
        }
        if 是编号列表(整行) {
            let 余下 = 整行.split_once('.').map(|(_, 后段)| 后段.trim()).unwrap_or("");
            块列表.push(文本块 { 类型: "列表项", 层级: 0, 正文: 余下.to_string(), 语言: None });
            continue;
        }
        块列表.push(文本块 { 类型: "段落", 层级: 0, 正文: 整行.to_string(), 语言: None });
    }
    if 代码中 {
        块列表.push(文本块 {
            类型: "代码块",
            层级: 0,
            正文: 代码行表.join("\n"),
            语言: 代码语言,
        });
    }
    块列表
}

fn 是编号列表(整行: &str) -> bool {
    let 数字段: String = 整行.chars().take_while(|单字元| 单字元.is_ascii_digit()).collect();
    if 数字段.is_empty() {
        return false;
    }
    let 余下 = &整行[数字段.len()..];
    余下.starts_with(". ") || 余下 == "."
}

fn 组装块JSON(块列表: &[文本块]) -> String {
    let mut 片段表: Vec<String> = Vec::new();
    for 单个块 in 块列表 {
        let mut 字段表: Vec<String> = Vec::new();
        字段表.push(format!("\"类型\":\"{}\"", 转义文本(单个块.类型)));
        if 单个块.类型 == "标题" {
            字段表.push(format!("\"层级\":{}", 单个块.层级));
        }
        字段表.push(format!("\"文本\":\"{}\"", 转义文本(&单个块.正文)));
        if let Some(语言名) = &单个块.语言 {
            字段表.push(format!("\"语言\":\"{}\"", 转义文本(语言名)));
        }
        片段表.push(format!("{{{}}}", 字段表.join(",")));
    }
    format!("{{\"块\":[{}]}}", 片段表.join(","))
}

fn 转义文本(输入文本: &str) -> String {
    let mut 输出 = String::new();
    for 当前字元 in 输入文本.chars() {
        match 当前字元 {
            '"' => 输出.push_str("\\\""),
            '\\' => 输出.push_str("\\\\"),
            '\n' => 输出.push_str("\\n"),
            '\r' => 输出.push_str("\\r"),
            '\t' => 输出.push_str("\\t"),
            其他字元 => 输出.push(其他字元),
        }
    }
    输出
}

// ── DOCX：有序块解析与生成（zip 容器 + XML事件引擎）────────────────

const 文档条目标识: &str = "word/document.xml";

const 最大文档尺寸: u64 = 32 * 1024 * 1024;

fn 解压文档正文(文件路径: &str) -> Result<String, u32> {
    let 源文件 = std::fs::File::open(文件路径).map_err(|_| 错误码::内容不合法)?;
    if 源文件.metadata().map_err(|_| 错误码::内容不合法)?.len() > 最大文档尺寸 {
        return Err(错误码::内容不合法);
    }
    let mut 压缩包 = zip::ZipArchive::new(源文件).map_err(|_| 错误码::内容不合法)?;
    let 条目值 = 压缩包.by_name(文档条目标识).map_err(|_| 错误码::内容不合法)?;
    if 条目值.size() > 最大文档尺寸 { return Err(错误码::内容不合法); }
    let mut 文档正文 = String::new();
    条目值.take(最大文档尺寸 + 1).read_to_string(&mut 文档正文).map_err(|_| 错误码::内容不合法)?;
    if 文档正文.len() as u64 > 最大文档尺寸 { return Err(错误码::内容不合法); }
    Ok(文档正文)
}

fn 生成PPTX文档(演示内容: &str, 输出路径: &str) -> Result<String, u32> {
    if 演示内容.len() > 4 * 1024 * 1024 {
        return Err(错误码::内容超限);
    }
    let 内容值: serde_json::Value =
        serde_json::from_str(演示内容).map_err(|_| 错误码::参数不合法)?;
    let 页值表 = 内容值.get("幻灯片").and_then(|值项| 值项.as_array()).ok_or(错误码::参数不合法)?;
    let 页宽磅 = 内容值.get("页宽磅").and_then(|值项| 值项.as_f64());
    let 页高磅 = 内容值.get("页高磅").and_then(|值项| 值项.as_f64());
    let mut 页表 = Vec::with_capacity(页值表.len());
    for 页值 in 页值表 {
        let 标题 = 页值.get("标题").and_then(|值项| 值项.as_str()).unwrap_or("").to_string();
        let mut 文本块 = Vec::new();
        if let Some(块值表) = 页值.get("文本块").and_then(|值项| 值项.as_array()) {
            for 块值 in 块值表 {
                let 文本 = 块值.as_str().ok_or(错误码::参数不合法)?.to_string();
                文本块.push(文本);
            }
        }
        页表.push(crate::演示文稿生成::幻灯片输入 { 标题, 文本块 });
    }
    let 字节数 = crate::演示文稿生成::生成演示文稿(页宽磅, 页高磅, &页表, 输出路径)?;
    Ok(format!(
        "{{\"输出路径\":\"{}\",\"字节数\":{},\"幻灯片数\":{}}}",
        转义文本(输出路径), 字节数, 页表.len()
    ))
}

fn 解析PPTX文档(文件路径: &str) -> Result<String, u32> {
    if !文件路径.starts_with('/') {
        return Err(错误码::参数不合法);
    }
    let 元数据项 = std::fs::metadata(文件路径).map_err(|_| 错误码::参数不合法)?;
    if !元数据项.is_file() {
        return Err(错误码::参数不合法);
    }
    if 元数据项.len() > 64 * 1024 * 1024 {
        return Err(错误码::内容超限);
    }
    let 字节 = std::fs::read(文件路径).map_err(|_| 错误码::内容不合法)?;
    let 文稿 = crate::演示文稿解析::解析演示文稿(&字节)?;
    // EMU → 磅：1 磅 = 12700 EMU（WPS/PowerPoint 页尺寸都按这个换算）
    let 页宽磅 = (文稿.页宽 as f64 / 12700.0 * 100.0).round() / 100.0;
    let 页高磅 = (文稿.页高 as f64 / 12700.0 * 100.0).round() / 100.0;
    let mut 页表 = Vec::with_capacity(文稿.幻灯片.len());
    for 页 in &文稿.幻灯片 {
        let 块JSON: Vec<String> = 页.文本块.iter()
            .map(|块| format!("{{\"文本\":\"{}\",\"类型\":\"{}\",\"字号\":{}}}",
                              转义文本(&块.文本), 转义文本(&块.类型), 块.字号))
            .collect();
        页表.push(format!(
            "{{\"序号\":{},\"标题\":\"{}\",\"文本块\":[{}],\"块数\":{}}}",
            页.序号, 转义文本(&页.标题), 块JSON.join(","), 页.文本块.len()
        ));
    }
    Ok(format!(
        "{{\"幻灯片数\":{},\"页宽EMU\":{},\"页高EMU\":{},\"页宽磅\":{},\"页高磅\":{},\"幻灯片\":[{}]}}",
        文稿.幻灯片数, 文稿.页宽, 文稿.页高, 页宽磅, 页高磅, 页表.join(",")
    ))
}

fn 解析DOCX文档(文件路径: &str) -> Result<String, u32> {
    let 正文JSON = crate::文档合并解析::解析增强正文(&解压文档正文(文件路径)?)?;
    let mut 解析结果: serde_json::Value = serde_json::from_str(&正文JSON).map_err(|_| 错误码::内容不合法)?;
    let 图片清单 = crate::办公资源::枚举图片资源(文件路径, "word/media/")?;
    解析结果["资源列表"] = crate::办公资源::组装资源JSON(&图片清单);
    Ok(解析结果.to_string())
}

fn 生成DOCX文档(内容文本: &str, 输出路径: &str) -> Result<String, u32> {
    let 内容值: serde_json::Value =
        serde_json::from_str(内容文本).map_err(|_| 错误码::参数不合法)?;
    let 正文片段 = crate::文档部件::构造正文XML(&内容值)?;
    let 文档XML = format!(
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\"><w:body>{}<w:sectPr/></w:body></w:document>",
        正文片段
    );
    let 类型XML = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"><Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/><Default Extension=\"xml\" ContentType=\"application/xml\"/><Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/><Override PartName=\"/word/styles.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml\"/></Types>";
    let 关系XML = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/></Relationships>";
    let 文档关系XML = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles\" Target=\"styles.xml\"/></Relationships>";
    let 样式XML = crate::文档部件::构造样式XML();
    let mut 缓冲流 = std::io::Cursor::new(Vec::new());
    {
        let mut 压缩包 = zip::ZipWriter::new(&mut 缓冲流);
        let 打包参数 = zip::write::SimpleFileOptions::default();
        for (条目名, 条目内容) in [
            ("[Content_Types].xml", 类型XML),
            ("_rels/.rels", 关系XML),
            ("word/_rels/document.xml.rels", 文档关系XML),
            ("word/styles.xml", 样式XML.as_str()),
            (文档条目标识, 文档XML.as_str()),
        ] {
            压缩包.start_file(条目名, 打包参数).map_err(|_| 错误码::写出失败)?;
            压缩包.write_all(条目内容.as_bytes()).map_err(|_| 错误码::写出失败)?;
        }
        压缩包.finish().map_err(|_| 错误码::写出失败)?;
    }
    let 打包字节 = 缓冲流.into_inner();
    crate::办公资源::原子写出(输出路径, &打包字节)?;
    let 字节数 = 打包字节.len();
    Ok(format!("{{\"输出路径\":\"{}\",\"字节数\":{}}}", 转义文本(输出路径), 字节数))
}

