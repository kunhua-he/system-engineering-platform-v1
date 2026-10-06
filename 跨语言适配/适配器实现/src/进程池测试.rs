use std::num::NonZeroU64;
use std::time::Duration;

use crate::进程池::{
    默认退避基数毫秒, 默认退避上限毫秒, 默认重启预算, 进程池, 进程池配置, 进程池错误, 执行域标识,
};

fn 造标识(实例号: u64) -> 执行域标识 {
    执行域标识 {
        适配器实例号: 实例号,
        扩展标识串: String::from("扩展一"),
        制品版本: (1, 0, 0),
    }
}

fn 慢进程() -> (&'static str, Vec<String>) {
    ("/bin/sh", vec![String::from("-c"), String::from("sleep 5")])
}

fn 短命进程() -> (&'static str, Vec<String>) {
    ("/bin/sh", vec![String::from("-c"), String::from("exit 1")])
}

fn 急切配置() -> 进程池配置 {
    进程池配置 { 退避基数毫秒: 0, 退避上限毫秒: 0, 重启预算: 默认重启预算, 熔断时长毫秒: 1000 }
}

#[test]
fn 默认配置值与默认常量一致() {
    assert_eq!(默认退避基数毫秒, 50);
    assert_eq!(默认重启预算, 5);
    let 配置 = 进程池配置::default();
    assert_eq!(配置.退避基数毫秒, 默认退避基数毫秒);
    assert_eq!(配置.退避上限毫秒, 默认退避上限毫秒);
}

#[test]
fn 拉起一个域并监督它仍在运行() {
    let mut 池 = 进程池::新建(进程池配置::default());
    let 标识 = 造标识(1);
    let (程序, 参数) = 慢进程();
    池.保证域在(&标识, 程序, &参数).unwrap();
    assert_eq!(池.已建域数(), 1);
    assert!(池.含域(&标识));
    let 判读 = 池.监督一域(&标识).unwrap();
    assert!(判读.仍在运行);
    assert_eq!(判读.连续崩溃次数, 0);
}

#[test]
fn 未知域监督给结构化域不存在() {
    let mut 池 = 进程池::新建(进程池配置::default());
    let 标识 = 造标识(9);
    assert_eq!(池.监督一域(&标识), Err(进程池错误::域不存在));
}

#[test]
fn 退避窗内不许重拉窗后才许() {
    // 退避基数 = 上限 = 300 毫秒 ⇒ 崩溃后 300 ms 内重拉必被拒，窗过才放行。
    let 配置 = 进程池配置 { 退避基数毫秒: 300, 退避上限毫秒: 300, 重启预算: 5, 熔断时长毫秒: 1000 };
    let mut 池 = 进程池::新建(配置);
    let 标识 = 造标识(2);
    let (程序, 参数) = 短命进程();
    池.保证域在(&标识, 程序, &参数).unwrap();
    std::thread::sleep(Duration::from_millis(80));
    assert_eq!(池.崩溃重拉(&标识, 程序, &参数), Err(进程池错误::拉起失败));
    std::thread::sleep(Duration::from_millis(320));
    let 判读 = 池.崩溃重拉(&标识, 程序, &参数).unwrap();
    assert!(判读.已重拉);
    assert!(判读.仍在运行);
    assert_eq!(判读.连续崩溃次数, 1);
}

#[test]
fn 越过重启预算即熔断() {
    let 配置 = 进程池配置 { 重启预算: 2, ..急切配置() };
    let mut 池 = 进程池::新建(配置);
    let 标识 = 造标识(3);
    let (程序, 参数) = 短命进程();
    池.保证域在(&标识, 程序, &参数).unwrap();
    std::thread::sleep(Duration::from_millis(80));
    池.保证域在(&标识, 程序, &参数).unwrap();
    std::thread::sleep(Duration::from_millis(80));
    assert_eq!(池.保证域在(&标识, 程序, &参数), Err(进程池错误::熔断中));
    assert!(池.监督一域(&标识).unwrap().熔断中);
}

#[test]
fn 重放只放装载初始化() {
    let mut 池 = 进程池::新建(进程池配置::default());
    let 标识 = 造标识(4);
    let (程序, 参数) = 慢进程();
    池.保证域在(&标识, 程序, &参数).unwrap();
    assert!(!池.已重放装载(&标识));
    池.重放装载初始化(&标识, NonZeroU64::new(1).unwrap()).unwrap();
    assert!(池.已重放装载(&标识));
}

#[test]
fn 击杀一个域后监督报已停() {
    let mut 池 = 进程池::新建(进程池配置::default());
    let 标识 = 造标识(5);
    let (程序, 参数) = 慢进程();
    池.保证域在(&标识, 程序, &参数).unwrap();
    池.击杀一域(&标识).unwrap();
    assert!(!池.监督一域(&标识).unwrap().仍在运行);
}
