use std::num::NonZeroU64;
use std::os::unix::net::UnixStream;
use std::thread;
use std::time::{Duration, Instant};

use v1_contract::{类型标签, 数据槽};

use crate::进程帧::{调用帧预算, 接收帧, 发送帧, 消息帧, 消息类别};
use crate::线协议::{
    单次调用槽数上限, 单槽盘面字节数, 清理临时入参, 请求头字节数, 编码调用请求, 编码调用结果,
    解码调用请求, 解码调用结果, 线协议错误, 线协议会话,
};
use crate::协议结果;

fn 内联槽(标签: u32, 值: u64) -> 数据槽 {
    数据槽::内联槽(类型标签::构造(标签), 值, 0)
}

fn 请求标识(号: u64) -> NonZeroU64 {
    NonZeroU64::new(号).unwrap()
}

fn 测试预算() -> 调用帧预算 {
    调用帧预算::创建(Instant::now() + Duration::from_millis(500)).unwrap()
}

#[test]
fn 调用请求编解码往返() {
    let 槽表 = vec![内联槽(1, 1101), 数据槽::空槽()];
    let 载荷 = 编码调用请求(1101, &槽表).unwrap();
    let (号值, 回读槽表) = 解码调用请求(&载荷).unwrap();
    assert_eq!(号值, 1101);
    assert_eq!(回读槽表, 槽表);
}

#[test]
fn 解码调用请求先校界限() {
    assert_eq!(解码调用请求(&[0u8; 4]).unwrap_err(), 线协议错误::载荷过短);
    let mut 载荷 = Vec::new();
    载荷.extend_from_slice(&1101u32.to_le_bytes());
    载荷.extend_from_slice(&((单次调用槽数上限 + 1) as u32).to_le_bytes());
    assert_eq!(解码调用请求(&载荷).unwrap_err(), 线协议错误::槽数越界);
}

#[test]
fn 编码拒绝无地址的引用槽() {
    // 「引用 + 长度 > 0」却没给出可读地址（槽值 = 0）⇒ 结构化拒（不静默当空值）。
    let 槽表 = vec![数据槽::指针(类型标签::构造(4), 0, 64, false)];
    assert_eq!(编码调用请求(1101, &槽表).unwrap_err(), 线协议错误::含引用槽);
}

/// 造一个「引用 + 带数据」的槽（字节活到本次测试结束）。
fn 带数据槽(标签号: u32, 字节: &[u8]) -> 数据槽 {
    数据槽::指针(类型标签::构造(标签号), 字节.as_ptr() as u64, 字节.len() as u64, false)
}

/// 取出一个带数据槽在**本地**材料化出来的字节。
fn 取本地字节(槽项: &数据槽) -> Vec<u8> {
    // SAFETY: `收下字节槽` 造的是本地 `Box<[u8]>`，长度逐字相符；只读这一遍。
    unsafe { core::slice::from_raw_parts(槽项.槽值 as *const u8, 槽项.槽字节长度 as usize) }.to_vec()
}

#[test]
fn 文本与字节集过线往返() {
    // ★ 覆盖非空 / 中文 / 含零字节字节集：入参侧（调用请求）与返回值侧（调用结果）都验。
    let 中文 = "整数 定义为 1。".as_bytes();
    let 含零 = [0u8, 1, 0, 255, 0, 7];
    let 槽表 = vec![内联槽(1, 1101), 带数据槽(4, 中文), 带数据槽(5, &含零)];
    let 载荷 = 编码调用请求(1101, &槽表).unwrap();
    assert!(载荷.len() > 请求头字节数 + 槽表.len() * 单槽盘面字节数, "带数据必须有数据区");
    let (号值, mut 回读槽表) = 解码调用请求(&载荷).unwrap();
    assert_eq!(号值, 1101);
    assert_eq!(回读槽表.len(), 3);
    assert_eq!(回读槽表[0], 内联槽(1, 1101), "内联槽逐字不变");
    assert_eq!(取本地字节(&回读槽表[1]), 中文, "中文文本逐字节往返");
    assert_eq!(取本地字节(&回读槽表[2]), 含零, "含零字节集逐字节往返");
    assert_eq!(回读槽表[1].类型标签.取号值(), 4);
    assert_eq!(回读槽表[2].类型标签.取号值(), 5);
    // 返回侧：同一个返回槽（含数据）走结果编解码。
    let 返回槽 = 带数据槽(5, 中文);
    let 结果载荷 = 编码调用结果(协议结果::成功, &返回槽).unwrap();
    let (协议码值, 回读返回槽) = 解码调用结果(&结果载荷).unwrap();
    assert_eq!(协议码值, 协议结果::成功);
    assert_eq!(取本地字节(&回读返回槽), 中文);
    清理临时入参(&mut 回读槽表);
    let mut 还返回 = 回读返回槽;
    crate::值归还::归还槽值(&mut 还返回);
}

