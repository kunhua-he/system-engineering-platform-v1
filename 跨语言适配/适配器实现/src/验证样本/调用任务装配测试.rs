//! 调用任务装配的测试 —— **整文件即测试**（`lib.rs` 用 `#[cfg(test)] #[path]` 挂进来）。
//!
//! | 判据 | 落点 |
//! |---|---|
//! | 单节点图结果与原路径一致 | `单节点图与原路径读数一致` |
//! | 叶子内二次提交被拒 | `叶子内二次提交被拒` |
//! | 同资源键先进先出 | `同资源键串行且按序` |
//! | 异键并行 | `异键并行执行` |
//! | 前置失败后代跳过 | `前置失败后代跳过` |
//! | 完成事件重放不双启 | `重复提交不双启` |
//! | 生成中不算成功 | `生成中不算成功` |

use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Condvar, Mutex};
use std::time::{Duration, Instant};

use v1_contract::数据槽;
use v1_dispatch::{调度错误, 调用节点阶段};

use crate::调用任务装配::{
    任务存储, 任务存储回调, 任务结局, 任务记录, 任务跟踪表, 叶子产出, 叶子执行口, 叶子标记,
    叶子请求, 存储错误, 工作线程数, 执行单次, 执行单能力, 节点素材, 装配错误, 调度实例, 资源键,
    跟踪错误, 跟踪阶段,
};

fn 空请求(节点: &str) -> 叶子请求 {
    叶子请求 {
        节点标识: 节点.to_owned(),
        执行批号: 0,
        编号: 0,
        入参: Vec::new(),
    }
}

fn 成功产出() -> 叶子产出 {
    叶子产出 {
        结果: crate::转发结果::成功(数据槽::空槽()),
        槽: 数据槽::空槽(),
        业务错误码: None,
    }
}

/// 假叶子：记录执行顺序；可指定一个节点失败。
#[derive(Default)]
struct 记数叶子 {
    执行序: Mutex<Vec<String>>,
    失败节点: Option<String>,
    标记: Arc<叶子标记>,
}

impl 记数叶子 {
    fn 新(失败节点: Option<&str>) -> Arc<Self> {
        Arc::new(Self {
            执行序: Mutex::new(Vec::new()),
            失败节点: 失败节点.map(str::to_owned),
            标记: Arc::new(叶子标记::新建()),
        })
    }

    /// 同一把防递归标记的第二个执行口（模拟生产：内层再提交走的还是同一适配器的快照）。
    fn 带标记(标记: Arc<叶子标记>) -> Arc<Self> {
        Arc::new(Self {
            执行序: Mutex::new(Vec::new()),
            失败节点: None,
            标记,
        })
    }

    fn 序(&self) -> Vec<String> {
        self.执行序
            .lock()
            .unwrap_or_else(|毒| 毒.into_inner())
            .clone()
    }
}

impl 叶子执行口 for 记数叶子 {
    fn 标记(&self) -> &叶子标记 {
        &self.标记
    }

    fn 执行(&self, 请求: &叶子请求) -> 叶子产出 {
        self.执行序
            .lock()
            .unwrap_or_else(|毒| 毒.into_inner())
            .push(请求.节点标识.clone());
        if self.失败节点.as_deref() == Some(请求.节点标识.as_str()) {
            return 叶子产出 {
                结果: crate::转发结果::失败(调度错误::配额用尽),
                槽: 数据槽::空槽(),
                业务错误码: None,
            };
        }
        成功产出()
    }
}

/// 并行假叶子：进叶子时 +1 记峰值，然后等「至少两个同时在跑」。
#[derive(Default)]
struct 并行叶子 {
    活跃: AtomicUsize,
    峰值: AtomicUsize,
    闸: (Mutex<usize>, Condvar),
    标记: Arc<叶子标记>,
}

impl 叶子执行口 for 并行叶子 {
    fn 标记(&self) -> &叶子标记 {
        &self.标记
    }

