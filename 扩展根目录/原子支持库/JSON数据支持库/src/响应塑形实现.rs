//! 响应塑形：裁剪响应、压缩描述字段、提取带前缀 JSON。
//!
//! 三条能力都只做 JSON 文本的纯内存变换，不访问外部系统；输入上界由
//! `执行函数面::输入上界` 按编号分派，其余能力保持原上限不变。

use crate::编号与码面::错误码;

use crate::业务实现::解析文本上限;

pub fn 执行裁剪响应(文本参数表: &[&str]) -> Result<(u32, Vec<u8>), u32> {
    if 文本参数表.len() != 7 {
        return Err(错误码::JSON参数不合法);
    }
    let 载荷值 = 解析文本上限(文本参数表[0], 4194304)?;
    let 最大条目数 = 解析整数文本(文本参数表[2])?;
    let 最大字节数 = 解析整数文本(文本参数表[3])?;
    if 最大条目数.is_some_and(|条目值| 条目值 < 0)
        || 最大字节数.is_some_and(|条目值| 条目值 < 0)
    {
        return Err(错误码::JSON参数不合法);
    }
    let 信封键 = match 解析文本上限(文本参数表[4], 65536)? {
        serde_json::Value::Array(键表) => {
            let mut 键集合: Vec<String> = Vec::with_capacity(键表.len());
            for 键项 in 键表 {
                match 键项 {
                    serde_json::Value::String(键文本) => 键集合.push(键文本),
                    _ => return Err(错误码::JSON类型不符),
                }
            }
            键集合
        }
        _ => return Err(错误码::JSON类型不符),
    };
    let 数据键 = if 文本参数表[6].is_empty() {
        "data".to_owned()
    } else {
        文本参数表[6].to_owned()
    };
    let 元数据键 = 文本参数表[5].trim().to_owned();
    let mut 省略计数: std::collections::BTreeMap<String, i64> =
        std::collections::BTreeMap::new();
    let mut 警告表: Vec<String> = Vec::new();
    let mut 选中路径值: Option<String> = None;
    let mut 塑形值 = 载荷值.clone();
    let 选择路径文本 = 文本参数表[1].trim().to_owned();
    if !选择路径文本.is_empty() {
        match 选中路径(&载荷值, &选择路径文本) {
            Ok((解析路径, 选中值)) => {
                选中路径值 = Some(解析路径);
                塑形值 = 已选中载荷(&载荷值, &选中值, &信封键, &数据键);
            }
            Err(警告文本) => 警告表.push(警告文本),
        }
    }
    if let Some(条目上限) = 最大条目数 {
        塑形值 = 裁剪列表(
            &塑形值,
            条目上限 as usize,
            &mut 省略计数,
            选中路径值.as_deref(),
            "",
            &数据键,
        );
    }
    if !元数据键.is_empty()
        && let serde_json::Value::Object(成员表) = &mut 塑形值
    {
            let mut 元数据成员 = serde_json::Map::new();
            元数据成员.insert(
                "truncated".to_owned(),
                serde_json::Value::Bool(!省略计数.is_empty()),
            );
            元数据成员.insert(
                "selected_path".to_owned(),
                选中路径值
                    .clone()
                    .map(serde_json::Value::String)
                    .unwrap_or(serde_json::Value::Null),
            );
            元数据成员.insert(
                "omitted_counts".to_owned(),
                serde_json::to_value(&省略计数).map_err(|_| 错误码::JSON参数不合法)?,
            );
            if !警告表.is_empty() {
                let 警告值表: Vec<serde_json::Value> = 警告表
                    .iter()
                    .map(|警告文本| serde_json::Value::String(警告文本.clone()))
                    .collect();
                元数据成员.insert("warnings".to_owned(), serde_json::Value::Array(警告值表));
            }
            成员表.insert(元数据键.clone(), serde_json::Value::Object(元数据成员));
    }
    if let Some(字节上限) = 最大字节数 {
        裁剪到最大字节(&mut 塑形值, 字节上限 as usize, &数据键, &元数据键);
    }
    let 返回JSON = 塑形值.to_string();
    if 返回JSON.len() > 4194304 {
        return Err(错误码::JSON资源受限);
    }
    Ok((4, 返回JSON.into_bytes()))
}