#[test]
fn 空文本与空字节集是合法值不是空槽() {
    let 槽表 = vec![带数据槽(4, &[]), 带数据槽(5, &[])];
    let 载荷 = 编码调用请求(1101, &槽表).unwrap();
    let (_号值, mut 回读槽表) = 解码调用请求(&载荷).unwrap();
    for 槽项 in &回读槽表 {
        assert!(槽项.是否引用(), "空文本/空字节集仍带引用标志");
        assert!(!槽项.是否空(), "它**不是**空槽");
        assert_eq!(槽项.槽字节长度, 0);
        assert_ne!(槽项.槽值, 0, "空值也要材料化成一块本地零长 Box");
    }
    assert_eq!(取本地字节(&回读槽表[0]).len(), 0);
    清理临时入参(&mut 回读槽表);
}

#[test]
fn 旧格式无数据区照样收() {
    // 长度自描述那条判据的反向样本：全内联 ⇒ 恰好旧格式长度，仍能收。
    let 槽表 = vec![内联槽(1, 42), 数据槽::空槽()];
    let 载荷 = 编码调用请求(1101, &槽表).unwrap();
    assert_eq!(载荷.len(), 请求头字节数 + 2 * 单槽盘面字节数, "全内联 ⇒ 恰好旧格式长度");
    let (号值, 回读槽表) = 解码调用请求(&载荷).unwrap();
    assert_eq!(号值, 1101);
    assert_eq!(回读槽表, 槽表);
}

#[test]
fn 数据区越界与槽区越界结构化拒() {
    // ② 头部 + 槽数×24 > 载荷长 ⇒ 载荷过短（先校界限再分配）。
    let mut 载荷 = Vec::new();
    载荷.extend_from_slice(&1101u32.to_le_bytes());
    载荷.extend_from_slice(&1u32.to_le_bytes());
    载荷.extend_from_slice(&[0u8; 8]);
    assert_eq!(解码调用请求(&载荷).unwrap_err(), 线协议错误::载荷过短);
    // ③ 带数据槽的偏移 + 长度超出数据区 ⇒ 数据区越界。
    let mut 坏 = Vec::new();
    坏.extend_from_slice(&1101u32.to_le_bytes());
    坏.extend_from_slice(&1u32.to_le_bytes());
    坏.extend_from_slice(&4u32.to_le_bytes());
    坏.extend_from_slice(&1u16.to_le_bytes());
    坏.extend_from_slice(&0u16.to_le_bytes());
    坏.extend_from_slice(&4096u64.to_le_bytes());
    坏.extend_from_slice(&0u64.to_le_bytes());
    坏.extend_from_slice(&[7u8; 8]);
    assert_eq!(解码调用请求(&坏).unwrap_err(), 线协议错误::数据区越界);
}

#[test]
fn 句柄与结构类型拒过线() {
    // 句柄（6）/ 任务句柄（7）不许当普通整数跨域。
    for 标签号 in [6u32, 7] {
        let 槽表 = vec![带数据槽(标签号, &[1, 2, 3])];
        assert_eq!(编码调用请求(1101, &槽表).unwrap_err(), 线协议错误::句柄不支持跨域);
    }
    // 尚无正式编码的结构类型（双精度 2 / 逻辑型 3）明确拒，不做字节搬运。
    for 标签号 in [2u32, 3] {
        let 槽表 = vec![带数据槽(标签号, &[1, 2, 3])];
        assert_eq!(编码调用请求(1101, &槽表).unwrap_err(), 线协议错误::结构未支持);
    }
}

