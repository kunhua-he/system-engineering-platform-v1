//! 实例自持的动态准入预算；不取消在途任务，不改配置硬上限。
use std::time::{Duration, Instant};

#[derive(Default)]
pub(crate) struct 动态预算状态 {
    CPU承压: bool,
    pub(super) 样本可信: bool,
    当前上限: u32,
    上次采样: Option<Instant>,
    上次CPU: Option<[u32; 4]>,
    最近CPU读数: Option<(Instant, u32)>,
    #[cfg(test)]
    pub(super) 固定样本: Option<(Option<u32>, Option<u32>)>,
}

impl 动态预算状态 {
    fn 重算(&mut self, 硬上限: u32, CPU忙碌: Option<u32>, 内存压力: Option<u32>) -> u32 {
        let CPU忙碌 = CPU忙碌.filter(|值| *值 <= 100);
        let 内存压力 = 内存压力.filter(|值| matches!(*值, 1 | 2 | 4));
        self.样本可信 = CPU忙碌.is_some() && 内存压力.is_some();
        match CPU忙碌 {
            Some(75..=100) => self.CPU承压 = true,
            Some(0..=60) | None => self.CPU承压 = false,
            _ => {}
        }
        if 硬上限 == 0 { self.当前上限 = 0; return 0; }
        let CPU上限 = if self.CPU承压 {
            ((u64::from(硬上限) * u64::from(100 - CPU忙碌.unwrap_or(0))).div_ceil(100) as u32).max(1)
        } else { 硬上限 };
        let 内存上限 = match 内存压力 {
            Some(2) => 硬上限.div_ceil(2),
            Some(4) => 1,
            _ => 硬上限,
        };
        self.当前上限 = 硬上限.min(CPU上限).min(内存上限);
        self.当前上限
    }

    pub(super) fn 取上限(&mut self, 硬上限: u32) -> u32 {
        #[cfg(test)]
        if let Some((CPU忙碌, 内存压力)) = self.固定样本 {
            return self.重算(硬上限, CPU忙碌, 内存压力);
        }
        if self.上次采样.is_some_and(|时刻| 时刻.elapsed() < Duration::from_millis(250)) {
            return self.当前上限.min(硬上限);
        }
        let (CPU计数, 内存压力) = 取系统压力样本();
        let 现在时刻 = Instant::now();
        self.上次采样 = Some(现在时刻);
        self.刷新样本(硬上限, CPU计数, 内存压力, 现在时刻)
    }

    fn 刷新样本(&mut self, 硬上限: u32, CPU计数: Option<[u32; 4]>, 内存压力: Option<u32>, 现在时刻: Instant) -> u32 {
        let CPU忙碌 = CPU计数.zip(self.上次CPU).and_then(|(当前计数, 上次)| {
            let 差分: [u64; 4] = std::array::from_fn(|序号| u64::from(当前计数[序号].wrapping_sub(上次[序号])));
            let 总差: u64 = 差分.iter().sum();
            (总差 > 0).then(|| ((总差 - 差分[2]) * 100 / 总差) as u32)
        });
        let CPU新鲜 = CPU忙碌.is_some();
        self.上次CPU = CPU计数;
        if let Some(忙碌比例) = CPU忙碌 { self.最近CPU读数 = Some((现在时刻, 忙碌比例)); }
        // 内核会缓存密集请求；零差分不是0%忙碌，最多沿用两秒已知压力且标不新鲜。
        let CPU忙碌 = CPU忙碌.or_else(|| CPU计数.and(self.最近CPU读数)
            .filter(|(时刻, _)| 现在时刻.saturating_duration_since(*时刻) <= Duration::from_secs(2)).map(|(_, 忙碌比例)| 忙碌比例));
        let 当前上限 = self.重算(硬上限, CPU忙碌, 内存压力);
        self.样本可信 &= CPU新鲜;
        当前上限
    }
}

/// 只读系统压力；主机端口每次归还，不启动进程、不管理其他应用。
#[cfg(target_os = "macos")]
fn 取系统压力样本() -> (Option<[u32; 4]>, Option<u32>) {
    use std::ffi::{c_char, c_void};
    unsafe extern "C" {
        fn mach_host_self() -> u32;
        fn task_self_trap() -> u32;
        fn host_statistics(主机端口: u32, 统计类别: i32, 输出: *mut i32, 统计项数: *mut u32) -> i32;
        fn mach_port_deallocate(任务端口: u32, 主机端口: u32) -> i32;
        fn sysctlbyname(名称: *const c_char, 输出: *mut c_void, 输出长度: *mut usize, 输入指针: *mut c_void, 输入长度: usize) -> i32;
    }
    let 当前任务端口 = unsafe { task_self_trap() };
    let 主机端口 = unsafe { mach_host_self() };
    let mut CPU计数 = [0u32; 4];
    let mut 统计项数 = 4u32;
    let CPU回执 = if 主机端口 == 0 { -1 } else { unsafe { host_statistics(主机端口, 3, CPU计数.as_mut_ptr().cast(), &mut 统计项数) } };
    if 主机端口 != 0 { unsafe { mach_port_deallocate(当前任务端口, 主机端口); } }
    if 当前任务端口 != 0 { unsafe { mach_port_deallocate(当前任务端口, 当前任务端口); } }
    let mut 内存压力 = 0u32;
    let mut 输出长度 = std::mem::size_of::<u32>();
    let 内存回执 = unsafe { sysctlbyname(c"kern.memorystatus_vm_pressure_level".as_ptr(), (&mut 内存压力 as *mut u32).cast(), &mut 输出长度, std::ptr::null_mut(), 0) };
    ((CPU回执 == 0 && 统计项数 == 4).then_some(CPU计数), (内存回执 == 0 && 输出长度 == 4).then_some(内存压力))
}

