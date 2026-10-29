use crate::编号与码面::{能力号, 错误码};
use v1_contract::复合值载荷::{复合值, 复合元素, 编码复合值载荷};
fn 解析文本(原文: &str) -> Result<serde_json::Value, u32> {
    if 原文.len() > 65536 {
        return Err(错误码::JSON资源受限);
    }
    let (mut 深度, mut 字符串内, mut 转义中) = (0usize, false, false);
    for 字节值 in 原文.bytes() {
        if 字符串内 {
            if 转义中 {
                转义中 = false;
            } else if 字节值 == b'\\' {
                转义中 = true;
            } else if 字节值 == b'"' {
                字符串内 = false;
            }
        } else {
            match 字节值 {
                b'"' => 字符串内 = true,
                b'[' | b'{' => {
                    深度 += 1;
                    if 深度 > 64 {
                        return Err(错误码::JSON资源受限);
                    }
                }
                b']' | b'}' => 深度 = 深度.saturating_sub(1),
                _ => {}
            }
        }
    }
    crate::JSON树解析::解析JSON树(原文).map_err(|_| 错误码::JSON参数不合法)
}
fn 指针取值<'载荷生命期>(
    解析值: &'载荷生命期 serde_json::Value,
    选择指针: &str,
) -> Result<&'载荷生命期 serde_json::Value, u32> {
    if 选择指针.len() > 4096 {
        return Err(错误码::JSON资源受限);
    }
    if !选择指针.is_empty() && !选择指针.starts_with('/') {
        return Err(错误码::JSON参数不合法);
    }
    let mut 字符迭代 = 选择指针.chars();
    while let Some(字符值) = 字符迭代.next() {
        if 字符值 == '~' && !matches!(字符迭代.next(), Some('0' | '1')) {
            return Err(错误码::JSON参数不合法);
        }
    }
    解析值.pointer(选择指针).ok_or(错误码::JSON路径不存在)
}

fn 取列表(文本内容: &str) -> Result<Vec<serde_json::Value>, u32> {
    match 解析文本(文本内容)? {
        serde_json::Value::Array(列表值) => {
            if 列表值.len() > 10000 {
                return Err(错误码::JSON资源受限);
            }
            Ok(列表值)
        }
        _ => Err(错误码::JSON类型不符),
    }
}

fn 取逻辑文本(文本内容: &str) -> Result<bool, u32> {
    match 文本内容.trim() {
        "真" | "true" => Ok(true),
        "假" | "false" => Ok(false),
        _ => Err(错误码::JSON参数不合法),
    }
}

fn 单项命中(条目: &serde_json::Value, 字段名: &str, 直接匹配: bool, 期望值: &serde_json::Value) -> bool {
    if 直接匹配 || 字段名.is_empty() {
        条目 == 期望值
    } else {
        条目.get(字段名).is_some_and(|字段值| 字段值 == 期望值)
    }
}


fn 值序号(候选值: &serde_json::Value) -> u8 {
    match 候选值 {
        serde_json::Value::Null => 0,
        serde_json::Value::Bool(_) => 1,
        serde_json::Value::Number(_) => 2,
        serde_json::Value::String(_) => 3,
        serde_json::Value::Array(_) => 4,
        serde_json::Value::Object(_) => 5,
    }
}

fn 比较值(左项: &serde_json::Value, 右项: &serde_json::Value) -> std::cmp::Ordering {
    let (左序, 右序) = (值序号(左项), 值序号(右项));
    if 左序 != 右序 {
        return 左序.cmp(&右序);
    }
    match (左项, 右项) {
        (serde_json::Value::Number(左数), serde_json::Value::Number(右数)) => {
            左数.as_f64().unwrap_or(0.0).total_cmp(&右数.as_f64().unwrap_or(0.0))
        }
        (serde_json::Value::String(左文), serde_json::Value::String(右文)) => 左文.cmp(右文),
        (serde_json::Value::Bool(左逻), serde_json::Value::Bool(右逻)) => 左逻.cmp(右逻),
        _ => std::cmp::Ordering::Equal,
    }
}

fn 取比较键<'a>(条目: &'a serde_json::Value, 字段名: &str, 直接匹配: bool) -> &'a serde_json::Value {
    if 直接匹配 || 字段名.is_empty() {
        条目
    } else {
        条目.get(字段名).unwrap_or(&serde_json::Value::Null)
    }
}


fn 标量文本(候选值: &serde_json::Value) -> String {
    match 候选值 {
        serde_json::Value::String(内文) => 内文.clone(),
        serde_json::Value::Null => String::new(),
        serde_json::Value::Bool(逻辑值) => {
            if *逻辑值 {
                "真".to_owned()
            } else {
                "假".to_owned()
            }
        }
        其他值 => 其他值.to_string(),
    }
}

