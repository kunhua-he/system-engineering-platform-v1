use std::process::Command;
use std::time::{Duration, Instant};

use crate::进程监督::{监督执行, 监督故障};

#[test]
fn 正常进程返回独立输出与退出码() {
    let mut 执行命令 = Command::new("/bin/sh");
    执行命令.args(["-c", "printf 正常; printf 诊断 >&2; exit 7"]);
    let 回执 = 监督执行(&mut 执行命令, Instant::now() + Duration::from_secs(1)).unwrap();
    assert_eq!(回执.退出状态.unwrap().code(), Some(7));
    assert_eq!(回执.标准输出, "正常".as_bytes());
    assert_eq!(回执.标准错误, "诊断".as_bytes());
    assert_eq!(回执.故障, None);
    assert!(回执.待回收进程.is_none());
    assert!(回执.进程组已回收);
}

#[test]
fn 正常退出回收后台后代并关闭输出通道() {
    for _ in 0..8 {
        let mut 执行命令 = Command::new("/bin/sh");
        执行命令.args(["-c", "sleep 20 & printf '%s %s\\n' \"$$\" \"$!\""]);
        let 回执 = 监督执行(&mut 执行命令, Instant::now() + Duration::from_secs(1)).unwrap();
        let 输出文本 = String::from_utf8(回执.标准输出.clone()).unwrap();
        let 进程编号: Vec<&str> = 输出文本.split_whitespace().collect();
        assert_eq!(进程编号.len(), 2);
        let 状态输出 = Command::new("/bin/ps").args(["-o", "stat=", "-p", 进程编号[1]]).output().unwrap();
        let 状态文本 = String::from_utf8_lossy(&状态输出.stdout).trim().to_owned();
        if !状态文本.is_empty() && !状态文本.starts_with('Z') {
            let _ = Command::new("/bin/kill").args(["-KILL", 进程编号[1]]).status();
        }
        assert!(状态文本.is_empty() || 状态文本.starts_with('Z'), "后代仍存活：{状态文本}");
        assert_eq!(回执.退出状态.unwrap().code(), Some(0));
        assert_eq!(回执.故障, None);
        assert!(回执.进程组已回收);
        assert!(回执.待回收进程.is_none());
        assert!(回执.耗时 < Duration::from_millis(500));
    }
}

#[test]
fn 已过期预算不启动进程() {
    let mut 执行命令 = Command::new("/不存在的进程");
    let 错误 = 监督执行(&mut 执行命令, Instant::now()).unwrap_err();
    assert_eq!(错误.kind(), std::io::ErrorKind::InvalidInput);
}

#[test]
fn 永久阻塞在截止后确认回收() {
    let mut 执行命令 = Command::new("/bin/sh");
    执行命令.args(["-c", "sleep 30"]);
    let 回执 = 监督执行(&mut 执行命令, Instant::now() + Duration::from_millis(80)).unwrap();
    assert_eq!(回执.故障, Some(监督故障::预算耗尽));
    assert!(回执.退出状态.is_some());
    assert!(回执.待回收进程.is_none());
    assert!(回执.耗时 < Duration::from_millis(100));
}

#[test]
fn 大量输出保留有界且不中断监督() {
    let mut 执行命令 = Command::new("/bin/sh");
    执行命令.args(["-c", "yes 输出"]);
    let 回执 = 监督执行(&mut 执行命令, Instant::now() + Duration::from_secs(1)).unwrap();
    assert_eq!(回执.故障, Some(监督故障::输出超量));
    assert_eq!(回执.标准输出.len(), 64 * 1024);
    assert!(回执.丢弃输出字节 > 0);
    assert!(回执.待回收进程.is_none());
}

#[test]
fn 大量错误输出使用独立限额() {
    let mut 执行命令 = Command::new("/bin/sh");
    执行命令.args(["-c", "yes 错误 >&2"]);
    let 回执 = 监督执行(&mut 执行命令, Instant::now() + Duration::from_secs(1)).unwrap();
    assert_eq!(回执.故障, Some(监督故障::输出超量));
    assert_eq!(回执.标准错误.len(), 64 * 1024);
    assert!(回执.丢弃错误字节 > 0);
    assert!(回执.待回收进程.is_none());
}

#[test]
fn 进程崩溃不带走宿主且可以继续执行() {
    let mut 执行命令 = Command::new("/bin/sh");
    执行命令.args(["-c", "kill -ABRT $$"]);
    let 回执 = 监督执行(&mut 执行命令, Instant::now() + Duration::from_secs(1)).unwrap();
    assert!(!回执.退出状态.unwrap().success());
    assert!(回执.待回收进程.is_none());
    正常进程返回独立输出与退出码();
}
