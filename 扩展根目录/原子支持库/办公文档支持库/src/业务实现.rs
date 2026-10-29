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
    if 编号 == 能力号::解析标记块 {
        let 源文本 = 取第几项文本(参数表, 0)?;
        if 源文本.len() > 最大标记长度 {
            return Err(错误码::内容不合法);
        }
        let 块列表 = 切分块(源文本);
        return Ok((4, 组装块JSON(&块列表).into_bytes()));
    }
    if 编号 == 能力号::解析DOCX {
        let 文件路径 = 取第几项文本(参数表, 0)?;
        return Ok((4, 解析DOCX文档(文件路径)?.into_bytes()));
    }
    if 编号 == 能力号::生成DOCX {
        let 内容文本 = 取第几项文本(参数表, 0)?;
        let 输出路径 = 取第几项文本(参数表, 1)?;
        return Ok((4, 生成DOCX文档(内容文本, 输出路径)?.into_bytes()));
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

// ── DOCX：解析与生成（zip 容器 + 手工 XML 抽取）────────────────

const 文档条目标识: &str = "word/document.xml";

fn 解压文档正文(文件路径: &str) -> Result<String, u32> {
    let 字节流 = std::fs::read(文件路径).map_err(|_| 错误码::内容不合法)?;
    let mut 压缩包 = zip::ZipArchive::new(std::io::Cursor::new(字节流))
        .map_err(|_| 错误码::内容不合法)?;
    let mut 条目 = 压缩包.by_name(文档条目标识).map_err(|_| 错误码::内容不合法)?;
    let mut 文档正文 = String::new();
    条目.read_to_string(&mut 文档正文).map_err(|_| 错误码::内容不合法)?;
    Ok(文档正文)
}

fn 解析DOCX文档(文件路径: &str) -> Result<String, u32> {
    let 文档正文 = 解压文档正文(文件路径)?;
    let mut 段落表: Vec<(String, String)> = Vec::new();
    let mut 表格表: Vec<Vec<Vec<String>>> = Vec::new();
    let mut 余下正文 = 文档正文;
    while let Some(表起点) = 余下正文.find("<w:tbl>") {
        let 表内余段 = 余下正文[表起点..].to_string();
        let Some(表止距) = 表内余段.find("</w:tbl>") else { break };
        let 表终点 = 表起点 + 表止距 + "</w:tbl>".len();
        let 表段文本 = 余下正文[表起点..表终点].to_string();
        表格表.push(解析表格(&表段文本));
        余下正文 = format!("{}{}", &余下正文[..表起点], &余下正文[表终点..]);
    }
    for 段落段 in 余下正文.split("</w:p>") {
        let 段落拼文 = 拼合段文(段落段);
        let 段落式名 = 取段落式名(段落段);
        if 段落拼文.is_empty() && 段落式名.is_empty() {
            continue;
        }
        段落表.push((段落式名, 段落拼文));
    }
    let mut 段落片段集: Vec<String> = Vec::new();
    for (段落式名, 段落拼文) in &段落表 {
        let mut 字段集: Vec<String> = Vec::new();
        if !段落式名.is_empty() {
            字段集.push(format!("\"样式\":\"{}\"", 转义文本(段落式名)));
        }
        字段集.push(format!("\"文本\":\"{}\"", 转义文本(段落拼文)));
        段落片段集.push(format!("{{{}}}", 字段集.join(",")));
    }
    let mut 表格片段集: Vec<String> = Vec::new();
    for 单表 in &表格表 {
        let mut 行片段集: Vec<String> = Vec::new();
        for 单行 in 单表 {
            let 格片段集: Vec<String> = 单行
                .iter()
                .map(|格内拼文| format!("\"{}\"", 转义文本(格内拼文)))
                .collect();
            行片段集.push(format!("[{}]", 格片段集.join(",")));
        }
        表格片段集.push(format!("[{}]", 行片段集.join(",")));
    }
    Ok(format!(
        "{{\"段落\":[{}],\"表格\":[{}],\"段数\":{},\"表数\":{}}}",
        段落片段集.join(","),
        表格片段集.join(","),
        段落表.len(),
        表格表.len()
    ))
}

fn 解析表格(表段文本: &str) -> Vec<Vec<String>> {
    let mut 行表集: Vec<Vec<String>> = Vec::new();
    for 行段 in 表段文本.split("</w:tr>") {
        if !行段.contains("<w:tc") {
            continue;
        }
        let mut 格表集: Vec<String> = Vec::new();
        for 格段 in 行段.split("</w:tc>") {
            if !格段.contains("<w:tc") {
                continue;
            }
            格表集.push(拼合段文(格段));
        }
        if !格表集.is_empty() {
            行表集.push(格表集);
        }
    }
    行表集
}

fn 取段落式名(段落段: &str) -> String {
    let Some(式起点) = 段落段.find("<w:pStyle") else { return String::new() };
    let 式余段 = &段落段[式起点..];
    let Some(值起点) = 式余段.find("w:val=\"") else { return String::new() };
    let 值余段 = &式余段[值起点 + 7..];
    match 值余段.find('"') {
        Some(值止距) => 值余段[..值止距].to_string(),
        None => String::new(),
    }
}

fn 拼合段文(段落段: &str) -> String {
    let mut 拼文累积 = String::new();
    let mut 游标位 = 0usize;
    while let Some(标签距) = 段落段[游标位..].find("<w:t") {
        let 标签起点 = 游标位 + 标签距;
        let 标签后位 = 标签起点 + "<w:t".len();
        let 紧随字 = 段落段[标签后位..].chars().next();
        if 紧随字 != Some('>') && 紧随字 != Some(' ') {
            游标位 = 标签后位;
            continue;
        }
        let Some(头止距) = 段落段[标签起点..].find('>') else { break };
        let 内容起点 = 标签起点 + 头止距 + 1;
        let Some(尾距) = 段落段[内容起点..].find("</w:t>") else { break };
        拼文累积.push_str(&反转义(&段落段[内容起点..内容起点 + 尾距]));
        游标位 = 内容起点 + 尾距 + "</w:t>".len();
    }
    拼文累积
}

fn 反转义(输入文本: &str) -> String {
    输入文本
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", "\"")
        .replace("&apos;", "'")
        .replace("&amp;", "&")
}