pub fn 执行压缩描述字段(文本参数表: &[&str]) -> Result<(u32, Vec<u8>), u32> {
    if 文本参数表.len() != 2 {
        return Err(错误码::JSON参数不合法);
    }
    let 数据值 = 解析文本上限(文本参数表[0], 4194304)?;
    let 返回JSON = 压缩描述字段值(&数据值, 文本参数表[1]).to_string();
    if 返回JSON.len() > 4194304 {
        return Err(错误码::JSON资源受限);
    }
    Ok((4, 返回JSON.into_bytes()))
}

pub fn 执行提取带前缀JSON(文本参数表: &[&str]) -> Result<(u32, Vec<u8>), u32> {
    if 文本参数表.len() != 2 {
        return Err(错误码::JSON参数不合法);
    }
    if 文本参数表[1].len() > 4096 {
        return Err(错误码::JSON资源受限);
    }
    let 返回JSON = 提取前缀JSON值(文本参数表[0], 文本参数表[1].trim()).to_string();
    Ok((4, 返回JSON.into_bytes()))
}


fn 解析整数文本(原文: &str) -> Result<Option<i64>, u32> {
    let 去空 = 原文.trim();
    if 去空.is_empty() {
        return Ok(None);
    }
    去空.parse::<i64>().map(Some).map_err(|_| 错误码::JSON参数不合法)
}

fn 连接路径(基路径: &str, 成员键: &str) -> String {
    if 基路径.is_empty() {
        成员键.to_owned()
    } else {
        format!("{基路径}.{成员键}")
    }
}

fn 解析JSON大小(条目值: &serde_json::Value) -> usize {
    serde_json::to_string_pretty(条目值).map(|文本输出| 文本输出.len()).unwrap_or(0)
}

fn 按字符截断(文本值: &str, 字符数: usize) -> String {
    文本值.chars().take(字符数).collect()
}

fn 类型名称文本(条目值: &serde_json::Value) -> &'static str {
    match 条目值 {
        serde_json::Value::Null => "空值",
        serde_json::Value::Bool(_) => "逻辑",
        serde_json::Value::Number(_) => "数值",
        serde_json::Value::String(_) => "文本",
        serde_json::Value::Array(_) => "列表",
        serde_json::Value::Object(_) => "对象",
    }
}

fn 选中路径(
    载荷: &serde_json::Value,
    选择路径: &str,
) -> Result<(String, serde_json::Value), String> {
    let 段表: Vec<&str> = 选择路径.split('.').filter(|单段| !单段.is_empty()).collect();
    if 段表.is_empty() {
        return Err("选择路径为空".to_owned());
    }
    let mut 当前位置 = 载荷;
    let mut 已走段表: Vec<&str> = Vec::with_capacity(段表.len());
    for 路径段 in 段表.iter().copied() {
        已走段表.push(路径段);
        let 已走 = 已走段表.join(".");
        match 当前位置 {
            serde_json::Value::Object(成员表) => {
                当前位置 = 成员表
                    .get(路径段)
                    .ok_or_else(|| format!("选择路径在 {已走} 处不存在"))?;
            }
            serde_json::Value::Array(列表值) => {
                let 索引值 = 路径段
                    .parse::<usize>()
                    .map_err(|_| format!("选择路径在 {已走} 处需要列表索引"))?;
                当前位置 = 列表值
                    .get(索引值)
                    .ok_or_else(|| format!("选择路径在 {已走} 处索引越界"))?;
            }
            _ => return Err(format!("选择路径在 {已走} 处无法继续下钻标量")),
        }
    }
    Ok((段表.join("."), 当前位置.clone()))
}

fn 已选中载荷(
    载荷: &serde_json::Value,
    选中值: &serde_json::Value,
    信封键: &[String],
    数据键: &str,
) -> serde_json::Value {
    let mut 新载荷 = serde_json::Map::new();
    if let serde_json::Value::Object(原成员) = 载荷 {
        for 成员键 in 信封键 {
            if let Some(条目值) = 原成员.get(成员键) {
                新载荷.insert(成员键.clone(), 条目值.clone());
            }
        }
        if let Some(serde_json::Value::Object(信封成员)) = 原成员.get(数据键) {
            if let Some(上游成功) = 信封成员.get("success") {
                新载荷.insert("upstream_success".to_owned(), 上游成功.clone());
            }
            if let Some(上游错误) = 信封成员.get("错误") {
                新载荷.insert("upstream_error".to_owned(), 上游错误.clone());
            }
        }
    }
    新载荷.insert(数据键.to_owned(), 选中值.clone());
    serde_json::Value::Object(新载荷)
}

