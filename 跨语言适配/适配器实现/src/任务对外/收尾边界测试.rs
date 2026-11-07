use super::*;
use crate::调用任务装配::{
    任务结局, 叶子产出, 叶子执行口, 叶子标记, 叶子请求, 节点素材
};
use std::sync::{Condvar, mpsc};

struct 闩锁叶子 {
    闩锁: Arc<(Mutex<bool>, Condvar)>,
    报到: mpsc::Sender<String>,
    标记: 叶子标记,
    未知: bool,
}
impl 叶子执行口 for 闩锁叶子 {
    fn 标记(&self) -> &叶子标记 {
        &self.标记
    }
    fn 执行(&self, 请求: &叶子请求) -> 叶子产出 {
        self.报到.send(请求.节点标识.clone()).unwrap();
        if 请求.节点标识 == "活根" {
            let mut 已放行 = self.闩锁.0.lock().unwrap();
            while !*已放行 {
                已放行 = self.闩锁.1.wait(已放行).unwrap();
            }
            return 叶子产出 {
                结果: crate::转发结果::成功(数据槽::空槽()),
                槽: 数据槽::空槽(),
                业务错误码: None,
            };
        }
        叶子产出 {
            结果: crate::转发结果::失败(if self.未知 {
                v1_dispatch::调度错误::超时 { 毫秒数: 1 }
            } else {
                v1_dispatch::调度错误::配额用尽
            }),
            槽: 数据槽::空槽(),
            业务错误码: None,
        }
    }
}

fn 造闩锁条目(未知: bool) -> (任务条目, Arc<(Mutex<bool>, Condvar)>) {
    let 闩锁 = Arc::new((Mutex::new(false), Condvar::new()));
    let (报到, 回报) = mpsc::channel();
    let 执行口 = Arc::new(闩锁叶子 {
        闩锁: Arc::clone(&闩锁),
        报到,
        标记: 叶子标记::default(),
        未知,
    });
    let mut 素材表: Vec<节点素材> = ["失败根", "活根"]
        .into_iter()
        .map(|标识| {
            节点素材::单能力(
                叶子请求 {
                    节点标识: 标识.to_owned(),
                    执行批号: 0,
                    编号: 0,
                    入参: vec![],
                },
                vec![],
            )
        })
        .collect();
    素材表.push(节点素材 {
        节点标识: "后继根".to_owned(),
        依赖节点: vec!["活根".to_owned()],
        资源键: vec![],
        请求: 叶子请求 {
            节点标识: "后继根".to_owned(),
            执行批号: 0,
            编号: 0,
            入参: vec![],
        },
    });
    let 调度本体 = Arc::new(调度实例::装配(素材表, 执行口, "收尾样本").unwrap());
    调度本体.提交().unwrap();
    for _ in 0..2 {
        回报.recv_timeout(Duration::from_secs(2)).unwrap();
    }
    let 起点 = Instant::now();
    while 调度本体.记录节点阶段("失败根")
        != Some(if 未知 {
            调用节点阶段::未知
        } else {
            调用节点阶段::失败
        })
    {
        if 起点.elapsed() > Duration::from_secs(2) {
            *闩锁.0.lock().unwrap() = true;
            闩锁.1.notify_all();
            panic!("失败根未提交完成事实");
        }
        std::thread::yield_now();
    }
    (
        任务条目 {
            任务标识: 1,
            请求标识: None,
            摘要: 0,
            实例: 调度本体,
            节点标识表: vec!["失败根".to_owned(), "活根".to_owned(), "后继根".to_owned()],
            取消: false,
            提交微秒: 0,
            末次访问: 0,
            失败表: Arc::new(Mutex::new(BTreeMap::from([(
                "失败根".to_owned(),
                "原始失败".to_owned(),
            )]))),
            产出表: Arc::new(Mutex::new(BTreeMap::new())),
        },
        闩锁,
    )
}

#[test]
fn 失败根与独立活根先收尾取消仍列在跑() {
    let (mut 条目, 闩锁) = 造闩锁条目(false);
    let 收尾阶段 = 阶段(&条目);
    let 读数 = 取消(&mut 条目);
    *闩锁.0.lock().unwrap() = true;
    闩锁.1.notify_all();
    let 结局 = 条目.实例.等待任务(Duration::from_secs(2));
    assert_eq!(收尾阶段, 调用任务阶段::收尾中);
    assert_eq!(读数.阶段, 调用任务阶段::收尾中);
    assert_eq!(读数.已取消节点, vec!["后继根".to_owned()]);
    assert!(条目.实例.节点时刻("后继根").is_none());
    assert_eq!(读数.在跑节点, vec!["活根".to_owned()]);
    assert!(matches!(结局, Some(任务结局::失败 { .. })));
    assert_eq!(阶段(&条目), 调用任务阶段::失败);
}

