use super::*;

#[test]
fn 公开投影只在接受回调写且未知不写失败() {
    let 产出表 = Arc::new(Mutex::new(BTreeMap::new()));
    let 失败表 = Arc::new(Mutex::new(BTreeMap::new()));
    let 图叶子 = 图任务叶子 {
        内层: 适配器叶子::由快照(
            适配器::装载(v1_loader::底座声明()).unwrap(),
            叶子标记::default(),
        ),
        计划表: Arc::new(BTreeMap::new()),
        产出表: Arc::clone(&产出表),
        失败表: Arc::clone(&失败表),
    };
    let 请求 = 叶子请求 {
        节点标识: "投影根".to_owned(),
        执行批号: 1,
        编号: 0,
        入参: vec![],
    };
    let 未接受产出 = 图叶子.执行(&请求);
    assert!(!未接受产出.节点成功());
    assert!(产出表.lock().unwrap().is_empty());
    assert!(失败表.lock().unwrap().is_empty(), "执行口不得先写错误表");
    let 超时产出 = 叶子产出 {
        结果: 转发结果::失败(调度错误::超时 { 毫秒数: 1 }),
        槽: 数据槽::空槽(),
        业务错误码: None,
    };
    图叶子.接受产出(&请求, &超时产出);
    assert!(失败表.lock().unwrap().is_empty(), "未知不写确认失败");
    let 确认失败产出 = 叶子产出 {
        结果: 转发结果::失败(调度错误::配额用尽),
        槽: 数据槽::空槽(),
        业务错误码: None,
    };
    图叶子.接受产出(&请求, &确认失败产出);
    assert!(失败表.lock().unwrap().contains_key("投影根"));
    let 成功产出 = 叶子产出 {
        结果: 转发结果::成功(数据槽::空槽()),
        槽: 数据槽::空槽(),
        业务错误码: None,
    };
    图叶子.接受产出(&请求, &成功产出);
    assert!(产出表.lock().unwrap().contains_key("投影根"));
}
