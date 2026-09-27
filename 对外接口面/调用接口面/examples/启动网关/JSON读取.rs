//! 启动网关 · 最小 JSON 读 —— 只为读扩展根声明；不引第三方 crate。
//!
//! 从 `examples/启动网关.rs` 搬来（那是装配入口，本件是它的一个关注点；**纯搬家**）。

/// 一个 JSON 值。`空` / `真` / `假` / `数` 本件不用，但解析器必须认得它们 ——
/// 声明里多一个数就「读不了」，比多写四个变体贵得多。
#[allow(dead_code)]
pub(crate) enum 值 {
    空,
    真,
    假,
    数(f64),
    串(String),
    表(Vec<(String, 值)>),
    列(Vec<值>),
}

impl 值 {
    pub(crate) fn 取成员(&self, 键: &str) -> Option<&值> {
        match self {
            值::表(项) => 项.iter().find(|(名, _)| 名 == 键).map(|(_, 值)| 值),
            _ => None,
        }
    }
    pub(crate) fn 串(&self) -> Option<&str> {
        if let 值::串(文) = self { Some(文) } else { None }
    }
    /// JSON 布尔 → `Some(true)` / `Some(false)`；**其余一律 `None`**
    /// （缺键、数、串、表、列都算「不是布尔」）。读方据此 fail-closed：
    /// 声明里 `可装载件` 缺键 / 非布尔时**不给默认值**（见 `装配.rs` 的那条口径）。
    pub(crate) fn 布尔(&self) -> Option<bool> {
        match self {
            值::真 => Some(true),
            值::假 => Some(false),
            _ => None,
        }
    }
    pub(crate) fn 列(&self) -> Option<&[值]> {
        if let 值::列(项) = self { Some(项) } else { None }
    }
}

pub(crate) struct 读器<'a> {
    字节: &'a [u8],
    位: usize,
}

impl<'a> 读器<'a> {
    pub(crate) fn 新(文本: &'a str) -> Self {
        Self { 字节: 文本.as_bytes(), 位: 0 }
    }

    fn 跳空白(&mut self) {
        while self.字节.get(self.位).is_some_and(u8::is_ascii_whitespace) {
            self.位 += 1;
        }
    }

    pub(crate) fn 值(&mut self) -> Result<值, String> {
        self.跳空白();
        match self.字节.get(self.位) {
            None => Err("JSON 提前结束".into()),
            Some(b'{') => self.表(),
            Some(b'[') => self.列(),
            Some(b'"') => self.串().map(值::串),
            Some(b't') => self.字面("true", 值::真),
            Some(b'f') => self.字面("false", 值::假),
            Some(b'n') => self.字面("null", 值::空),
            Some(_) => self.数(),
        }
    }

    fn 字面(&mut self, 文: &str, 出: 值) -> Result<值, String> {
        if !self.字节[self.位..].starts_with(文.as_bytes()) {
            return Err(format!("第 {} 字节处不是合法 JSON 值", self.位));
        }
        self.位 += 文.len();
        Ok(出)
    }

    fn 表(&mut self) -> Result<值, String> {
        self.位 += 1; // '{'
        let mut 项 = Vec::new();
        self.跳空白();
        if self.字节.get(self.位) == Some(&b'}') {
            self.位 += 1;
            return Ok(值::表(项));
        }
        loop {
            self.跳空白();
            let 名 = self.串()?;
            self.跳空白();
            if self.字节.get(self.位) != Some(&b':') {
                return Err(format!("第 {} 字节处缺冒号", self.位));
            }
            self.位 += 1;
            项.push((名, self.值()?));
            self.跳空白();
            match self.字节.get(self.位) {
                Some(b',') => self.位 += 1,
                Some(b'}') => {
                    self.位 += 1;
                    return Ok(值::表(项));
                }
                _ => return Err(format!("第 {} 字节处缺逗号或右括号", self.位)),
            }
        }
    }

    fn 列(&mut self) -> Result<值, String> {
        self.位 += 1; // '['
        let mut 项 = Vec::new();
        self.跳空白();
        if self.字节.get(self.位) == Some(&b']') {
            self.位 += 1;
            return Ok(值::列(项));
        }
        loop {
            项.push(self.值()?);
            self.跳空白();
            match self.字节.get(self.位) {
                Some(b',') => self.位 += 1,
                Some(b']') => {
                    self.位 += 1;
                    return Ok(值::列(项));
                }
                _ => return Err(format!("第 {} 字节处缺逗号或右括号", self.位)),
            }
        }
    }

    fn 串(&mut self) -> Result<String, String> {
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

    fn 数(&mut self) -> Result<值, String> {
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
            .map(值::数)
            .ok_or_else(|| format!("第 {起} 字节处不是合法 JSON 值"))
    }
}
