//! 裁剪与摘要：解析整数入参、点分路径选中、信封键复制、按条目数裁剪、按字节预算换摘要。

use crate::编号与码面::错误码;

pub(super) fn 解析整数文本(原文: &str) -> Result<Option<i64>, u32> {
    let 去空 = 原文.trim();
    if 去空.is_empty() {
        return Ok(None);
    }
    去空.parse::<i64>().map(Some).map_err(|_| 错误码::JSON参数不合法)
}

pub(super) fn 连接路径(基路径: &str, 成员键: &str) -> String {
    if 基路径.is_empty() {
        成员键.to_owned()
    } else {
        format!("{基路径}.{成员键}")
    }
}

pub(super) fn 解析JSON大小(条目值: &serde_json::Value) -> usize {
    serde_json::to_string_pretty(条目值).map(|文本输出| 文本输出.len()).unwrap_or(0)
}

pub(super) fn 按字符截断(文本值: &str, 字符数: usize) -> String {
    文本值.chars().take(字符数).collect()
}

pub(super) fn 类型名称文本(条目值: &serde_json::Value) -> &'static str {
    match 条目值 {
        serde_json::Value::Null => "空值",
        serde_json::Value::Bool(_) => "逻辑",
        serde_json::Value::Number(_) => "数值",
        serde_json::Value::String(_) => "文本",
        serde_json::Value::Array(_) => "列表",
        serde_json::Value::Object(_) => "对象",
    }
}

pub(super) fn 选中路径(
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

pub(super) fn 已选中载荷(
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

pub(super) fn 裁剪列表(
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

pub(super) fn 摘要值(条目值: &serde_json::Value, 预算: usize) -> serde_json::Value {
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

pub(super) fn 裁剪到最大字节(
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
