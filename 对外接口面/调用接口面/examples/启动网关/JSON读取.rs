//! 启动网关 · 最小 JSON 读 —— 只为读扩展根声明；不引第三方 crate。
//!
//! 从 `examples/启动网关.rs` 搬来（那是装配入口，本件是它的一个关注点；**纯搬家**）。

/// 一个 JSON 值。`空值` / `逻辑真` / `逻辑假` / `数值` 本件不用，但解析器必须认得它们 ——
/// 声明里多一个数就「读不了」，比多写四个变体贵得多。
#[allow(dead_code)]
pub(crate) enum JSON值 {
    空值,
    逻辑真,
    逻辑假,
    数值(f64),
    字符串(String),
    对象(Vec<(String, JSON值)>),
    数组(Vec<JSON值>),
}

impl JSON值 {
    pub(crate) fn 取成员(&self, 键: &str) -> Option<&JSON值> {
        match self {
            JSON值::对象(项) => 项.iter().find(|(名, _)| 名 == 键).map(|(_, 值)| 值),
            _ => None,
        }
    }
    pub(crate) fn 取字符串(&self) -> Option<&str> {
        if let JSON值::字符串(文) = self { Some(文) } else { None }
    }
    /// JSON 布尔 → `Some(true)` / `Some(false)`；**其余一律 `None`**
    /// （缺键、数、串、表、列都算「不是布尔」）。读方据此 fail-closed：
    /// 声明里 `可装载件` 缺键 / 非布尔时**不给默认值**（见 `装配.rs` 的那条口径）。
    pub(crate) fn 布尔(&self) -> Option<bool> {
        match self {
            JSON值::逻辑真 => Some(true),
            JSON值::逻辑假 => Some(false),
            _ => None,
        }
    }
    pub(crate) fn 取数组(&self) -> Option<&[JSON值]> {
        if let JSON值::数组(项) = self { Some(项) } else { None }
    }
}

pub(crate) struct 读器<'a> {
    字节: &'a [u8],
    位: usize,
}

impl<'a> 读器<'a> {
    pub(crate) fn 新建(文本: &'a str) -> Self {
        Self { 字节: 文本.as_bytes(), 位: 0 }
    }

    fn 跳空白(&mut self) {
        while self.字节.get(self.位).is_some_and(u8::is_ascii_whitespace) {
            self.位 += 1;
        }
    }

    pub(crate) fn 读一个值(&mut self) -> Result<JSON值, String> {
        self.跳空白();
        match self.字节.get(self.位) {
            None => Err("JSON 提前结束".into()),
            Some(b'{') => self.读对象(),
            Some(b'[') => self.读数组(),
            Some(b'"') => self.读字符串().map(JSON值::字符串),
            Some(b't') => self.字面("true", JSON值::逻辑真),
            Some(b'f') => self.字面("false", JSON值::逻辑假),
            Some(b'n') => self.字面("null", JSON值::空值),
            Some(_) => self.读数值(),
        }
    }

    fn 字面(&mut self, 文: &str, 出: JSON值) -> Result<JSON值, String> {
        if !self.字节[self.位..].starts_with(文.as_bytes()) {
            return Err(format!("第 {} 字节处不是合法 JSON 值", self.位));
        }
        self.位 += 文.len();
        Ok(出)
    }

    fn 读对象(&mut self) -> Result<JSON值, String> {
        self.位 += 1; // '{'
        let mut 项 = Vec::new();
        self.跳空白();
        if self.字节.get(self.位) == Some(&b'}') {
            self.位 += 1;
            return Ok(JSON值::对象(项));
        }
        loop {
            self.跳空白();
            let 名 = self.读字符串()?;
            self.跳空白();
            if self.字节.get(self.位) != Some(&b':') {
                return Err(format!("第 {} 字节处缺冒号", self.位));
            }
            self.位 += 1;
            项.push((名, self.读一个值()?));
            self.跳空白();
            match self.字节.get(self.位) {
                Some(b',') => self.位 += 1,
                Some(b'}') => {
                    self.位 += 1;
                    return Ok(JSON值::对象(项));
                }
                _ => return Err(format!("第 {} 字节处缺逗号或右括号", self.位)),
            }
        }
    }

    fn 读数组(&mut self) -> Result<JSON值, String> {
        self.位 += 1; // '['
        let mut 项 = Vec::new();
        self.跳空白();
        if self.字节.get(self.位) == Some(&b']') {
            self.位 += 1;
            return Ok(JSON值::数组(项));
        }
        loop {
            项.push(self.读一个值()?);
            self.跳空白();
            match self.字节.get(self.位) {
                Some(b',') => self.位 += 1,
                Some(b']') => {
                    self.位 += 1;
                    return Ok(JSON值::数组(项));
                }
                _ => return Err(format!("第 {} 字节处缺逗号或右括号", self.位)),
            }
        }
    }

    fn 读字符串(&mut self) -> Result<String, String> {
        if self.字节.get(self.位) != Some(&b'"') {
            return Err(format!("第 {} 字节处缺字符串", self.位));
        }
        self.位 += 1;
        let mut 出 = String::new();
        loop {
            match self.字节.get(self.位) {
                None => return Err("字符串没闭合".into()),
                Some(b'"') => {
                    self.位 += 1;
                    return Ok(出);
                }
                Some(b'\\') => {
                    self.位 += 1;
                    let 转 = self.字节.get(self.位).copied().unwrap_or(b'?');
                    self.位 += 1;
                    出.push(match 转 {
                        b'"' => '"',
                        b'\\' => '\\',
                        b'/' => '/',
                        b'b' => '\u{8}',
                        b'f' => '\u{c}',
                        b'n' => '\n',
                        b'r' => '\r',
                        b't' => '\t',
                        _ => '\u{fffd}',
                    });
                }
                Some(_) => {
                    let 余 = core::str::from_utf8(&self.字节[self.位..]).map_err(|_| "不是合法 UTF-8")?;
                    let 字 = 余.chars().next().ok_or("空字符")?;
                    出.push(字);
                    self.位 += 字.len_utf8();
                }
            }
        }
    }

    fn 读数值(&mut self) -> Result<JSON值, String> {
        let 起 = self.位;
        while self
            .字节
            .get(self.位)
            .is_some_and(|字| 字.is_ascii_digit() || matches!(字, b'-' | b'+' | b'.' | b'e' | b'E'))
        {
            self.位 += 1;
        }
        core::str::from_utf8(&self.字节[起..self.位])
            .ok()
            .and_then(|文| 文.parse::<f64>().ok())
            .map(JSON值::数值)
            .ok_or_else(|| format!("第 {起} 字节处不是合法 JSON 值"))
    }
}
