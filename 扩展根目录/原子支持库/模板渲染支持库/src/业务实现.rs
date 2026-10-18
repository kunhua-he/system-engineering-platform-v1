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
pub fn 执行业务操作(编号:u32,参数表:&[&[u8]])->Result<(u32,Vec<u8>),u32> {
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
