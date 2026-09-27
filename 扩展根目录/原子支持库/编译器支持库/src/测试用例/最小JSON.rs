//! 测试 · 最小 JSON 读取器（**只在测试里用**）。
//!
//! 为什么自身写：本扩展零第三方依赖，仓库里也没有 Rust 侧 JSON 读取器
//! （生成器是 Python）。声明自洽测试要读 `能力声明/*.json` 与 `错误码表/*.json`，
//! 所以在这里放一个只够用的递归下降读取器——它只服务测试，不进制品。
//!
//! 从 `src/lib.rs` 的 `#[cfg(test)] mod 测试` 里那个 `mod 最小JSON` 原样搬来（去掉外层模块壳）。

#[derive(Debug, Clone, PartialEq)]
pub(crate) enum JSON值 {
    空值,
    逻辑真(bool),
    数值(f64),
    字符串(String),
    数组(Vec<JSON值>),
    对象(Vec<(String, JSON值)>),
}

impl JSON值 {
    pub(crate) fn 取成员(&self, 键名: &str) -> Option<&JSON值> {
        match self {
            JSON值::对象(项s) => 项s.iter().find(|(名, _)| 名 == 键名).map(|(_, 值)| 值),
            _ => None,
        }
    }

    pub(crate) fn 取数值(&self) -> Option<f64> {
        match self {
            JSON值::数值(数) => Some(*数),
            _ => None,
        }
    }

    pub(crate) fn 取字符串(&self) -> Option<&str> {
        match self {
            JSON值::字符串(串) => Some(串),
            _ => None,
        }
    }

    pub(crate) fn 取数组(&self) -> Option<&[JSON值]> {
        match self {
            JSON值::数组(表) => Some(表),
            _ => None,
        }
    }

    /// JSON 的 `true` / `false`。
    pub(crate) fn 真假(&self) -> Option<bool> {
        match self {
            JSON值::逻辑真(真) => Some(*真),
            _ => None,
        }
    }
}

pub(crate) fn 解析(文本: &str) -> Option<JSON值> {
    let mut 读 = 读器 { 字节: 文本.as_bytes(), 位: 0 };
    读.跳空白();
    let 值 = 读.读一个值()?;
    读.跳空白();
    if 读.位 != 读.字节.len() {
        return None;
    }
    Some(值)
}

struct 读器<'a> {
    字节: &'a [u8],
    位: usize,
}

impl<'a> 读器<'a> {
    fn 取当前字节(&self) -> Option<u8> {
        self.字节.get(self.位).copied()
    }

    fn 跳空白(&mut self) {
        while matches!(self.取当前字节(), Some(b' ' | b'\t' | b'\n' | b'\r')) {
            self.位 += 1;
        }
    }

    fn 读一个值(&mut self) -> Option<JSON值> {
        self.跳空白();
        match self.取当前字节()? {
            b'{' => self.对象(),
            b'[' => self.数组(),
            b'"' => Some(JSON值::字符串(self.读字符串()?)),
            b't' => self.字面量(b"true", JSON值::逻辑真(true)),
            b'f' => self.字面量(b"false", JSON值::逻辑真(false)),
            b'n' => self.字面量(b"null", JSON值::空值),
            _ => self.读数值(),
        }
    }

    fn 字面量(&mut self, 期望: &[u8], 待处理值: JSON值) -> Option<JSON值> {
        if self.字节.get(self.位..self.位 + 期望.len())? == 期望 {
            self.位 += 期望.len();
            Some(待处理值)
        } else {
            None
        }
    }

    fn 对象(&mut self) -> Option<JSON值> {
        self.位 += 1; // {
        let mut 项s = Vec::new();
        self.跳空白();
        if self.取当前字节()? == b'}' {
            self.位 += 1;
            return Some(JSON值::对象(项s));
        }
        loop {
            self.跳空白();
            let 键 = self.读字符串()?;
            self.跳空白();
            if self.取当前字节()? != b':' {
                return None;
            }
            self.位 += 1;
            let 值 = self.读一个值()?;
            项s.push((键, 值));
            self.跳空白();
            match self.取当前字节()? {
                b',' => self.位 += 1,
                b'}' => {
                    self.位 += 1;
                    return Some(JSON值::对象(项s));
                }
                _ => return None,
            }
        }
    }

    fn 数组(&mut self) -> Option<JSON值> {
        self.位 += 1; // [
        let mut 项s = Vec::new();
        self.跳空白();
        if self.取当前字节()? == b']' {
            self.位 += 1;
            return Some(JSON值::数组(项s));
        }
        loop {
            let 值 = self.读一个值()?;
            项s.push(值);
            self.跳空白();
            match self.取当前字节()? {
                b',' => self.位 += 1,
                b']' => {
                    self.位 += 1;
                    return Some(JSON值::数组(项s));
                }
                _ => return None,
            }
        }
    }

    fn 读字符串(&mut self) -> Option<String> {
        if self.取当前字节()? != b'"' {
            return None;
        }
        self.位 += 1;
        let mut 出 = String::new();
        loop {
            let 字节 = self.取当前字节()?;
            match 字节 {
                b'"' => {
                    self.位 += 1;
                    return Some(出);
                }
                b'\\' => {
                    self.位 += 1;
                    let 转 = self.取当前字节()?;
                    self.位 += 1;
                    match 转 {
                        b'"' => 出.push('"'),
                        b'\\' => 出.push('\\'),
                        b'/' => 出.push('/'),
                        b'n' => 出.push('\n'),
                        b'r' => 出.push('\r'),
                        b't' => 出.push('\t'),
                        b'u' => {
                            let 码 = u32::from_str_radix(
                                std::str::from_utf8(self.字节.get(self.位..self.位 + 4)?)
                                    .ok()?,
                                16,
                            )
                            .ok()?;
                            self.位 += 4;
                            出.push(char::from_u32(码)?);
                        }
                        _ => return None,
                    }
                }
                _ => {
                    // 多字节 UTF-8：整块拷贝。
                    let 起 = self.位;
                    self.位 += UTF8字节长(字节);
                    出.push_str(std::str::from_utf8(self.字节.get(起..self.位)?).ok()?);
                }
            }
        }
    }

    fn 读数值(&mut self) -> Option<JSON值> {
        let 起 = self.位;
        while matches!(self.取当前字节(), Some(b'0'..=b'9' | b'-' | b'+' | b'.' | b'e' | b'E')) {
            self.位 += 1;
        }
        if self.位 == 起 {
            return None;
        }
        std::str::from_utf8(self.字节.get(起..self.位)?)
            .ok()?
            .parse()
            .ok()
            .map(JSON值::数值)
    }
}

/// 一个 UTF-8 首字节对应几字节。
fn UTF8字节长(首字节: u8) -> usize {
    if 首字节 < 0x80 {
        1
    } else if 首字节 >> 5 == 0b110 {
        2
    } else if 首字节 >> 4 == 0b1110 {
        3
    } else {
        4
    }
}