fn 裁剪列表(
    条目值: &serde_json::Value,
    最大条目数: usize,
    省略计数: &mut std::collections::BTreeMap<String, i64>,
    选中路径值: Option<&str>,
    路径: &str,
    数据键: &str,
) -> serde_json::Value {
    match 条目值 {
        serde_json::Value::Array(列表值) => {
            let 省略数 = 列表值.len().saturating_sub(最大条目数);
            if 省略数 > 0 {
                let 计数键 = if 路径 == 数据键 && 选中路径值.is_some() {
                    选中路径值.unwrap_or("$").to_owned()
                } else if 路径.is_empty() {
                    "$".to_owned()
                } else {
                    路径.to_owned()
                };
                省略计数.insert(计数键, 省略数 as i64);
            }
            let mut 保留项 = Vec::with_capacity(列表值.len().min(最大条目数));
            for (索引值, 条目项) in 列表值.iter().take(最大条目数).enumerate() {
                let 子路径 = 连接路径(路径, &索引值.to_string());
                保留项.push(裁剪列表(
                    条目项,
                    最大条目数,
                    &mut *省略计数,
                    选中路径值,
                    &子路径,
                    数据键,
                ));
            }
            serde_json::Value::Array(保留项)
        }
        serde_json::Value::Object(成员表) => {
            let mut 新成员 = serde_json::Map::new();
            for (成员键, 条目项) in 成员表 {
                let 子路径 = 连接路径(路径, 成员键);
                新成员.insert(
                    成员键.clone(),
                    裁剪列表(条目项, 最大条目数, &mut *省略计数, 选中路径值, &子路径, 数据键),
                );
            }
            serde_json::Value::Object(新成员)
        }
        其他值 => 其他值.clone(),
    }
}

fn 摘要值(条目值: &serde_json::Value, 预算: usize) -> serde_json::Value {
    use serde_json::json;
    match 条目值 {
        serde_json::Value::String(文本值) => json!({
            "_truncated": true,
            "类型": "文本",
            "bytes_before": 解析JSON大小(条目值),
            "预览": 按字符截断(文本值, 预算 / 4),
        }),
        serde_json::Value::Array(列表值) => json!({
            "_truncated": true,
            "类型": "列表",
            "original_length": 列表值.len(),
            "预览": 列表值.iter().take(3).map(|条目项| 摘要值(条目项, 预算 / 2)).collect::<Vec<_>>(),
        }),
        serde_json::Value::Object(成员表) => {
            let mut 预览 = serde_json::Map::new();
            for (成员键, 条目项) in 成员表.iter().take(8) {
                if 条目项.is_null() || 条目项.is_boolean() || 条目项.is_number() || 条目项.is_string() {
                    预览.insert(成员键.clone(), 条目项.clone());
                } else {
                    预览.insert(成员键.clone(), 摘要值(条目项, 预算 / 2));
                }
            }
            json!({
                "_truncated": true,
                "类型": "对象",
                "keys": 成员表.keys().take(20).collect::<Vec<_>>(),
                "预览": 预览,
                "bytes_before": 解析JSON大小(条目值),
            })
        }
        其他值 => 其他值.clone(),
    }
}

