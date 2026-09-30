//! 最小 JSON —— 案例文件与运行回执用的读写件。
//!
//! **不是平台能力，是案例目录的载体格式。** 所以它可以住在这里，不必经适配器：
//! 适配器只管「装载 / 调用 / 清单 / 契约」四件事，与 JSON 无关。
//!
//! 零第三方依赖（宪法级：`Cargo.lock` 里除 `v1-*` 外不许出现任何包）⇒ 自身写一个。
//! 只支持 JSON 的子集够用：对象 · 数组 · 字符串 · 数字 · `true` / `false` / `null`。
//! 不做：注释 · 尾随逗号 · 单引号 · `NaN` / `Infinity`（都不是合法 JSON）。
//!
//! 读进来一律 UTF-8；写出时非 ASCII 不转义（JSON 允许，且案例名是中文）。
//!
//! # 与 `扩展根目录/原子支持库/编译器支持库/src/测试用例/最小JSON.rs` 的关系（2026-09-30）
//!
//! 仓里有**两份**最小 JSON 读取器，分处**互斥的层**（本份住 `v1-case-runner`，那份住
//! 编译器支持库的测试面）⇒ 实现体**不合并**，只对齐**类型定义**与**行为**。**本份是严的那份**：
//! ① 代理对（`\ud83d\ude00`）解得成一个字符；② 字符串里未转义的控制字符（`< 0x20`）当场拒；
//! ③ 数字的 `+/-` 只在开头收（见 `取数`）。那份是有意简化的**测试子集**（返回 `Option`、
//! 只服务声明自洽测试），**行为不许比本份更松** —— 三处差异见那份件头。

use std::fmt::Write as _;

/// 一个 JSON 值。
#[derive(Debug, Clone, PartialEq)]
pub enum JSON值 {
    空值,
    真,
    假,
    数值(f64),
    字符串(String),
    数组(Vec<JSON值>),
    对象(Vec<(String, JSON值)>),
}

impl JSON值 {
    /// 按键取成员。**只对对象有意义**，其余一律 `None`（不猜、不转换）。
    pub fn 取成员(&self, 键名: &str) -> Option<&JSON值> {
        match self {
            JSON值::对象(项表) => 项表.iter().find(|(名称, _)| 名称 == 键名).map(|(_, 待处理值)| 待处理值),
            _ => None,
        }
    }

    pub fn 取字符串(&self) -> Option<&str> {
        match self {
            JSON值::字符串(文本) => Some(文本),
            _ => None,
        }
    }

    pub fn 取数值(&self) -> Option<f64> {
        match self {
            JSON值::数值(数值) => Some(*数值),
            _ => None,
        }
    }

    /// 非负整数：`3.0` 算整数，`3.5` 不算（**不截断**——截断会把写错的数当对的用）。
    pub fn 整数(&self) -> Option<u64> {
        let 数值 = self.取数值()?;
        if 数值 < 0.0 || 数值.fract() != 0.0 || 数值 > u64::MAX as f64 {
            return None;
        }
        Some(数值 as u64)
    }

    pub fn 取数组(&self) -> Option<&[JSON值]> {
        match self {
            JSON值::数组(项表) => Some(项表),
            _ => None,
        }
    }

    pub fn 真假(&self) -> Option<bool> {
        match self {
            JSON值::真 => Some(true),
            JSON值::假 => Some(false),
            _ => None,
        }
    }
}

/// 解析。错误信息带**字节位置**——案例文件写错时要能直接找到那一处。
pub fn 解析(来源: &str) -> Result<JSON值, String> {
    let mut 读器 = 读器 { 字节: 来源.as_bytes(), 位: 0 };
    读器.跳空白();
    let 文本缓冲 = 读器.取值()?;
    读器.跳空白();
    if 读器.位 != 读器.字节.len() {
        return Err(format!("第 {} 字节起有多余内容（JSON 只许一个顶层值）", 读器.位));
    }
    Ok(文本缓冲)
}

