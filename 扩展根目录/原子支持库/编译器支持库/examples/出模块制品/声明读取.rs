//! 声明读取 —— 把扩展目录里的 `包声明.json` / `能力声明/<编号>.json` 读成可查询的值。
//!
//! **为什么自带一个最小读取器**：本仓零第三方依赖（`扩展装载/开发标准/必备件.json` 的
//! 「零第三方依赖」条），而构建侧要按**真实声明**装配类型表 / 命令表 / 锁定依赖 ——
//! 不能像旧版那样把六字段与依赖签名**字面写死**在例子代码里（写死就只会认一个样本模块，
//! 换一个模块就装不起来，等于构建器不认识声明）。本件只读不写、只认本仓声明用到的
//! JSON 子集（对象 / 数组 / 文本 / 整数 / 真 / 假 / 空），遇到子集外的形状**明确报错**，
//! 不静默跳过。

/// 一条声明读出来的值。
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum 声明值 {
    文本值(String),
    数值项(i64),
    表项(Vec<声明值>),
    对象项(Vec<(String, 声明值)>),
    逻辑值(bool),
    空值项,
}

impl 声明值 {
    /// 按名取对象成员（不是对象就回 `None`）。
    pub fn 取键(&self, 键名: &str) -> Option<&声明值> {
        match self {
            声明值::对象项(成员表) => 成员表.iter().find(|(成员名, _)| 成员名 == 键名).map(|(_, 成员值)| 成员值),
            _ => None,
        }
    }

    /// 取文本成员。
    pub fn 取文本(&self) -> Option<&str> {
        match self {
            声明值::文本值(文本本体) => Some(文本本体),
            _ => None,
        }
    }

    /// 取整数成员。
    pub fn 取数值(&self) -> Option<i64> {
        match self {
            声明值::数值项(数值本体) => Some(*数值本体),
            _ => None,
        }
    }

    /// 取数组成员。
    pub fn 取表(&self) -> Option<&[声明值]> {
        match self {
            声明值::表项(项表) => Some(项表),
            _ => None,
        }
    }

    /// 取数组里的整数表（缺项 / 非整数即 `None`）。
    pub fn 取整数表(&self) -> Option<Vec<i64>> {
        self.取表()?.iter().map(声明值::取数值).collect()
    }

    /// 取数组里的文本表。
    pub fn 取文本表(&self) -> Option<Vec<String>> {
        self.取表()?.iter().map(|文本项| 文本项.取文本().map(str::to_owned)).collect()
    }
}

/// 读一份声明文件 → `声明值`。读不动（文件缺失 / 子集外形状）即 `Err`。
pub fn 读声明件(路径: &std::path::Path) -> Result<声明值, String> {
    let 原文 = std::fs::read_to_string(路径)
        .map_err(|失败因由| format!("读不到声明 {}：{失败因由}", 路径.display()))?;
    解析声明(&原文).map_err(|失败因由| format!("声明 {} 读不动：{失败因由}", 路径.display()))
}

/// 解析一段 JSON 文本（本仓声明用到的子集）。
pub fn 解析声明(原文: &str) -> Result<声明值, String> {
    let mut 读取位置 = 0usize;
    let 读出的值 = 读值(原文, &mut 读取位置)?;
    跳空白(原文, &mut 读取位置);
    if 读取位置 != 原文.len() {
        return Err(format!("尾部多余字节（位置 {读取位置}）"));
    }
    Ok(读出的值)
}

fn 跳空白(原文: &str, 读取位置: &mut usize) {
    let 字节 = 原文.as_bytes();
    while *读取位置 < 字节.len() && matches!(字节[*读取位置], b' ' | b'\t' | b'\n' | b'\r') {
        *读取位置 += 1;
    }
}

fn 读值(原文: &str, 读取位置: &mut usize) -> Result<声明值, String> {
    跳空白(原文, 读取位置);
    let 字节 = 原文.as_bytes();
    match 字节.get(*读取位置) {
        Some(b'{') => 读对象(原文, 读取位置),
        Some(b'[') => 读数组(原文, 读取位置),
        Some(b'"') => 读文本(原文, 读取位置).map(声明值::文本值),
        Some(b't') => 读定字(原文, 读取位置, "true", 声明值::逻辑值(true)),
        Some(b'f') => 读定字(原文, 读取位置, "false", 声明值::逻辑值(false)),
        Some(b'n') => 读定字(原文, 读取位置, "null", 声明值::空值项),
        Some(b'-' | b'0'..=b'9') => 读整数(原文, 读取位置),
        Some(其他字节) => Err(format!("不认的字符 {:?}（位置 {}）", *其他字节 as char, *读取位置)),
        None => Err("意外结束".to_owned()),
    }
}