fn 生成DOCX文档(内容文本: &str, 输出路径: &str) -> Result<String, u32> {
    let 内容值: serde_json::Value =
        serde_json::from_str(内容文本).map_err(|_| 错误码::参数不合法)?;
    let mut 正文片段 = String::new();
    if let Some(段表值) = 内容值.get("段落").and_then(|条目值| 条目值.as_array()) {
        for 单段 in 段表值 {
            let 段落拼文 = 单段.get("文本").and_then(|条目值| 条目值.as_str()).unwrap_or("");
            let 段落式名 = 单段.get("样式").and_then(|条目值| 条目值.as_str()).unwrap_or("");
            正文片段.push_str(&段落XML(段落拼文, 段落式名));
        }
    }
    if let Some(表表值) = 内容值.get("表格").and_then(|条目值| 条目值.as_array()) {
        for 单表 in 表表值 {
            let Some(行表值) = 单表.as_array() else { continue };
            正文片段.push_str("<w:tbl>");
            for 单行 in 行表值 {
                let Some(格表值) = 单行.as_array() else { continue };
                正文片段.push_str("<w:tr>");
                for 单格 in 格表值 {
                    let 格内拼文 = 单格.as_str().unwrap_or("");
                    正文片段.push_str("<w:tc><w:p><w:r><w:t xml:space=\"preserve\">");
                    正文片段.push_str(&转义文本(格内拼文));
                    正文片段.push_str("</w:t></w:r></w:p></w:tc>");
                }
                正文片段.push_str("</w:tr>");
            }
            正文片段.push_str("</w:tbl>");
        }
    }
    let 文档XML = format!(
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\"><w:body>{}<w:sectPr/></w:body></w:document>",
        正文片段
    );
    let 类型XML = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"><Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/><Default Extension=\"xml\" ContentType=\"application/xml\"/><Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/><Override PartName=\"/word/styles.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml\"/></Types>";
    let 关系XML = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/></Relationships>";
    let 文档关系XML = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles\" Target=\"styles.xml\"/></Relationships>";
    let 样式XML = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><w:styles xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii=\"Times New Roman\" w:eastAsia=\"宋体\" w:hAnsi=\"Times New Roman\"/><w:sz w:val=\"21\"/><w:szCs w:val=\"21\"/></w:rPr></w:rPrDefault></w:docDefaults><w:style w:type=\"paragraph\" w:default=\"1\" w:styleId=\"Normal\"><w:name w:val=\"Normal\"/><w:qFormat/></w:style><w:style w:type=\"paragraph\" w:styleId=\"Heading1\"><w:name w:val=\"heading 1\"/><w:basedOn w:val=\"Normal\"/><w:qFormat/><w:pPr><w:outlineLvl w:val=\"0\"/></w:pPr><w:rPr><w:b/><w:sz w:val=\"36\"/><w:szCs w:val=\"36\"/></w:rPr></w:style><w:style w:type=\"paragraph\" w:styleId=\"Heading2\"><w:name w:val=\"heading 2\"/><w:basedOn w:val=\"Normal\"/><w:qFormat/><w:pPr><w:outlineLvl w:val=\"1\"/></w:pPr><w:rPr><w:b/><w:sz w:val=\"32\"/><w:szCs w:val=\"32\"/></w:rPr></w:style><w:style w:type=\"paragraph\" w:styleId=\"Heading3\"><w:name w:val=\"heading 3\"/><w:basedOn w:val=\"Normal\"/><w:qFormat/><w:pPr><w:outlineLvl w:val=\"2\"/></w:pPr><w:rPr><w:b/><w:sz w:val=\"28\"/><w:szCs w:val=\"28\"/></w:rPr></w:style></w:styles>";
    let 源文件 = std::fs::File::create(输出路径).map_err(|_| 错误码::写出失败)?;
    let mut 压缩包 = zip::ZipWriter::new(源文件);
    let 打包参数 = zip::write::SimpleFileOptions::default();
    for (条目名, 条目内容) in [
        ("[Content_Types].xml", 类型XML),
        ("_rels/.rels", 关系XML),
        ("word/_rels/document.xml.rels", 文档关系XML),
        ("word/styles.xml", 样式XML),
        (文档条目标识, 文档XML.as_str()),
    ] {
        压缩包.start_file(条目名, 打包参数).map_err(|_| 错误码::写出失败)?;
        压缩包.write_all(条目内容.as_bytes()).map_err(|_| 错误码::写出失败)?;
    }
    压缩包.finish().map_err(|_| 错误码::写出失败)?;
    let 字节数 = std::fs::metadata(输出路径).map(|元数据项| 元数据项.len()).unwrap_or(0);
    Ok(format!("{{\"输出路径\":\"{}\",\"字节数\":{}}}", 转义文本(输出路径), 字节数))
}

fn 段落XML(段落拼文: &str, 段落式名: &str) -> String {
    let 式片段 = if 段落式名.is_empty() {
        String::new()
    } else {
        format!("<w:pPr><w:pStyle w:val=\"{}\"/></w:pPr>", 转义文本(段落式名))
    };
    format!(
        "<w:p>{}<w:r><w:t xml:space=\"preserve\">{}</w:t></w:r></w:p>",
        式片段,
        转义文本(段落拼文)
    )
}