#[test]
fn 内联句柄与任务句柄拒过线() {
    // 句柄（6）/ 任务句柄（7）的**正常形状是内联**（`内联槽(0006, 7, 0)`）——
    // 非引用槽同样不许过线（旧口径只校引用槽 ⇒ 句柄值被当普通整数搬过去）。
    for 标签号 in [6u32, 7] {
        let 槽表 = vec![内联槽(标签号, 7)];
        assert_eq!(
            编码调用请求(1101, &槽表).unwrap_err(),
            线协议错误::句柄不支持跨域,
            "内联 {标签号} 号槽必须拒过线"
        );
    }
    // 解码侧同理：非引用槽也要过同一道校（一个内联 6 号槽的盘面）。
    let mut 坏载荷 = Vec::new();
    坏载荷.extend_from_slice(&1101u32.to_le_bytes());
    坏载荷.extend_from_slice(&1u32.to_le_bytes());
    坏载荷.extend_from_slice(&6u32.to_le_bytes());
    坏载荷.extend_from_slice(&0u16.to_le_bytes());
    坏载荷.extend_from_slice(&0u16.to_le_bytes());
    坏载荷.extend_from_slice(&0u64.to_le_bytes());
    坏载荷.extend_from_slice(&7u64.to_le_bytes());
    assert_eq!(解码调用请求(&坏载荷).unwrap_err(), 线协议错误::句柄不支持跨域);
}

#[test]
fn 内联结构类型与整数照放行() {
    // 拒的只有句柄 6/7：内联结构类型（双精度 2 / 逻辑型 3）与整数、空槽在非引用分支照放行。
    let 槽表 = vec![内联槽(2, 1), 内联槽(3, 0), 内联槽(1, 42), 数据槽::空槽()];
    let 载荷 = 编码调用请求(1101, &槽表).unwrap();
    let (号值, 回读槽表) = 解码调用请求(&载荷).unwrap();
    assert_eq!(号值, 1101);
    assert_eq!(回读槽表, 槽表, "非引用分支除 6/7 外不设卡");
}

#[test]
fn 超单帧上限的载荷结构化过大() {
    // 编码侧**先判长度再复制**：超过单帧上限的带数据槽当场报「载荷过大」（不先整块复制）。
    {
        let 字节 = vec![7u8; crate::进程帧::单帧载荷上限 + 1];
        let 槽表 = vec![带数据槽(4, &字节)];
        assert_eq!(编码调用请求(1101, &槽表).unwrap_err(), 线协议错误::载荷过大);
    }
    // 恰好在上限内的仍可编（边界不误伤）。
    {
        let 字节 = vec![7u8; crate::进程帧::单帧载荷上限 - 请求头字节数 - 单槽盘面字节数];
        let 槽表 = vec![带数据槽(4, &字节)];
        assert!(编码调用请求(1101, &槽表).is_ok(), "上限内必须编得出");
    }
}

#[test]
fn 解码失败不泄漏已材料化的槽() {
    // 第 1 个槽合法、第 2 个槽偏移越界 ⇒ 第 1 个已材料化的本地 Box 必须被守卫归还。
    // 反向样本：把守卫去掉，这条会以重复释放 / 泄漏暴露（本测试只证不崩且拒对）。
    let mut 坏 = Vec::new();
    坏.extend_from_slice(&1101u32.to_le_bytes());
    坏.extend_from_slice(&2u32.to_le_bytes());
    坏.extend_from_slice(&4u32.to_le_bytes());
    坏.extend_from_slice(&1u16.to_le_bytes());
    坏.extend_from_slice(&0u16.to_le_bytes());
    坏.extend_from_slice(&3u64.to_le_bytes());
    坏.extend_from_slice(&0u64.to_le_bytes());
    坏.extend_from_slice(&4u32.to_le_bytes());
    坏.extend_from_slice(&1u16.to_le_bytes());
    坏.extend_from_slice(&0u16.to_le_bytes());
    坏.extend_from_slice(&3u64.to_le_bytes());
    坏.extend_from_slice(&99u64.to_le_bytes());
    坏.extend_from_slice(b"abc");
    assert_eq!(解码调用请求(&坏).unwrap_err(), 线协议错误::数据区越界);
}

