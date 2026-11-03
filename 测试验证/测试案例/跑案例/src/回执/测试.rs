use super::收敛::收敛回执带等待;
use super::环境::民用日期;
use super::锁与追加::{追加一行带等待, 锁件路径};
use std::path::Path;
use std::process::Command;

use crate::错误码::错误码登记;

use super::*;

/// 正向样本：已知时间点必须算出已知日期（否则时间戳是假的）。
#[test]
fn 日期算得对() {
    assert_eq!(民用日期(0), (1970, 1, 1));
    assert_eq!(民用日期(19_000), (2022, 1, 8));
    assert_eq!(民用日期(-1), (1969, 12, 31));
    assert_eq!(民用日期(29_000), (2049, 5, 26));
}

/// 反向样本：`工作区是否干净` 必须真的读 git（拿不到就报错，不许默认 true）。
#[test]
fn 提交哈希取不到就报错() {
    assert!(提交哈希(Path::new("/绝对不存在的目录")).is_err());
}

#[test]
fn 时间戳形状是UTC() {
    let 时间戳 = 现在UTC();
    assert_eq!(时间戳.len(), 20, "形状该是 YYYY-MM-DDTHH:MM:SSZ：{时间戳}");
    assert!(时间戳.ends_with('Z'));
}

/// 正向样本：一行回执必须是**合法 JSON**（回执自身读不回来就是假读数）。
#[test]
fn 回执行是合法JSON() {
    let 回执值 = 回执 {
        提交哈希: "a".repeat(40),
        工作区是否干净: false,
        案例名: "首项\"次项".to_owned(),
        调用结局: "失败".to_owned(),
        死在哪一层: Some("内核".to_owned()),
        死在哪一步: Some("调度".to_owned()),
        错误码: Some(错误码登记 {
            码值: 1,
            段位: 0,
            名称: "提供者未载入".to_owned(),
            可重试: true,
            可自愈: true,
            需人工: false,
            已登记: true,
        }),
        耗时微秒: 7,
        跑的时间: 现在UTC(),
        说明: "换行\n也要转义".to_owned(),
        案例步骤: vec![步骤读数 {
            名字: "首项".to_owned(),
            扩展种类: "能力".to_owned(),
            能力编号: 1105,
            能力名: Some("反解容器".to_owned()),
            调用结果: "成功".to_owned(),
            符合期望: true,
            死在哪一层: None,
            死在哪一步: None,
            错误码: None,
            耗时微秒: 3,
            说明: "无".to_owned(),
        }],
    };
    let 源码行 = 回执值.写成一行();
    let 解析值 = crate::最小JSON::解析JSON值(&源码行).expect("回执必须是合法 JSON");
    assert_eq!(
        解析值.取成员("案例名").and_then(|成员值| 成员值.取字符串()),
        Some("首项\"次项")
    );
    assert_eq!(
        解析值
            .取成员("死在哪一层")
            .and_then(|成员值| 成员值.取字符串()),
        Some("内核")
    );
    assert!(matches!(
        解析值
            .取成员("步骤")
            .and_then(|成员值| 成员值.取数组())
            .map(<[crate::最小JSON::JSON值]>::len),
        Some(1)
    ));
}

/// 造「一次运行的一行」假回执：字段形状与 [`回执::写成一行`] 一致，够收敛判据用。
fn 一次运行的一行(序号: u32) -> String {
    format!(
        "{{\"提交哈希\":\"{:040x}\",\"工作区是否干净\":true,\"案例名\":\"样本案例\",\
             \"结果\":\"通过\",\"跑的时间\":\"2026-01-01T00:00:00Z\",\"说明\":\"样本\",\"步骤\":[]}}",
        序号
    )
}

