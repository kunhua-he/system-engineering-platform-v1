//! 仅以接口桩驱动真实句柄层，不读取数据库配置、不建立网络连接。
#![allow(dead_code)]
#[path = "../src/编号与码面.rs"]
mod 编号与码面;
#[path = "../src/连接与句柄.rs"]
mod 连接与句柄;
use std::sync::{Condvar, Mutex, OnceLock, mpsc};
use std::time::{Duration, Instant};
use 编号与码面::错误码;
static 测试互斥: Mutex<()> = Mutex::new(());
static 观测存储: OnceLock<Mutex<Option<mpsc::Sender<String>>>> = OnceLock::new();
static 阻塞开关: (Mutex<bool>, Condvar) = (Mutex::new(false), Condvar::new());
mod 引擎封装 {
    use super::*;
    pub struct 引擎连接 {
        连接名称: String,
        事务空闲: bool,
    }
    impl 引擎连接 {
        pub fn 打开(连接文本: &str) -> Result<Self, u32> {
            Ok(Self {
                连接名称: 连接文本.to_owned(),
                事务空闲: true,
            })
        }
        pub fn 执行(
            &mut self,
            语句文本: &str,
            _截止时刻: Instant,
        ) -> Result<serde_json::Value, u32> {
            if let Some(发送端) = 观测存储
                .get_or_init(|| Mutex::new(None))
                .lock()
                .unwrap()
                .as_ref()
            {
                发送端
                    .send(format!("{}:{}", self.连接名称, 语句文本))
                    .unwrap();
            }
            if 语句文本.contains("等待") {
                let mut 阻塞守卫 = 阻塞开关.0.lock().unwrap();
                while *阻塞守卫 {
                    阻塞守卫 = 阻塞开关.1.wait(阻塞守卫).unwrap();
                }
            }
            if 语句文本.starts_with("BEGIN") {
                self.事务空闲 = false;
            }
            if 语句文本 == "ROLLBACK" && self.连接名称 == "回滚损坏连接" {
                return Err(错误码::数据库语句失败);
            }
            if ["ROLLBACK", "COMMIT"].contains(&语句文本) {
                self.事务空闲 = true;
            }
            if 语句文本.contains("损坏") {
                return Err(错误码::连接不可继续);
            }
            if 语句文本.contains("失败") {
                return Err(错误码::数据库语句失败);
            }
            Ok(serde_json::json!({"行列表": []}))
        }
        pub fn 空闲(&self) -> bool {
            self.事务空闲
        }
    }
    impl Drop for 引擎连接 {
        fn drop(&mut self) {
            if let Some(发送端) = 观测存储
                .get_or_init(|| Mutex::new(None))
                .lock()
                .unwrap()
                .as_ref()
            {
                发送端.send(format!("{}:DROP", self.连接名称)).unwrap();
            }
        }
    }
    pub fn 核语句(_语句文本: &str, _只读: bool) -> Result<(), u32> {
        Ok(())
    }
}
fn 设观测() -> mpsc::Receiver<String> {
    let (发送端, 接收端) = mpsc::channel();
    *观测存储.get_or_init(|| Mutex::new(None)).lock().unwrap() = Some(发送端);
    接收端
}
fn 放行等待() {
    *阻塞开关.0.lock().unwrap() = false;
    阻塞开关.1.notify_all();
}
#[test]
fn 独立连接并行且同连接事务不插队() {
    let _测试守卫 = 测试互斥.lock().unwrap();
    let 接收端 = 设观测();
    let 写入编号 = 连接与句柄::打开连接("写入连接").unwrap();
    let 读取编号 = 连接与句柄::打开连接("读取连接").unwrap();
    *阻塞开关.0.lock().unwrap() = true;
    let 写入线程 = std::thread::spawn(move || {
        连接与句柄::事务(写入编号, &["UPDATE 等待".into(), "UPDATE 后续".into()])
    });
    assert_eq!(接收端.recv().unwrap(), "写入连接:BEGIN");
    assert_eq!(接收端.recv().unwrap(), "写入连接:UPDATE 等待");
    let (完成发送, 完成接收) = mpsc::channel();
    let 读取线程 = std::thread::spawn(move || {
        完成发送
            .send(连接与句柄::查询(读取编号, "SELECT 独立"))
            .unwrap()
    });
    let 独立返回 = 完成接收.recv_timeout(Duration::from_secs(1));
    let (同连接发送, 同连接接收) = mpsc::channel();
    let 同连接线程 = std::thread::spawn(move || {
        同连接发送
            .send(连接与句柄::查询(写入编号, "SELECT 同连接"))
            .unwrap()
    });
    let 同连接提前返回 = 同连接接收.recv_timeout(Duration::from_millis(50));
    放行等待();
    assert_eq!(写入线程.join().unwrap(), Ok(2));
    读取线程.join().unwrap();
    同连接线程.join().unwrap();
    assert!(同连接提前返回.is_err(), "同连接必须等待整个事务完成");
    assert!(同连接接收.recv().unwrap().is_ok());
    assert!(独立返回.unwrap().is_ok(), "独立连接不应被表锁拒绝或阻挡");
    连接与句柄::释放连接(写入编号).unwrap();
    连接与句柄::释放连接(读取编号).unwrap();
    let 记录列表: Vec<_> = 接收端.try_iter().collect();
    let 写入记录: Vec<_> = 记录列表
        .iter()
        .filter(|记录文本| 记录文本.starts_with("写入连接:"))
        .map(String::as_str)
        .collect();
    assert_eq!(
        写入记录,
        [
            "写入连接:UPDATE 后续",
            "写入连接:COMMIT",
            "写入连接:BEGIN READ ONLY",
            "写入连接:SELECT 同连接",
            "写入连接:COMMIT",
            "写入连接:DROP"
        ]
    );
}
#[test]
fn 关闭等待在途执行且只收尾一次() {
    let _测试守卫 = 测试互斥.lock().unwrap();
    let 接收端 = 设观测();
    let 连接编号 = 连接与句柄::打开连接("关闭连接").unwrap();
    *阻塞开关.0.lock().unwrap() = true;
    let 查询线程 = std::thread::spawn(move || 连接与句柄::查询(连接编号, "SELECT 等待"));
    接收端.recv().unwrap();
    接收端.recv().unwrap();
    let (完成发送, 完成接收) = mpsc::channel();
    let 关闭线程 =
        std::thread::spawn(move || 完成发送.send(连接与句柄::释放连接(连接编号)).unwrap());
    let 提前返回 = 完成接收.recv_timeout(Duration::from_millis(50));
    放行等待();
    assert!(查询线程.join().unwrap().is_ok());
    关闭线程.join().unwrap();
    assert!(提前返回.is_err());
    assert_eq!(完成接收.recv().unwrap(), Ok(1));
    assert_eq!(
        连接与句柄::查询(连接编号, "SELECT 后续"),
        Err(错误码::连接句柄无效)
    );
    assert_eq!(
        接收端.try_iter().collect::<Vec<_>>(),
        ["关闭连接:COMMIT", "关闭连接:DROP"]
    );
}
#[test]
fn 失败回滚保留连接且损坏连接移除() {
    let _测试守卫 = 测试互斥.lock().unwrap();
    let 接收端 = 设观测();
    let 连接编号 = 连接与句柄::打开连接("回滚连接").unwrap();
    assert_eq!(
        连接与句柄::事务(连接编号, &["UPDATE 失败".into()]),
        Err(错误码::数据库语句失败)
    );
    assert_eq!(
        接收端.try_iter().collect::<Vec<_>>(),
        [
            "回滚连接:BEGIN",
            "回滚连接:UPDATE 失败",
            "回滚连接:ROLLBACK"
        ]
    );
    assert!(连接与句柄::查询(连接编号, "SELECT 恢复").is_ok());
    assert_eq!(
        连接与句柄::查询(连接编号, "SELECT 损坏"),
        Err(错误码::连接不可继续)
    );
    assert_eq!(连接与句柄::释放连接(连接编号), Err(错误码::连接句柄无效));
    let 损坏编号 = 连接与句柄::打开连接("回滚损坏连接").unwrap();
    assert_eq!(
        连接与句柄::事务(损坏编号, &["UPDATE 失败".into()]),
        Err(错误码::连接不可继续)
    );
    assert_eq!(连接与句柄::释放连接(损坏编号), Err(错误码::连接句柄无效));
}

