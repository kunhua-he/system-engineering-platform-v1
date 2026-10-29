use crate::编号与码面::错误码;
use std::collections::HashMap;
use std::io::Read;
use std::net::{IpAddr, SocketAddr, ToSocketAddrs};
use std::net::IpAddr::{V4 as IPv4地址, V6 as IPv6地址};
use url::Url as URL地址;
use std::sync::{Arc, atomic::{AtomicBool, Ordering}};
use std::time::{Duration, Instant};
use ureq::unversioned::resolver::{ResolvedSocketAddrs, Resolver};
use ureq::unversioned::transport::{DefaultConnector, NextTimeout};
use serde_json::{Value, json};

#[derive(Debug)]
struct 固定地址解析 { 固定地址: Vec<SocketAddr> }
impl Resolver for 固定地址解析 {
    fn resolve(&self, _: &ureq::http::Uri, _: &ureq::config::Config, _: NextTimeout) -> Result<ResolvedSocketAddrs, ureq::Error> {
        let mut 地址容器 = self.empty();
        for 地址条目 in &self.固定地址 { 地址容器.push(*地址条目); }
        Ok(地址容器)
    }
}

pub(crate) struct 网络请求说明 {
    pub(crate) 请求地址: URL地址,
    请求方法: String,
    请求头表: HashMap<String, String>,
    请求正文: Vec<u8>,
    pub(crate) 超时秒数: f64,
    响应上限: usize,
    允许回环: bool,
    仅校验: bool,
}

impl 网络请求说明 {
    pub(crate) fn 解析(请求参数: Value) -> Result<Self, u32> {
        let 参数映射 = 请求参数.as_object().ok_or(错误码::参数不合法)?;
        let 合法字段 = ["地址","方法","请求头","请求体","超时秒","最大字节数","允许回环","代理","SSL验证","跟随重定向","Cookie","仅校验"];
        if 参数映射.keys().any(|字段名| !合法字段.contains(&字段名.as_str())) { return Err(错误码::参数不合法); }
        let 请求地址 = URL地址::parse(参数映射.get("地址").and_then(Value::as_str).ok_or(错误码::参数不合法)?).map_err(|_|错误码::参数不合法)?;
        if !["http","https"].contains(&请求地址.scheme()) || 请求地址.host_str().is_none() || !请求地址.username().is_empty() || 请求地址.password().is_some() || 请求地址.fragment().is_some() { return Err(错误码::参数不合法); }
        let 超时秒数 = 参数映射.get("超时秒").map(|取值|取值.as_f64().ok_or(错误码::参数不合法)).transpose()?.unwrap_or(10.0);
        if !超时秒数.is_finite() || 超时秒数<=0.0 || 超时秒数>60.0 { return Err(错误码::参数不合法); }
        let 响应上限 = 参数映射.get("最大字节数").map(|取值|取值.as_u64().ok_or(错误码::参数不合法)).transpose()?.unwrap_or(2*1024*1024);
        if 响应上限==0 || 响应上限>4*1024*1024 { return Err(错误码::资源受限); }
        let 取逻辑值 = |字段名: &str, 默认值: bool| -> Result<bool,u32> { 参数映射.get(字段名).map(|取值|取值.as_bool().ok_or(错误码::参数不合法)).transpose().map(|取值|取值.unwrap_or(默认值)) };
        if !取逻辑值("SSL验证",true)? || 取逻辑值("跟随重定向",false)? || 参数映射.get("代理").is_some_and(|取值| !取值.is_null() && 取值.as_str()!=Some("")) { return Err(错误码::参数不合法); }
        let 请求方法 = 参数映射.get("方法").map(|取值|取值.as_str().ok_or(错误码::参数不合法)).transpose()?.unwrap_or("GET").to_uppercase();
        if !["GET","POST","PUT","PATCH","DELETE","HEAD","OPTIONS"].contains(&请求方法.as_str()) { return Err(错误码::参数不合法); }
        let mut 请求头表 = HashMap::new();
        if let Some(请求头值) = 参数映射.get("请求头") {
            for (头名称, 头内容) in 请求头值.as_object().ok_or(错误码::参数不合法)? {
                if ["host","content-length","transfer-encoding","connection","proxy-authorization"].contains(&头名称.to_ascii_lowercase().as_str()) { return Err(错误码::参数不合法); }
                请求头表.insert(头名称.clone(),头内容.as_str().ok_or(错误码::参数不合法)?.to_owned());
            }
        }
        if let Some(Cookie文本) = 参数映射.get("Cookie") { 请求头表.insert("Cookie".into(), Cookie文本.as_str().ok_or(错误码::参数不合法)?.to_owned()); }
        if 请求头表.len()>128 || 请求头表.iter().map(|(头名称,头内容)|头名称.len()+头内容.len()).sum::<usize>()>65536 { return Err(错误码::资源受限); }
        let 请求正文 = match 参数映射.get("请求体") {
            None | Some(Value::Null) => Vec::new(),
            Some(Value::String(正文文本)) => 正文文本.as_bytes().to_vec(),
            Some(正文对象) => { 请求头表.entry("Content-Type".into()).or_insert_with(||"application/json".into()); serde_json::to_vec(正文对象).map_err(|_|错误码::参数不合法)? },
        };
        if 请求正文.len()>131072 { return Err(错误码::资源受限); }
        Ok(Self{请求地址,请求方法,请求头表,请求正文,超时秒数,响应上限:响应上限 as usize,允许回环:取逻辑值("允许回环",false)?,仅校验:取逻辑值("仅校验",false)?})
    }

