use crate::异步请求执行::网络请求说明;
use crate::编号与码面::错误码;
use serde_json::{Value,json};
use std::collections::HashMap;
use std::hash::{BuildHasher,RandomState};
use std::sync::{Mutex,OnceLock,Arc,atomic::{AtomicBool,Ordering}};
use std::thread::JoinHandle;
use std::time::{Duration,Instant};

struct 网络任务条目 {
    创建时刻:Instant,
    超时预算:Duration,
    完成时刻:Option<Instant>,
    执行结果:Option<Result<Value,u32>>,
    取消标志:Arc<AtomicBool>,
    丢弃结果:bool,
    超时触发:bool,
    工作线程:Option<JoinHandle<()>>,
}
#[derive(Default)]
struct 网络任务总表 {任务条目表:HashMap<u64,网络任务条目>,停止接收:bool}
/// 完成后结果可读窗口；与平台十秒硬顶同口径，过期即回收。
const 结果保留时长:Duration=Duration::from_secs(10);
static 网络任务存储:OnceLock<Mutex<网络任务总表>>=OnceLock::new();
fn 任务表锁()->Result<std::sync::MutexGuard<'static,网络任务总表>,u32>{网络任务存储.get_or_init(Default::default).lock().map_err(|_|错误码::资源受限)}

impl 网络任务总表 {
    fn 清到期(&mut self){
        for 任务条目 in self.任务条目表.values_mut(){
            if 任务条目.执行结果.is_none() && 任务条目.创建时刻.elapsed()>任务条目.超时预算 && !任务条目.取消标志.load(Ordering::Acquire) {任务条目.超时触发=true;任务条目.取消标志.store(true,Ordering::Release);}
        }
        self.任务条目表.retain(|_,任务条目|{
            let 线程已退=任务条目.工作线程.as_ref().is_some_and(JoinHandle::is_finished);
            let 结果已过期=任务条目.完成时刻.is_some_and(|完成时刻|完成时刻.elapsed()>=结果保留时长);
            if 线程已退 && (任务条目.丢弃结果||结果已过期){
                if let Some(工作线程)=任务条目.工作线程.take(){let _=工作线程.join();}
                false
            }else{true}
        });
    }
}

pub(crate) fn 提交请求(请求参数:Value)->Result<u64,u32>{
    let 请求说明=网络请求说明::解析(请求参数)?;
    let 超时预算=Duration::from_secs_f64(请求说明.超时秒数);
    let mut 任务总表=任务表锁()?;
    if 任务总表.停止接收{return Err(错误码::资源受限);}
    任务总表.清到期();
    if 任务总表.任务条目表.len()>=32{return Err(错误码::资源受限);}
    let 任务句柄=loop{let 候选号=RandomState::new().hash_one((Instant::now(),std::process::id()));if 候选号!=0&&!任务总表.任务条目表.contains_key(&候选号){break 候选号;}};
    let 取消标志=Arc::new(AtomicBool::new(false));
    任务总表.任务条目表.insert(任务句柄,网络任务条目{创建时刻:Instant::now(),超时预算,完成时刻:None,执行结果:None,取消标志:取消标志.clone(),丢弃结果:false,超时触发:false,工作线程:None});
    let 启动结果=std::thread::Builder::new().name("网络请求执行".into()).spawn(move||{
        let 执行结果=std::panic::catch_unwind(std::panic::AssertUnwindSafe(||请求说明.执行(取消标志.clone()))).unwrap_or(Err(错误码::请求失败));
        if let Ok(mut 任务总表)=任务表锁() && let Some(任务条目)=任务总表.任务条目表.get_mut(&任务句柄){
                任务条目.执行结果=Some(if 任务条目.超时触发{Err(错误码::请求超时)}else if 取消标志.load(Ordering::Acquire){Err(错误码::任务已取消)}else{执行结果});
                任务条目.完成时刻=Some(Instant::now());
        }
    });
    match 启动结果{
        Ok(工作线程)=>{任务总表.任务条目表.get_mut(&任务句柄).ok_or(错误码::任务无效)?.工作线程=Some(工作线程);Ok(任务句柄)},
        Err(_)=>{任务总表.任务条目表.remove(&任务句柄);Err(错误码::资源受限)},
    }
}

pub(crate) fn 读取任务(任务句柄:u64)->Result<Value,u32>{
    let mut 任务总表=任务表锁()?;
    任务总表.清到期();
    let 任务条目=任务总表.任务条目表.get(&任务句柄).ok_or(错误码::任务无效)?;
    if 任务条目.丢弃结果{return Err(错误码::任务无效);}
    let 资源在途=!任务条目.工作线程.as_ref().is_some_and(JoinHandle::is_finished);
    if let Some(执行结果)=&任务条目.执行结果{
        let mut 完成结果=match 执行结果{
            Ok(完成结果)=>完成结果.clone(),
            Err(失败码)=>json!({"错误码":失败码,"错误信息":match *失败码{错误码::任务已取消=>"网络任务已取消",错误码::请求超时=>"网络请求超时",错误码::出站被拒=>"目标地址不符合出站策略",错误码::资源受限=>"响应或资源超限",错误码::内容不合法=>"响应不是有效UTF-8文本",_=>"网络请求执行失败"}}),
        };
        完成结果["已完成"]=json!(!资源在途);
        完成结果["资源在途"]=json!(资源在途);
        return Ok(完成结果);
    }
    Ok(json!({"已完成":false,"资源在途":true,"取消已请求":任务条目.取消标志.load(Ordering::Acquire)}))
}

pub(crate) fn 取消任务(任务句柄:u64,丢弃结果:bool)->Result<bool,u32>{
    let mut 任务总表=任务表锁()?;
    任务总表.清到期();
    let 任务条目=任务总表.任务条目表.get_mut(&任务句柄).ok_or(错误码::任务无效)?;
    任务条目.取消标志.store(true,Ordering::Release);
    任务条目.丢弃结果|=丢弃结果;
    let 线程已退=任务条目.工作线程.as_ref().is_some_and(JoinHandle::is_finished);
    if 丢弃结果&&线程已退 && let Some(mut 任务条目)=任务总表.任务条目表.remove(&任务句柄) && let Some(工作线程)=任务条目.工作线程.take(){let _=工作线程.join();}
    Ok(if 丢弃结果{线程已退}else{true})
}

pub(crate) unsafe extern "C" fn 生命周期通知(通知编号:v1_contract::通知号,_:usize,_:usize)->isize{
    let Ok(mut 任务总表)=任务表锁() else{return v1_contract::通知返回::延迟释放;};
    match 通知编号.取号值(){
        2000=>{任务总表.停止接收=false;0},
        2001..=2003=>{
            任务总表.停止接收=true;
            for 任务条目 in 任务总表.任务条目表.values_mut(){任务条目.取消标志.store(true,Ordering::Release);任务条目.丢弃结果=true;}
            任务总表.清到期();
            if 任务总表.任务条目表.is_empty(){0}else{v1_contract::通知返回::延迟释放}
        },
        _=>0,
    }
}