#[test]
fn 未知不写确认失败且取消不改未知() {
    let (mut 条目, 闩锁) = 造闩锁条目(true);
    let 读数 = 取消(&mut 条目);
    let 快照 = 造快照(&条目, None).unwrap();
    *闩锁.0.lock().unwrap() = true;
    闩锁.1.notify_all();
    let 结局 = 条目.实例.等待任务(Duration::from_secs(2));
    assert_eq!(读数.阶段, 调用任务阶段::收尾中);
    assert!(!读数.已取消节点.contains(&"失败根".to_owned()));
    assert!(快照.错误.is_none());
    assert_eq!(节点报读(&条目, "失败根"), 调用节点阶段::未知);
    assert_eq!(阶段(&条目), 调用任务阶段::未确认);
    assert!(matches!(结局, Some(任务结局::未确认 { .. })));
}

/// 叶子真被执行就说明「保存故障先于叶子」这条前提不成立了 —— 用例当场炸掉。
struct 不应执行叶子 {
    标记: 叶子标记,
}
impl 叶子执行口 for 不应执行叶子 {
    fn 标记(&self) -> &叶子标记 {
        &self.标记
    }
    fn 执行(&self, 请求: &叶子请求) -> 叶子产出 {
        panic!("保存故障必须在进叶子之前收束：{} 不该被调用", 请求.节点标识);
    }
}

/// 准入保存必失败的存储：装配时那一次初始落盘放行，之后一律失败 ——
/// 这样才能落到「装配成功、提交即持久故障」这一态（装配即失败是另一条腿）。
struct 必失败存储 {
    已写次数: usize,
}
impl crate::调用任务装配::任务存储回调 for 必失败存储 {
    fn 写入(
        &mut self,
        待存记录: &crate::调用任务装配::任务记录,
    ) -> Result<(), crate::调用任务装配::存储错误> {
        self.已写次数 += 1;
        if self.已写次数 == 1 {
            return Ok(());
        }
        Err(crate::调用任务装配::存储错误::持久故障(format!(
            "对第 {} 次保存注入故障：{}",
            self.已写次数, 待存记录.任务标识
        )))
    }
}

struct 可控落盘存储 { 日志故障开关: Arc<std::sync::atomic::AtomicBool> }
impl crate::调用任务装配::任务存储回调 for 可控落盘存储 {
    fn 写入(&mut self, 当前任务记录: &crate::调用任务装配::任务记录) -> Result<(), crate::调用任务装配::存储错误> {
        if self.日志故障开关.load(std::sync::atomic::Ordering::SeqCst)
            && 当前任务记录.节点阶段.get("完成节点") == Some(&调用节点阶段::成功)
        {
            return Err(crate::调用任务装配::存储错误::持久故障("完成节点保存故障".to_owned()));
        }
        Ok(())
    }
}

struct 双节点闩锁执行口 {
    节点闩锁集合: Arc<(Mutex<std::collections::BTreeSet<String>>, Condvar)>,
    节点到达接收器: mpsc::Sender<String>,
    标记: 叶子标记,
}
impl 叶子执行口 for 双节点闩锁执行口 {
    fn 标记(&self) -> &叶子标记 { &self.标记 }
    fn 执行(&self, 请求: &叶子请求) -> 叶子产出 {
        self.节点到达接收器.send(请求.节点标识.clone()).unwrap();
        let mut 已放行 = self.节点闩锁集合.0.lock().unwrap();
        while !已放行.contains(&请求.节点标识) {
            已放行 = self.节点闩锁集合.1.wait(已放行).unwrap();
        }
        叶子产出 {
            结果: crate::转发结果::成功(数据槽::空槽()),
            槽: 数据槽::空槽(),
            业务错误码: None,
        }
    }
}

