//! 纯判据层：命令行 → 进程端口 / 归属命中 / 受保护原因。
//!
//! 这里不读进程表、不杀进程、不碰 launchctl —— 全是可以造夹具验的字符串判据。

/// 取进程声明的端口：`--port 40118` / `--port=40118` / `-p 40118` / `--端口 40118`。
pub fn 取进程端口(命令行: &str) -> Option<i64> {
    let 参数字表: Vec<&str> = 命令行.split_whitespace().collect();
    for (参数位置, 参数) in 参数字表.iter().enumerate() {
        let 余段 = if *参数 == "--port" || *参数 == "--端口" || *参数 == "-p" {
            参数字表.get(参数位置 + 1).copied()
        } else if let Some(带等号) = 参数
            .strip_prefix("--port=")
            .or_else(|| 参数.strip_prefix("--端口="))
        {
            Some(带等号)
        } else {
            None
        };
        if let Some(端口值) = 余段 {
            if let Ok(端口数值) = 端口值.parse::<i64>() {
                return Some(端口数值);
            }
        }
    }
    None
}

/// 归属命中：端口指纹相等，或任一参数包含登记路径。
/// 返回命中说明（`端口:40118` / `路径:/…`），None = 没被证明归属 ⇒ 不进可清理。
pub fn 命中归属(命令行: &str, 端口集合: &[i64], 登记路径表: &[String]) -> Option<String> {
    if let Some(端口值) = 取进程端口(命令行) {
        if 端口集合.contains(&端口值) {
            return Some(format!("端口:{}", 端口值));
        }
    }
    for 登记路径 in 登记路径表 {
        if !登记路径.is_empty() && 命令行.contains(登记路径.as_str()) {
            return Some(format!("路径:{}", 登记路径));
        }
    }
    None
}

/// 受保护优先于可清理：命中保护程序关键词，或端口在保护端口表里。
pub fn 受保护原因(命令行: &str, 保护端口表: &[i64], 保护程序表: &[String]) -> Option<String> {
    for 保护程序 in 保护程序表 {
        if !保护程序.is_empty() && 命令行.contains(保护程序.as_str()) {
            return Some(format!("保护程序:{}", 保护程序));
        }
    }
    if let Some(端口值) = 取进程端口(命令行) {
        if 保护端口表.contains(&端口值) {
            return Some(format!("保护端口:{}", 端口值));
        }
    }
    None
}
