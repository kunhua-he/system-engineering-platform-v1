//! 真数据库集成测试：缺少夹具连接串即失败，绝不跳过。
use serde_json::Value;
use std::time::{Duration, Instant};
use v1_contract::{数据槽, 类型标签};
fn 文本槽(文本值: &str) -> 数据槽 {
    数据槽::指针(
        类型标签::构造(4),
        文本值.as_ptr() as u64,
        文本值.len() as u64,
        false,
    )
}
fn 句柄槽(连接编号: u64) -> 数据槽 {
    数据槽::内联槽(类型标签::构造(6), 连接编号, 8)
}
fn 调用(编号: u32, 参数槽: &[数据槽]) -> Result<数据槽, u32> {
    let 声明引用 = v1_libpq::扩展声明();
    let mut 返回槽 = 数据槽::空槽();
    unsafe {
        (声明引用.函数表.add((编号 - 5401) as usize).read())(
            &mut 返回槽,
            参数槽.len() as u32,
            参数槽.as_ptr(),
        );
    }
    if 返回槽.类型标签.取号值() == u32::MAX {
        Err(返回槽.槽值 as u32)
    } else {
        Ok(返回槽)
    }
}
fn 查询(连接编号: u64, 语句文本: &str) -> Result<Value, u32> {
    let 返回槽 = 调用(5402, &[句柄槽(连接编号), 文本槽(语句文本)])?;
    assert_eq!(返回槽.类型标签.取号值(), 4);
    let 返回字节 = unsafe {
        Box::from_raw(std::ptr::slice_from_raw_parts_mut(
            返回槽.槽值 as *mut u8,
            返回槽.槽字节长度 as usize,
        ))
    };
    Ok(serde_json::from_slice(&返回字节).unwrap())
}
fn 事务(连接编号: u64, 语句列表: &[&str]) -> Result<数据槽, u32> {
    let 事务文本 = serde_json::to_string(语句列表).unwrap();
    调用(5403, &[句柄槽(连接编号), 文本槽(&事务文本)])
}
fn 核错误(执行结果: Result<数据槽, u32>, 期望码: u32) {
    assert_eq!(执行结果.err(), Some(期望码));
}
#[test]
fn 真实连接事务回滚释放及卸载() {
    let 连接文本 = std::env::var("V1_LIBPQ_TEST_DSN").expect("必须显式提供隔离PG夹具");
    let 连接编号 = 调用(5401, &[文本槽(&连接文本)]).unwrap().槽值;
    let 对照编号 = 调用(5401, &[文本槽(&连接文本)]).unwrap().槽值;
    assert_ne!(连接编号, 对照编号);
    let 后端查询 = "SELECT pg_backend_pid(), '中文', NULL, ''";
    let 原始结果 = 查询(连接编号, 后端查询).unwrap();
    let 后端编号 = 原始结果["行列表"][0][0].as_str().unwrap();
    assert_eq!(原始结果["行列表"][0][1], "中文");
    assert!(原始结果["行列表"][0][2].is_null());
    assert_eq!(原始结果["行列表"][0][3], "");
    assert_eq!(查询(连接编号, 后端查询).unwrap(), 原始结果);
    assert_ne!(查询(对照编号, 后端查询).unwrap()["行列表"][0][0], 后端编号);
    assert_eq!(
        事务(
            连接编号,
            &[
                "CREATE TABLE IF NOT EXISTS formal_probe(value integer)",
                "TRUNCATE formal_probe",
                "INSERT INTO formal_probe VALUES(1)"
            ]
        )
        .unwrap()
        .槽值,
        3
    );
    事务(
        连接编号,
        &["CREATE TEMP TABLE formal_private(value integer)"],
    )
    .unwrap();
    核错误(
        事务(
            连接编号,
            &[
                "INSERT INTO formal_probe VALUES(2)",
                "INSERT INTO formal_missing VALUES(3)",
            ],
        ),
        5413,
    );
    assert_eq!(
        查询(连接编号, "SELECT count(*) FROM formal_probe").unwrap()["行列表"][0][0],
        "1"
    );
    核错误(
        事务(连接编号, &["INSERT INTO formal_probe VALUES(2); COMMIT"]),
        5413,
    );
    核错误(
        事务(连接编号, &["INSERT INTO formal_probe VALUES(2)", "COMMIT"]),
        5411,
    );
    assert_eq!(
        查询(连接编号, "SELECT count(*) FROM formal_probe").unwrap()["行列表"][0][0],
        "1"
    );
    assert_eq!(
        查询(对照编号, "SELECT * FROM formal_private").err(),
        Some(5413)
    );
    assert_eq!(
        查询(
            连接编号,
            "WITH removed AS (DELETE FROM formal_probe RETURNING *) SELECT * FROM removed"
        )
        .err(),
        Some(5413)
    );
    assert_eq!(查询(连接编号, "SELECT 1; SELECT 2").err(), Some(5413));
    assert_eq!(查询(连接编号, "SELECT repeat('a',65537)").err(), Some(5416));
    assert_eq!(
        查询(连接编号, "SELECT generate_series(1,1025)").err(),
        Some(5416)
    );
    assert_eq!(
        查询(连接编号, "SELECT 1 WHERE false").unwrap()["行列表"],
        serde_json::json!([])
    );
    let 起始时刻 = Instant::now();
    assert_eq!(查询(连接编号, "SELECT pg_sleep(2)").err(), Some(5413));
    assert!(起始时刻.elapsed() < Duration::from_secs(2));
    assert_eq!(查询(连接编号, "SELECT 1").unwrap()["行列表"][0][0], "1");
    核错误(
        调用(5401, &[文本槽("host=127.0.0.1 port=1 dbname=missing")]),
        5412,
    );
    核错误(调用(5401, &[文本槽("bad\0input")]), 5411);
    核错误(调用(5403, &[句柄槽(连接编号), 文本槽("[]")]), 5411);
    assert_eq!(调用(5404, &[句柄槽(连接编号)]).unwrap().槽值, 1);
    核错误(调用(5404, &[句柄槽(连接编号)]), 5414);
    assert_eq!(查询(连接编号, "SELECT 1").err(), Some(5414));
    let 观察语句 = format!("SELECT count(*) FROM pg_stat_activity WHERE pid={后端编号}");
    let 观察截止 = Instant::now() + Duration::from_millis(500);
    loop {
        if 查询(对照编号, &观察语句).unwrap()["行列表"][0][0] == "0" {
            break;
        }
        assert!(Instant::now() < 观察截止, "PQfinish后会话仍在");
        std::thread::sleep(Duration::from_millis(2));
    }
    let 故障编号 = 调用(5401, &[文本槽(&连接文本)]).unwrap().槽值;
    查询(故障编号, "SELECT set_config('statement_timeout','0',false)").unwrap();
    let 故障起点 = Instant::now();
    assert_eq!(查询(故障编号, "SELECT pg_sleep(2)").err(), Some(5417));
    assert!(故障起点.elapsed() < Duration::from_secs(2));
    assert_eq!(查询(故障编号, "SELECT 1").err(), Some(5414));
    let 通知函数 = v1_libpq::扩展声明().通知函数.unwrap();
    assert_eq!(
        unsafe { 通知函数(v1_contract::通知号::构造(2001), 0, 0) },
        0
    );
    assert_eq!(查询(对照编号, "SELECT 1").err(), Some(5414));
    核错误(调用(5401, &[文本槽(&连接文本)]), 5415);
    assert_eq!(
        unsafe { 通知函数(v1_contract::通知号::构造(2000), 0, 0) },
        0
    );
    let 新连接号 = 调用(5401, &[文本槽(&连接文本)]).unwrap().槽值;
    assert_ne!(新连接号, 对照编号);
    assert_eq!(调用(5404, &[句柄槽(新连接号)]).unwrap().槽值, 1);
}