fn 拼接路径(路径前缀: &str, 分隔符: &str, 末段: &str) -> String {
    if 路径前缀.is_empty() {
        末段.to_owned()
    } else {
        format!("{路径前缀}{分隔符}{末段}")
    }
}

fn 展平字典递归(
    候选值: &serde_json::Value,
    路径前缀: &str,
    分隔符: &str,
    剩余深度: usize,
    收录: &mut serde_json::Map<String, serde_json::Value>,
) {
    match 候选值 {
        serde_json::Value::Object(成员表) if 剩余深度 > 1 => {
            for (字段名, 字段值) in 成员表 {
                展平字典递归(字段值, &拼接路径(路径前缀, 分隔符, 字段名), 分隔符, 剩余深度 - 1, 收录);
            }
        }
        其他值 => {
            收录.insert(路径前缀.to_owned(), 其他值.clone());
        }
    }
}

struct 展平上下文<'a> {
    分隔符: &'a str,
    索引格式: &'a str,
    超深标记: &'a str,
    根路径: &'a str,
    最大条目数: usize,
    条目表: Vec<serde_json::Value>,
    已截断: bool,
}

fn 渲染索引(格式: &str, 序号: usize) -> String {
    格式.replace("{索引}", &序号.to_string())
}

fn 展平条目递归(候选值: &serde_json::Value, 路径: &str, 剩余深度: usize, 上下文: &mut 展平上下文<'_>) {
    if 上下文.条目表.len() >= 上下文.最大条目数 {
        上下文.已截断 = true;
        return;
    }
    match 候选值 {
        serde_json::Value::Object(成员表) if 剩余深度 > 0 => {
            if 成员表.is_empty() {
                上下文.条目表.push(serde_json::json!({
                    "路径": if 路径.is_empty() { 上下文.根路径 } else { 路径 },
                    "值": serde_json::Value::Object(成员表.clone()),
                    "超深": false,
                }));
                return;
            }
            for (字段名, 字段值) in 成员表 {
                展平条目递归(字段值, &拼接路径(路径, 上下文.分隔符, 字段名), 剩余深度 - 1, 上下文);
            }
        }
        serde_json::Value::Array(列表值) if 剩余深度 > 0 => {
            if 列表值.is_empty() {
                上下文.条目表.push(serde_json::json!({
                    "路径": if 路径.is_empty() { 上下文.根路径 } else { 路径 },
                    "值": serde_json::Value::Array(Vec::new()),
                    "超深": false,
                }));
                return;
            }
            for (序号, 元素值) in 列表值.iter().enumerate() {
                let 索引段 = 渲染索引(上下文.索引格式, 序号);
                展平条目递归(元素值, &拼接路径(路径, 上下文.分隔符, &索引段), 剩余深度 - 1, 上下文);
            }
        }
        serde_json::Value::Object(_) | serde_json::Value::Array(_) => {
            上下文.条目表.push(serde_json::json!({
                "路径": if 路径.is_empty() { 上下文.根路径 } else { 路径 },
                "值": 上下文.超深标记,
                "超深": true,
            }));
        }
        标量值 => {
            上下文.条目表.push(serde_json::json!({
                "路径": if 路径.is_empty() { 上下文.根路径 } else { 路径 },
                "值": 标量值.clone(),
                "超深": false,
            }));
        }
    }
}

