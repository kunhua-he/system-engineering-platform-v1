use std::path::PathBuf;
use std::process::Command;
use std::sync::atomic::AtomicBool;
use std::thread;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use db_seam_research::{
    代际令牌, 契约错误, 数据库连接, 版本号, 装载单元, 跨进程租约
};
use v1_dataroot::{子目录, 确保子目录, 解析当前环境};

fn 连接信息() -> String {
    数据库连接::默认连接信息()
}

fn 临时路径(名称: &str) -> PathBuf {
    let 根目录 = 解析当前环境().expect("解析运行数据根");
    let 临时目录 = 确保子目录(&根目录, 子目录::临时件).expect("建立临时件目录");
    临时目录.join(format!(
        "v1-db-seam-{}-{}-{}",
        名称,
        std::process::id(),
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos()
    ))
}

fn 后端已结束(后端进程号: i32) -> bool {
    let mut 查询连接 = match 数据库连接::建立(&连接信息()) {
        Ok(连接) => 连接,
        Err(_) => return false,
    };
    let 计数 = 查询连接
        .查询单值(&format!(
            "SELECT count(*) FROM pg_stat_activity WHERE pid = {后端进程号}"
        ))
        .ok()
        .and_then(|文本| 文本.parse::<u32>().ok())
        .unwrap_or(1);
    计数 == 0
}

fn 等待后端结束(后端进程号: i32) {
    let 截止时刻 = Instant::now() + Duration::from_secs(3);
    while Instant::now() < 截止时刻 {
        if 后端已结束(后端进程号) {
            return;
        }
        thread::sleep(Duration::from_millis(30));
    }
    assert!(
        后端已结束(后端进程号),
        "PQfinish 后后端仍在活动：{后端进程号}"
    );
}

fn 需要真实数据库() -> bool {
    match 数据库连接::建立(&连接信息()) {
        Ok(_) => true,
        Err(错误) => {
            eprintln!("PG_BLOCKED：{错误}；仅跳过真实 libpq 探针，不能据此宣称完成");
            false
        }
    }
}

#[test]
fn 内部契约_同版重装拒绝旧代际租约() {
    let 装载单元 = 装载单元::装载("数据库访问模块", 版本号::构造(0, 1));
    let 旧上下文 = 装载单元.当前上下文().expect("初始装载上下文");
    let 新上下文 = 装载单元.重装(版本号::构造(0, 1)).expect("同版重装");
    assert_eq!(旧上下文.实现版本, 新上下文.实现版本);
    assert_ne!(旧上下文.代际令牌, 新上下文.代际令牌);
    assert_ne!(旧上下文.代际序号, 新上下文.代际序号);
}

#[test]
fn 同版重装_旧执行租约按代际令牌拒绝() {
    if !需要真实数据库() {
        return;
    }
    let 装载单元 = 装载单元::装载("数据库访问模块", 版本号::构造(0, 1));
    let mut 旧租约 = 装载单元.申请执行租约(&连接信息()).expect("建立旧代租约");
    装载单元.重装(版本号::构造(0, 1)).expect("同版重装");
    assert_eq!(旧租约.验证当前代际(&装载单元), Err(契约错误::代际不符));
    let 是否执行 = std::sync::atomic::AtomicBool::new(false);
    let 结果 = 旧租约.执行受控(
        &装载单元,
        &AtomicBool::new(false),
        Instant::now() + Duration::from_secs(1),
        |_连接| {
            是否执行.store(true, std::sync::atomic::Ordering::Release);
            Ok::<_, 契约错误>(())
        },
    );
    assert_eq!(结果, Err(契约错误::代际不符));
    assert!(!是否执行.load(std::sync::atomic::Ordering::Acquire));
}

#[test]
fn 代际令牌_序列化后只接受完整格式() {
    let 装载单元 = 装载单元::装载("数据库访问模块", 版本号::构造(0, 1));
    let 令牌 = 装载单元.当前上下文().unwrap().代际令牌;
    let 文本 = 令牌.十六进制();
    assert_eq!(代际令牌::从十六进制(&文本).unwrap(), 令牌);
    assert!(代际令牌::从十六进制("旧令牌").is_err());
}