#[test]
fn 调用结果只在两个协议码内() {
    let 载荷 = 编码调用结果(协议结果::成功, &内联槽(1, 42)).unwrap();
    let (协议码值, 返回槽) = 解码调用结果(&载荷).unwrap();
    assert_eq!(协议码值, 协议结果::成功);
    assert_eq!(返回槽, 内联槽(1, 42));
    let mut 坏载荷 = 7i32.to_le_bytes().to_vec();
    坏载荷.extend_from_slice(&载荷[4..]);
    assert_eq!(解码调用结果(&坏载荷).unwrap_err(), 线协议错误::协议码越界);
    assert_eq!(解码调用结果(&载荷[..5]).unwrap_err(), 线协议错误::结果头不符);
}

#[test]
fn 会话收发一次调用结果() {
    let (客户端, 服务端) = UnixStream::pair().unwrap();
    let 服务线程 = thread::spawn(move || {
        let mut 服务端 = 服务端;
        let 请求帧 = 接收帧(&mut 服务端, 请求标识(7), &mut 测试预算()).unwrap();
        let (号值, _参数槽表) = 解码调用请求(&请求帧.载荷).unwrap();
        let 返回槽 = 内联槽(2, u64::from(号值));
        let 结果帧 = 消息帧 {
            消息类型: 消息类别::调用结果,
            请求标识: 请求标识(7),
            载荷: 编码调用结果(协议结果::成功, &返回槽).unwrap(),
        };
        发送帧(&mut 服务端, &结果帧, &mut 测试预算()).unwrap();
    });
    let mut 会话 = 线协议会话::新建(客户端);
    let 标识 = 请求标识(7);
    会话.发起调用(标识, 1101, &[内联槽(1, 5)]).unwrap();
    let (协议码值, 返回槽) = 会话.收调用结果(标识).unwrap();
    服务线程.join().unwrap();
    assert_eq!(协议码值, 协议结果::成功);
    assert_eq!(返回槽, 内联槽(2, 1101));
}

#[test]
fn 收到别的类别即拒() {
    let (客户端, 服务端) = UnixStream::pair().unwrap();
    let 服务线程 = thread::spawn(move || {
        let mut 服务端 = 服务端;
        let 通知帧 = 消息帧 { 消息类型: 消息类别::通知, 请求标识: 请求标识(8), 载荷: Vec::new() };
        发送帧(&mut 服务端, &通知帧, &mut 测试预算()).unwrap();
    });
    let mut 会话 = 线协议会话::新建(客户端);
    assert_eq!(会话.收调用结果(请求标识(8)), Err(线协议错误::非调用结果帧));
    服务线程.join().unwrap();
}

#[test]
fn 排队投递满了结构化拒绝() {
    let (客户端, 服务端) = UnixStream::pair().unwrap();
    let 服务线程 = thread::spawn(move || {
        let mut 服务端 = 服务端;
        let 帧 = 消息帧 {
            消息类型: 消息类别::调用结果,
            请求标识: 请求标识(5),
            载荷: 编码调用结果(协议结果::成功, &数据槽::空槽()).unwrap(),
        };
        for _次 in 0..9 {
            发送帧(&mut 服务端, &帧, &mut 测试预算()).unwrap();
        }
    });
    let mut 会话 = 线协议会话::新建(客户端);
    let mut 结果 = Ok(());
    for _次 in 0..9 {
        结果 = 会话.排队投递(请求标识(5));
    }
    服务线程.join().unwrap();
    assert_eq!(结果, Err(线协议错误::队列已满));
    assert!(会话.取一件().is_some());
}