    fn 执行(&self, _请求: &叶子请求) -> 叶子产出 {
        let 当前 = self.活跃.fetch_add(1, Ordering::SeqCst) + 1;
        self.峰值.fetch_max(当前, Ordering::SeqCst);
        {
            let mut 计数 = self.闸.0.lock().unwrap_or_else(|毒| 毒.into_inner());
            *计数 += 1;
            self.闸.1.notify_all();
            let 起点 = Instant::now();
            while *计数 < 2 && 起点.elapsed() < Duration::from_millis(500) {
                let 剩余 = Duration::from_millis(500).saturating_sub(起点.elapsed());
                let (收下, _) = self
                    .闸
                    .1
                    .wait_timeout(计数, 剩余)
                    .unwrap_or_else(|毒| 毒.into_inner());
                计数 = 收下;
            }
        }
        self.活跃.fetch_sub(1, Ordering::SeqCst);
        成功产出()
    }
}

/// 判据：单能力走调度器与原路（直接进调度核心）**段位与槽逐字一致**。
#[test]
fn 单节点图与原路径读数一致() {
    let 适配器实例 = crate::适配器::装载(v1_loader::底座声明()).expect("底座可装载");
    let 入参 = crate::测试夹具::底座入参();
    let mut 新路槽 = 数据槽::空槽();
    let (新路, _追踪号) = 适配器实例.调用能力带追踪(0, &入参, &mut 新路槽);

    let 号值 = v1_contract::能力号::构造(0);
    let mut 原路槽 = 数据槽::空槽();
    // SAFETY: 入参 是 1 个可读槽、原路槽 可写；个数与声明一致（1）。
    let 原路关口 = unsafe {
        v1_dispatch::调用命令(
            适配器实例.取注册表(号值),
            &*适配器实例.账本,
            号值,
            &入参,
            &mut 原路槽,
        )
    };
    let 原路 = match 原路关口 {
        v1_dispatch::调用结果::成功 => crate::转发结果::成功(原路槽),
        v1_dispatch::调用结果::失败(值) => crate::转发结果::失败(值),
    };
    assert!(
        matches!(新路, crate::转发结果::成功(_)),
        "底座命令 0 应成功"
    );
    assert_eq!(新路, 原路, "段位必须逐字一致");
    assert_eq!(新路槽, 原路槽, "返回槽必须逐字一致");
}

/// 判据：叶子执行期间再提交任务图 ⇒ 被拒（防递归），且不静默放过。
#[test]
fn 叶子内二次提交被拒() {
    struct 重入叶子 {
        观测: Arc<Mutex<Option<装配错误>>>,
        标记: Arc<叶子标记>,
    }
    impl 叶子执行口 for 重入叶子 {
        fn 标记(&self) -> &叶子标记 {
            &self.标记
        }

        fn 执行(&self, _请求: &叶子请求) -> 叶子产出 {
            assert!(self.标记.在叶子内(), "叶子执行期间防递归标记必须置位");
            let 素材 = 节点素材::单能力(空请求("内层"), vec!["键".to_owned()]);
            let 读数 = 执行单次(
                vec![素材],
                记数叶子::带标记(Arc::clone(&self.标记)),
                "内层任务",
                Duration::from_secs(1),
            );
            let 错误 = 读数.expect_err("叶子内再提交必须被拒");
            *self.观测.lock().unwrap_or_else(|毒| 毒.into_inner()) = Some(错误);
            成功产出()
        }
    }

    let 观测 = Arc::new(Mutex::new(None));
    let 外层标记 = Arc::new(叶子标记::新建());
    let 素材 = vec![节点素材::单能力(
        空请求("外层"),
        vec!["键".to_owned()],
    )];
    let 结局 = 执行单次(
        素材,
        Arc::new(重入叶子 {
            观测: Arc::clone(&观测),
            标记: Arc::clone(&外层标记),
        }),
        "外层任务",
        Duration::from_secs(5),
    )
    .expect("外层应能收口");
    assert!(matches!(结局, 任务结局::成功(_)));
    let 记录 = 观测
        .lock()
        .unwrap_or_else(|毒| 毒.into_inner())
        .clone()
        .expect("内层必须留下被拒的读数");
    assert_eq!(记录, 装配错误::叶子内重入);
    assert!(!外层标记.在叶子内(), "叶子退出后标记必须复位");
}