#[test]
fn 跨进程租约_令牌校验与子进程析构回收() {
    let 路径 = 临时路径("lease");
    let 装载单元 = 装载单元::装载("数据库访问模块", 版本号::构造(0, 1));
    let 令牌 = 装载单元.当前上下文().unwrap().代际令牌;
    let 父租约 = 跨进程租约::申请(&路径, 令牌).expect("父进程建立租约");
    let 探针程序 = env!("CARGO_BIN_EXE_db-seam-probe");
    let 错误令牌 = 装载单元.重装(版本号::构造(0, 1)).unwrap().代际令牌;
    let 错误回执 = Command::new(探针程序)
        .args(["child-lease", 路径.to_str().unwrap(), &错误令牌.十六进制()])
        .output()
        .expect("启动旧代际跨进程探针");
    assert!(!错误回执.status.success(), "旧代际跨进程租约必须拒绝");
    assert!(路径.exists(), "拒绝旧代际不能删除当前租约");
    drop(父租约);

    let 子代路径 = 临时路径("child-lease");
    let 子代回执 = Command::new(探针程序)
        .args([
            "child-create-lease",
            子代路径.to_str().unwrap(),
            &令牌.十六进制(),
        ])
        .output()
        .expect("启动子进程租约探针");
    assert!(
        子代回执.status.success(),
        "子进程租约失败：{}",
        String::from_utf8_lossy(&子代回执.stderr)
    );
    assert!(!子代路径.exists(), "子进程退出后租约析构未回收");
}

#[test]
fn 真实_pgconn_宿主退出时_pqfinish_释放后端() {
    if !需要真实数据库() {
        return;
    }
    let PID文件 = 临时路径("pid");
    let 探针程序 = env!("CARGO_BIN_EXE_db-seam-probe");
    let 回执 = Command::new(探针程序)
        .args(["child-host-exit", PID文件.to_str().unwrap()])
        .output()
        .expect("启动宿主退出探针");
    assert!(
        回执.status.success(),
        "宿主退出子进程失败：{}",
        String::from_utf8_lossy(&回执.stderr)
    );
    let 后端进程号 = std::fs::read_to_string(&PID文件)
        .unwrap()
        .parse::<i32>()
        .unwrap();
    等待后端结束(后端进程号);
    let _ = std::fs::remove_file(PID文件);
}

#[test]
fn 异常取消超时_真实连接均释放() {
    if !需要真实数据库() {
        return;
    }
    let 装载单元 = 装载单元::装载("数据库访问模块", 版本号::构造(0, 1));

    let 异常后端 = {
        let mut 租约 = 装载单元.申请执行租约(&连接信息()).expect("异常场景连接");
        let 后端进程号 = 租约.后端进程号().unwrap();
        let 异常回执 = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            let _: Result<(), 契约错误> = 租约.执行受控(
                &装载单元,
                &std::sync::atomic::AtomicBool::new(false),
                Instant::now() + Duration::from_secs(1),
                |连接| {
                    let 当前后端 = 连接.后端进程号();
                    panic!("故意异常，后端 {当前后端}");
                },
            );
        }));
        assert!(异常回执.is_err(), "异常场景必须被捕获");
        后端进程号
    };
    等待后端结束(异常后端);

    let 取消后端 = {
        let mut 租约 = 装载单元.申请执行租约(&连接信息()).expect("取消场景连接");
        let 后端进程号 = 租约.后端进程号().unwrap();
        let 取消错误 = 租约
            .执行受控(
                &装载单元,
                &std::sync::atomic::AtomicBool::new(true),
                Instant::now() + Duration::from_secs(1),
                |_连接| Ok::<_, 契约错误>(()),
            )
            .expect_err("已取消必须拒绝");
        assert_eq!(取消错误, 契约错误::已取消);
        后端进程号
    };
    等待后端结束(取消后端);

    let 超时后端 = {
        let mut 租约 = 装载单元.申请执行租约(&连接信息()).expect("超时场景连接");
        let 后端进程号 = 租约.后端进程号().unwrap();
        let 结果 = 租约.执行受控(
            &装载单元,
            &AtomicBool::new(false),
            Instant::now() + Duration::from_millis(10),
            |_连接| {
                thread::sleep(Duration::from_millis(30));
                Ok::<_, 契约错误>(())
            },
        );
        assert_eq!(结果.expect_err("超时必须拒绝"), 契约错误::已超时);
        后端进程号
    };
    等待后端结束(超时后端);
}
