use crate::编号与码面::{能力号,错误码};
use minijinja::{Environment as 模板环境, UndefinedBehavior as 未定义行为};
use v1_contract::复合值载荷::{复合值,复合元素,编码复合值载荷};
struct 有界文本 { 文本内容: String, 已越界: bool }
impl std::io::Write for 有界文本 {
    fn write(&mut self, 片段:&[u8])->std::io::Result<usize> {
        if self.文本内容.len()+片段.len()>65536 { self.已越界=true; return Err(std::io::Error::other("输出越界")); }
        self.文本内容.push_str(std::str::from_utf8(片段).map_err(std::io::Error::other)?);
        Ok(片段.len())
    }
    fn flush(&mut self)->std::io::Result<()> {Ok(())}
}

fn 是否标识符字符(待判字符:char)->bool { 待判字符=='_' || 待判字符.is_alphanumeric() }

fn 收集上下文键名(上下文值:&serde_json::Value,收集表:&mut Vec<String>) {
    match 上下文值 {
        serde_json::Value::Object(键值表) => {
            for (键名,子值) in 键值表 { 收集表.push(键名.clone()); 收集上下文键名(子值,收集表); }
        }
        serde_json::Value::Array(元素表) => { for 子值 in 元素表 { 收集上下文键名(子值,收集表); } }
        _ => {}
    }
}

fn 生成标识符映射(待处理模板:&str,上下文值:&serde_json::Value)->Vec<(String,String)> {
    let mut 收集表:Vec<String>=Vec::new();
    收集上下文键名(上下文值,&mut 收集表);
    let 字符表:Vec<char>=待处理模板.chars().collect();
    let mut 扫描起点=0usize;
    while 扫描起点<字符表.len() {
        let 是起始标记=字符表[扫描起点]=='{' && 扫描起点+1<字符表.len() && (字符表[扫描起点+1]=='{' || 字符表[扫描起点+1]=='%');
        if !是起始标记 { 扫描起点+=1; continue; }
        let 结束字符=if 字符表[扫描起点+1]=='{' {'}'} else {'%'};
        let mut 扫描位置=扫描起点+2;
        while 扫描位置<字符表.len() {
            if 字符表[扫描位置]=='}' && 结束字符=='}' { break; }
            if 字符表[扫描位置]=='%' && 结束字符=='%' && 扫描位置+1<字符表.len() && 字符表[扫描位置+1]=='}' { break; }
            if 是否标识符字符(字符表[扫描位置]) {
                let 标识符起始位置=扫描位置;
                while 扫描位置<字符表.len() && (是否标识符字符(字符表[扫描位置]) || 字符表[扫描位置]=='.') { 扫描位置+=1; }
                let 片段文本:String=字符表[标识符起始位置..扫描位置].iter().collect();
                for 路径词段 in 片段文本.split('.') {
                    if !路径词段.is_empty() && !路径词段.is_ascii() { 收集表.push(路径词段.to_string()); }
                }
                continue;
            }
            扫描位置+=1;
        }
        扫描起点=扫描位置+1;
    }
    let mut 映射名称表:Vec<(String,String)>=Vec::new();
    for 候选名称 in 收集表 {
        if 候选名称.is_empty() || 候选名称.is_ascii() { continue; }
        if 映射名称表.iter().any(|(旧名,_)| 旧名==&候选名称) { continue; }
        let 替换名称=format!("v{}",映射名称表.len()+1);
        映射名称表.push((候选名称,替换名称));
    }
    映射名称表.sort_by_key(|次项| std::cmp::Reverse(次项.0.chars().count()));
    映射名称表
}

fn 替换区间标识符(模板区间文本:&str,映射名称表:&[(String,String)])->String {
    let mut 当前文本=模板区间文本.to_string();
    for (旧名,替换名称) in 映射名称表 { 当前文本=当前文本.replace(旧名.as_str(),替换名称.as_str()); }
    当前文本
}

fn 处理模板标识符(待处理模板:&str,映射名称表:&[(String,String)])->String {
    let mut 输出页面文本=String::with_capacity(待处理模板.len());
    let mut 剩余模板=待处理模板;
    loop {
        let 双花括号位置=剩余模板.find("{{");
        let 百分号位置=剩余模板.find("{%");
        let 起始位置选项=match (双花括号位置,百分号位置) {
            (Some(左位),Some(右位)) => Some((左位.min(右位),左位<=右位)),
            (Some(左位),None) => Some((左位,true)),
            (None,Some(右位)) => Some((右位,false)),
            (None,None) => None,
        };
        let (起点位置,是双花括号)=match 起始位置选项 {
            Some(起点项)=>(起点项.0,起点项.1),
            None=>{ 输出页面文本.push_str(剩余模板); break; }
        };
        输出页面文本.push_str(&剩余模板[..起点位置]);
        let 区间余下=&剩余模板[起点位置+2..];
        let 结束标记=if 是双花括号 {"}}"} else {"%}"};
        match 区间余下.find(结束标记) {
            Some(结束位置) => {
                输出页面文本.push_str(if 是双花括号 {"{{"} else {"{%"});
                输出页面文本.push_str(&替换区间标识符(&区间余下[..结束位置],映射名称表));
                输出页面文本.push_str(结束标记);
                剩余模板=&区间余下[结束位置+结束标记.len()..];
            }
            None => { 输出页面文本.push_str(&剩余模板[起点位置..]); break; }
        }
    }
    输出页面文本
}