#[cfg(not(target_os = "macos"))]
fn 取系统压力样本() -> (Option<[u32; 4]>, Option<u32>) { (None, None) }

#[cfg(test)]
#[test]
fn 压力预算收缩恢复不超过配置() {
    let mut 预算状态 = 动态预算状态::default();
    assert_eq!(预算状态.重算(32, Some(90), Some(1)), 4);
    assert_eq!(预算状态.重算(32, Some(65), Some(1)), 12);
    assert_eq!(预算状态.重算(32, Some(50), Some(1)), 32);
    assert_eq!(预算状态.重算(32, Some(10), Some(2)), 16);
    assert_eq!(预算状态.重算(32, Some(10), Some(4)), 1);
    assert_eq!(预算状态.重算(0, Some(10), Some(4)), 0);
    assert_eq!(预算状态.重算(32, None, None), 32);
    assert!(!预算状态.样本可信);
}

#[cfg(all(test, target_os = "macos"))]
#[test]
#[ignore = "内核端口引用实测须单线程单跑"]
fn 真实内核采样齐全且主机端口无累积() {
    unsafe extern "C" {
        fn mach_host_self() -> u32;
        fn task_self_trap() -> u32;
        fn mach_port_get_refs(任务端口: u32, 主机端口: u32, 权利种类: i32, 引用数: *mut u32) -> i32;
        fn mach_port_deallocate(任务端口: u32, 主机端口: u32) -> i32;
    }
    let 当前任务端口 = unsafe { task_self_trap() };
    let 主机端口 = unsafe { mach_host_self() };
    let mut 原有引用数 = 0u32;
    assert_eq!(unsafe { mach_port_get_refs(当前任务端口, 主机端口, 0, &mut 原有引用数) }, 0);
    let mut 原有任务引用数 = 0u32;
    assert_eq!(unsafe { mach_port_get_refs(当前任务端口, 当前任务端口, 0, &mut 原有任务引用数) }, 0);
    for _ in 0..512 {
        let (CPU计数, 内存压力) = 取系统压力样本();
        assert!(CPU计数.is_some());
        assert!(matches!(内存压力, Some(1 | 2 | 4)));
    }
    let mut 当前引用数 = 0u32;
    assert_eq!(unsafe { mach_port_get_refs(当前任务端口, 主机端口, 0, &mut 当前引用数) }, 0);
    assert_eq!(原有引用数, 当前引用数, "每次采样的主机端口必须归还");
    let mut 当前任务引用数 = 0u32;
    assert_eq!(unsafe { mach_port_get_refs(当前任务端口, 当前任务端口, 0, &mut 当前任务引用数) }, 0);
    assert_eq!(原有任务引用数, 当前任务引用数, "采样取得的任务端口也须归还");
    assert_eq!(unsafe { mach_port_deallocate(当前任务端口, 主机端口) }, 0);
    assert_eq!(unsafe { mach_port_deallocate(当前任务端口, 当前任务端口) }, 0);
    let mut 预算状态 = 动态预算状态::default();
    预算状态.取上限(32);
    let 验证期限 = Instant::now() + Duration::from_secs(2);
    while !预算状态.样本可信 && Instant::now() < 验证期限 {
        std::thread::sleep(Duration::from_millis(260));
        预算状态.取上限(32);
    }
    let 当前上限 = 预算状态.当前上限;
    assert!(预算状态.样本可信, "CPU计数={:?} 原生样本={:?} 上次采样={:?} 当前上限={}", 预算状态.上次CPU, 取系统压力样本(), 预算状态.上次采样, 当前上限);
    assert!((1..=32).contains(&当前上限));
    println!("真实采样512次，端口引用前后{}={}，差分CPU与内存压力齐全，预算{}", 原有引用数, 当前引用数, 当前上限);
}

#[cfg(test)]
#[test]
fn 压力预算边界穷举保持硬配置护栏() {
    let mut 预算状态 = 动态预算状态::default();
    for 硬上限 in 0..=128u32 {
        for CPU忙碌 in 0..=101u32 {
            for 内存压力 in [None, Some(1), Some(2), Some(4), Some(7)] {
                let 当前上限 = 预算状态.重算(硬上限, Some(CPU忙碌), 内存压力);
                assert!(当前上限 <= 硬上限);
                assert!(硬上限 == 0 || 当前上限 >= 1);
                if CPU忙碌 == 101 || !matches!(内存压力, Some(1 | 2 | 4)) { assert!(!预算状态.样本可信); }
            }
        }
    }
}

#[cfg(test)]
#[test]
fn 内核重复计数不可当成零压力且缓存有界() {
    let mut 预算状态 = 动态预算状态::default();
    let 现在时刻 = Instant::now();
    assert_eq!(预算状态.刷新样本(32, Some([0, 0, 100, 0]), Some(1), 现在时刻), 32);
    assert!(!预算状态.样本可信);
    assert_eq!(预算状态.刷新样本(32, Some([90, 0, 110, 0]), Some(1), 现在时刻 + Duration::from_millis(250)), 4);
    assert!(预算状态.样本可信);
    assert_eq!(预算状态.刷新样本(32, Some([90, 0, 110, 0]), Some(1), 现在时刻 + Duration::from_millis(500)), 4);
    assert!(!预算状态.样本可信);
    assert_eq!(预算状态.刷新样本(32, Some([90, 0, 110, 0]), Some(1), 现在时刻 + Duration::from_secs(3)), 32);
    assert!(!预算状态.样本可信);
    assert_eq!(预算状态.刷新样本(32, Some([100, 0, 200, 0]), Some(1), 现在时刻 + Duration::from_secs(4)), 32);
    assert!(预算状态.样本可信);
}
