//! JSON 解析 —— 手写递归下降，零第三方依赖。
//!
//! **为什么手写而不引一个库**：本仓硬规矩「进制品的形态必须零第三方依赖」——
//! 仓库外没有任何东西能改变行为。JSON 是**协议层**的形状，网关要把它翻译成定长槽，
//! 所以它必须完全在本仓可读、可判。
//!
//! # 三条 fail-closed（宁可 400，不替调用方猜）
//!
//! 1. **重复键即拒**：`{"编号":1,"编号":2}` 有两解，猜一个就是把语义改错。
//! 2. **尾部多余内容即拒**：`{"a":1} 垃圾` 不是合法 JSON，不许「读到能解析的为止」。
//! 3. **深度上限**：递归下降在恶意嵌套下会爆栈；爆栈是崩溃，不是 400。
//!
//! 数字一律**按形状**分类：有小数点或指数 ⇒ 小数；否则 ⇒ 整数。
//! 整数超出 64 位即拒（不当成小数兜住——那是静默改形状）。

use crate::协议值::协议值;

/// 嵌套深度上限。超了报 400（请求形状不合法），不是崩。
const 最大深度: usize = 64;

/// 解析错误。**带位置**：位置是「哪一处」的落点，不说位置等于把定位成本推给调用方。
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct 解析错误 {
    /// 出错字节偏移（0 起）。
    pub 位置: usize,
    /// 哪一处不合法。
    pub 说明: String,
}

/// 解析一段 JSON 文本。**整个输入必须是一个值**，尾部不许有余料。
pub fn 解析(来源: &str) -> Result<协议值, 解析错误> {
    let mut 游标 = 游标 {
        字节: 来源.as_bytes(),
        位: 0,
    };
    游标.跳空白();
    let 待处理值 = 游标.取值(0)?;
    游标.跳空白();
    if 游标.位 != 游标.字节.len() {
        return Err(游标.报错("尾部还有多余内容"));
    }
    Ok(待处理值)
}

/// 一个只进不退的读游标。
struct 游标<'a> {
    字节: &'a [u8],
    位: usize,
}

impl<'a> 游标<'a> {
    fn 报错(&self, 说明: &str) -> 解析错误 {
        解析错误 {
            位置: self.位,
            说明: 说明.to_owned(),
        }
    }

    fn 取当前字节(&self) -> Option<u8> {
        self.字节.get(self.位).copied()
    }

    fn 前进一字节(&mut self) -> Option<u8> {
        let 字符表 = self.取当前字节();
        if 字符表.is_some() {
            self.位 += 1;
        }
        字符表
    }

    fn 跳空白(&mut self) {
        while matches!(self.取当前字节(), Some(b' ' | b'\t' | b'\n' | b'\r')) {
            self.位 += 1;
        }
    }

    fn 取值(&mut self, 深度: usize) -> Result<协议值, 解析错误> {
        if 深度 >= 最大深度 {
            return Err(self.报错("嵌套深度超出上限"));
        }
        match self.取当前字节() {
            Some(b'{') => self.取对象(深度),
            Some(b'[') => self.取数组(深度),
            Some(b'"') => self.取文本().map(协议值::文本),
            Some(b't') => self.取字面(b"true", 协议值::逻辑真),
            Some(b'f') => self.取字面(b"false", 协议值::逻辑假),
            Some(b'n') => self.取字面(b"null", 协议值::空值),
            Some(b'-' | b'0'..=b'9') => self.取数(),
            Some(_) => Err(self.报错("这里不是一个 JSON 值")),
            None => Err(self.报错("值没写完就到头了")),
        }
    }

    fn 取字面(&mut self, 期望: &[u8], 待处理值: 协议值) -> Result<协议值, 解析错误> {
        if self.字节[self.位..].starts_with(期望) {
            self.位 += 期望.len();
            return Ok(待处理值);
        }
        Err(self.报错("字面量写错了"))
    }

    fn 取对象(&mut self, 深度: usize) -> Result<协议值, 解析错误> {
        self.位 += 1; // '{'
        let mut 成员: Vec<(String, 协议值)> = Vec::new();
        self.跳空白();
        if self.取当前字节() == Some(b'}') {
            self.位 += 1;
            return Ok(协议值::对象(成员));
        }
        loop {
            self.跳空白();
            if self.取当前字节() != Some(b'"') {
                return Err(self.报错("对象的键必须是字符串"));
            }
            let 键名 = self.取文本()?;
            if 成员.iter().any(|(名, _)| *名 == 键名) {
                // 重复键有两解。**不猜**：猜一个就是把语义改错。
                return Err(self.报错("同一个键出现了两次"));
            }
            self.跳空白();
            if self.前进一字节() != Some(b':') {
                return Err(self.报错("键后面必须是冒号"));
            }
            self.跳空白();
            let 待处理值 = self.取值(深度 + 1)?;
            成员.push((键名, 待处理值));
            self.跳空白();
            match self.前进一字节() {
                Some(b',') => continue,
                Some(b'}') => return Ok(协议值::对象(成员)),
                _ => return Err(self.报错("对象里缺少逗号或右花括号")),
            }
        }
    }

