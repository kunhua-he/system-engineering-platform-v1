//! 逐层读取部署声明；分类不启动进程、不展开后代、不复制能力实现。
use crate::协议值::协议值;
use crate::索引请求::索引请求;
use crate::工具响应::读JSON件;
use std::collections::BTreeMap;
use std::path::Path;

fn 文本字段<'a>(声明对象: &'a 协议值, 键名: &str) -> Result<&'a str, String> {
    声明对象.取成员(键名).and_then(协议值::取文本).ok_or_else(|| format!("索引声明缺文本字段：{键名}"))
}
fn 目录卡(名称: &str, 路径: &str, 节点种类: &str) -> 协议值 {
    协议值::对象值(vec![("名称".to_owned(),协议值::文本值(名称.to_owned())),("路径".to_owned(),协议值::文本值(路径.to_owned())),("节点".to_owned(),协议值::文本值(节点种类.to_owned()))])
}
fn 取族路径(声明: &协议值) -> Result<Vec<String>, String> {
    let Some(字段) = 声明.取成员("族类路径") else { return Ok(Vec::new()) };
    let 路径表 = 字段.取数组().ok_or("族类路径须为文本数组")?;
    if 路径表.len() > 14 { return Err("能力族路径超过14层".to_owned()); }
    路径表.iter().map(|族段| {
        let 族名 = 族段.取文本().ok_or("族路径含非文本段")?;
        if 族名.is_empty() || 族名 == "." || 族名 == ".." || 族名.len() > 240 || 族名.contains(['/', '\\', '\0']) { return Err("族路径含无效段".to_owned()); }
        Ok(族名.to_owned())
    }).collect()
}

