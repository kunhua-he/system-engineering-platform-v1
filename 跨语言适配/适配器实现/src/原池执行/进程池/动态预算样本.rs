//! 注入样本只在测试编译中存在；真实内核采样另有独立测试。
use super::动态预算::{动态预算状态, 固定压力样本};
use super::{执行域标识, 申请进程额度, 进程池, 进程池配置, 进程池错误};
use std::sync::{
    Arc, Mutex,
    atomic::{AtomicU32, Ordering},
};

fn 样本域标识(序号: u32) -> 执行域标识 {
    执行域标识 {
        适配器实例号: 99,
        扩展标识串: format!("压力执行域{序号}"),
        制品版本: (1, 0, 0),
    }
}

#[test]
fn 预算原子准入不超发且租约全部归还() {
    let 活进程数 = Arc::new(AtomicU32::new(0));
    let 动态预算 = Arc::new(Mutex::new(动态预算状态::default()));
    动态预算.lock().unwrap().固定样本 = Some(固定压力样本 {
        CPU忙碌: Some(90),
        内存压力: Some(1),
        GPU忙碌: None,
    });
    let 额度列表 = std::thread::scope(|线程域| {
        let 线程表: Vec<_> = (0..32)
            .map(|_| 线程域.spawn(|| 申请进程额度(&活进程数, &动态预算, 32)))
            .collect();
        线程表
            .into_iter()
            .filter_map(|线程| 线程.join().unwrap().ok())
            .collect::<Vec<_>>()
    });
    assert_eq!(额度列表.len(), 4);
    assert_eq!(活进程数.load(Ordering::Acquire), 4);
    drop(额度列表);
    assert_eq!(活进程数.load(Ordering::Acquire), 0);
}

#[test]
fn 压力预算实例隔离且解除恢复硬配置() {
    let 承压池 = 进程池::创建(进程池配置 {
        子进程数上限: 32,
        ..进程池配置::default()
    });
    let 正常池 = 进程池::创建(进程池配置 {
        子进程数上限: 32,
        ..进程池配置::default()
    });
    承压池.设置压力样本(Some(90), Some(4));
    正常池.设置压力样本(Some(10), Some(1));
    assert_eq!(承压池.当前进程预算(), (1, true));
    assert_eq!(正常池.当前进程预算(), (32, true));
    承压池.设置压力样本(Some(40), Some(1));
    assert_eq!(承压池.当前进程预算(), (32, true));
    承压池.设置压力样本(None, None);
    assert_eq!(承压池.当前进程预算(), (32, false));
}

#[test]
fn 压力准入首拉接管与句柄重拉同额() {
    use crate::进程调用::域部署;
    use std::os::unix::net::UnixStream;
    let 承压池 = 进程池::创建(进程池配置 {
        子进程数上限: 2,
        退避基数毫秒: 0,
        ..进程池配置::default()
    });
    承压池.设置压力样本(Some(10), Some(4));
    let 启动参数 = vec![String::from("30")];
    let 当前执行域 = 样本域标识(1);
    let 候补执行域 = 样本域标识(2);
    承压池
        .保证域在(&当前执行域, "/bin/sleep", &启动参数)
        .unwrap();
    assert!(matches!(
        承压池.保证域在(&候补执行域, "/bin/sleep", &启动参数),
        Err(进程池错误::子进程数已满)
    ));
    let (宿主端, _对端) = UnixStream::pair().unwrap();
    let 部署参数 = 域部署 {
        启动程序: String::from("/bin/sleep"),
        启动参数: 启动参数.clone(),
    };
    assert!(matches!(
        承压池.收下已连域(候补执行域.clone(), 宿主端, 部署参数),
        Err(进程池错误::子进程数已满)
    ));
    let 句柄 = 承压池.取域句柄(&当前执行域).unwrap();
    承压池.击杀一域(&当前执行域).unwrap();
    承压池
        .保证域在(&候补执行域, "/bin/sleep", &启动参数)
        .unwrap();
    assert!(matches!(
        句柄.保证在("/bin/sleep", &启动参数),
        Err(进程池错误::子进程数已满)
    ));
    assert_eq!(承压池.活进程数(), 1);
    承压池.击杀一域(&候补执行域).unwrap();
    句柄.保证在("/bin/sleep", &启动参数).unwrap();
    assert_eq!(承压池.活进程数(), 1);
    承压池.击杀一域(&当前执行域).unwrap();
    assert_eq!(承压池.活进程数(), 0);
}

#[test]
fn 压力准入启动失败不吞额度() {
    let 承压池 = 进程池::创建(进程池配置 {
        子进程数上限: 2,
        ..进程池配置::default()
    });
    承压池.设置压力样本(Some(10), Some(4));
    assert!(
        承压池
            .保证域在(&样本域标识(1), "/不存在的执行器", &[])
            .is_err()
    );
    assert_eq!(承压池.活进程数(), 0);
    assert_eq!(承压池.已建域数(), 0);
    承压池
        .保证域在(&样本域标识(2), "/bin/sleep", &[String::from("30")])
        .unwrap();
    承压池.击杀一域(&样本域标识(2)).unwrap();
    assert_eq!(承压池.活进程数(), 0);
}

/// GPU 一路的收缩规则：**90 以上才收紧**（按剩余比例）；80 以下不动；读不到不缩。
///
/// 反向样本（老实现）：只看 CPU + 内存，`CPU=10 / 内存=1 / GPU=95` 时一直是 32 ⇒
/// 本地跑大模型、截图编码把 GPU 拉满而 CPU 还有余量时，进程照样起。
#[test]
fn GPU只在高位收紧且读不到不缩() {
    let 建池 = || {
        进程池::创建(进程池配置 {
            子进程数上限: 32,
            ..进程池配置::default()
        })
    };

    let 图卡池 = 建池();
    图卡池.设置压力样本含GPU(Some(10), Some(1), Some(95));
    // 32 × (100 − 95) / 100 = 1.6 ⇒ 向上取整 2
    assert_eq!(图卡池.当前进程预算(), (2, true));

    let 半载池 = 建池();
    半载池.设置压力样本含GPU(Some(10), Some(1), Some(70));
    assert_eq!(
        半载池.当前进程预算(),
        (32, true),
        "80 以下属正常负载：在算图不代表该掐并发"
    );

    let 读不到池 = 建池();
    读不到池.设置压力样本含GPU(Some(10), Some(1), None);
    assert_eq!(
        读不到池.当前进程预算(),
        (32, true),
        "读不到 GPU 就不缩 —— 不猜，也不假装 0"
    );

    let 满池 = 建池();
    满池.设置压力样本含GPU(Some(10), Some(1), Some(100));
    assert_eq!(满池.当前进程预算(), (1, true), "GPU 满退到 1，但不低于 1");
}