    fn 取数组(&mut self, 深度: usize) -> Result<协议值, 解析错误> {
        self.位 += 1; // '['
        let mut 一项: Vec<协议值> = Vec::new();
        self.跳空白();
        if self.取当前字节() == Some(b']') {
            self.位 += 1;
            return Ok(协议值::数组(一项));
        }
        loop {
            self.跳空白();
            一项.push(self.取值(深度 + 1)?);
            self.跳空白();
            match self.前进一字节() {
                Some(b',') => continue,
                Some(b']') => return Ok(协议值::数组(一项)),
                _ => return Err(self.报错("数组里缺少逗号或右方括号")),
            }
        }
    }

    fn 取文本(&mut self) -> Result<String, 解析错误> {
        self.位 += 1; // 开引号
        let mut 输出缓冲: Vec<u8> = Vec::new();
        loop {
            match self.前进一字节() {
                None => return Err(self.报错("字符串没写完就到头了")),
                Some(b'"') => break,
                Some(b'\\') => self.取转义(&mut 输出缓冲)?,
                // 未转义的控制字符在 JSON 里不合法（含裸换行）。
                Some(字) if 字 < 0x20 => return Err(self.报错("字符串里有未转义的控制字符")),
                Some(字) => 输出缓冲.push(字),
            }
        }
        String::from_utf8(输出缓冲).map_err(|_| self.报错("字符串不是合法 UTF-8"))
    }

    fn 取转义(&mut self, 输出缓冲: &mut Vec<u8>) -> Result<(), 解析错误> {
        let 字符表 = self.前进一字节().ok_or_else(|| self.报错("转义没写完"))?;
        match 字符表 {
            b'"' => 输出缓冲.push(b'"'),
            b'\\' => 输出缓冲.push(b'\\'),
            b'/' => 输出缓冲.push(b'/'),
            b'b' => 输出缓冲.push(0x08),
            b'f' => 输出缓冲.push(0x0C),
            b'n' => 输出缓冲.push(b'\n'),
            b'r' => 输出缓冲.push(b'\r'),
            b't' => 输出缓冲.push(b'\t'),
            b'u' => {
                let 码元 = self.取四位十六进制()?;
                // 代理对：高代理必须紧跟一个低代理，合起来才是一个码点。
                let 码点 = if (0xD800..0xDC00).contains(&码元) {
                    if self.前进一字节() != Some(b'\\') || self.前进一字节() != Some(b'u') {
                        return Err(self.报错("高代理后面必须紧跟一个 \\u 低代理"));
                    }
                    let 低码元 = self.取四位十六进制()?;
                    if !(0xDC00..0xE000).contains(&低码元) {
                        return Err(self.报错("代理对的后半不是低代理"));
                    }
                    0x1_0000 + ((u32::from(码元) - 0xD800) << 10) + (u32::from(低码元) - 0xDC00)
                } else if (0xDC00..0xE000).contains(&码元) {
                    return Err(self.报错("单个低代理不构成码点"));
                } else {
                    u32::from(码元)
                };
                let 字符表 = char::from_u32(码点).ok_or_else(|| self.报错("码点不合法"))?;
                let mut 编码缓冲 = [0u8; 4];
                输出缓冲.extend_from_slice(字符表.encode_utf8(&mut 编码缓冲).as_bytes());
            }
            _ => return Err(self.报错("不认识的转义")),
        }
        Ok(())
    }

    fn 取四位十六进制(&mut self) -> Result<u16, 解析错误> {
        let mut 待处理值: u16 = 0;
        for _ in 0..4 {
            let 字符表 = self.前进一字节().ok_or_else(|| self.报错("\\u 后面要跟四位十六进制"))?;
            let 十六进制值 = (字符表 as char)
                .to_digit(16)
                .ok_or_else(|| self.报错("\\u 后面要跟四位十六进制"))?;
            待处理值 = 待处理值 * 16 + 十六进制值 as u16;
        }
        Ok(待处理值)
    }

