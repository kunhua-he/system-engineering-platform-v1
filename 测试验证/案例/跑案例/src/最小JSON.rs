//! 最小 JSON —— 案例文件与运行回执用的读写件。
//!
//! **不是平台能力，是案例目录的载体格式。** 所以它可以住在这里，不必经适配器：
//! 适配器只管「装载 / 调用 / 清单 / 契约」四件事，与 JSON 无关。
//!
//! 零第三方依赖（宪法级：`Cargo.lock` 里除 `v1-*` 外不许出现任何包）⇒ 自己写一个。
//! 只支持 JSON 的子集够用：对象 · 数组 · 字符串 · 数字 · `true` / `false` / `null`。
//! 不做：注释 · 尾随逗号 · 单引号 · `NaN` / `Infinity`（都不是合法 JSON）。
//!
//! 读进来一律 UTF-8；写出时非 ASCII 不转义（JSON 允许，且案例名是中文）。

use std::fmt::Write as _;

/// 一个 JSON 值。
#[derive(Debug, Clone, PartialEq)]
pub enum 值 {
    空,
    真,
    假,
    数(f64),
    串(String),
    表(Vec<值>),
    对象(Vec<(String, 值)>),
}

impl 值 {
    /// 按键取成员。**只对对象有意义**，其余一律 `None`（不猜、不转换）。
    pub fn 取(&self, 键: &str) -> Option<&值> {
        match self {
            值::对象(项表) => 项表.iter().find(|(名, _)| 名 == 键).map(|(_, 值)| 值),
            _ => None,
        }
    }

    pub fn 串(&self) -> Option<&str> {
        match self {
            值::串(文) => Some(文),
            _ => None,
        }
    }

    pub fn 数(&self) -> Option<f64> {
        match self {
            值::数(数) => Some(*数),
            _ => None,
        }
    }

    /// 非负整数：`3.0` 算整数，`3.5` 不算（**不截断**——截断会把写错的数当对的用）。
    pub fn 整数(&self) -> Option<u64> {
        let 数 = self.数()?;
        if 数 < 0.0 || 数.fract() != 0.0 || 数 > u64::MAX as f64 {
            return None;
        }
        Some(数 as u64)
    }

    pub fn 表(&self) -> Option<&[值]> {
        match self {
            值::表(项表) => Some(项表),
            _ => None,
        }
    }

    pub fn 真假(&self) -> Option<bool> {
        match self {
            值::真 => Some(true),
            值::假 => Some(false),
            _ => None,
        }
    }
}

