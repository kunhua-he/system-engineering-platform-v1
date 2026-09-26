//! 运行回执 —— **追加**一行 JSON 到 `测试验证/案例/运行回执.jsonl`。
//!
//! # 为什么必须绑提交哈希
//!
//! 照抄 `项目文档/设计文档/判据的可信性.md` 第三节「假绿的六种来源」第 4 条
//! （「空集被算成通过」）与它的上位结论：
//!
//! > **回执必须绑提交哈希** —— 否则「回执是旧的」和「代码坏了」不可区分。
//!
//! 具体到本件：回执是**上一次跑**的读数。没有提交哈希，一份旧回执与一份新回执长得一模一样，
//! 于是「没跑过」会被当成「跑过了且通过」——那就是假绿。绑了哈希之后，门禁能直接判
//! 「这份回执说的是不是**这一个**提交」，`装门禁.sh` 就是这么判的。
//!
//! # 三个字段的口径
//!
//! - `提交哈希`：`git rev-parse HEAD` 的**完整**值（40 位十六进制，不截断）。
//! - `工作区是否干净`：`git status --porcelain` 除**回执自己**之外是否为空。
//!   排除回执自己是因为**每跑一次就追加一行 ⇒ 它自己永远是脏的**，不排除就恒为 `false`，
//!   那个字段就永远没有信息量。
//! - `跑的时间`：UTC 的 `YYYY-MM-DDTHH:MM:SSZ`（**不是本地时间**：跨机器比读数时本地时区是噪声）。

use std::io::Write;
use std::path::Path;
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

use crate::错误码::登记;

/// 回执文件名（写死一处）。住在案例根下，与案例目录并列。
pub const 回执文件名: &str = "运行回执.jsonl";

/// 回执相对仓根的路径。**它不参与「工作区是否干净」的判定**（见文件头）。
pub const 回执相对路: &str = "测试验证/案例/运行回执.jsonl";

/// 一条步骤读数。
#[derive(Debug, Clone)]
pub struct 步骤读数 {
    pub 名: String,
    pub 能力编号: u32,
    /// 适配器当场取到的能力名；`None` = 这个号没被任何已装载声明认领。
    pub 能力名: Option<String>,
    /// **这次调用**的结果：`成功` / `失败`（平台那一侧的结果，不是案例判定）。
    ///
    /// 与 [`步骤读数::符合期望`] 分开是**必须的**：「调 1101 期望它失败」这条案例里，
    /// 调用结果是 `失败`、判定结果是 `符合期望`。合成一个字段，读者会把
    /// 「案例通过」误读成「能力可用」——那正是假绿。
    pub 调用结果: String,
    /// 这一步是否符合 `期望.json` 写的那一条。
    pub 符合期望: bool,
    pub 死在哪一层: Option<String>,
    pub 死在哪一步: Option<String>,
    pub 错误码: Option<登记>,
    pub 耗时微秒: u128,
    /// 一句话读数（人读；机器只读上面那些字段）。
    pub 说明: String,
}

/// 一个案例一行。
#[derive(Debug, Clone)]
pub struct 回执 {
    pub 提交哈希: String,
    pub 工作区是否干净: bool,
    pub 案例名: String,
    pub 结果: String,
    pub 死在哪一层: Option<String>,
    pub 死在哪一步: Option<String>,
    pub 错误码: Option<登记>,
    pub 耗时微秒: u128,
    pub 跑的时间: String,
    pub 说明: String,
    pub 步骤: Vec<步骤读数>,
}

