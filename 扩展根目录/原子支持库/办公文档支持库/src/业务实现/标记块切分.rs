//! Markdown 切块：行级扫描 → 标题 / 段落 / 列表项 / 引用 / 代码块 / 分隔线，再组装块 JSON。

use super::基础件::转义文本;

pub(super) struct 文本块 {
    类型: &'static str,
    层级: u32,
    正文: String,
    语言: Option<String>,
}

pub(super) fn 切分块(源文本: &str) -> Vec<文本块> {
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

pub(super) fn 组装块JSON(块列表: &[文本块]) -> String {
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