struct 读器<'a> {
    字节: &'a [u8],
    位: usize,
}

impl 读器<'_> {
    fn 跳空白(&mut self) {
        while matches!(self.字节.get(self.位), Some(b' ' | b'\t' | b'\n' | b'\r')) {
            self.位 += 1;
        }
    }

    fn 取当前字节(&self) -> Option<u8> {
        self.字节.get(self.位).copied()
    }

    fn 期望(&mut self, 字符表: u8) -> Result<(), String> {
        match self.取当前字节() {
            Some(实到字节) if 实到字节 == 字符表 => {
                self.位 += 1;
                Ok(())
            }
            Some(实到字节) => Err(format!(
                "第 {} 字节：期望 `{}`，实到 `{}`",
                self.位,
                字符表 as char,
                实到字节 as char
            )),
            None => Err(format!("第 {} 字节：期望 `{}`，已到末尾", self.位, 字符表 as char)),
        }
    }

    fn 取字面(&mut self, 文本: &str) -> Result<(), String> {
        if self.字节[self.位..].starts_with(文本.as_bytes()) {
            self.位 += 文本.len();
            Ok(())
        } else {
            Err(format!("第 {} 字节：期望 `{文本}`", self.位))
        }
    }

    fn 取值(&mut self) -> Result<JSON值, String> {
        match self.取当前字节() {
            None => Err("第 0 字节起：没有值".to_owned()),
            Some(b'{') => self.取对象(),
            Some(b'[') => self.取数组(),
            Some(b'"') => self.取串().map(JSON值::字符串),
            Some(b't') => self.取字面("true").map(|()| JSON值::真),
            Some(b'f') => self.取字面("false").map(|()| JSON值::假),
            Some(b'n') => self.取字面("null").map(|()| JSON值::空值),
            Some(_) => self.取数(),
        }
    }

    fn 取对象(&mut self) -> Result<JSON值, String> {
        self.期望(b'{')?;
        let mut 项表 = Vec::new();
        self.跳空白();
        if self.取当前字节() == Some(b'}') {
            self.位 += 1;
            return Ok(JSON值::对象(项表));
        }
        loop {
            self.跳空白();
            let 名称 = self.取串()?;
            self.跳空白();
            self.期望(b':')?;
            self.跳空白();
            let 待处理值 = self.取值()?;
            项表.push((名称, 待处理值));
            self.跳空白();
            match self.取当前字节() {
                Some(b',') => self.位 += 1,
                Some(b'}') => {
                    self.位 += 1;
                    return Ok(JSON值::对象(项表));
                }
                Some(实到字节) => return Err(format!("第 {} 字节：对象里期望 `,` 或 `}}`，实到 `{}`", self.位, 实到字节 as char)),
                None => return Err("对象未闭合（缺 `}`）".to_owned()),
            }
        }
    }

    fn 取数组(&mut self) -> Result<JSON值, String> {
        self.期望(b'[')?;
        let mut 项表 = Vec::new();
        self.跳空白();
        if self.取当前字节() == Some(b']') {
            self.位 += 1;
            return Ok(JSON值::数组(项表));
        }
        loop {
            self.跳空白();
            项表.push(self.取值()?);
            self.跳空白();
            match self.取当前字节() {
                Some(b',') => self.位 += 1,
                Some(b']') => {
                    self.位 += 1;
                    return Ok(JSON值::数组(项表));
                }
                Some(实到字节) => return Err(format!("第 {} 字节：数组里期望 `,` 或 `]`，实到 `{}`", self.位, 实到字节 as char)),
                None => return Err("数组未闭合（缺 `]`）".to_owned()),
            }
        }
    }

    fn 取串(&mut self) -> Result<String, String> {
        self.期望(b'"')?;
        let mut 文本缓冲 = String::new();
        loop {
            let 区间起点 = self.位;
            match self.取当前字节() {
                None => return Err("字符串未闭合（缺 `\"`）".to_owned()),
                Some(b'"') => {
                    self.位 += 1;
                    return Ok(文本缓冲);
                }
                Some(b'\\') => {
                    self.位 += 1;
                    let 转义字节 = self.取当前字节().ok_or_else(|| "转义符后已到末尾".to_owned())?;
                    self.位 += 1;
                    match 转义字节 {
                        b'"' => 文本缓冲.push('"'),
                        b'\\' => 文本缓冲.push('\\'),
                        b'/' => 文本缓冲.push('/'),
                        b'b' => 文本缓冲.push('\u{8}'),
                        b'f' => 文本缓冲.push('\u{c}'),
                        b'n' => 文本缓冲.push('\n'),
                        b'r' => 文本缓冲.push('\r'),
                        b't' => 文本缓冲.push('\t'),
                        b'u' => 文本缓冲.push(self.取码点()?),
                        _ => return Err(format!("第 {} 字节：不认的转义 `\\{}`", 区间起点, 转义字节 as char)),
                    }
                }
                Some(实到字节) if 实到字节 < 0x20 => {
                    return Err(format!("第 {区间起点} 字节：字符串里出现未转义的控制字符"));
                }
                Some(实到字节) if 实到字节 < 0x80 => {
                    文本缓冲.push(实到字节 as char);
                    self.位 += 1;
                }
                Some(_) => {
                    // 多字节 UTF-8：整字搬。源是 &str ⇒ 剩下的字节一定是合法 UTF-8，
                    // 取首字符再按它的字节长前进，天然落在字符边界上。
                    let 剩余文本 = std::str::from_utf8(&self.字节[区间起点..])
                        .map_err(|错误| format!("第 {区间起点} 字节：不是合法 UTF-8（{错误}）"))?;
                    let 首字符 = 剩余文本
                        .chars()
                        .next()
                        .ok_or_else(|| format!("第 {区间起点} 字节：字符串内容到头了"))?;
                    文本缓冲.push(首字符);
                    self.位 += 首字符.len_utf8();
                }
            }
        }
    }

    fn 取码点(&mut self) -> Result<char, String> {
        let 高代理 = self.取四位()?;
        // 代理对：高代理 + `\u` + 低代理 ⇒ 合成一个字符。
        if (0xD800..0xDC00).contains(&高代理) {
            self.期望(b'\\')?;
            self.期望(b'u')?;
            let 低代理 = self.取四位()?;
            if !(0xDC00..0xE000).contains(&低代理) {
                return Err("\\u 代理对不配对（低代理不在 DC00–DFFF）".to_owned());
            }
            let 合成码点 = 0x10000 + ((高代理 - 0xD800) << 10) + (低代理 - 0xDC00);
            return char::from_u32(合成码点).ok_or_else(|| format!("\\u 合成的码点 {合成码点:#x} 不是字符"));
        }
        char::from_u32(高代理).ok_or_else(|| format!("\\u{高代理:04x} 不是字符"))
    }

    fn 取四位(&mut self) -> Result<u32, String> {
        let 片段 = self
            .字节
            .get(self.位..self.位 + 4)
            .ok_or_else(|| "\\u 后不足 4 位十六进制".to_owned())?;
        let 文本 = std::str::from_utf8(片段).map_err(|_| "\\u 后不是 UTF-8".to_owned())?;
        let 四位值 = u32::from_str_radix(文本, 16).map_err(|_| format!("\\u 后不是十六进制：{文本}"))?;
        self.位 += 4;
        Ok(四位值)
    }

    fn 取数(&mut self) -> Result<JSON值, String> {
        let 区间起点 = self.位;
        if matches!(self.取当前字节(), Some(b'-' | b'+')) {
            self.位 += 1;
        }
        while matches!(self.取当前字节(), Some(b'0'..=b'9' | b'.' | b'e' | b'E' | b'+' | b'-')) {
            self.位 += 1;
        }
        if 区间起点 == self.位 {
            return Err(format!("第 {区间起点} 字节：不是一个值"));
        }
        let 文本 = std::str::from_utf8(&self.字节[区间起点..self.位]).map_err(|_| "数字不是 UTF-8".to_owned())?;
        文本.parse::<f64>()
            .map(JSON值::数值)
            .map_err(|_| format!("第 {区间起点} 字节：`{文本}` 不是数"))
    }
}

