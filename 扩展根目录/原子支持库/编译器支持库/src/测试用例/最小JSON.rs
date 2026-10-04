//! 测试 · 最小 JSON 读取器（**只在测试里用**）。
//!
//! 为什么自身写：本扩展零第三方依赖，仓库里也没有 Rust 侧 JSON 读取器
//! （生成器是 Python）。声明自洽测试要读 `能力声明/*.json` 与 `错误码表/*.json`，
//! 所以在这里放一个只够用的递归下降读取器——它只服务测试，不进制品。
//!
//! 从 `src/lib.rs` 的 `#[cfg(test)] mod 测试` 里那个 `mod 最小JSON` 原样搬来（去掉外层模块壳）。
//!
//! # 与 `测试验证/案例/跑案例/src/最小JSON.rs` 的关系（2026-09-30）
//!
//! 仓里有**两份**最小 JSON 读取器，分处**互斥的层**（那份住 `v1-case-runner`，本份住编译器
//! 支持库的测试面）⇒ 实现体**不合并**。**那份是严的**；**本份是有意简化的测试子集**
//! （返回 `Option` 而非 `Result`、不带字节位置、只服务声明自洽测试）。**但行为不许更松**：
//! 2026-09-30 已把三处差异按严的那份对齐 —— ① 代理对（`\ud83d\ude00`）解得成一个字符；
//! ② 字符串里未转义的控制字符（`< 0x20`）当场拒；③ 数字的 `+/-` 只在开头收。

#[derive(Debug, Clone, PartialEq)]
pub(crate) enum JSON值 {
    空值,
    真,
    假,
    数值(f64),
    字符串(String),
    数组(Vec<JSON值>),
    对象(Vec<(String, JSON值)>),
}

impl JSON值 {
    pub(crate) fn 取成员(&self, 键名: &str) -> Option<&JSON值> {
        match self {
            JSON值::对象(项s) => 项s.iter().find(|(名称, _)| 名称 == 键名).map(|(_, 待处理值)| 待处理值),
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
            JSON值::真 => Some(true),
            JSON值::假 => Some(false),
            _ => None,
        }
    }
}

pub(crate) fn 解析JSON值(文本: &str) -> Option<JSON值> {
    let mut 顺序读器 = 顺序读器 { 字节: 文本.as_bytes(), 位: 0 };
    顺序读器.跳空白();
    let 待处理值 = 顺序读器.读一个值()?;
    顺序读器.跳空白();
    if 顺序读器.位 != 顺序读器.字节.len() {
        return None;
    }
    Some(待处理值)
}

struct 顺序读器<'a> {
    字节: &'a [u8],
    位: usize,
}

impl<'a> 顺序读器<'a> {
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
            b'"' => Some(JSON值::字符串(self.读JSON串()?)),
            b't' => self.吃字面量(b"true", JSON值::真),
            b'f' => self.吃字面量(b"false", JSON值::假),
            b'n' => self.吃字面量(b"null", JSON值::空值),
            _ => self.读数值(),
        }
    }

    fn 吃字面量(&mut self, 期望: &[u8], 待处理值: JSON值) -> Option<JSON值> {
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
            let 键名 = self.读JSON串()?;
            self.跳空白();
            if self.取当前字节()? != b':' {
                return None;
            }
            self.位 += 1;
            let 待处理值 = self.读一个值()?;
            项s.push((键名, 待处理值));
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
            let 待处理值 = self.读一个值()?;
            项s.push(待处理值);
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

    fn 读JSON串(&mut self) -> Option<String> {
        if self.取当前字节()? != b'"' {
            return None;
        }
        self.位 += 1;
        let mut 输出缓冲 = String::new();
        loop {
            let 字节 = self.取当前字节()?;
            match 字节 {
                b'"' => {
                    self.位 += 1;
                    return Some(输出缓冲);
                }
                b'\\' => {
                    self.位 += 1;
                    let 转义符 = self.取当前字节()?;
                    self.位 += 1;
                    match 转义符 {
                        b'"' => 输出缓冲.push('"'),
                        b'\\' => 输出缓冲.push('\\'),
                        b'/' => 输出缓冲.push('/'),
                        b'b' => 输出缓冲.push('\u{8}'),
                        b'f' => 输出缓冲.push('\u{c}'),
                        b'n' => 输出缓冲.push('\n'),
                        b'r' => 输出缓冲.push('\r'),
                        b't' => 输出缓冲.push('\t'),
                        b'u' => 输出缓冲.push(self.取码点()?),
                        _ => return None,
                    }
                }
                // 未转义的控制字符不是合法 JSON（与 `跑案例/最小JSON.rs` 同一口径）。
                控制字节 if 控制字节 < 0x20 => return None,
                _ => {
                    // 多字节 UTF-8：整块拷贝。
                    let 区间起点 = self.位;
                    self.位 += UTF8字节长(字节);
                    输出缓冲.push_str(std::str::from_utf8(self.字节.get(区间起点..self.位)?).ok()?);
                }
            }
        }
    }

    /// `\u` 后的码点；**代理对合成一个字符**（与 `跑案例/最小JSON.rs` 同一口径）。
    fn 取码点(&mut self) -> Option<char> {
        let 高代理 = self.取四位()?;
        if (0xD800..0xDC00).contains(&高代理) {
            if self.取当前字节()? != b'\\' {
                return None;
            }
            self.位 += 1;
            if self.取当前字节()? != b'u' {
                return None;
            }
            self.位 += 1;
            let 低代理 = self.取四位()?;
            if !(0xDC00..0xE000).contains(&低代理) {
                return None;
            }
            let 合成码点 = 0x10000 + ((高代理 - 0xD800) << 10) + (低代理 - 0xDC00);
            return char::from_u32(合成码点);
        }
        char::from_u32(高代理)
    }

    /// 取 `\u` 后的 4 位十六进制。
    fn 取四位(&mut self) -> Option<u32> {
        let 四位值 = u32::from_str_radix(
            std::str::from_utf8(self.字节.get(self.位..self.位 + 4)?).ok()?,
            16,
        )
        .ok()?;
        self.位 += 4;
        Some(四位值)
    }

    fn 读数值(&mut self) -> Option<JSON值> {
        let 区间起点 = self.位;
        if matches!(self.取当前字节(), Some(b'-' | b'+')) {
            self.位 += 1;
        }
        while matches!(self.取当前字节(), Some(b'0'..=b'9' | b'.' | b'e' | b'E' | b'+' | b'-')) {
            self.位 += 1;
        }
        if self.位 == 区间起点 {
            return None;
        }
        std::str::from_utf8(self.字节.get(区间起点..self.位)?)
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
