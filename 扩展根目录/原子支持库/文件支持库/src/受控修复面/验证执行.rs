//! 验证执行 —— 3122 只按参数列表与明确超时在工作区里执行一次。
//!
//! 参数列表是 JSON 字符串数组（不拼 shell），超时 1–5000 毫秒；超时即杀，
//! 非零退出或超时一律 `受控验证失败`，并把工作区状态回读进结果。

use std::path::Path;
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

use crate::错误码;

use super::基础件::{命令, 对象JSON, 验证工作区};
use super::路径与参数解析::解析参数数组;

pub(super) fn 受控验证(参数: &[&str]) -> Result<Vec<u8>, u32> {
    let 根 = 验证工作区(Path::new(参数[0]))?;
    let 参数表 = 解析参数数组(参数[1])?;
    let 超时 = 参数[2].parse::<u64>().map_err(|_| 错误码::参数不合法)?;
    if !(1..=5000).contains(&超时) {
        return Err(错误码::参数不合法);
    }
    let mut 子进程 = Command::new(&参数表[0])
        .args(&参数表[1..])
        .current_dir(&根)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|_| 错误码::受控验证失败)?;
    let 开始 = Instant::now();
    let 状态 = loop {
        if let Some(退出) = 子进程.try_wait().map_err(|_| 错误码::受控验证失败)? {
            break Some(退出);
        }
        if 开始.elapsed() >= Duration::from_millis(超时) {
            let _ = 子进程.kill();
            break None;
        }
        std::thread::sleep(Duration::from_millis(10));
    };
    let 输出 = 子进程
        .wait_with_output()
        .map_err(|_| 错误码::受控验证失败)?;
    let 代码 = 状态.as_ref().and_then(|值| 值.code()).unwrap_or(-1);
    let 结果 = 对象JSON(&[
        ("退出码", 代码.to_string()),
        ("超时", 状态.is_none().to_string()),
        (
            "标准输出",
            String::from_utf8_lossy(&输出.stdout).into_owned(),
        ),
        (
            "标准错误",
            String::from_utf8_lossy(&输出.stderr).into_owned(),
        ),
        (
            "工作区状态",
            命令(&根, ["status", "--short"]).unwrap_or_else(|_| "状态读取失败".into()),
        ),
    ]);
    if 状态.is_none() || 代码 != 0 {
        Err(错误码::受控验证失败)
    } else {
        Ok(结果)
    }
}