/// 写出：转义控制字符与 `"` `\`，其余原样（含中文）。
pub fn 写串(文本缓冲: &mut String, 文本: &str) {
    文本缓冲.push('"');
    for 单个字符 in 文本.chars() {
        match 单个字符 {
            '"' => 文本缓冲.push_str("\\\""),
            '\\' => 文本缓冲.push_str("\\\\"),
            '\n' => 文本缓冲.push_str("\\n"),
            '\r' => 文本缓冲.push_str("\\r"),
            '\t' => 文本缓冲.push_str("\\t"),
            控制字符 if (控制字符 as u32) < 0x20 => {
                let _ = write!(文本缓冲, "\\u{:04x}", 控制字符 as u32);
            }
            其他字符 => 文本缓冲.push(其他字符),
        }
    }
    文本缓冲.push('"');
}

#[cfg(test)]
mod 测试 {
    use super::*;

    fn 解析JSON(来源: &str) -> JSON值 {
        解析(来源).unwrap_or_else(|错误| panic!("{来源} 该能解析：{错误}"))
    }

    /// 正向样本：干净输入必须通过，且读到的东西与写的一样。
    #[test]
    fn 干净输入逐字段读得对() {
        let 待处理值 = 解析JSON(r#"{"案例名":"反解","步骤":[{"能力编号":1105}],"结果":true,"无":null,"数":1568}"#);
        assert_eq!(待处理值.取成员("案例名").and_then(|一项| 一项.取字符串()), Some("反解"));
        assert_eq!(待处理值.取成员("步骤").and_then(|一项| 一项.取数组()).map(<[JSON值]>::len), Some(1));
        assert_eq!(
            待处理值.取成员("步骤").and_then(|步骤值| 步骤值.取数组()).and_then(|步骤值| 步骤值.first()).and_then(|步骤值| 步骤值.取成员("能力编号")).and_then(|一项| 一项.整数()),
            Some(1105)
        );
        assert_eq!(待处理值.取成员("结果").and_then(|一项| 一项.真假()), Some(true));
        assert!(matches!(待处理值.取成员("无"), Some(JSON值::空值)));
        assert_eq!(待处理值.取成员("数").and_then(|一项| 一项.整数()), Some(1568));
    }

    /// 反向样本：坏输入必须报错（不是静默给一个空值）。
    #[test]
    fn 坏输入一律报错() {
        for 坏输入 in [
            "{",
            "[1,",
            r#"{"首项":}"#,
            r#"{"首项" 1}"#,
            "tru",
            "1.2.3",
            r#"{"首项":1} 尾巴"#,
            "\"未闭合",
        ] {
            assert!(解析(坏输入).is_err(), "`{坏输入}` 该被拒");
        }
    }

    /// 反向样本：`3.5` 不是整数（截断会把写错的数当对的用）。
    #[test]
    fn 小数不算整数() {
        assert_eq!(解析JSON("3.5").整数(), None);
        assert_eq!(解析JSON("3.0").整数(), Some(3));
        assert_eq!(解析JSON("-1").整数(), None);
    }

    #[test]
    fn 串的转义与中文都读得出() {
        assert_eq!(解析JSON(r#""a\u0041\n中""#).取字符串(), Some("aA\n中"));
        assert_eq!(解析JSON(r#""\ud83d\ude00""#).取字符串(), Some("😀"));
        let mut 文本缓冲 = String::new();
        写串(&mut 文本缓冲, "中\n\"");
        assert_eq!(文本缓冲, "\"中\\n\\\"\"");
        assert_eq!(解析JSON(&文本缓冲).取字符串(), Some("中\n\""));
    }
}