fn 重命名上下文键(上下文值:serde_json::Value,映射名称表:&[(String,String)])->serde_json::Value {
    match 上下文值 {
        serde_json::Value::Object(键值表) => {
            let mut 重命名后键值表=serde_json::Map::new();
            for (键名,子值) in 键值表 {
                let 新键名=映射名称表.iter().find(|(旧名,_)| 旧名==&键名).map(|(_,替换名称)| 替换名称.clone()).unwrap_or(键名);
                重命名后键值表.insert(新键名,重命名上下文键(子值,映射名称表));
            }
            serde_json::Value::Object(重命名后键值表)
        }
        serde_json::Value::Array(元素表) => serde_json::Value::Array(
            元素表.into_iter().map(|子值| 重命名上下文键(子值,映射名称表)).collect()),
        _ => 上下文值,
    }
}

fn 渲染网页页面(参数表:&[&[u8]])->Result<(u32,Vec<u8>),u32> {
    let 待处理模板=std::str::from_utf8(参数表[0]).map_err(|_|错误码::参数不合法)?;
    let 上下文原文=std::str::from_utf8(参数表[1]).map_err(|_|错误码::参数不合法)?;
    let 上下文值:serde_json::Value=serde_json::from_str(上下文原文).map_err(|_|错误码::内容不合法)?;
    if !上下文值.is_object() { return Err(错误码::内容不合法); }
    let 映射名称表=生成标识符映射(待处理模板,&上下文值);
    let 页面渲染前模板=处理模板标识符(待处理模板,&映射名称表);
    let 重命名后上下文=重命名上下文键(上下文值,&映射名称表);
    let mut 环境=模板环境::new();
    环境.set_undefined_behavior(未定义行为::Strict);
    环境.set_fuel(Some(100000));
    环境.add_template("页面.html",页面渲染前模板.as_str()).map_err(|_|错误码::内容不合法)?;
    let 模板=环境.get_template("页面.html").map_err(|_|错误码::内容不合法)?;
    let mut 输出=有界文本{文本内容:String::new(),已越界:false};
    模板.render_captured_to(minijinja::value::Serde(重命名后上下文),&mut 输出)
        .map_err(|失败| if 失败.kind()==minijinja::ErrorKind::OutOfFuel || 输出.已越界 {错误码::资源受限} else {错误码::内容不合法})?;
    Ok((4,输出.文本内容.into_bytes()))
}

pub fn 执行业务操作(编号:u32,参数表:&[&[u8]])->Result<(u32,Vec<u8>),u32> {
    if 编号==能力号::渲染网页页面 { return 渲染网页页面(参数表); }
    let 原文=std::str::from_utf8(参数表[0]).map_err(|_|错误码::参数不合法)?;
    if 原文.contains("{%") || 原文.contains("{#") {return Err(错误码::内容不合法);}
    let mut 剩余模板=原文;
    while let Some(起点)=剩余模板.find("{{") {
        剩余模板=&剩余模板[起点+2..];
        let 闭合位置=剩余模板.find("}}").ok_or(错误码::内容不合法)?;
        let 变量路径=剩余模板[..闭合位置].trim();
        if 变量路径.is_empty() || !变量路径.split('.').all(|片段| !片段.is_empty() && 片段.chars().enumerate().all(|(字符位置,路径字符)| 路径字符=='_' || (路径字符.is_alphanumeric() && (字符位置>0 || !路径字符.is_numeric())))) {return Err(错误码::内容不合法);}
        剩余模板=&剩余模板[闭合位置+2..];
    }
    let mut 环境=模板环境::new();
    环境.set_undefined_behavior(未定义行为::Strict);
    环境.set_fuel(Some(100000));
    环境.add_template("正文",原文).map_err(|_|错误码::内容不合法)?;
    let 模板=环境.get_template("正文").map_err(|_|错误码::内容不合法)?;
    if 编号==能力号::提取变量名 {
        let mut 名称表=模板.undeclared_variables(true).into_iter().collect::<Vec<_>>();名称表.sort();
        if 名称表.len()>1000 { return Err(错误码::资源受限); }
        let 元素表=名称表.into_iter().map(|名称|复合元素{名称:String::new(),值:复合值::文本载荷(名称)}).collect::<Vec<_>>();
        return Ok((100,编码复合值载荷(100,&元素表).map_err(|_|错误码::内容不合法)?));
    }
    let 上下文:serde_json::Value=serde_json::from_slice(参数表[1]).map_err(|_|错误码::内容不合法)?;
    if !上下文.is_object(){return Err(错误码::内容不合法);}
    let mut 输出=有界文本{文本内容:String::new(),已越界:false};
    模板.render_captured_to(minijinja::value::Serde(上下文),&mut 输出).map_err(|失败| if 失败.kind()==minijinja::ErrorKind::OutOfFuel || 输出.已越界 {错误码::资源受限}else{错误码::内容不合法})?;
    Ok((4,输出.文本内容.into_bytes()))
}
