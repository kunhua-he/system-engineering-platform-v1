//! 格式互转与合并：CSV 全文解析、JSON 深合并、JSON 到 YAML 值转换。

use crate::编号与码面::错误码;

pub(super) fn 解析CSV全文(CSV文本: &str, 分隔符: char, 严格模式: bool) -> Result<Vec<Vec<String>>, u32> {
    let mut 行表: Vec<Vec<String>> = Vec::new();
    let mut 字段表: Vec<String> = Vec::new();
    let mut 字段缓冲 = String::new();
    let (mut 在引号内, mut 字段已开始) = (false, false);
    let mut 字符迭代 = CSV文本.chars().peekable();
    while let Some(当前字符) = 字符迭代.next() {
        if 在引号内 {
            if 当前字符 == '"' {
                if 字符迭代.peek() == Some(&'"') {
                    字符迭代.next();
                    字段缓冲.push('"');
                } else {
                    在引号内 = false;
                }
            } else {
                字段缓冲.push(当前字符);
            }
            continue;
        }
        if 当前字符 == '"' {
            if 严格模式 && (!字段缓冲.is_empty() || 字段已开始) {
                return Err(错误码::JSON参数不合法);
            }
            在引号内 = true;
            字段已开始 = true;
            continue;
        }
        if 当前字符 == 分隔符 {
            字段表.push(std::mem::take(&mut 字段缓冲));
            字段已开始 = false;
            if 字段表.len() > 1000 {
                return Err(错误码::JSON资源受限);
            }
            continue;
        }
        if 当前字符 == '\n' || 当前字符 == '\r' {
            if 当前字符 == '\r' && 字符迭代.peek() == Some(&'\n') {
                字符迭代.next();
            }
            字段表.push(std::mem::take(&mut 字段缓冲));
            字段已开始 = false;
            if 字段表.len() == 1 && 字段表[0].is_empty() {
                字段表.clear();
            } else {
                行表.push(std::mem::take(&mut 字段表));
            }
            if 行表.len() > 10000 {
                return Err(错误码::JSON资源受限);
            }
            continue;
        }
        字段缓冲.push(当前字符);
        字段已开始 = true;
    }
    if 在引号内 && 严格模式 {
        return Err(错误码::JSON参数不合法);
    }
    字段表.push(字段缓冲);
    if !(字段表.len() == 1 && 字段表[0].is_empty()) {
        行表.push(字段表);
    }
    Ok(行表)
}

pub(super) fn 深合并值(基础值: &mut serde_json::Value, 覆盖值: &serde_json::Value) {
    if let (serde_json::Value::Object(基础表), serde_json::Value::Object(覆盖表)) = (&mut *基础值, 覆盖值) {
        for (键名, 值项) in 覆盖表 {
            match 基础表.get_mut(键名) {
                Some(已有项) => 深合并值(已有项, 值项),
                None => {
                    基础表.insert(键名.clone(), 值项.clone());
                }
            }
        }
        return;
    }
    *基础值 = 覆盖值.clone();
}

pub(super) fn 转YAML值(候选值: &serde_json::Value) -> serde_yaml_ng::Value {
    match 候选值 {
        serde_json::Value::Null => serde_yaml_ng::Value::Null,
        serde_json::Value::Bool(逻辑值) => serde_yaml_ng::Value::Bool(*逻辑值),
        serde_json::Value::Number(数值项) => {
            if let Some(整数项) = 数值项.as_i64() {
                serde_yaml_ng::Value::Number(整数项.into())
            } else if let Some(无符号项) = 数值项.as_u64() {
                serde_yaml_ng::Value::Number(无符号项.into())
            } else if let Some(浮点项) = 数值项.as_f64() {
                serde_yaml_ng::Value::Number(浮点项.into())
            } else {
                serde_yaml_ng::Value::String(数值项.to_string())
            }
        }
        serde_json::Value::String(文本项) => serde_yaml_ng::Value::String(文本项.clone()),
        serde_json::Value::Array(列表项) => {
            serde_yaml_ng::Value::Sequence(列表项.iter().map(转YAML值).collect())
        }
        serde_json::Value::Object(对象项) => serde_yaml_ng::Value::Mapping(
            对象项
                .iter()
                .map(|(键名, 值项)| (serde_yaml_ng::Value::String(键名.clone()), 转YAML值(值项)))
                .collect(),
        ),
    }
}