fn 裁剪到最大字节(
    载荷: &mut serde_json::Value,
    字节上限: usize,
    数据键: &str,
    元数据键: &str,
) {
    if 解析JSON大小(载荷) <= 字节上限 {
        return;
    }
    let 原大小 = 解析JSON大小(载荷);
    let 原数据 = 载荷
        .get(数据键)
        .cloned()
        .unwrap_or(serde_json::Value::Null);
    match 载荷 {
        serde_json::Value::Object(成员表) => {
            let 元数据项 = 成员表
                .entry(元数据键.to_owned())
                .or_insert_with(|| serde_json::Value::Object(serde_json::Map::new()));
            if let serde_json::Value::Object(元数据成员) = 元数据项 {
                元数据成员.insert("truncated".to_owned(), serde_json::Value::Bool(true));
                元数据成员.insert(
                    "max_bytes".to_owned(),
                    serde_json::Value::Number(字节上限.into()),
                );
                元数据成员.insert(
                    "bytes_before".to_owned(),
                    serde_json::Value::Number(原大小.into()),
                );
            }
        }
        _ => return,
    }
    if let serde_json::Value::Object(成员表) = 载荷 {
        成员表.insert(数据键.to_owned(), 摘要值(&原数据, 字节上限));
    }
    if 解析JSON大小(载荷) <= 字节上限 {
        return;
    }
    let mut 兜底成员 = serde_json::Map::new();
    兜底成员.insert("_truncated".to_owned(), serde_json::Value::Bool(true));
    兜底成员.insert(
        "类型".to_owned(),
        serde_json::Value::String(类型名称文本(&原数据).to_owned()),
    );
    兜底成员.insert(
        "bytes_before".to_owned(),
        serde_json::Value::Number(解析JSON大小(&原数据).into()),
    );
    let 兜底值 = serde_json::Value::Object(兜底成员);
    if let serde_json::Value::Object(成员表) = 载荷 {
        成员表.insert(数据键.to_owned(), 兜底值);
    }
    if 解析JSON大小(载荷) <= 字节上限 {
        return;
    }
    if let serde_json::Value::Object(成员表) = 载荷
        && let Some(serde_json::Value::Object(元数据成员)) = 成员表.get_mut(元数据键)
    {
        let 警告项 = serde_json::Value::String("最小响应已超出字节上限".to_owned());
        match 元数据成员.get_mut("warnings") {
            Some(serde_json::Value::Array(警告表)) => 警告表.push(警告项),
            _ => {
                元数据成员.insert(
                    "warnings".to_owned(),
                    serde_json::Value::Array(vec![警告项]),
                );
            }
        }
    }
}

fn 压缩描述字段值(条目值: &serde_json::Value, 字段名: &str) -> serde_json::Value {
    match 条目值 {
        serde_json::Value::Array(列表值) => {
            let 折叠项: Vec<serde_json::Value> = 列表值
                .iter()
                .map(|条目项| 压缩描述字段值(条目项, 字段名))
                .collect();
            serde_json::Value::Array(折叠项)
        }
        serde_json::Value::Object(成员表) => {
            let mut 新成员 = serde_json::Map::new();
            for (成员键, 条目项) in 成员表 {
                let 压缩后值 = if 成员键 == 字段名 && 条目项.is_string() {
                    serde_json::Value::String(
                        条目项.as_str()
                            .unwrap_or("")
                            .split_whitespace()
                            .collect::<Vec<_>>()
                            .join(" "),
                    )
                } else {
                    压缩描述字段值(条目项, 字段名)
                };
                新成员.insert(成员键.clone(), 压缩后值);
            }
            serde_json::Value::Object(新成员)
        }
        其他值 => 其他值.clone(),
    }
}

fn 提取前缀JSON值(文本值: &str, 行首前缀: &str) -> serde_json::Value {
    use serde_json::json;
    for 单行 in 文本值.lines().rev() {
        let 行文本 = 单行.trim();
        if !行文本.starts_with(行首前缀) {
            continue;
        }
        let 剩余文本 = 行文本[行首前缀.len()..].trim();
        return match serde_json::from_str::<serde_json::Value>(剩余文本) {
            Ok(解析值 @ serde_json::Value::Object(_)) => {
                json!({ "找到": true, "数据": 解析值 })
            }
            _ => json!({ "找到": false }),
        };
    }
    json!({ "找到": false })
}