impl 回执 {
    /// 一行 JSON（**没有换行**，追加时补）。
    pub fn 到行(&self) -> String {
        let mut 出 = String::from("{");
        出.push_str("\"提交哈希\":");
        crate::最小JSON::写串(&mut 出, &self.提交哈希);
        出.push_str(&format!(",\"工作区是否干净\":{}", self.工作区是否干净));
        出.push_str(",\"案例名\":");
        crate::最小JSON::写串(&mut 出, &self.案例名);
        出.push_str(",\"结果\":");
        crate::最小JSON::写串(&mut 出, &self.结果);
        出.push_str(",\"死在哪一层\":");
        写可选串(&mut 出, self.死在哪一层.as_deref());
        出.push_str(",\"死在哪一步\":");
        写可选串(&mut 出, self.死在哪一步.as_deref());
        出.push_str(",\"错误码\":");
        match &self.错误码 {
            Some(码) => 出.push_str(&码.到JSON()),
            None => 出.push_str("null"),
        }
        出.push_str(&format!(",\"耗时微秒\":{}", self.耗时微秒));
        出.push_str(",\"跑的时间\":");
        crate::最小JSON::写串(&mut 出, &self.跑的时间);
        出.push_str(",\"说明\":");
        crate::最小JSON::写串(&mut 出, &self.说明);
        出.push_str(",\"步骤\":[");
        for (序, 步) in self.步骤.iter().enumerate() {
            if 序 > 0 {
                出.push(',');
            }
            出.push('{');
            出.push_str("\"名\":");
            crate::最小JSON::写串(&mut 出, &步.名);
            出.push_str(&format!(",\"能力编号\":{},\"能力名\":", 步.能力编号));
            写可选串(&mut 出, 步.能力名.as_deref());
            出.push_str(",\"调用结果\":");
            crate::最小JSON::写串(&mut 出, &步.调用结果);
            出.push_str(&format!(",\"符合期望\":{}", 步.符合期望));
            出.push_str(",\"死在哪一层\":");
            写可选串(&mut 出, 步.死在哪一层.as_deref());
            出.push_str(",\"死在哪一步\":");
            写可选串(&mut 出, 步.死在哪一步.as_deref());
            出.push_str(",\"错误码\":");
            match &步.错误码 {
                Some(码) => 出.push_str(&码.到JSON()),
                None => 出.push_str("null"),
            }
            出.push_str(&format!(",\"耗时微秒\":{},\"说明\":", 步.耗时微秒));
            crate::最小JSON::写串(&mut 出, &步.说明);
            出.push('}');
        }
        出.push_str("]}");
        出
    }
}

fn 写可选串(出: &mut String, 值: Option<&str>) {
    match 值 {
        Some(文) => crate::最小JSON::写串(出, 文),
        None => 出.push_str("null"),
    }
}

/// **追加**一行。追加不是覆盖：回执是历史，抹掉历史就没法判「回执是不是旧的」。
pub fn 追加(路: &Path, 行: &str) -> Result<(), String> {
    if let Some(父) = 路.parent() {
        std::fs::create_dir_all(父).map_err(|错| format!("建不了 {}：{错}", 父.display()))?;
    }
    let mut 件 = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(路)
        .map_err(|错| format!("打不开 {}：{错}", 路.display()))?;
    件.write_all(行.as_bytes())
        .and_then(|()| 件.write_all(b"\n"))
        .map_err(|错| format!("写不进 {}：{错}", 路.display()))
}

/// `git rev-parse HEAD` 的**完整**值。取不到就报错——**不许拿一个空串或短哈希顶上**。
pub fn 提交哈希(仓根: &Path) -> Result<String, String> {
    let 出 = Command::new("git")
        .arg("-C")
        .arg(仓根)
        .args(["rev-parse", "HEAD"])
        .output()
        .map_err(|错| format!("跑不了 git rev-parse：{错}"))?;
    if !出.status.success() {
        return Err(format!(
            "git rev-parse HEAD 失败：{}",
            String::from_utf8_lossy(&出.stderr).trim()
        ));
    }
    let 哈希 = String::from_utf8_lossy(&出.stdout).trim().to_owned();
    if 哈希.len() < 40 {
        return Err(format!("提交哈希不是完整值（{} 位）：`{哈希}`", 哈希.len()));
    }
    Ok(哈希)
}

/// 工作区是否干净：除**回执自己**之外的改动数为 0。
pub fn 工作区干净(仓根: &Path) -> Result<bool, String> {
    let 出 = Command::new("git")
        .arg("-C")
        .arg(仓根)
        .args(["status", "--porcelain", "--"])
        .arg(format!(":(exclude){回执相对路}"))
        .output()
        .map_err(|错| format!("跑不了 git status：{错}"))?;
    if !出.status.success() {
        return Err(format!(
            "git status 失败：{}",
            String::from_utf8_lossy(&出.stderr).trim()
        ));
    }
    Ok(String::from_utf8_lossy(&出.stdout).trim().is_empty())
}