    pub(crate) fn 执行(self, 取消标志: Arc<AtomicBool>) -> Result<Value,u32> {
        let 开始时刻 = Instant::now();
        let 固定地址 = self.解析安全地址()?;
        if 取消标志.load(Ordering::Acquire) { return Err(错误码::任务已取消); }
        let 剩余预算 = Duration::from_secs_f64(self.超时秒数).checked_sub(开始时刻.elapsed()).ok_or(错误码::请求超时)?;
        if self.仅校验 { return Ok(json!({"状态码":0,"响应头":{},"响应文本":"","错误信息":"","地址":self.请求地址.as_str()})); }
        let 配置 = ureq::Agent::config_builder().timeout_global(Some(剩余预算)).proxy(None).max_redirects(0).http_status_as_error(false).build();
        let 请求代理 = ureq::Agent::with_parts(配置,DefaultConnector::default(),固定地址解析{固定地址});
        let mut 请求构造 = ureq::http::Request::builder().method(self.请求方法.as_str()).uri(self.请求地址.as_str());
        for (头名称,头内容) in self.请求头表 { 请求构造=请求构造.header(头名称,头内容); }
        let 请求实例 = 请求构造.body(self.请求正文).map_err(|_|错误码::参数不合法)?;
        let mut 网络响应 = 请求代理.run(请求实例).map_err(|调用错误| if matches!(调用错误,ureq::Error::Timeout(_)){错误码::请求超时}else{错误码::请求失败})?;
        let 状态码 = 网络响应.status().as_u16();
        let mut 响应头表 = serde_json::Map::new();
        let mut 响应头长度=0;
        for (头名称,头内容) in 网络响应.headers() {
            let 头内容 = 头内容.to_str().map_err(|_|错误码::内容不合法)?;
            响应头长度+=头名称.as_str().len()+头内容.len();
            if 响应头长度>65536 { return Err(错误码::资源受限); }
            响应头表.insert(头名称.to_string(), Value::String(头内容.to_owned()));
        }
        let mut 响应正文 = Vec::new();
        let mut 响应读取器 = 网络响应.body_mut().as_reader().take(self.响应上限 as u64+1);
        let mut 正文缓冲 = [0u8;8192];
        loop {
            if 取消标志.load(Ordering::Acquire) { return Err(错误码::任务已取消); }
            let 本次长度 = 响应读取器.read(&mut 正文缓冲).map_err(|_| if 开始时刻.elapsed()>=Duration::from_secs_f64(self.超时秒数){错误码::请求超时}else{错误码::请求失败})?;
            if 本次长度==0 { break; }
            响应正文.extend_from_slice(&正文缓冲[..本次长度]);
            if 响应正文.len()>self.响应上限 { return Err(错误码::资源受限); }
        }
        let 响应文本 = String::from_utf8(响应正文).map_err(|_|错误码::内容不合法)?;
        Ok(json!({"状态码":状态码,"响应头":响应头表,"响应文本":响应文本,"错误信息":""}))
    }

    fn 解析安全地址(&self) -> Result<Vec<SocketAddr>,u32> {
        let 主机文本 = self.请求地址.host_str().ok_or(错误码::参数不合法)?.trim_matches(['[',']']);
        let 目标端口 = self.请求地址.port_or_known_default().ok_or(错误码::参数不合法)?;
        let 地址迭代 = (主机文本,目标端口).to_socket_addrs().map_err(|_|错误码::请求失败)?;
        let mut 固定地址 = Vec::new();
        for 地址条目 in 地址迭代 {
            if !地址允许(地址条目.ip(),self.允许回环) { return Err(错误码::出站被拒); }
            if !固定地址.contains(&地址条目) { 固定地址.push(地址条目); }
            if 固定地址.len()>8 { return Err(错误码::资源受限); }
        }
        if 固定地址.is_empty() { return Err(错误码::请求失败); }
        Ok(固定地址)
    }
}

pub(crate) fn 地址允许(地址值:IpAddr,允许回环:bool)->bool{
    match 地址值 {
        IPv4地址(地址值)=>{
            let 地址字节=地址值.octets();
            if 地址值.is_loopback(){return 允许回环;}
            !地址值.is_private() && !地址值.is_link_local() && !地址值.is_broadcast() && !地址值.is_documentation() && !地址值.is_multicast()
                && 地址字节[0]!=0 && 地址字节[0]<224 && !(地址字节[0]==100&&(64..=127).contains(&地址字节[1]))
                && !(地址字节[0]==198&&(18..=19).contains(&地址字节[1])) && !(地址字节[0]==192&&地址字节[1]==0&&地址字节[2]==0)
        },
        IPv6地址(地址值)=>{
            if let Some(映射地址)=地址值.to_ipv4_mapped(){return 地址允许(IPv4地址(映射地址),允许回环);}
            if 地址值.is_loopback(){return 允许回环;}
            let 地址分段=地址值.segments();
            (地址分段[0]&0xe000)==0x2000 && !(地址分段[0]==0x2001 && (地址分段[1]<=0x01ff||地址分段[1]==0x0db8)) && 地址分段[0]!=0x2002
        },
    }
}