#[cfg(test)]
mod 塑形验证样本 {
    use super::*;

    fn 取结果(输出槽: Result<(u32, Vec<u8>), u32>) -> serde_json::Value {
        let (标签, 字节) = 输出槽.unwrap();
        assert_eq!(标签, 4);
        serde_json::from_slice(&字节).unwrap()
    }

    #[test]
    fn 裁剪响应按条目数裁列表并记录省略() {
        let 测试载荷 = r#"{"status_code":200,"data":{"items":[1,2,3,4,5]}}"#;
        let 测试输出 = 执行裁剪响应(&[测试载荷, "", "2", "", r#"["status_code"]"#, "meta", "data"]);
        let 解析结果 = 取结果(测试输出);
        assert_eq!(解析结果["data"]["items"], serde_json::json!([1, 2]));
        assert_eq!(解析结果["meta"]["truncated"], serde_json::json!(true));
        assert_eq!(解析结果["meta"]["omitted_counts"]["data.items"], serde_json::json!(3));
    }

    #[test]
    fn 裁剪响应按路径选中并复制信封键() {
        let 测试载荷 = r#"{"status_code":200,"error":"无","data":{"success":true,"错误":{"码":1},"内容":[1,2]}}"#;
        let 测试输出 = 执行裁剪响应(&[测试载荷, "data.内容", "", "", r#"["status_code","error"]"#, "meta", "data"]);
        let 解析结果 = 取结果(测试输出);
        assert_eq!(解析结果["data"], serde_json::json!([1, 2]));
        assert_eq!(解析结果["status_code"], serde_json::json!(200));
        assert_eq!(解析结果["error"], serde_json::json!("无"));
        assert_eq!(解析结果["upstream_success"], serde_json::json!(true));
        assert_eq!(解析结果["meta"]["selected_path"], serde_json::json!("data.内容"));
    }

    #[test]
    fn 裁剪响应负数条目被拒() {
        let 测试载荷 = r#"{"data":[1]}"#;
        assert_eq!(
            执行裁剪响应(&[测试载荷, "", "-1", "", "[]", "meta", "data"]).unwrap_err(),
            错误码::JSON参数不合法
        );
        assert_eq!(
            执行裁剪响应(&[测试载荷, "data.不存在", "", "", "[]", "meta", "data"])
                .map(|(标签, 字节)| 取结果(Ok((标签, 字节))))
                .map(|解析结果| 解析结果["meta"]["warnings"].clone()),
            Ok(serde_json::json!(["选择路径在 data.不存在 处需要列表索引"]))
        );
    }

    #[test]
    fn 裁剪响应字节预算换摘要() {
        let 大文本 = "字".repeat(4000);
        let 测试载荷 = format!(r#"{{"data":{{"正文":"{大文本}"}}}}"#);
        let 测试输出 = 执行裁剪响应(&[&测试载荷, "", "", "1000", "[]", "meta", "data"]);
        let 解析结果 = 取结果(测试输出);
        assert_eq!(解析结果["meta"]["truncated"], serde_json::json!(true));
        assert_eq!(解析结果["meta"]["max_bytes"], serde_json::json!(1000));
        assert_eq!(解析结果["data"]["_truncated"], serde_json::json!(true));
        assert!(serde_json::to_string(&解析结果).unwrap().len() < 4000);
    }

    #[test]
    fn 压缩描述字段折叠空白() {
        let 测试载荷 = "{\"description\":\"多   空白\\n换行\",\"嵌套\":[{\"description\":\"第一段   第二段\"}],\"其他\":\"保留   原样\"}";
        let 解析结果 = 取结果(执行压缩描述字段(&[测试载荷, "description"]));
        assert_eq!(解析结果["description"], serde_json::json!("多 空白 换行"));
        assert_eq!(解析结果["嵌套"][0]["description"], serde_json::json!("第一段 第二段"));
        assert_eq!(解析结果["其他"], serde_json::json!("保留   原样"));
    }

    #[test]
    fn 提取带前缀JSON从末尾取() {
        let 测试载荷 = "前置\n摘要A: {\"verdict\":\"FAIL\"}\n摘要A: {\"verdict\":\"PASS\"}\n";
        let 解析结果 = 取结果(执行提取带前缀JSON(&[测试载荷, "摘要A:"]));
        assert_eq!(解析结果["找到"], serde_json::json!(true));
        assert_eq!(解析结果["数据"]["verdict"], serde_json::json!("PASS"));
    }

    #[test]
    fn 提取带前缀JSON解析失败视为未找到() {
        let 测试载荷 = "摘要A: {\"verdict\":\"PASS\"}\n摘要A: {坏json}\n";
        let 解析结果 = 取结果(执行提取带前缀JSON(&[测试载荷, "摘要A:"]));
        assert_eq!(解析结果["找到"], serde_json::json!(false));
        let 非对象 = 取结果(执行提取带前缀JSON(&["摘要A: [1,2]\n", "摘要A:"]));
        assert_eq!(非对象["找到"], serde_json::json!(false));
        let 无命中 = 取结果(执行提取带前缀JSON(&["无关文本\n", "摘要A:"]));
        assert_eq!(无命中["找到"], serde_json::json!(false));
    }
}