pub fn 执行文本操作(编号: u32, 文本参数表: &[&str]) -> Result<(u32, Vec<u8>), u32> {
    let 解析值 = 解析文本(文本参数表[0])?;
    if 编号 == 能力号::提取摘要 {
        let (类型名称, 成员数量) = match &解析值 {
            serde_json::Value::Null => ("空值", 0),
            serde_json::Value::Bool(_) => ("逻辑", 0),
            serde_json::Value::Number(_) => ("数值", 0),
            serde_json::Value::String(_) => ("文本", 0),
            serde_json::Value::Array(列表值) => ("列表", 列表值.len()),
            serde_json::Value::Object(成员表) => ("对象", 成员表.len()),
        };
        let 元素表 = vec![
            复合元素 {
                名称: "类型名称".into(),
                值: 复合值::文本载荷(类型名称.into()),
            },
            复合元素 {
                名称: "成员数量".into(),
                值: 复合值::整数值(成员数量 as i64),
            },
            复合元素 {
                名称: "规范文本".into(),
                值: 复合值::文本载荷(解析值.to_string()),
            },
        ];
        return Ok((
            103,
            编码复合值载荷(103, &元素表).map_err(|_| 错误码::JSON资源受限)?,
        ));
    }
    let 返回文本 = match 编号 {
        能力号::规范化JSON => 解析值.to_string(),
        能力号::按指针取值 => 指针取值(&解析值, 文本参数表[1])?.to_string(),
        能力号::按指针取文本 => 指针取值(&解析值, 文本参数表[1])?
            .as_str()
            .ok_or(错误码::JSON类型不符)?
            .to_owned(),
        能力号::按字段查找 => {
            let 列表值 = 取列表(文本参数表[0])?;
            let 期望值 = 解析文本(文本参数表[2])?;
            let 直接匹配 = 取逻辑文本(文本参数表[3])?;
            match 列表值.iter().find(|条目| 单项命中(条目, 文本参数表[1], 直接匹配, &期望值)) {
                Some(命中项) => 命中项.to_string(),
                None => String::new(),
            }
        }
        能力号::过滤 => {
            let 列表值 = 取列表(文本参数表[0])?;
            let 期望值 = 解析文本(文本参数表[2])?;
            let 直接匹配 = 取逻辑文本(文本参数表[3])?;
            let 命中表: Vec<serde_json::Value> = 列表值
                .into_iter()
                .filter(|条目| 单项命中(条目, 文本参数表[1], 直接匹配, &期望值))
                .collect();
            serde_json::Value::Array(命中表).to_string()
        }
        能力号::映射转换 => {
            let 列表值 = 取列表(文本参数表[0])?;
            let 映射对象 = match 解析文本(文本参数表[1])? {
                serde_json::Value::Object(字段映射) => 字段映射,
                _ => return Err(错误码::JSON类型不符),
            };
            let mut 结果表 = Vec::with_capacity(列表值.len());
            for 条目 in 列表值 {
                match 条目 {
                    serde_json::Value::Object(原对象) => {
                        let mut 新对象 = serde_json::Map::new();
                        for (字段名, 字段值) in 原对象 {
                            let 新字段名 = 映射对象
                                .get(&字段名)
                                .and_then(|映射值| 映射值.as_str())
                                .map(str::to_owned)
                                .unwrap_or_else(|| 字段名.clone());
                            新对象.insert(新字段名, 字段值);
                        }
                        结果表.push(serde_json::Value::Object(新对象));
                    }
                    其他值 => 结果表.push(其他值),
                }
            }
            serde_json::Value::Array(结果表).to_string()
        }
        能力号::按字段排序 => {
            let mut 列表值 = 取列表(文本参数表[0])?;
            let 升序 = 取逻辑文本(文本参数表[2])?;
            let 直接匹配 = 取逻辑文本(文本参数表[3])?;
            let 字段名 = 文本参数表[1];
            列表值.sort_by(|左项, 右项| {
                比较值(取比较键(左项, 字段名, 直接匹配), 取比较键(右项, 字段名, 直接匹配))
            });
            if !升序 {
                列表值.reverse();
            }
            serde_json::Value::Array(列表值).to_string()
        }
        能力号::列表添加 => {
            let mut 列表值 = 取列表(文本参数表[0])?;
            if 列表值.len() >= 10000 {
                return Err(错误码::JSON资源受限);
            }
            列表值.push(解析文本(文本参数表[1])?);
            serde_json::Value::Array(列表值).to_string()
        }
        能力号::列表移除 => {
            let mut 列表值 = 取列表(文本参数表[0])?;
            let 目标值 = 解析文本(文本参数表[1])?;
            if let Some(命中位置) = 列表值.iter().position(|条目| 条目 == &目标值) {
                列表值.remove(命中位置);
            }
            serde_json::Value::Array(列表值).to_string()
        }
        能力号::展平字典 => {
            let 数据值 = 解析文本(文本参数表[0])?;
            let 分隔符 = 文本参数表[1];
            let 保留扁平键 = 取逻辑文本(文本参数表[2])?;
            let 最大深度: usize = 文本参数表[3]
                .trim()
                .parse()
                .map_err(|_| 错误码::JSON参数不合法)?;
            if 最大深度 == 0 || 最大深度 > 64 {
                return Err(错误码::JSON参数不合法);
            }
            let mut 收录 = serde_json::Map::new();
            match &数据值 {
                serde_json::Value::Object(成员表) => {
                    for (字段名, 字段值) in 成员表 {
                        let 是标量 = !字段值.is_object();
                        if 是标量 && !保留扁平键 {
                            continue;
                        }
                        展平字典递归(字段值, 字段名, 分隔符, 最大深度, &mut 收录);
                    }
                }
                其他值 => {
                    if 保留扁平键 {
                        收录.insert(String::new(), 其他值.clone());
                    }
                }
            }
            serde_json::Value::Object(收录).to_string()
        }
        能力号::展平结构条目 => {
            let 数据值 = 解析文本(文本参数表[0])?;
            let 最大深度: usize = 文本参数表[3]
                .trim()
                .parse()
                .map_err(|_| 错误码::JSON参数不合法)?;
            let 最大条目数: usize = 文本参数表[4]
                .trim()
                .parse()
                .map_err(|_| 错误码::JSON参数不合法)?;
            if 最大深度 == 0 || 最大深度 > 64 || 最大条目数 == 0 || 最大条目数 > 100_000 {
                return Err(错误码::JSON参数不合法);
            }
            let mut 上下文 = 展平上下文 {
                分隔符: 文本参数表[1],
                索引格式: 文本参数表[2],
                超深标记: 文本参数表[5],
                根路径: 文本参数表[6],
                最大条目数,
                条目表: Vec::new(),
                已截断: false,
            };
            展平条目递归(&数据值, "", 最大深度, &mut 上下文);
            serde_json::json!({
                "条目列表": 上下文.条目表,
                "总条目数": 上下文.条目表.len(),
                "已截断": 上下文.已截断,
            })
            .to_string()
        }
        能力号::规范化条目指纹 => {
            let 条目表 = 取列表(文本参数表[0])?;
            let 字段顺序: Vec<String> = match 解析文本(文本参数表[1])? {
                serde_json::Value::Array(字段值表) => 字段值表
                    .iter()
                    .map(|字段值| 字段值.as_str().unwrap_or_default().to_owned())
                    .collect(),
                _ => return Err(错误码::JSON类型不符),
            };
            if 字段顺序.is_empty() || 字段顺序.len() > 64 {
                return Err(错误码::JSON参数不合法);
            }
            let 条目分隔符 = 文本参数表[2];
            let 字段分隔符 = 文本参数表[3];
            let mut 行表: Vec<String> = Vec::with_capacity(条目表.len());
            for 条目项 in &条目表 {
                let mut 字段表: Vec<String> = Vec::with_capacity(字段顺序.len());
                for 字段名 in &字段顺序 {
                    let 字段值 = 条目项.get(字段名).unwrap_or(&serde_json::Value::Null);
                    字段表.push(标量文本(字段值));
                }
                行表.push(字段表.join(字段分隔符));
            }
            let 规范化文本 = 行表.join(条目分隔符);
            if 规范化文本.len() > 65536 {
                return Err(错误码::JSON资源受限);
            }
            use sha2 as 摘要算法;
            use sha2::Digest as 摘要接口;
            let mut 摘要器 = 摘要算法::Sha256::new();
            摘要接口::update(&mut 摘要器, 规范化文本.as_bytes());
            let 十六进制 = 摘要接口::finalize(摘要器)
                .iter()
                .map(|字节| format!("{字节:02x}"))
                .collect::<String>();
            serde_json::json!({ "指纹": 十六进制 }).to_string()
        }
        _ => return Err(错误码::JSON参数不合法),
    };
    if 返回文本.len() > 65536 {
        return Err(错误码::JSON资源受限);
    }
    Ok((4, 返回文本.into_bytes()))
}
#[cfg(test)]
mod 验证样本 {
    use super::*;
    #[test]
    fn 保留引擎私有同名对象键() {
        let 原文 = r#"{"$serde_json::private::Number":"123"}"#;
        assert_eq!(执行文本操作(5201, &[原文]).unwrap().1, 原文.as_bytes());
    }
    #[test]
    fn 大数空值和路径不混淆() {
        let 原文 = r#"{"金额":123456789012345678901234567890,"空":null,"假":false,"零":0,"空文":"","a/b":{"~":"中文\u0000"}}"#;
        for (路径, 期望) in [
            ("/金额", "123456789012345678901234567890"),
            ("/空", "null"),
            ("/假", "false"),
            ("/零", "0"),
            ("/空文", "\"\""),
        ] {
            assert_eq!(
                执行文本操作(5202, &[原文, 路径]).unwrap().1,
                期望.as_bytes()
            );
        }
        assert_eq!(
            执行文本操作(5203, &[原文, "/a~1b/~0"]).unwrap().1,
            "中文\0".as_bytes()
        );
        assert_eq!(执行文本操作(5202, &[原文, "/不存在"]), Err(5202));
        assert_eq!(执行文本操作(5203, &[原文, "/零"]), Err(5203));
        assert_eq!(执行文本操作(5202, &[原文, "/~2"]), Err(5201));
        assert_eq!(执行文本操作(5201, &["NaN"]), Err(5201));
        assert_eq!(
            执行文本操作(5201, &[&("[".repeat(65) + &"]".repeat(65))]),
            Err(5204)
        );
    }
}
