use crate::协议构造;
use crate::协议解析::生成状态;
use crate::编号与码面::错误码;
use crate::连接与句柄;
use serde_json::{Value, json};
use std::collections::HashMap;
use std::hash::{BuildHasher, RandomState};
use std::io::{BufRead, BufReader, Read};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, OnceLock};
use std::thread::JoinHandle;
use std::time::{Duration, Instant};

struct 任务登记 {
    取消标志: Arc<AtomicBool>,
    状态容器: Arc<Mutex<生成状态>>,
    工作线程: Option<JoinHandle<()>>,
}

#[derive(Default)]
struct 任务总表 {
    登记表: HashMap<u64, 任务登记>,
    停止接收: bool,
}

const 任务上限: usize = 64;
const 请求正文上限: usize = 1048576;
const 内容上限: usize = 8 * 1024 * 1024;
const 错误片段上限: u64 = 4096;

static 任务存储: OnceLock<Mutex<任务总表>> = OnceLock::new();

fn 任务锁() -> Result<std::sync::MutexGuard<'static, 任务总表>, u32> {
    任务存储
        .get_or_init(Default::default)
        .lock()
        .map_err(|_| 错误码::资源受限)
}

fn 说明(失败码: u32) -> &'static str {
    match 失败码 {
        错误码::参数不合法 => "生成参数不合法",
        错误码::协议不支持 => "协议不支持",
        错误码::句柄无效 => "句柄不存在或已释放",
        错误码::任务无效 => "生成任务不存在",
        错误码::资源受限 => "生成内容或资源超出上限",
        错误码::响应不合法 => "上游响应不是可解析的流式事件",
        _ => "上游调用失败",
    }
}

/// 一次生成请求的业务载荷；字段数量固定，避免长参数表。
pub(crate) struct 生成请求<'a> {
    pub(crate) 消息列表: &'a Value,
    pub(crate) 系统提示词: &'a str,
    pub(crate) 温度: f64,
    pub(crate) 最大令牌数: u64,
    pub(crate) 工具: &'a Value,
    pub(crate) 响应格式: &'a Value,
    pub(crate) 附加请求头: &'a Value,
}

pub(crate) fn 提交(句柄编号: u64, 请求: 生成请求<'_>) -> Result<u64, u32> {
    let 连接值 = 连接与句柄::取句柄与协议(句柄编号, "chat_completions")?;
    let 请求正文 = 协议构造::构造请求(
        &连接值.模型,
        请求.消息列表,
        请求.系统提示词,
        请求.温度,
        请求.最大令牌数,
        请求.工具,
        请求.响应格式,
    )?;
    if 请求正文.len() > 请求正文上限 {
        return Err(错误码::资源受限);
    }
    let 单次头表 = crate::业务实现::解析头表(请求.附加请求头)?;
    let mut 附加头表 = 连接值.静态头表.clone();
    附加头表.extend(单次头表);
    let mut 任务表 = 任务锁()?;
    if 任务表.停止接收 {
        return Err(错误码::资源受限);
    }
    if 任务表.登记表.len() >= 任务上限 {
        return Err(错误码::资源受限);
    }
    let 任务句柄 = 新任务号(&任务表)?;
    let 取消标志 = Arc::new(AtomicBool::new(false));
    let 状态容器 = Arc::new(Mutex::new(生成状态::default()));
    任务表.登记表.insert(
        任务句柄,
        任务登记 {
            取消标志: 取消标志.clone(),
            状态容器: 状态容器.clone(),
            工作线程: None,
        },
    );
    let 线程取消标志 = 取消标志.clone();
    let 线程状态容器 = 状态容器.clone();
    let 请求地址 = 连接值.请求地址.clone();
    let 接口密钥 = 连接值.接口密钥.clone();
    let 许可资源 = crate::模型服务::找端点服务(&请求地址)
        .map(crate::推理许可::许可资源::服务)
        .unwrap_or_else(|| crate::推理许可::许可资源::端点(请求地址.clone()));
    let 启动结果 = std::thread::Builder::new()
        .name("模型生成任务".into())
        .spawn(move || {
            let 执行结果 = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                let _任务许可 =
                    crate::推理许可::取得可取消任务许可(许可资源, &线程取消标志)?;
                if 线程取消标志.load(Ordering::Acquire) {
                    return Ok(());
                }
                跑流式请求(
                    &请求地址,
                    &接口密钥,
                    &附加头表,
                    &请求正文,
                    &线程取消标志,
                    &线程状态容器,
                )
            }))
            .unwrap_or(Err(错误码::上游失败));
            if let Ok(mut 状态值) = 线程状态容器.lock() {
                状态值.收尾();
                if let Err(失败码) = 执行结果
                    && 状态值.失败说明.is_empty()
                {
                    状态值.失败说明 = 说明(失败码).to_owned();
                }
                状态值.已完成 = true;
            }
        });
    match 启动结果 {
        Ok(工作线程) => {
            if let Some(登记项) = 任务表.登记表.get_mut(&任务句柄) {
                登记项.工作线程 = Some(工作线程);
            }
            Ok(任务句柄)
        }
        Err(_) => {
            任务表.登记表.remove(&任务句柄);
            Err(错误码::资源受限)
        }
    }
}