/// 判据：同一条资源键的节点**串行**且按图序先进先出。
#[test]
fn 同资源键串行且按序() {
    let 叶子 = 记数叶子::新(None);
    let 键 = vec!["实例/原池/0/同一句柄".to_owned()];
    let 素材 = vec![
        节点素材::单能力(空请求("先"), 键.clone()),
        节点素材::单能力(空请求("后"), 键),
    ];
    let 结局 = 执行单次(
        素材,
        Arc::clone(&叶子) as Arc<dyn 叶子执行口>,
        "同键任务",
        Duration::from_secs(5),
    )
    .expect("同键两节点应能收口");
    assert!(matches!(结局, 任务结局::成功(_)));
    assert_eq!(
        叶子.序(),
        vec!["先".to_owned(), "后".to_owned()],
        "同键必须按图序先进先出"
    );
}

/// 判据：不同资源键的节点**同时在跑**（两条工作线都在启用）。
#[test]
fn 异键并行执行() {
    let 叶子 = Arc::new(并行叶子::default());
    let 素材 = vec![
        节点素材::单能力(空请求("左"), vec!["键-左".to_owned()]),
        节点素材::单能力(空请求("右"), vec!["键-右".to_owned()]),
    ];
    let mut 实例 = 调度实例::装配(素材, Arc::clone(&叶子) as Arc<dyn 叶子执行口>, "并行任务")
        .expect("应能装配");
    实例.提交().expect("提交应成立");
    let 结局 = 实例
        .等待任务(Duration::from_secs(5))
        .expect("应在时限内收口");
    assert!(matches!(结局, 任务结局::成功(_)));
    assert!(实例.停止(), "停机必须汇合全部工作线程");
    assert!(
        叶子.峰值.load(Ordering::SeqCst) >= 2,
        "两条不同的键必须能同时在跑，实测峰值 = {}",
        叶子.峰值.load(Ordering::SeqCst)
    );
}

/// 判据：前置失败 ⇒ 后代跳过，任务报失败（不把跳过当成功）。
#[test]
fn 前置失败后代跳过() {
    let 叶子 = 记数叶子::新(Some("起点"));
    let 素材 = vec![
        节点素材 {
            节点标识: "起点".to_owned(),
            依赖节点: Vec::new(),
            资源键: vec!["键-起点".to_owned()],
            请求: 空请求("起点"),
        },
        节点素材 {
            节点标识: "后继".to_owned(),
            依赖节点: vec!["起点".to_owned()],
            资源键: vec!["键-后继".to_owned()],
            请求: 空请求("后继"),
        },
    ];
    let 实例 = 调度实例::装配(素材, Arc::clone(&叶子) as Arc<dyn 叶子执行口>, "失败任务")
        .expect("应能装配");
    实例.提交().expect("提交应成立");
    let 结局 = 实例
        .等待任务(Duration::from_secs(5))
        .expect("应在时限内收口");
    match 结局 {
        任务结局::失败 { 错误, .. } => {
            assert_eq!(错误, Some(调度错误::配额用尽), "段位要原样交回")
        }
        _ => panic!("前置失败必须让任务报失败"),
    }
    assert_eq!(实例.记录阶段(), Some(v1_dispatch::调用任务阶段::失败));
    assert_eq!(实例.节点阶段("后继"), Some(调用节点阶段::跳过));
    assert_eq!(叶子.序(), vec!["起点".to_owned()], "后代不许被执行");
}

/// 判据：重复提交 / 完成事件重放 ⇒ 不双启、不改结论。
#[test]
fn 重复提交不双启() {
    let 叶子 = 记数叶子::新(None);
    let 素材 = vec![节点素材::单能力(
        空请求("唯一"),
        vec!["键".to_owned()],
    )];
    let 实例 = 调度实例::装配(素材, Arc::clone(&叶子) as Arc<dyn 叶子执行口>, "重放任务")
        .expect("应能装配");
    实例.提交().expect("首次提交成立");
    assert!(matches!(
        实例.等待任务(Duration::from_secs(5)),
        Some(任务结局::成功(_))
    ));
    实例.提交().expect("二次提交成立");
    assert!(matches!(
        实例.等待任务(Duration::from_secs(1)),
        Some(任务结局::成功(_))
    ));
    assert_eq!(叶子.序(), vec!["唯一".to_owned()], "重放不许再启一次");
    assert_eq!(实例.记录阶段(), Some(v1_dispatch::调用任务阶段::成功));
}