/// 反证（回执组 · 按份）：1200 次运行（每次一行）⇒ 只留最近 [`回执运行上限`] 次运行的行。
#[test]
fn 收敛回执_千二百次运行只留五百次() {
    let 样本根 = std::env::temp_dir().join(format!("v1-回执收敛-按份-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&样本根);
    std::fs::create_dir_all(&样本根).expect("建样本目录");
    let 回执路径 = 样本根.join("运行回执.jsonl");
    let 全文本: String = (0..1200u32)
        .map(|序号| 一次运行的一行(序号) + "\n")
        .collect();
    std::fs::write(&回执路径, 全文本.as_bytes()).expect("写样本回执");
    let 读数 = 收敛回执(&回执路径).expect("收敛回执");
    let 收敛后 = std::fs::read_to_string(&回执路径).expect("读回收敛后的回执");
    let 剩行表: Vec<&str> = 收敛后
        .lines()
        .filter(|源码行| !源码行.trim().is_empty())
        .collect();
    assert_eq!(
        读数.删掉行数, 700,
        "1200 次运行 - 上限 500 次 = 该删 700 行"
    );
    assert_eq!(读数.跳过坏行, 0, "样本里没有坏行 ⇒ 跳过的必须是 0");
    assert_eq!(剩行表.len(), 500, "只留最近 500 次运行");
    assert_eq!(
        剩行表[0],
        一次运行的一行(700),
        "留下的必须是最新那 500 次（第 700 次起）"
    );
    assert_eq!(
        剩行表[499],
        一次运行的一行(1199),
        "最后一行必须是最新那次运行"
    );
    let _ = std::fs::remove_dir_all(&样本根);
}

/// 反证（回执组 · 按龄）：刚好到上限 ⇒ 一个字节都不动（不许顺手「规范化」把旧行重排）。
#[test]
fn 收敛回执_未到界一个字节都不动() {
    let 样本根 = std::env::temp_dir().join(format!("v1-回执收敛-按龄-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&样本根);
    std::fs::create_dir_all(&样本根).expect("建样本目录");
    let 回执路径 = 样本根.join("运行回执.jsonl");
    let 原文本: String = (0..回执运行上限 as u32)
        .map(|序号| 一次运行的一行(序号) + "\n")
        .collect();
    std::fs::write(&回执路径, 原文本.as_bytes()).expect("写样本回执");
    let 读数 = 收敛回执(&回执路径).expect("收敛回执");
    let 现文本 = std::fs::read_to_string(&回执路径).expect("读回回执");
    assert_eq!(
        读数,
        收敛读数 {
            删掉行数: 0,
            跳过坏行: 0
        },
        "刚好到上限且没有坏行 ⇒ 两个读数都是 0"
    );
    assert_eq!(现文本, 原文本, "没到界 ⇒ 文件必须逐字节不变");
    let _ = std::fs::remove_dir_all(&样本根);
}

/// 反证（回执组 · 坏行）：拼不上的行**跳过并上报**，好行一条不少。
///
/// 「跳过」不等于「静默」：坏行数从 [`收敛读数::跳过坏行`] 出来，收敛照旧成功。
#[test]
fn 收敛回执_坏行被跳过并上报() {
    let 样本根 = std::env::temp_dir().join(format!("v1-回执收敛-坏行-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&样本根);
    std::fs::create_dir_all(&样本根).expect("建样本目录");
    let 回执路径 = 样本根.join("运行回执.jsonl");
    // 坏行摆在最旧那一端：它们拼不上 ⇒ 跳过并计数，**不占「一次运行」的位置**。
    let 全文本: String = "坏行样例上\n坏行样例中\n\n".to_owned()
        + &(0..回执运行上限 as u32)
            .map(|序号| 一次运行的一行(序号) + "\n")
            .collect::<String>();
    std::fs::write(&回执路径, 全文本.as_bytes()).expect("写样本回执");
    let 读数 = 收敛回执(&回执路径).expect("收敛回执");
    let 收敛后 = std::fs::read_to_string(&回执路径).expect("读回收敛后的回执");
    assert_eq!(读数.删掉行数, 0, "好行一条都没到界 ⇒ 一条好行都不许删");
    assert_eq!(读数.跳过坏行, 3, "两行拼不上 + 一个空行 = 三条");
    assert!(!收敛后.contains("坏行样例"), "坏行该被清干净");
    assert_eq!(
        收敛后
            .lines()
            .filter(|源码行| !源码行.trim().is_empty())
            .count(),
        回执运行上限,
        "清完坏行之后好行一条不少"
    );
    let _ = std::fs::remove_dir_all(&样本根);
}

/// 反证（读端容错）：两行截断 + 一个空行 ⇒ 跳过三条、好行原样读出、**不报错**。
#[test]
fn 逐行读回执_两截断一空行跳过三条() {
    let 好行首 = 一次运行的一行(1);
    let 好行尾 = 一次运行的一行(2);
    let mut 原文本 = String::new();
    原文本.push_str(&好行首);
    原文本.push('\n');
    原文本.push_str("{\"提交哈希\":\"截断在这\n");
    原文本.push('\n');
    原文本.push_str("{\"提交哈希\":\"另一条也断了\n");
    原文本.push_str(&好行尾);
    原文本.push('\n');
    let (可用行表, 跳过坏行) = 逐行读回执(&原文本);
    assert_eq!(跳过坏行, 3, "两行截断 + 一个空行 = 三条拼不上");
    assert_eq!(
        可用行表,
        vec![好行首, 好行尾],
        "可用的行必须原样、按文件次序读出"
    );
}

/// 反证（并发写）：8 路 × 20 行同时追加 ⇒ 盘上 **0 条坏行**、160 条一条不丢。
///
/// 这条是真缺陷的回归样本：早先「正文 + 换行」两次 `write_all` 且无互斥，并发写会拼出
/// 拼不上的行（盘上实测攒到过 52 条）。
#[test]
fn 并发八路各二十行_零坏行() {
    let 样本根 = std::env::temp_dir().join(format!("v1-回执并发-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&样本根);
    std::fs::create_dir_all(&样本根).expect("建样本目录");
    let 回执路径 = 样本根.join("运行回执.jsonl");
    let 路数: u32 = 8;
    let 每路行数: u32 = 20;
    let mut 把手表 = Vec::new();
    for 路号 in 0..路数 {
        let 本路路径 = 回执路径.clone();
        把手表.push(std::thread::spawn(move || {
            for 行号 in 0..每路行数 {
                let 本条回执行 = 一次运行的一行(路号 * 1000 + 行号);
                追加一行(&本路路径, &本条回执行).expect("并发追加不许失败");
            }
        }));
    }
    for 把手 in 把手表 {
        把手.join().expect("追加线程不许 panic");
    }
    let 现文本 = std::fs::read_to_string(&回执路径).expect("读回回执");
    let (可用行表, 跳过坏行) = 逐行读回执(&现文本);
    assert_eq!(跳过坏行, 0, "8 路并发追加不许留下任何一条拼不上的行");
    assert_eq!(
        可用行表.len() as u32,
        路数 * 每路行数,
        "每一条都得在（并发不许吞行）"
    );
    let _ = std::fs::remove_dir_all(&样本根);
}

/// 造一个独用样本目录（并发进程之间不能共用一个根，否则互相删目录）。
fn 建样本根(档名: &str) -> std::path::PathBuf {
    let 样本根 = std::env::temp_dir().join(format!("v1-回执-{档名}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&样本根);
    std::fs::create_dir_all(&样本根).expect("建样本目录");
    样本根
}

/// 反证（锁失败不回退）：别人持锁 ⇒ [`追加一行`] 回 **Err**，盘上一字节都不许动。
///
/// 这条钉的是 2026-10-29 修掉的降级路：早先拿不到锁就退回「无锁单 `write` 追加」——
/// 那条路正是拼坏行的来源（另一个写者正在「读全文 → rename」中间时插进去 ⇒ 被 rename 踩掉）。
#[test]
fn 锁拿不到就不写盘_不回退无锁追加() {
    let 样本根 = 建样本根("锁失败");
    let 回执路径 = 样本根.join("运行回执.jsonl");
    let 原文本 = 一次运行的一行(1) + "\n";
    std::fs::write(&回执路径, 原文本.as_bytes()).expect("写样本回执");
    let 锁路径 = 锁件路径(&回执路径);
    let 外人锁 = 独占锁::取锁(&锁路径, 0).expect("外人先把锁拿到");
    let 结果值 = 追加一行带等待(&回执路径, &一次运行的一行(2), 80);
    let 现在文本 = std::fs::read_to_string(&回执路径).expect("读回回执");
    drop(外人锁);
    let 错误文本 = 结果值.expect_err("拿不到锁必须失败，不许静默无锁追加");
    assert!(
        错误文本.contains("锁"),
        "错误里要点明是锁的问题：{错误文本}"
    );
    assert!(
        错误文本.contains("回执没写"),
        "错误里要点明「回执没写」：{错误文本}"
    );
    assert_eq!(
        现在文本, 原文本,
        "拿不到锁 ⇒ 盘上必须逐字节不变（不许无锁追加）"
    );
    assert!(
        !回执路径.with_extension("jsonl.写入中").exists(),
        "失败不许留半成品临时件"
    );
    let _ = std::fs::remove_dir_all(&样本根);
}

/// 反证（有界等待）：持锁 80 毫秒 ⇒ 追加在 80 毫秒后**自身**失败，不无限期挂着。
#[test]
fn 锁等待有界_超时即失败() {
    let 样本根 = 建样本根("锁有界");
    let 回执路径 = 样本根.join("运行回执.jsonl");
    std::fs::write(&回执路径, b"").expect("建空回执");
    let 外人锁 = 独占锁::取锁(&锁件路径(&回执路径), 0).expect("外人先把锁拿到");
    let 起点 = std::time::Instant::now();
    let 结果值 = 追加一行带等待(&回执路径, &一次运行的一行(3), 80);
    let 用时毫秒 = 起点.elapsed().as_millis();
    drop(外人锁);
    assert!(结果值.is_err(), "持锁期内追加必须失败");
    assert!(用时毫秒 >= 80, "必须真的等满 80 毫秒（实测 {用时毫秒}）");
    assert!(
        用时毫秒 < 2000,
        "等待必须有界：实测 {用时毫秒} 毫秒，不许挂死"
    );
    let 错误文本 = 结果值.expect_err("必须失败");
    assert!(
        错误文本.contains("等满 80 毫秒"),
        "错误里要带等了多久：{错误文本}"
    );
    let _ = std::fs::remove_dir_all(&样本根);
}

/// 反证（与追加同一把锁）：持锁期内的收敛**不许重写**，且「该裁却裁不了」要明确失败。
///
/// 这条钉的是「收敛与追加共享同一锁件」这条口径：若两边各用一把锁，收敛的 `rename`
/// 会把持锁期内追加进来的行整条抹掉（读定稿 → 别人追加 → rename 覆盖 = 丢行）。
#[test]
fn 收敛与追加同一把锁_拿不到锁就不重写且明确失败() {
    let 样本根 = 建样本根("收敛同锁");
    let 回执路径 = 样本根.join("运行回执.jsonl");
    let 原文本: String = (0..回执运行上限 as u32 + 100)
        .map(|序号| 一次运行的一行(序号) + "\n")
        .collect();
    std::fs::write(&回执路径, 原文本.as_bytes()).expect("写样本回执");
    let 外人锁 = 独占锁::取锁(&锁件路径(&回执路径), 0).expect("外人先把锁拿到");
    let 追加结果 = 追加一行带等待(&回执路径, &一次运行的一行(9001), 40);
    let 收敛结果 = 收敛回执带等待(&回执路径, 40);
    let 现在文本 = std::fs::read_to_string(&回执路径).expect("读回回执");
    drop(外人锁);
    assert!(
        追加结果.is_err(),
        "同一把锁 ⇒ 持锁期内追加必须失败（不许无锁写）"
    );
    let 错误文本 = 收敛结果.expect_err("已到界却拿不到锁 ⇒ 必须明确失败，不许静默不收敛");
    assert!(
        错误文本.contains("回执没收敛"),
        "错误里要点明「回执没收敛」：{错误文本}"
    );
    assert_eq!(现在文本, 原文本, "拿不到锁 ⇒ 收敛一个字都不许重写");
    // 放锁之后同一条收敛要能真裁到 500 组。
    let 读数 = 收敛回执(&回执路径).expect("放锁后收敛该成功");
    assert_eq!(读数.删掉行数, 100, "600 组 ⇒ 裁到 500 组");
    let _ = std::fs::remove_dir_all(&样本根);
}

/// 子进程样本：由 [`六进程并发追加_零坏行且不丢行`] 拉起，只为在**真进程间**争同一把锁。
///
/// 父进程用环境变量递两个事实（路径 / 路号），本样本各追加 20 行；不设该变量时它是空跑
/// （正常 `cargo test` 整包跑时不许因此红）。
#[test]
fn 子进程追加样本() {
    let Ok(样本路径) = std::env::var("V1_回执追加样本路径") else {
        return;
    };
    let 路号: u32 = std::env::var("V1_回执追加路号")
        .ok()
        .and_then(|值| 值.parse().ok())
        .unwrap_or(0);
    let 路径 = std::path::Path::new(&样本路径);
    for 行号 in 0..20u32 {
        追加一行(路径, &一次运行的一行(10_000 * 路号 + 行号)).expect("子进程追加不许失败");
    }
}

/// 反证（跨进程并发）：6 个真进程 × 20 行同时追加 ⇒ 0 条坏行、120 条一条不丢。
///
/// 线程样本（[`并发八路各二十行_零坏行`]）走的是「同进程不同描述符」，跨进程是**另一件事**：
/// 一次跑案例起一个进程，构建装配还会并发起多份 —— 真正要证的是进程之间这把 `flock` 也成立。
#[test]
fn 六进程并发追加_零坏行且不丢行() {
    let 样本根 = 建样本根("跨进程");
    let 回执路径 = 样本根.join("运行回执.jsonl");
    let 本程序 = std::env::current_exe().expect("取当前测试可执行件");
    let 路数: u32 = 6;
    let mut 子进程表 = Vec::new();
    for 路号 in 0..路数 {
        let 子进程 = Command::new(&本程序)
            // ★ 过滤名必须是**完整路径**（`回执::测试::<样本名>`）：只写 `测试::<样本名>`
            //   会让子进程回「0 tests」并以 0 退出 —— 那样样本空跑也绿（假绿的一类）。
            .args(["--exact", "回执::测试::子进程追加样本", "--nocapture"])
            .env("V1_回执追加样本路径", &回执路径)
            .env("V1_回执追加路号", 路号.to_string())
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::piped())
            .spawn()
            .expect("拉起子进程");
        子进程表.push((路号, 子进程));
    }
    for (路号, 子进程) in 子进程表 {
        let 产物 = 子进程.wait_with_output().expect("等子进程");
        assert!(
            产物.status.success() && String::from_utf8_lossy(&产物.stdout).contains("1 passed"),
            "第 {路号} 路子进程退出码 {:?}（stdout {}\nstderr {}）",
            产物.status.code(),
            String::from_utf8_lossy(&产物.stdout),
            String::from_utf8_lossy(&产物.stderr)
        );
    }
    let 现文本 = std::fs::read_to_string(&回执路径).expect("读回回执");
    let (可用行表, 跳过坏行) = 逐行读回执(&现文本);
    assert_eq!(跳过坏行, 0, "6 个真进程并发追加不许留下任何一条拼不上的行");
    assert_eq!(
        可用行表.len() as u32,
        路数 * 20,
        "每条都得在（跨进程不许吞行）"
    );
    let _ = std::fs::remove_dir_all(&样本根);
}