fn 新任务号(任务表: &任务总表) -> Result<u64, u32> {
    for _ in 0..64 {
        let 候选号 = RandomState::new().hash_one((Instant::now(), std::process::id()));
        if 候选号 != 0 && !任务表.登记表.contains_key(&候选号) {
            return Ok(候选号);
        }
    }
    Err(错误码::资源受限)
}

fn 跑流式请求(
    请求地址: &str,
    接口密钥: &str,
    附加头表: &[(String, String)],
    请求正文: &[u8],
    取消标志: &AtomicBool,
    状态容器: &Mutex<生成状态>,
) -> Result<(), u32> {
    let 代理配置 = ureq::Agent::config_builder()
        .timeout_connect(Some(Duration::from_millis(5000)))
        // 推理静默不代表执行退场；不能以五秒读超时释放仍在生成的资源。
        .timeout_recv_response(None)
        .timeout_recv_body(None)
        .proxy(None)
        .max_redirects(0)
        .http_status_as_error(false)
        .build();
    let 请求代理 = ureq::Agent::new_with_config(代理配置);
    let mut 请求构造 = 请求代理
        .post(请求地址)
        .header("Content-Type", "application/json")
        .header("Accept", "text/event-stream");
    if !接口密钥.is_empty() {
        请求构造 = 请求构造.header("Authorization", format!("Bearer {接口密钥}"));
    }
    for (头名称, 头内容) in 附加头表 {
        请求构造 = 请求构造.header(头名称.as_str(), 头内容.as_str());
    }
    let mut 响应 = 请求构造.send(请求正文).map_err(|_| 错误码::上游失败)?;
    let 响应状态码 = 响应.status().as_u16();
    if 响应状态码 != 200 {
        let mut 错误片段 = String::new();
        let _ = 响应
            .body_mut()
            .as_reader()
            .take(错误片段上限)
            .read_to_string(&mut 错误片段);
        let mut 状态值 = 状态容器.lock().map_err(|_| 错误码::资源受限)?;
        状态值.失败说明 = format!("上游状态 {响应状态码}：{}", 错误片段.trim());
        状态值.已完成 = true;
        return Ok(());
    }
    let 响应读取器 = BufReader::new(响应.body_mut().as_reader());
    for 行结果 in 响应读取器.lines() {
        if 取消标志.load(Ordering::Acquire) {
            return Ok(());
        }
        let Ok(事件行文本) = 行结果 else {
            break;
        };
        let mut 状态值 = 状态容器.lock().map_err(|_| 错误码::资源受限)?;
        if 状态值.回复内容.len() + 状态值.思考内容.len() > 内容上限 {
            return Err(错误码::资源受限);
        }
        状态值.处理事件行(&事件行文本);
        let 已完成 = 状态值.已完成;
        drop(状态值);
        if 已完成 {
            break;
        }
    }
    Ok(())
}