struct 环境还原(&'static str);
impl Drop for 环境还原 {
    fn drop(&mut self) {
        // 外层持 `测试互斥`、本线程独占该环境变量 ⇒ 清理不与别的用例竞争。
        unsafe { std::env::remove_var(self.0) };
    }
}
#[test]
fn 连接上限随环境变量收缩且非法值回落默认() {
    let _测试守卫 = 测试互斥.lock().unwrap();
    // 替身 `Drop` 会往观测通道发一条，没装接收端时 unwrap 会炸 ⇒ 本用例装一个并留住。
    let _观测守卫 = 设观测();
    assert_eq!(连接与句柄::连接上限(), 256, "未设环境变量时取默认上限");
    unsafe { std::env::set_var("V1_PG最大连接", "2") };
    let _还原守卫 = 环境还原("V1_PG最大连接");
    assert_eq!(连接与句柄::连接上限(), 2);
    let 第一连接 = 连接与句柄::打开连接("上限连接一").unwrap();
    let 第二连接 = 连接与句柄::打开连接("上限连接二").unwrap();
    assert_eq!(
        连接与句柄::打开连接("上限连接三"),
        Err(错误码::连接资源受限),
        "上限收到 2 之后第三个必须被拒"
    );
    连接与句柄::释放连接(第一连接).unwrap();
    let 第三连接 = 连接与句柄::打开连接("上限连接三").expect("释放腾出的槽应能再开");
    连接与句柄::释放连接(第二连接).unwrap();
    连接与句柄::释放连接(第三连接).unwrap();
    unsafe { std::env::set_var("V1_PG最大连接", "不是数字") };
    assert_eq!(
        连接与句柄::连接上限(),
        256,
        "非法值必须回落默认，不能当成 0"
    );
    unsafe { std::env::set_var("V1_PG最大连接", "0") };
    assert_eq!(连接与句柄::连接上限(), 256, "0 不合法 ⇒ 回落默认");
}