/// UTC 的 `YYYY-MM-DDTHH:MM:SSZ`。自己算，不调外部程序（少一个环境依赖）。
pub fn 现在UTC() -> String {
    let 秒 = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|时| 时.as_secs() as i64)
        .unwrap_or(0);
    let 天 = 秒.div_euclid(86_400);
    let 日内 = 秒.rem_euclid(86_400);
    let (年, 月, 日) = 民用日期(天);
    format!(
        "{年:04}-{月:02}-{日:02}T{:02}:{:02}:{:02}Z",
        日内 / 3600,
        (日内 % 3600) / 60,
        日内 % 60
    )
}

/// 天数（1970-01-01 起）→ 公历日期。Howard Hinnant 的 `civil_from_days`，整数运算，无外部依赖。
fn 民用日期(天: i64) -> (i64, u32, u32) {
    let 移 = 天 + 719_468;
    let 纪元 = if 移 >= 0 { 移 } else { 移 - 146_096 } / 146_097;
    let 纪内 = (移 - 纪元 * 146_097) as u64;
    let 年内 = (纪内 - 纪内 / 1460 + 纪内 / 36_524 - 纪内 / 146_096) / 365;
    let 年 = 年内 as i64 + 纪元 * 400;
    let 日年 = 纪内 - (365 * 年内 + 年内 / 4 - 年内 / 100);
    let 月内 = (5 * 日年 + 2) / 153;
    let 日 = (日年 - (153 * 月内 + 2) / 5 + 1) as u32;
    let 月 = if 月内 < 10 { 月内 + 3 } else { 月内 - 9 } as u32;
    (if 月 <= 2 { 年 + 1 } else { 年 }, 月, 日)
}

#[cfg(test)]
mod 测试 {
    use super::*;

    /// 正向样本：已知时间点必须算出已知日期（否则时间戳是假的）。
    #[test]
    fn 日期算得对() {
        assert_eq!(民用日期(0), (1970, 1, 1));
        assert_eq!(民用日期(19_000), (2022, 1, 8));
        assert_eq!(民用日期(-1), (1969, 12, 31));
        assert_eq!(民用日期(29_000), (2049, 5, 26));
    }

    /// 反向样本：`工作区是否干净` 必须真的读 git（拿不到就报错，不许默认 true）。
    #[test]
    fn 提交哈希取不到就报错() {
        assert!(提交哈希(Path::new("/绝对不存在的目录")).is_err());
    }

    #[test]
    fn 时间戳形状是UTC() {
        let 时 = 现在UTC();
        assert_eq!(时.len(), 20, "形状该是 YYYY-MM-DDTHH:MM:SSZ：{时}");
        assert!(时.ends_with('Z'));
    }

    /// 正向样本：一行回执必须是**合法 JSON**（回执自己读不回来就是假读数）。
    #[test]
    fn 回执行是合法JSON() {
        let 回 = 回执 {
            提交哈希: "a".repeat(40),
            工作区是否干净: false,
            案例名: "甲\"乙".to_owned(),
            结果: "失败".to_owned(),
            死在哪一层: Some("内核".to_owned()),
            死在哪一步: Some("调度".to_owned()),
            错误码: Some(登记 {
                码: 1,
                段位: 0,
                名称: "提供者未载入".to_owned(),
                可重试: true,
                可自愈: true,
                需人工: false,
                已登记: true,
            }),
            耗时微秒: 7,
            跑的时间: 现在UTC(),
            说明: "换行\n也要转义".to_owned(),
            步骤: vec![步骤读数 {
                名: "甲".to_owned(),
                能力编号: 1105,
                能力名: Some("反解容器".to_owned()),
                调用结果: "成功".to_owned(),
                符合期望: true,
                死在哪一层: None,
                死在哪一步: None,
                错误码: None,
                耗时微秒: 3,
                说明: "无".to_owned(),
            }],
        };
        let 行 = 回.到行();
        let 解 = crate::最小JSON::解析(&行).expect("回执必须是合法 JSON");
        assert_eq!(解.取("案例名").and_then(|一| 一.串()), Some("甲\"乙"));
        assert_eq!(解.取("死在哪一层").and_then(|一| 一.串()), Some("内核"));
        assert!(matches!(解.取("步骤").and_then(|一| 一.表()).map(<[crate::最小JSON::值]>::len), Some(1)));
    }
}