pub(crate) fn 读取(任务句柄: u64) -> Result<Value, u32> {
    let 任务表 = 任务锁()?;
    let 登记项 = 任务表.登记表.get(&任务句柄).ok_or(错误码::任务无效)?;
    let 线程已退 = 登记项
        .工作线程
        .as_ref()
        .is_some_and(JoinHandle::is_finished);
    let 状态值 = 登记项.状态容器.lock().map_err(|_| 错误码::资源受限)?;
    let 失败码 = if 状态值.失败说明.is_empty() {
        0
    } else {
        错误码::上游失败
    };
    Ok(json!({
        "已完成": 状态值.已完成 && 线程已退,
        "资源在途": !线程已退,
        "内容": 状态值.回复内容.clone(),
        "思考": 状态值.思考内容.clone(),
        "工具调用": 状态值.工具调用.clone(),
        "结束原因": 状态值.结束原因.clone(),
        "用量": 状态值.用量信息.clone(),
        "错误码": 失败码,
        "错误信息": 状态值.失败说明.clone(),
    }))
}

pub(crate) fn 取消(任务句柄: u64) -> Result<bool, u32> {
    let 任务表 = 任务锁()?;
    let 登记项 = 任务表.登记表.get(&任务句柄).ok_or(错误码::任务无效)?;
    登记项.取消标志.store(true, Ordering::Release);
    crate::推理许可::唤醒等待();
    // 取消请求不等于取消完成：只有生成线程真实退出才能返回真。
    Ok(登记项
        .工作线程
        .as_ref()
        .is_some_and(JoinHandle::is_finished))
}

/// 真 = 线程已退出且归属已移除；假 = 线程仍在跑，仍持归属。
pub(crate) fn 释放(任务句柄: u64) -> Result<bool, u32> {
    let mut 任务表 = 任务锁()?;
    let 线程已退 = {
        let 登记项 = 任务表.登记表.get_mut(&任务句柄).ok_or(错误码::任务无效)?;
        登记项.取消标志.store(true, Ordering::Release);
        crate::推理许可::唤醒等待();
        登记项
            .工作线程
            .as_ref()
            .is_some_and(JoinHandle::is_finished)
    };
    if !线程已退 {
        return Ok(false);
    }
    let 待释放登记 = 任务表.登记表.remove(&任务句柄).ok_or(错误码::任务无效)?;
    if let Some(工作线程) = 待释放登记.工作线程 {
        let _ = 工作线程.join();
    }
    Ok(true)
}

pub(crate) fn 统计() -> Result<(usize, usize), u32> {
    let 任务表 = 任务锁()?;
    let 在途数 = 任务表
        .登记表
        .values()
        .filter(|登记项| {
            !登记项
                .工作线程
                .as_ref()
                .is_some_and(JoinHandle::is_finished)
        })
        .count();
    Ok((任务表.登记表.len(), 在途数))
}

pub(crate) unsafe extern "C" fn 生命周期通知(
    通知编号: v1_contract::通知号,
    _: usize,
    _: usize,
) -> isize {
    let Ok(mut 任务表) = 任务锁() else {
        return v1_contract::通知返回::延迟释放;
    };
    match 通知编号.取号值() {
        2000 => {
            任务表.停止接收 = false;
            0
        }
        2001..=2003 => {
            任务表.停止接收 = true;
            for 登记项 in 任务表.登记表.values_mut() {
                登记项.取消标志.store(true, Ordering::Release);
            }
            crate::推理许可::唤醒等待();
            let 仍有在途 = 任务表.登记表.values().any(|登记项| {
                !登记项
                    .工作线程
                    .as_ref()
                    .is_some_and(JoinHandle::is_finished)
            });
            if 仍有在途 {
                v1_contract::通知返回::延迟释放
            } else {
                0
            }
        }
        _ => 0,
    }
}