#[test]
fn 存储故障仍有独立活节点时报收尾中() {
    let 节点闩锁集合 = Arc::new((Mutex::new(std::collections::BTreeSet::new()), Condvar::new()));
    let (节点到达接收器, 节点到达回报) = mpsc::channel();
    let 日志故障开关 = Arc::new(std::sync::atomic::AtomicBool::new(false));
    let 执行口 = Arc::new(双节点闩锁执行口 {
        节点闩锁集合: Arc::clone(&节点闩锁集合),
        节点到达接收器,
        标记: 叶子标记::default(),
    });
    let 节点素材表 = ["完成节点", "独立活节点"]
        .into_iter()
        .map(|节点标识| 节点素材::单能力(
            叶子请求 { 节点标识: 节点标识.to_owned(), 执行批号: 0, 编号: 0, 入参: vec![] },
            vec![],
        ))
        .collect();
    let 活动任务实例 = Arc::new(调度实例::装配带注入(
        节点素材表,
        执行口,
        "A11 存储故障活节点",
        Some(Box::new(可控落盘存储 { 日志故障开关: Arc::clone(&日志故障开关) })),
    ).unwrap());
    活动任务实例.提交().unwrap();
    let mut 活节点到达表 = std::collections::BTreeSet::new();
    for _ in 0..2 {
        活节点到达表.insert(节点到达回报.recv_timeout(Duration::from_secs(2)).unwrap());
    }
    assert_eq!(活节点到达表.len(), 2, "两节点都必须真实进入执行体");
    日志故障开关.store(true, std::sync::atomic::Ordering::SeqCst);
    {
        let mut 已放行 = 节点闩锁集合.0.lock().unwrap();
        已放行.insert("完成节点".to_owned());
        节点闩锁集合.1.notify_all();
    }
    let 运行起始时刻 = Instant::now();
    while 活动任务实例.存储故障().is_none() {
        assert!(运行起始时刻.elapsed() < Duration::from_secs(2), "完成节点的持久化故障必须真实触发");
        std::thread::yield_now();
    }
    let 收尾任务条目 = 任务条目 {
        任务标识: 1,
        请求标识: None,
        摘要: 0,
        实例: Arc::clone(&活动任务实例),
        节点标识表: vec!["完成节点".to_owned(), "独立活节点".to_owned()],
        取消: false,
        提交微秒: 0,
        末次访问: 0,
        失败表: Arc::new(Mutex::new(BTreeMap::new())),
        产出表: Arc::new(Mutex::new(BTreeMap::new())),
    };
    assert_eq!(阶段(&收尾任务条目), 调用任务阶段::收尾中, "存储故障不能盖过仍执行中的节点");
    assert_eq!(节点报读(&收尾任务条目, "完成节点"), 调用节点阶段::成功);
    assert_eq!(节点报读(&收尾任务条目, "独立活节点"), 调用节点阶段::执行中);
    {
        let mut 已放行 = 节点闩锁集合.0.lock().unwrap();
        已放行.insert("独立活节点".to_owned());
        节点闩锁集合.1.notify_all();
    }
    let 终态等待结果 = 活动任务实例.等待任务(Duration::from_secs(2));
    assert!(终态等待结果.is_some(), "放行后任务必须真实收口");
    drop(收尾任务条目);
    drop(活动任务实例);
}

#[test]
fn 存储故障下确认失败优先于未确认() {
    let 素材表 = vec![节点素材::单能力(
        叶子请求 {
            节点标识: "待执行节点".to_owned(),
            执行批号: 0,
            编号: 0,
            入参: vec![],
        },
        vec![],
    )];
    let 执行口 = Arc::new(不应执行叶子 {
        标记: 叶子标记::default(),
    });
    let 调度样本 = Arc::new(
        调度实例::装配带注入(
            素材表,
            执行口,
            "存储故障样本",
            Some(Box::new(必失败存储 { 已写次数: 0 })),
        )
        .unwrap(),
    );
    assert!(调度样本.提交().is_err(), "保存故障必须让提交失败");
    assert!(调度样本.存储故障().is_some(), "保存故障必须记在实例上");
    let 条目 = 任务条目 {
        任务标识: 1,
        请求标识: None,
        摘要: 0,
        实例: 调度样本,
        节点标识表: vec!["待执行节点".to_owned()],
        取消: false,
        提交微秒: 0,
        末次访问: 0,
        失败表: Arc::new(Mutex::new(BTreeMap::new())),
        产出表: Arc::new(Mutex::new(BTreeMap::new())),
    };
    assert_eq!(
        节点报读(&条目, "待执行节点"),
        调用节点阶段::失败,
        "确认未执行的节点记失败，不许写成未知"
    );
    assert_eq!(
        阶段(&条目),
        调用任务阶段::失败,
        "确认的失败不被存储故障改写成未确认（未确认只属于真有未知节点）"
    );
}
