use std::path::Path;

use super::回执件与读数::回执相对路径;
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

/// `git rev-parse HEAD` 的**完整**值。取不到就报错——**不许拿一个空串或短哈希顶上**。
pub fn 提交哈希(仓根: &Path) -> Result<String, String> {
    let 文本缓冲 = Command::new("git")
        .arg("-C")
        .arg(仓根)
        .args(["rev-parse", "HEAD"])
        .output()
        .map_err(|错误| format!("跑不了 git rev-parse：{错误}"))?;
    if !文本缓冲.status.success() {
        return Err(format!(
            "git rev-parse HEAD 失败：{}",
            String::from_utf8_lossy(&文本缓冲.stderr).trim()
        ));
    }
    let 哈希值 = String::from_utf8_lossy(&文本缓冲.stdout).trim().to_owned();
    if 哈希值.len() < 40 {
        return Err(format!(
            "提交哈希不是完整值（{} 位）：`{哈希值}`",
            哈希值.len()
        ));
    }
    Ok(哈希值)
}

/// 工作区是否干净：除**回执自身**之外的改动数为 0。
pub fn 工作区干净(仓根: &Path) -> Result<bool, String> {
    let 文本缓冲 = Command::new("git")
        .arg("-C")
        .arg(仓根)
        .args(["status", "--porcelain", "--"])
        .arg(format!(":(exclude){回执相对路径}"))
        .output()
        .map_err(|错误| format!("跑不了 git status：{错误}"))?;
    if !文本缓冲.status.success() {
        return Err(format!(
            "git status 失败：{}",
            String::from_utf8_lossy(&文本缓冲.stderr).trim()
        ));
    }
    Ok(String::from_utf8_lossy(&文本缓冲.stdout).trim().is_empty())
}

/// UTC 的 `YYYY-MM-DDTHH:MM:SSZ`。自身算，不调外部程序（少一个环境依赖）。
pub fn 现在UTC() -> String {
    let 纪元秒数 = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|时长| 时长.as_secs() as i64)
        .unwrap_or(0);
    let 天数 = 纪元秒数.div_euclid(86_400);
    let 日内 = 纪元秒数.rem_euclid(86_400);
    let (年份, 月份, 日序号) = 民用日期(天数);
    format!(
        "{年份:04}-{月份:02}-{日序号:02}T{:02}:{:02}:{:02}Z",
        日内 / 3600,
        (日内 % 3600) / 60,
        日内 % 60
    )
}

/// 天数（1970-01-01 起）→ 公历日期。Howard Hinnant 的 `civil_from_days`，整数运算，无外部依赖。
pub(super) fn 民用日期(天数: i64) -> (i64, u32, u32) {
    let 偏移天数 = 天数 + 719_468;
    let 纪元 = if 偏移天数 >= 0 {
        偏移天数
    } else {
        偏移天数 - 146_096
    } / 146_097;
    let 纪内 = (偏移天数 - 纪元 * 146_097) as u64;
    let 年内 = (纪内 - 纪内 / 1460 + 纪内 / 36_524 - 纪内 / 146_096) / 365;
    let 年份 = 年内 as i64 + 纪元 * 400;
    let 日年 = 纪内 - (365 * 年内 + 年内 / 4 - 年内 / 100);
    let 月内 = (5 * 日年 + 2) / 153;
    let 日序号 = (日年 - (153 * 月内 + 2) / 5 + 1) as u32;
    let 月份 = if 月内 < 10 { 月内 + 3 } else { 月内 - 9 } as u32;
    (if 月份 <= 2 { 年份 + 1 } else { 年份 }, 月份, 日序号)
}