#[cfg(test)]
mod 生成生命周期回归 {
    use super::*;
    use std::io::Write;
    struct 模拟服务 {
        地址文本: String,
        完成标志: Arc<AtomicBool>,
        停止标志: Arc<AtomicBool>,
        接收计数: Arc<std::sync::atomic::AtomicUsize>,
        服务线程: Option<JoinHandle<()>>,
    }
    impl 模拟服务 {
        fn 启动模拟() -> Self {
            let 监听器 = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
            监听器.set_nonblocking(true).unwrap();
            let 地址文本 = format!("http://{}", 监听器.local_addr().unwrap());
            let 完成标志 = Arc::new(AtomicBool::new(false));
            let 停止标志 = Arc::new(AtomicBool::new(false));
            let 接收计数 = Arc::new(std::sync::atomic::AtomicUsize::new(0));
            let 线程完成标志 = 完成标志.clone();
            let 线程停止标志 = 停止标志.clone();
            let 线程接收计数 = 接收计数.clone();
            let 服务线程 = std::thread::spawn(move || {
                let mut 在途连接 = Vec::new();
                while !线程停止标志.load(Ordering::Acquire) {
                    if let Ok((mut 网络连接, _)) = 监听器.accept() {
                        网络连接
                            .set_read_timeout(Some(Duration::from_secs(1)))
                            .unwrap();
                        let mut 请求缓冲 = [0u8; 8192];
                        let _ = 网络连接.read(&mut 请求缓冲);
                        let _ = 网络连接.write_all(b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nConnection: close\r\n\r\n");
                        线程接收计数.fetch_add(1, Ordering::AcqRel);
                        在途连接.push(网络连接);
                    }
                    if 线程完成标志.load(Ordering::Acquire) {
                        for mut 网络连接 in 在途连接.drain(..) {
                            let _ = 网络连接.write_all(b"data: [DONE]\n\n");
                        }
                    }
                    std::thread::sleep(Duration::from_millis(2));
                }
            });
            Self {
                地址文本,
                完成标志,
                停止标志,
                接收计数,
                服务线程: Some(服务线程),
            }
        }
    }
    impl Drop for 模拟服务 {
        fn drop(&mut self) {
            self.停止标志.store(true, Ordering::Release);
            if let Some(服务线程) = self.服务线程.take() {
                服务线程.join().unwrap();
            }
        }
    }
    fn 提交模拟(连接编号: u64) -> u64 {
        提交(
            连接编号,
            生成请求 {
                消息列表: &json!([{"role":"user","content":"生命周期验收"}]),
                系统提示词: "",
                温度: 0.0,
                最大令牌数: 8,
                工具: &json!([]),
                响应格式: &json!({}),
                附加请求头: &json!({}),
            },
        )
        .unwrap()
    }
    fn 等待退场(任务编号: u64) {
        let 截止时刻 = Instant::now() + Duration::from_secs(3);
        while !读取(任务编号).unwrap()["已完成"].as_bool().unwrap() {
            assert!(Instant::now() < 截止时刻, "生成未退场");
            std::thread::sleep(Duration::from_millis(2));
        }
    }
    #[test]
    fn 返回任务句柄后超过五秒仍独占且取消须退场() {
        let 模拟实例 = 模拟服务::启动模拟();
        let 连接编号 = 连接与句柄::连接对话模型(
            "模拟模型",
            &模拟实例.地址文本,
            "",
            "chat_completions",
            vec![],
        )
        .unwrap();
        let 先发任务 = 提交模拟(连接编号);
        let 截止时刻 = Instant::now() + Duration::from_secs(2);
        while 模拟实例.接收计数.load(Ordering::Acquire) == 0 {
            assert!(Instant::now() < 截止时刻);
            std::thread::sleep(Duration::from_millis(2));
        }
        let 后发任务 = 提交模拟(连接编号);
        std::thread::sleep(Duration::from_millis(5200));
        let 在途读数 = 读取(先发任务).unwrap();
        let 收到请求数 = 模拟实例.接收计数.load(Ordering::Acquire);
        let 取消已完成 = 取消(先发任务).unwrap();
        模拟实例.完成标志.store(true, Ordering::Release);
        等待退场(先发任务);
        等待退场(后发任务);
        assert!(取消(先发任务).unwrap());
        assert!(释放(先发任务).unwrap());
        assert!(释放(后发任务).unwrap());
        assert!(连接与句柄::释放(连接编号).unwrap());
        assert_eq!(收到请求数, 1, "同一端点出现重叠请求");
        assert_eq!(在途读数["资源在途"], true);
        assert!(!取消已完成, "仍在读取网络的取消不能宣布完成");
    }
}
