use super::*;
use std::sync::atomic::{AtomicUsize, Ordering};
use v1_dispatch::{调用任务图, 调用任务节点};

struct 验证存储 {
    写入计数: Arc<AtomicUsize>,
}
impl super::super::存储::任务存储回调 for 验证存储 {
    fn 写入(
        &mut self,
        _记录: &super::super::存储::任务记录,
    ) -> Result<(), super::super::存储::存储错误> {
        self.写入计数.fetch_add(1, Ordering::SeqCst);
        Ok(())
    }
}

fn 造驱动状态() -> (实例状态, Arc<AtomicUsize>) {
    let 素材表: BTreeMap<String, 节点素材> = ["已成根", "活根"]
        .into_iter()
        .map(|标识| {
            let 请求 = 叶子请求 {
                节点标识: 标识.to_owned(),
                执行批号: 0,
                编号: 0,
                入参: vec![],
            };
            (标识.to_owned(), 节点素材::单能力(请求, vec![]))
        })
        .collect();
    let 节点表 = 素材表
        .keys()
        .map(|标识| 调用任务节点::构造(标识.clone(), Vec::<String>::new()))
        .collect();
    let 写入计数 = Arc::new(AtomicUsize::new(0));
    let mut 任务记录 = 任务存储::带注入(
        "边界样本",
        Box::new(验证存储 {
            写入计数: Arc::clone(&写入计数),
        }),
    );
    任务记录.登记(素材表.keys().cloned()).unwrap();
    let mut 状态 = 实例状态 {
        调度器: 调用任务调度器::构造(调用任务图::构造图(节点表).unwrap()),
        素材表,
        待执行: VecDeque::new(),
        槽表: BTreeMap::new(),
        失败表: BTreeMap::new(),
        未知表: BTreeMap::new(),
        结局: None,
        停止: false,
        请求取消: false,
        记录: 任务记录,
        跟踪: 任务跟踪表::新建(),
        零时: Instant::now(),
        时刻表: BTreeMap::new(),
    };
    状态.冲刷().unwrap();
    (状态, 写入计数)
}

fn 成功样本() -> 叶子产出 {
    叶子产出 {
        结果: crate::转发结果::成功(数据槽::空槽()),
        槽: 数据槽::空槽(),
        业务错误码: None,
    }
}

fn 超时样本() -> 叶子产出 {
    叶子产出 {
        结果: crate::转发结果::失败(调度错误::超时 { 毫秒数: 1 }),
        槽: 数据槽::空槽(),
        业务错误码: None,
    }
}

fn 核对零写(状态: &mut 实例状态, 工作: &工作项, 写入计数: &AtomicUsize) {
    let 旧写入次数 = 写入计数.load(Ordering::SeqCst);
    let 时刻表 = 状态.时刻表.clone();
    let 槽表 = 状态.槽表.clone();
    let 旧记录 = 状态.记录.取().cloned();
    let 跟踪读数 = format!("{:?}", 状态.跟踪);
    let 待执行数 = 状态.待执行.len();
    状态.记账完成(工作, 超时样本());
    assert_eq!(
        写入计数.load(Ordering::SeqCst),
        旧写入次数,
        "拒收不得调用存储写口"
    );
    assert_eq!(状态.时刻表, 时刻表, "拒收不得改时刻");
    assert_eq!(状态.槽表, 槽表);
    assert_eq!(状态.记录.取().cloned(), 旧记录);
    assert_eq!(format!("{:?}", 状态.跟踪), 跟踪读数);
    assert_eq!(状态.待执行.len(), 待执行数);
    assert!(状态.未知表.is_empty(), "拒收不得造未知");
    assert!(状态.失败表.is_empty(), "拒收不得造确认失败");
    assert!(状态.结局.is_none());
}

#[test]
fn 同批重复超时严格零写() {
    let (mut 状态, 写入计数) = 造驱动状态();
    let 工作 = 状态.待执行.pop_front().unwrap();
    状态.记账完成(&工作, 成功样本());
    核对零写(&mut 状态, &工作, &写入计数);
}

#[test]
fn 旧批迟到超时严格零写() {
    let (mut 状态, 写入计数) = 造驱动状态();
    let mut 工作 = 状态.待执行.pop_front().unwrap();
    状态.记账完成(&工作, 成功样本());
    工作.执行批号 = 工作.执行批号.saturating_sub(1);
    核对零写(&mut 状态, &工作, &写入计数);
}

#[test]
fn 内核真错不伪造能力失败() {
    let (mut 状态, 写入计数) = 造驱动状态();
    let 工作 = 工作项 {
        节点标识: "未登记根".to_owned(),
        执行批号: 1,
        请求: 叶子请求 {
            节点标识: "未登记根".to_owned(),
            执行批号: 1,
            编号: 0,
            入参: vec![],
        },
    };
    核对零写(&mut 状态, &工作, &写入计数);
}