    fn 取数(&mut self) -> Result<协议值, 解析错误> {
        let 区间起点 = self.位;
        if self.取当前字节() == Some(b'-') {
            self.位 += 1;
        }
        // 前导零不合法（`01` 与 `1` 是两种写法，JSON 只认后者）。
        if self.取当前字节() == Some(b'0') && matches!(self.字节.get(self.位 + 1), Some(b'0'..=b'9')) {
            return Err(self.报错("数字不许有前导零"));
        }
        while matches!(self.取当前字节(), Some(b'0'..=b'9')) {
            self.位 += 1;
        }
        let mut 是小数 = false;
        if self.取当前字节() == Some(b'.') {
            是小数 = true;
            self.位 += 1;
            if !matches!(self.取当前字节(), Some(b'0'..=b'9')) {
                return Err(self.报错("小数点后面必须有数字"));
            }
            while matches!(self.取当前字节(), Some(b'0'..=b'9')) {
                self.位 += 1;
            }
        }
        if matches!(self.取当前字节(), Some(b'e' | b'E')) {
            是小数 = true;
            self.位 += 1;
            if matches!(self.取当前字节(), Some(b'+' | b'-')) {
                self.位 += 1;
            }
            if !matches!(self.取当前字节(), Some(b'0'..=b'9')) {
                return Err(self.报错("指数后面必须有数字"));
            }
            while matches!(self.取当前字节(), Some(b'0'..=b'9')) {
                self.位 += 1;
            }
        }
        let 文本 = core::str::from_utf8(&self.字节[区间起点..self.位])
            .map_err(|_| self.报错("数字不是合法 UTF-8"))?;
        if 是小数 {
            return 文本
                .parse::<f64>()
                .map(协议值::小数)
                .map_err(|_| self.报错("小数超出 64 位浮点能表达的范围"));
        }
        // 整数：先试有符号，再试无符号（`数据槽.值` 是 u64，高位句柄不许被静默改写）。
        文本
            .parse::<i64>()
            .map(协议值::整数)
            .or_else(|_| 文本.parse::<u64>().map(协议值::无符号))
            .map_err(|_| self.报错("整数超出 64 位范围"))
    }
}

#[cfg(test)]
mod 解析测试 {
    use super::*;

    #[test]
    fn 基本形状_都解析得出来() {
        assert!(matches!(解析("null"), Ok(协议值::空值)));
        assert!(matches!(解析(" true "), Ok(协议值::逻辑真)));
        assert!(matches!(解析("false"), Ok(协议值::逻辑假)));
        assert!(matches!(解析("-12"), Ok(协议值::整数(-12))));
        // 超出 i64 但仍在 u64 内：单列一支，不许静默改写。
        assert!(matches!(
            解析("18446744073709551615"),
            Ok(协议值::无符号(18446744073709551615))
        ));
        assert!(matches!(解析("1.5"), Ok(协议值::小数(_))));
        assert!(matches!(解析("2e3"), Ok(协议值::小数(_))));
        assert_eq!(解析(r#""a\u0062""#).expect("转义").取文本(), Some("ab"));
        assert_eq!(解析(r#""\ud83d\ude00""#).expect("代理对").取文本(), Some("😀"));
    }

    #[test]
    fn 对象与数组_键序原样保留() {
        let 待处理值 = 解析(r#"{"次项":2,"首项":[1,{"末项":null}]}"#).expect("合法");
        let 成员 = match &待处理值 {
            协议值::对象(成员) => 成员,
            _ => panic!("应当是对象"),
        };
        assert_eq!(成员[0].0, "次项", "键序 = 插入序");
        assert_eq!(成员[1].0, "首项");
        assert_eq!(待处理值.取成员("首项").and_then(协议值::取数组).map(<[_]>::len), Some(2));
    }

    #[test]
    fn 坏输入_一律报错不崩溃() {
        for 坏件表 in [
            "",
            "{",
            "}",
            "[1,]",
            r#"{"a":1,}"#,
            r#"{"a":1,"a":2}"#,
            r#"{"a"1}"#,
            "\"没写完",
            "01",
            "1.",
            "1e",
            "12345678901234567890123",
            "{} 尾巴",
            "\"\u{1}裸控制字符\"",
            r#""\ud800""#,
            r#""\q""#,
        ] {
            assert!(解析(坏件表).is_err(), "「{坏件表}」必须被判不合法");
        }
    }

    #[test]
    fn 深度上限_超了就报错不爆栈() {
        let 超深文本 = "[".repeat(最大深度 + 5);
        assert!(解析(&超深文本).is_err(), "超深必须报错（爆栈是崩溃，不是 400）");
    }

    #[test]
    fn 错误带位置() {
        let 错误 = 解析("{\"a\":1,}").expect_err("尾部逗号不合法");
        assert!(错误.位置 > 0, "错误必须报出位置");
        assert!(!错误.说明.is_empty(), "错误必须说清哪一处");
    }
}