/// 判据：「生成中」不算节点成功；完成事件重放不改阶段。
#[test]
fn 生成中不算成功() {
    let mut 跟踪 = 任务跟踪表::新建();
    跟踪.登记生成中("节点", 7);
    assert_eq!(跟踪.查询("节点"), Some(跟踪阶段::生成中));
    assert!(!跟踪.算成功("节点"), "生成中一律不算成功");
    assert!(!跟踪.全部已收口(), "生成中即未收口");
    跟踪.登记完成(&v1_dispatch::节点完成事件 {
        节点标识: "节点".to_owned(),
        执行批号: 7,
        成功: true,
    });
    assert!(跟踪.算成功("节点"));
    assert!(跟踪.全部已收口());
    // 重放：阶段不变（仍已完成），不会退回生成中，也不会双计。
    跟踪.登记完成(&v1_dispatch::节点完成事件 {
        节点标识: "节点".to_owned(),
        执行批号: 7,
        成功: false,
    });
    assert_eq!(跟踪.查询("节点"), Some(跟踪阶段::已完成), "重放不许改结论");
}

/// 判据：单能力入口在叶子外可直接跑（装配层的正常路径）。
#[test]
fn 单能力入口可用() {
    let 适配器实例 = crate::适配器::装载(v1_loader::底座声明()).expect("底座可装载");
    let 入参 = crate::测试夹具::底座入参();
    let 标记 = 适配器实例.叶子标记.clone();
    let 结局 = 执行单能力(适配器实例, 标记, 0, &入参, 11);
    assert!(matches!(结局, 任务结局::成功(_)), "底座命令 0 应成功");
}

/// 判据：任务存储的注入位真的接得上（真库将来走这里）。
#[test]
fn 存储注入回调落盘() {
    struct 记账回调 {
        收下: Arc<Mutex<Vec<String>>>,
    }
    impl 任务存储回调 for 记账回调 {
        fn 写入(&mut self, 记录: &任务记录) -> Result<(), 存储错误> {
            self.收下
                .lock()
                .unwrap_or_else(|毒| 毒.into_inner())
                .push(format!("{:?}", 记录.阶段));
            Ok(())
        }
    }

    let 收下 = Arc::new(Mutex::new(Vec::new()));
    let mut 存储 = 任务存储::带注入(
        "外部库任务",
        Box::new(记账回调 {
            收下: Arc::clone(&收下),
        }),
    );
    存储.登记(vec!["节点".to_owned()]).expect("登记应成立");
    存储
        .保存阶段("节点", 调用节点阶段::执行中)
        .expect("落阶段应成立");
    存储
        .设置任务阶段(v1_dispatch::调用任务阶段::成功)
        .expect("落任务阶段应成立");
    let 条数 = 收下.lock().unwrap_or_else(|毒| 毒.into_inner()).len();
    assert_eq!(
        条数, 3,
        "注入回调必须逐条收到（登记 + 节点阶段 + 任务阶段）"
    );
    assert_eq!(
        存储.取().map(|记录| 记录.阶段),
        Some(v1_dispatch::调用任务阶段::成功)
    );
}

/// 判据：资源键按四段推导；图任务的车道节点独属（异节点并行、同键不会撞）。
#[test]
fn 资源键四段推导与车道独属() {
    let 键 = 资源键::推导(7, "原池", 3, "能力0");
    assert_eq!(
        键.车道键(),
        vec!["7/原池/3/能力0".to_owned()],
        "四段逐段拼，形态写死"
    );
    assert_ne!(
        crate::调用任务装配::图任务车道键(7, "节点一"),
        crate::调用任务装配::图任务车道键(7, "节点二"),
        "同图两节点不许共用车道"
    );
    const { assert!(工作线程数 >= 2, "异键并行要至少两条工作线") };
}

/// 判据：跟踪表只许「生成中」被取消；收口后取消是假动作。
#[test]
fn 取消只对生成中成立() {
    let mut 跟踪 = 任务跟踪表::新建();
    跟踪.登记生成中("节点", 1);
    跟踪.取消("节点").expect("生成中可以取消");
    assert_eq!(跟踪.查询("节点"), Some(跟踪阶段::已取消));
    assert_eq!(
        跟踪.取消("节点"),
        Err(跟踪错误::状态不可取消(跟踪阶段::已取消)),
        "已取消的项不许再取消"
    );
    assert!(跟踪.释放("节点"));
    assert!(!跟踪.释放("节点"), "释放幂等");
}