fn 读定字(原文: &str, 读取位置: &mut usize, 定字: &str, 定值: 声明值) -> Result<声明值, String> {
    if 原文[*读取位置..].starts_with(定字) {
        *读取位置 += 定字.len();
        Ok(定值)
    } else {
        Err(format!("不是合法定字（位置 {}）", *读取位置))
    }
}

fn 读对象(原文: &str, 读取位置: &mut usize) -> Result<声明值, String> {
    *读取位置 += 1; // 吃掉 '{'
    let mut 成员表: Vec<(String, 声明值)> = Vec::new();
    跳空白(原文, 读取位置);
    if 原文.as_bytes().get(*读取位置) == Some(&b'}') {
        *读取位置 += 1;
        return Ok(声明值::对象项(成员表));
    }
    loop {
        跳空白(原文, 读取位置);
        let 键名 = 读文本(原文, 读取位置)?;
        跳空白(原文, 读取位置);
        if 原文.as_bytes().get(*读取位置) != Some(&b':') {
            return Err(format!("对象成员缺冒号（位置 {}）", *读取位置));
        }
        *读取位置 += 1;
        let 成员值 = 读值(原文, 读取位置)?;
        if 成员表.iter().any(|(已有键名, _)| 已有键名 == &键名) {
            return Err(format!(
                "对象里重复的键 {键名}（位置 {}）—— 重复键会让后一份值静默丢失，直接拒",
                *读取位置
            ));
        }
        成员表.push((键名, 成员值));
        跳空白(原文, 读取位置);
        match 原文.as_bytes().get(*读取位置) {
            Some(b',') => *读取位置 += 1,
            Some(b'}') => {
                *读取位置 += 1;
                return Ok(声明值::对象项(成员表));
            }
            _ => return Err(format!("对象成员后既不是逗号也不是右括号（位置 {}）", *读取位置)),
        }
    }
}

fn 读数组(原文: &str, 读取位置: &mut usize) -> Result<声明值, String> {
    *读取位置 += 1; // 吃掉 '['
    let mut 项表: Vec<声明值> = Vec::new();
    跳空白(原文, 读取位置);
    if 原文.as_bytes().get(*读取位置) == Some(&b']') {
        *读取位置 += 1;
        return Ok(声明值::表项(项表));
    }
    loop {
        let 项值 = 读值(原文, 读取位置)?;
        项表.push(项值);
        跳空白(原文, 读取位置);
        match 原文.as_bytes().get(*读取位置) {
            Some(b',') => *读取位置 += 1,
            Some(b']') => {
                *读取位置 += 1;
                return Ok(声明值::表项(项表));
            }
            _ => return Err(format!("数组项后既不是逗号也不是右括号（位置 {}）", *读取位置)),
        }
    }
}

fn 读文本(原文: &str, 读取位置: &mut usize) -> Result<String, String> {
    if 原文.as_bytes().get(*读取位置) != Some(&b'"') {
        return Err(format!("这里该是文本（位置 {}）", *读取位置));
    }
    *读取位置 += 1;
    let 起点 = *读取位置;
    let 字节 = 原文.as_bytes();
    while let Some(&当前字节) = 字节.get(*读取位置) {
        match 当前字节 {
            b'"' => {
                let 取到正文 = 原文[起点..*读取位置].to_owned();
                *读取位置 += 1;
                return Ok(取到正文);
            }
            b'\\' => return Err("本仓声明不含转义，遇到反斜杠即拒".to_owned()),
            _ => *读取位置 += 1,
        }
    }
    Err("文本没有收尾引号".to_owned())
}

fn 读整数(原文: &str, 读取位置: &mut usize) -> Result<声明值, String> {
    let 起点 = *读取位置;
    let 字节 = 原文.as_bytes();
    if 字节.get(*读取位置) == Some(&b'-') {
        *读取位置 += 1;
    }
    while 字节.get(*读取位置).is_some_and(u8::is_ascii_digit) {
        *读取位置 += 1;
    }
    原文[起点..*读取位置]
        .parse::<i64>()
        .map(声明值::数值项)
        .map_err(|失败因由| format!("不是合法整数：{失败因由}"))
}