/// 解析。错误信息带**字节位置**——案例文件写错时要能直接找到那一处。
pub fn 解析(源: &str) -> Result<值, String> {
    let mut 读 = 读器 { 字节: 源.as_bytes(), 位: 0 };
    读.跳空白();
    let 文本缓冲 = 读.取值()?;
    读.跳空白();
    if 读.位 != 读.字节.len() {
        return Err(format!("第 {} 字节起有多余内容（JSON 只许一个顶层值）", 读.位));
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

    fn 看(&self) -> Option<u8> {
        self.字节.get(self.位).copied()
    }

    fn 期望(&mut self, 字: u8) -> Result<(), String> {
        match self.看() {
            Some(实) if 实 == 字 => {
                self.位 += 1;
                Ok(())
            }
            Some(实) => Err(format!(
                "第 {} 字节：期望 `{}`，实到 `{}`",
                self.位,
                字 as char,
                实 as char
            )),
            None => Err(format!("第 {} 字节：期望 `{}`，已到末尾", self.位, 字 as char)),
        }
    }

    fn 取字面(&mut self, 文: &str) -> Result<(), String> {
        if self.字节[self.位..].starts_with(文.as_bytes()) {
            self.位 += 文.len();
            Ok(())
        } else {
            Err(format!("第 {} 字节：期望 `{文}`", self.位))
        }
    }

    fn 取值(&mut self) -> Result<值, String> {
        match self.看() {
            None => Err("第 0 字节起：没有值".to_owned()),
            Some(b'{') => self.取对象(),
            Some(b'[') => self.取数组(),
            Some(b'"') => self.取串().map(值::串),
            Some(b't') => self.取字面("true").map(|()| 值::真),
            Some(b'f') => self.取字面("false").map(|()| 值::假),
            Some(b'n') => self.取字面("null").map(|()| 值::空),
            Some(_) => self.取数(),
        }
    }

    fn 取对象(&mut self) -> Result<值, String> {
        self.期望(b'{')?;
        let mut 项表 = Vec::new();
        self.跳空白();
        if self.看() == Some(b'}') {
            self.位 += 1;
            return Ok(值::对象(项表));
        }
        loop {
            self.跳空白();
            let 名 = self.取串()?;
            self.跳空白();
            self.期望(b':')?;
            self.跳空白();
            let 值 = self.取值()?;
            项表.push((名, 值));
            self.跳空白();
            match self.看() {
                Some(b',') => self.位 += 1,
                Some(b'}') => {
                    self.位 += 1;
                    return Ok(值::对象(项表));
                }
                Some(实) => return Err(format!("第 {} 字节：对象里期望 `,` 或 `}}`，实到 `{}`", self.位, 实 as char)),
                None => return Err("对象未闭合（缺 `}`）".to_owned()),
            }
        }
    }

    fn 取数组(&mut self) -> Result<值, String> {
        self.期望(b'[')?;
        let mut 项表 = Vec::new();
        self.跳空白();
        if self.看() == Some(b']') {
            self.位 += 1;
            return Ok(值::表(项表));
        }
        loop {
            self.跳空白();
            项表.push(self.取值()?);
            self.跳空白();
            match self.看() {
                Some(b',') => self.位 += 1,
                Some(b']') => {
                    self.位 += 1;
                    return Ok(值::表(项表));
                }
                Some(实) => return Err(format!("第 {} 字节：数组里期望 `,` 或 `]`，实到 `{}`", self.位, 实 as char)),
                None => return Err("数组未闭合（缺 `]`）".to_owned()),
            }
        }
    }

    fn 取串(&mut self) -> Result<String, String> {
        self.期望(b'"')?;
        let mut 文本缓冲 = String::new();
        loop {
            let 起 = self.位;
            match self.看() {
                None => return Err("字符串未闭合（缺 `\"`）".to_owned()),
                Some(b'"') => {
                    self.位 += 1;
                    return Ok(文本缓冲);
                }
                Some(b'\\') => {
                    self.位 += 1;
                    let 转 = self.看().ok_or_else(|| "转义符后已到末尾".to_owned())?;
                    self.位 += 1;
                    match 转 {
                        b'"' => 文本缓冲.push('"'),
                        b'\\' => 文本缓冲.push('\\'),
                        b'/' => 文本缓冲.push('/'),
                        b'b' => 文本缓冲.push('\u{8}'),
                        b'f' => 文本缓冲.push('\u{c}'),
                        b'n' => 文本缓冲.push('\n'),
                        b'r' => 文本缓冲.push('\r'),
                        b't' => 文本缓冲.push('\t'),
                        b'u' => 文本缓冲.push(self.取码点()?),
                        _ => return Err(format!("第 {} 字节：不认的转义 `\\{}`", 起, 转 as char)),
                    }
                }
                Some(实) if 实 < 0x20 => {
                    return Err(format!("第 {起} 字节：字符串里出现未转义的控制字符"));
                }
                Some(实) if 实 < 0x80 => {
                    文本缓冲.push(实 as char);
                    self.位 += 1;
                }
                Some(_) => {
                    // 多字节 UTF-8：整字搬。源是 &str ⇒ 剩下的字节一定是合法 UTF-8，
                    // 取首字符再按它的字节长前进，天然落在字符边界上。
                    let 剩 = std::str::from_utf8(&self.字节[起..])
                        .map_err(|错| format!("第 {起} 字节：不是合法 UTF-8（{错}）"))?;
                    let 字 = 剩
                        .chars()
                        .next()
                        .ok_or_else(|| format!("第 {起} 字节：字符串内容到头了"))?;
                    文本缓冲.push(字);
                    self.位 += 字.len_utf8();
                }
            }
        }
    }

    fn 取码点(&mut self) -> Result<char, String> {
        let 高 = self.取四位()?;
        // 代理对：高代理 + `\u` + 低代理 ⇒ 合成一个字符。
        if (0xD800..0xDC00).contains(&高) {
            self.期望(b'\\')?;
            self.期望(b'u')?;
            let 低 = self.取四位()?;
            if !(0xDC00..0xE000).contains(&低) {
                return Err("\\u 代理对不配对（低代理不在 DC00–DFFF）".to_owned());
            }
            let 合 = 0x10000 + ((高 - 0xD800) << 10) + (低 - 0xDC00);
            return char::from_u32(合).ok_or_else(|| format!("\\u 合成的码点 {合:#x} 不是字符"));
        }
        char::from_u32(高).ok_or_else(|| format!("\\u{高:04x} 不是字符"))
    }

    fn 取四位(&mut self) -> Result<u32, String> {
        let 片 = self
            .字节
            .get(self.位..self.位 + 4)
            .ok_or_else(|| "\\u 后不足 4 位十六进制".to_owned())?;
        let 文 = std::str::from_utf8(片).map_err(|_| "\\u 后不是 UTF-8".to_owned())?;
        let 数 = u32::from_str_radix(文, 16).map_err(|_| format!("\\u 后不是十六进制：{文}"))?;
        self.位 += 4;
        Ok(数)
    }

    fn 取数(&mut self) -> Result<值, String> {
        let 起 = self.位;
        if matches!(self.看(), Some(b'-' | b'+')) {
            self.位 += 1;
        }
        while matches!(self.看(), Some(b'0'..=b'9' | b'.' | b'e' | b'E' | b'+' | b'-')) {
            self.位 += 1;
        }
        if 起 == self.位 {
            return Err(format!("第 {起} 字节：不是一个值"));
        }
        let 文 = std::str::from_utf8(&self.字节[起..self.位]).map_err(|_| "数字不是 UTF-8".to_owned())?;
        文.parse::<f64>()
            .map(值::数)
            .map_err(|_| format!("第 {起} 字节：`{文}` 不是数"))
    }
}

/// 写出：转义控制字符与 `"` `\`，其余原样（含中文）。
pub fn 写串(文本缓冲: &mut String, 文: &str) {
    文本缓冲.push('"');
    for 字 in 文.chars() {
        match 字 {
            '"' => 文本缓冲.push_str("\\\""),
            '\\' => 文本缓冲.push_str("\\\\"),
            '\n' => 文本缓冲.push_str("\\n"),
            '\r' => 文本缓冲.push_str("\\r"),
            '\t' => 文本缓冲.push_str("\\t"),
            控 if (控 as u32) < 0x20 => {
                let _ = write!(文本缓冲, "\\u{:04x}", 控 as u32);
            }
            其 => 文本缓冲.push(其),
        }
    }
    文本缓冲.push('"');
}

#[cfg(test)]
mod 测试 {
    use super::*;

    fn 解(源: &str) -> 值 {
        解析(源).unwrap_or_else(|错| panic!("{源} 该能解析：{错}"))
    }

    /// 正向样本：干净输入必须通过，且读到的东西与写的一样。
    #[test]
    fn 干净输入逐字段读得对() {
        let 值 = 解(r#"{"案例名":"反解","步骤":[{"能力编号":1105}],"结果":true,"无":null,"数":1568}"#);
        assert_eq!(值.取("案例名").and_then(|一| 一.串()), Some("反解"));
        assert_eq!(值.取("步骤").and_then(|一| 一.表()).map(<[值]>::len), Some(1));
        assert_eq!(
            值.取("步骤").and_then(|步| 步.表()).and_then(|步| 步.first()).and_then(|步| 步.取("能力编号")).and_then(|一| 一.整数()),
            Some(1105)
        );
        assert_eq!(值.取("结果").and_then(|一| 一.真假()), Some(true));
        assert!(matches!(值.取("无"), Some(值::空)));
        assert_eq!(值.取("数").and_then(|一| 一.整数()), Some(1568));
    }

    /// 反向样本：坏输入必须报错（不是静默给一个空值）。
    #[test]
    fn 坏输入一律报错() {
        for 坏 in [
            "{",
            "[1,",
            r#"{"首项":}"#,
            r#"{"首项" 1}"#,
            "tru",
            "1.2.3",
            r#"{"首项":1} 尾巴"#,
            "\"未闭合",
        ] {
            assert!(解析(坏).is_err(), "`{坏}` 该被拒");
        }
    }

    /// 反向样本：`3.5` 不是整数（截断会把写错的数当对的用）。
    #[test]
    fn 小数不算整数() {
        assert_eq!(解("3.5").整数(), None);
        assert_eq!(解("3.0").整数(), Some(3));
        assert_eq!(解("-1").整数(), None);
    }

    #[test]
    fn 串的转义与中文都读得出() {
        assert_eq!(解(r#""a\u0041\n中""#).串(), Some("aA\n中"));
        assert_eq!(解(r#""\ud83d\ude00""#).串(), Some("😀"));
        let mut 文本缓冲 = String::new();
        写串(&mut 文本缓冲, "中\n\"");
        assert_eq!(文本缓冲, "\"中\\n\\\"\"");
        assert_eq!(解(&文本缓冲).串(), Some("中\n\""));
    }
}