pub fn 读取索引(工具根: &Path, 请求: &索引请求) -> Result<协议值, String> {
    let 根声明 = 读JSON件(&工具根.join(crate::常量::扩展根声明))?;
    if 文本字段(&根声明,"路径基准")? != "工作目录" { return Err("索引只认工作目录基准".to_owned()); }
    let 种类表 = 根声明.取成员("种类").and_then(协议值::取数组).ok_or("扩展根缺种类表")?;
    if 请求.路径.is_empty() && let Some(待选编号) = 请求.编号 {
        return 查编号声明(工具根, 种类表, 待选编号);
    }
    let mut 子项表 = BTreeMap::new();
    if 请求.路径.is_empty() {
        for 种类项 in 种类表 {
            let 种类名 = 文本字段(种类项,"种类")?;
            子项表.insert(种类名.to_owned(),目录卡(种类名,种类名,"种类"));
        }
    } else {
        let 种类项 = 种类表.iter().find(|种类项| 种类项.取成员("种类").and_then(协议值::取文本) == Some(请求.路径[0].as_str())).ok_or("没有这个扩展种类")?;
        let 类根 = 工具根.join(文本字段(种类项,"扩展落点")?);
        if 请求.路径.len() == 1 {
            for 目录项 in std::fs::read_dir(&类根).map_err(|错误| format!("读扩展类目录失败：{错误}"))? {
                let 目录项 = 目录项.map_err(|错误| format!("读扩展目录项失败：{错误}"))?;
                if !目录项.file_type().map_err(|错误| format!("读目录类型失败：{错误}"))?.is_dir() { continue; }
                let 包名 = 目录项.file_name().into_string().map_err(|_| "包目录不是合法UTF-8")?;
                if !目录项.path().join("包声明.json").is_file() { return Err(format!("扩展目录缺包声明：{包名}")); }
                子项表.insert(包名.clone(),目录卡(&包名,&format!("{}/{包名}",请求.路径[0]),"包"));
            }
        } else {
            let 包目录 = 类根.join(&请求.路径[1]);
            let 规范根 = 类根.canonicalize().map_err(|错误| format!("扩展根不可解析：{错误}"))?;
            let 规范包 = 包目录.canonicalize().map_err(|错误| format!("包目录不可解析：{错误}"))?;
            if !规范包.starts_with(&规范根) { return Err("包路径越出扩展类根".to_owned()); }
            let _包声明 = 读JSON件(&包目录.join("包声明.json"))?;
            let 族前缀 = &请求.路径[2..];
            let 声明目录 = 包目录.join("能力声明");
            let mut 前缀存在 = 族前缀.is_empty();
            let mut 精确声明 = None;
            for 声明项 in std::fs::read_dir(&声明目录).map_err(|错误| format!("读能力声明目录失败：{错误}"))? {
                let 声明件 = 声明项.map_err(|错误| format!("读能力声明项失败：{错误}"))?.path();
                if 声明件.extension().and_then(|后缀项| 后缀项.to_str()) != Some("json") { continue; }
                let 能力声明 = 读JSON件(&声明件)?;
                let 族路径 = 取族路径(&能力声明)?;
                if !族路径.starts_with(族前缀) { continue; }
                前缀存在 = true;
                let 编号 = 能力声明.取成员("编号").and_then(协议值::取无符号).ok_or("能力声明缺编号")?;
                if 请求.编号.is_some_and(|选择号| u64::from(选择号) == 编号) { 精确声明 = Some(能力声明.clone()); }
                if let Some(下族) = 族路径.get(族前缀.len()) {
                    子项表.insert(format!("族/{下族}"),目录卡(下族,&format!("{}/{下族}",请求.路径.join("/")),"族"));
                } else {
                    let 完整名称 = 文本字段(&能力声明,"名称")?;
                    let 名称 = 完整名称.rsplit('_').next().unwrap_or(完整名称);
                    let 参数数 = 能力声明.取成员("参数表").and_then(协议值::取数组).ok_or("能力声明缺参数表")?.len();
                    let 返回类型 = 能力声明.取成员("返回类型").and_then(协议值::取无符号).ok_or("能力声明缺返回类型")?;
                    子项表.insert(format!("能力/{编号:010}"),协议值::对象值(vec![("节点".to_owned(),协议值::文本值("能力".to_owned())),("编号".to_owned(),协议值::无符号值(编号)),("名称".to_owned(),协议值::文本值(名称.to_owned())),("参数个数".to_owned(),协议值::无符号值(参数数 as u64)),("返回类型".to_owned(),协议值::无符号值(返回类型))]));
                }
            }
            if let Some(选择号) = 请求.编号 { return 精确声明.ok_or_else(|| format!("指定族路径中没有能力：{选择号}")); }
            if !前缀存在 { return Err("没有这个族路径".to_owned()); }
        }
    }
    let 总项数 = 子项表.len();
    let 起点 = 请求.起始.min(总项数);
    let 末位 = 起点.saturating_add(请求.一次条数).min(总项数);
    Ok(协议值::对象值(vec![
        ("路径".to_owned(),协议值::文本值(请求.路径.join("/"))),
        ("总项数".to_owned(),协议值::无符号值(总项数 as u64)),
        ("下页起始".to_owned(),if 末位 < 总项数 { 协议值::无符号值(末位 as u64) } else { 协议值::空值项 }),
        ("子项".to_owned(),协议值::数组值(子项表.into_values().skip(起点).take(末位-起点).collect())),
        ("依据".to_owned(),协议值::文本值("声明候选".to_owned())),
    ]))
}
/// 已知编号只定位对应文件，不读取全库的参数正文。
fn 查编号声明(工具根: &Path, 种类表: &[协议值], 待选编号: u32) -> Result<协议值, String> {
    let mut 命中表 = Vec::new();
    let 文件名 = format!("{待选编号}.json");
    let 底座候选 = 工具根.join("契约声明/能力声明").join(format!("{待选编号:04}.json"));
    if 底座候选.is_file() { 命中表.push(读JSON件(&底座候选)?); }
    for 种类项 in 种类表 {
        let 类根 = 工具根.join(文本字段(种类项,"扩展落点")?);
        for 目录项 in std::fs::read_dir(&类根).map_err(|错误| format!("编号定位读根失败：{错误}"))? {
            let 目录项 = 目录项.map_err(|错误| format!("编号定位读目录失败：{错误}"))?;
            if !目录项.file_type().map_err(|错误| format!("编号定位读类型失败：{错误}"))?.is_dir() { continue; }
            let 声明件 = 目录项.path().join("能力声明").join(&文件名);
            if 声明件.is_file() { 命中表.push(读JSON件(&声明件)?); }
        }
    }
    if 命中表.len() != 1 { return Err(format!("编号{待选编号}命中{}份声明；要求唯一",命中表.len())); }
    let 命中声明 = 命中表.pop().ok_or("编号定位无结果")?;
    if 命中声明.取成员("编号").and_then(协议值::取无符号) != Some(u64::from(待选编号)) { return Err("能力文件名与正文编号不一致".to_owned()); }
    Ok(命中声明)
}

