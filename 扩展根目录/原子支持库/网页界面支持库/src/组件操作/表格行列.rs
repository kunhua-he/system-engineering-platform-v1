//! 表格行列结构变更：插入、删除、清空、列属性、行高与提示文本。
//!
//! 所有入口只改实例字段，改完由父模块统一校验并回片段；行列结构一变，
//! 选择序号、检查框状态、图片坐标、提示文本都必须跟着走，否则身份会串。

use super::{
    取数组字段, 取正整数参数, 取选择值, 更新表格字段, 校验行数据, 调整图片坐标, 调整行属性字段,
    调整选择序号,
};
use crate::组件实例;
use crate::编号与码面::错误码;
use serde_json::{Value, json};

/// 行级数组字段：行列一变，这些都按同一下标插或删。
fn 行级字段表() -> [&'static str; 11] {
    [
        "__表项数值",
        "__表项图片",
        "__表项状态图片",
        "__表项缩进",
        "__检查状态",
        "检查框状态",
        "图片组",
        "状态图片组",
        "表项数值",
        "表项缩进",
        "__表项提示",
    ]
}

/// 列级数组字段：插列删列移列都要同步。
fn 列级字段表() -> [&'static str; 6] {
    [
        "列宽",
        "列对齐方式",
        "__列图片",
        "__列图片居右",
        "表头图片组",
        "列提示",
    ]
}

/// 把某个值写到数组字段的指定下标，并把长度补齐到目标长度。
fn 写下标(
    节点: &Value,
    字段名: &str,
    下标: usize,
    新值: Value,
    目标长度: usize,
) -> (String, Value) {
    let mut 数组 = 节点
        .get(字段名)
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    while 数组.len() <= 下标 {
        数组.push(Value::Null);
    }
    数组[下标] = 新值;
    while 数组.len() < 目标长度 {
        数组.push(Value::Null);
    }
    (字段名.to_string(), Value::Array(数组))
}

/// 在指定下标插入一个值，其余顺延；缺位按默认值补齐到旧长度再插。
fn 插下标(
    节点: &Value,
    字段名: &str,
    下标: usize,
    新值: Value,
    默认值: Value,
    旧长度: usize,
) -> (String, Value) {
    let 填充值 = 默认值;
    let mut 数组 = 节点
        .get(字段名)
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_else(|| vec![填充值.clone(); 旧长度]);
    while 数组.len() < 旧长度 {
        数组.push(填充值.clone());
    }
    let 插入点 = 下标.min(数组.len());
    数组.insert(插入点, 新值);
    (字段名.to_string(), Value::Array(数组))
}

pub(super) fn 插入表格行(
    句柄: u64, 参数: &Value, 追加: bool
) -> Result<(u32, Vec<u8>), u32> {
    let 节点 = 组件实例::取节点(句柄)?;
    let 新行 = 参数.get("行数据").cloned().ok_or(错误码::参数不合法)?;
    校验行数据(&节点, &新行)?;
    let 行数组 = 取数组字段(&节点, "行")?;
    let 行数 = 行数组.len();
    let 插入位置 = if 追加 {
        行数
    } else {
        参数
            .get("插入位置")
            .and_then(Value::as_u64)
            .map(|值| 值 as usize)
            .unwrap_or(行数)
    };
    if 插入位置 > 行数 {
        return Err(错误码::参数不合法);
    }
    let mut 新行数组 = 行数组;
    新行数组.insert(插入位置, 新行);
    let mut 字段表 = vec![("行".to_string(), Value::Array(新行数组))];
    if let Some(原选择) = 节点.get("__选中") {
        字段表.push(("__选中".to_string(), 调整选择序号(原选择, 插入位置, true)));
    }
    字段表.extend(调整行属性字段(&节点, 插入位置, true));
    for 字段名 in 行级字段表() {
        if 节点.get(字段名).and_then(Value::as_array).is_some() {
            字段表.push(插下标(
                &节点,
                字段名,
                插入位置,
                Value::Null,
                Value::Null,
                行数,
            ));
        }
    }
    字段表.push((
        "__单元格图片".to_string(),
        调整图片坐标(&节点, 0, 插入位置, "插入", 0),
    ));
    for (参数键, 字段名) in [
        ("表项数值", "__表项数值"),
        ("图片索引", "__表项图片"),
        ("状态图片", "__表项状态图片"),
        ("缩进数目", "__表项缩进"),
        ("检查框状态", "__检查状态"),
    ] {
        if let Some(值) = 参数.get(参数键) {
            字段表.push(写下标(&节点, 字段名, 插入位置, 值.clone(), 行数 + 1));
        }
    }
    更新表格字段(句柄, 字段表)
}

pub(super) fn 删除表格行(句柄: u64, 参数: &Value) -> Result<(u32, Vec<u8>), u32> {
    let 节点 = 组件实例::取节点(句柄)?;
    let 行序号 = 取正整数参数(参数, "表项索引")?;
    let mut 行数组 = 取数组字段(&节点, "行")?;
    if 行序号 >= 行数组.len() {
        return Err(错误码::参数不合法);
    }
    行数组.remove(行序号);
    let mut 字段表 = vec![("行".to_string(), Value::Array(行数组))];
    if let Some(原选择) = 节点.get("__选中") {
        字段表.push(("__选中".to_string(), 调整选择序号(原选择, 行序号, false)));
    }
    字段表.extend(调整行属性字段(&节点, 行序号, false));
    字段表.push((
        "__单元格图片".to_string(),
        调整图片坐标(&节点, 0, 行序号, "删除", 0),
    ));
    更新表格字段(句柄, 字段表)
}

pub(super) fn 清空表格数据(句柄: u64) -> Result<(u32, Vec<u8>), u32> {
    let 节点 = 组件实例::取节点(句柄)?;
    let mut 字段表 = vec![("行".to_string(), Value::Array(Vec::new()))];
    // 行级数组一律跟行数同长，清空必须一起清，留一个旧长度就会被渲染判长度不符。
    for 字段名 in 行级字段表() {
        if 节点.get(字段名).is_some() {
            字段表.push((字段名.to_string(), Value::Array(Vec::new())));
        }
    }
    字段表.push(("__选中".to_string(), json!([])));
    字段表.push(("__编辑单元格".to_string(), Value::Null));
    字段表.push(("__单元格图片".to_string(), json!({})));
    字段表.push(("__滚动目标".to_string(), Value::Null));
    更新表格字段(句柄, 字段表)
}

pub(super) fn 设置表格单元格(句柄: u64, 参数: &Value) -> Result<(u32, Vec<u8>), u32> {
    let 节点 = 组件实例::取节点(句柄)?;
    let 行序号 = 取正整数参数(参数, "表项索引")?;
    let 列索引 = 参数
        .get("列索引")
        .and_then(Value::as_u64)
        .map(|值| 值 as usize)
        .unwrap_or(0);
    let 新值 = 参数
        .get("标题")
        .or_else(|| 参数.get("文本"))
        .or_else(|| 参数.get("值"))
        .cloned()
        .ok_or(错误码::参数不合法)?;
    let mut 行数组 = 取数组字段(&节点, "行")?;
    let 目标行 = 行数组.get_mut(行序号).ok_or(错误码::参数不合法)?;
    let 单元格表 = 目标行.as_array_mut().ok_or(错误码::内容不合法)?;
    if 列索引 >= 单元格表.len() {
        return Err(错误码::参数不合法);
    }
    单元格表[列索引] = 新值;
    更新表格字段(句柄, vec![("行".to_string(), Value::Array(行数组))])
}

pub(super) fn 插入表格列(句柄: u64, 参数: &Value) -> Result<(u32, Vec<u8>), u32> {
    let 节点 = 组件实例::取节点(句柄)?;
    let 标题 = 参数
        .get("标题")
        .and_then(Value::as_str)
        .ok_or(错误码::参数不合法)?
        .to_string();
    let mut 列定义 = 取数组字段(&节点, "列")?;
    let 列数 = 列定义.len();
    let 插入位置 = 参数
        .get("插入位置")
        .and_then(Value::as_u64)
        .map(|值| 值 as usize)
        .unwrap_or(列数);
    if 插入位置 > 列数 {
        return Err(错误码::参数不合法);
    }
    列定义.insert(插入位置, Value::from(标题));
    let mut 字段表 = vec![("列".to_string(), Value::Array(列定义))];
    let 默认值表: [(&str, Value); 6] = [
        ("列宽", json!("自适应")),
        ("列对齐方式", json!("左")),
        ("__列图片", Value::Null),
        ("__列图片居右", json!(false)),
        ("表头图片组", Value::Null),
        ("列提示", Value::Null),
    ];
    for (字段名, 默认值) in 默认值表 {
        let 参数键 = match 字段名 {
            "列对齐方式" => "对齐方式",
            "__列图片" => "图片索引",
            "表头图片组" => "图片索引",
            "__列图片居右" => "图片居右",
            _ => 字段名,
        };
        let 新值 = 参数.get(参数键).cloned().unwrap_or_else(|| 默认值.clone());
        字段表.push(插下标(&节点, 字段名, 插入位置, 新值, 默认值, 列数));
    }
    let mut 新行表 = Vec::new();
    for 行项 in 取数组字段(&节点, "行")? {
        let mut 单元格表 = 行项.as_array().cloned().ok_or(错误码::内容不合法)?;
        if 插入位置 <= 单元格表.len() {
            单元格表.insert(插入位置, Value::Null);
        }
        新行表.push(Value::Array(单元格表));
    }
    字段表.push(("行".to_string(), Value::Array(新行表)));
    字段表.push((
        "__单元格图片".to_string(),
        调整图片坐标(&节点, 1, 插入位置, "插入", 0),
    ));
    更新表格字段(句柄, 字段表)
}

pub(super) fn 删除表格列(句柄: u64, 参数: &Value) -> Result<(u32, Vec<u8>), u32> {
    let 节点 = 组件实例::取节点(句柄)?;
    let 列索引 = 取正整数参数(参数, "列索引")?;
    let mut 列定义 = 取数组字段(&节点, "列")?;
    if 列索引 >= 列定义.len() {
        return Err(错误码::参数不合法);
    }
    列定义.remove(列索引);
    let mut 字段表 = vec![("列".to_string(), Value::Array(列定义))];
    for 字段名 in 列级字段表() {
        if let Some(数组) = 节点.get(字段名).and_then(Value::as_array) {
            let mut 新数组 = 数组.clone();
            if 列索引 < 新数组.len() {
                新数组.remove(列索引);
            }
            字段表.push((字段名.to_string(), Value::Array(新数组)));
        }
    }
    let mut 新行表 = Vec::new();
    for 行项 in 取数组字段(&节点, "行")? {
        let mut 单元格表 = 行项.as_array().cloned().ok_or(错误码::内容不合法)?;
        if 列索引 < 单元格表.len() {
            单元格表.remove(列索引);
        }
        新行表.push(Value::Array(单元格表));
    }
    字段表.push(("行".to_string(), Value::Array(新行表)));
    字段表.push((
        "__单元格图片".to_string(),
        调整图片坐标(&节点, 1, 列索引, "删除", 0),
    ));
    更新表格字段(句柄, 字段表)
}

pub(super) fn 设置表格列属性(
    句柄: u64,
    参数: &Value,
    字段名: &str,
    值键: &str,
) -> Result<(u32, Vec<u8>), u32> {
    let 节点 = 组件实例::取节点(句柄)?;
    let 列索引 = 取正整数参数(参数, "列索引")?;
    let 新值 = 参数.get(值键).cloned().ok_or(错误码::参数不合法)?;
    let 列数 = 节点
        .get("列")
        .and_then(Value::as_array)
        .ok_or(错误码::内容不合法)?
        .len();
    if 列索引 >= 列数 {
        return Err(错误码::参数不合法);
    }
    let mut 属性表 = 节点
        .get(字段名)
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_else(|| {
            let 默认值 = match 字段名 {
                "列宽" => json!("自适应"),
                "列对齐方式" => json!("左"),
                _ => json!(false),
            };
            vec![默认值; 列数]
        });
    while 属性表.len() < 列数 {
        属性表.push(Value::Null);
    }
    if 字段名 == "列宽" && 新值.as_str() != Some("自适应") {
        let 宽度 = 新值.as_u64().ok_or(错误码::参数不合法)?;
        if !(40..=2000).contains(&宽度) {
            return Err(错误码::参数不合法);
        }
    }
    if 字段名 == "列对齐方式" && !matches!(新值.as_str(), Some("左" | "中" | "右")) {
        return Err(错误码::参数不合法);
    }
    if 字段名 == "__列图片" && !(新值.is_null() || 新值.is_string()) {
        return Err(错误码::参数不合法);
    }
    if 字段名 == "__列图片居右" && 新值.as_bool().is_none() {
        return Err(错误码::参数不合法);
    }
    属性表[列索引] = 新值;
    更新表格字段(句柄, vec![(字段名.to_string(), Value::Array(属性表))])
}

pub(super) fn 设置表格行高(句柄: u64, 参数: &Value) -> Result<(u32, Vec<u8>), u32> {
    let 行高 = 取正整数参数(参数, "行高")?;
    // 与渲染侧同一区间：低于 20 会切字，高于 200 一屏放不下两行。
    if !(20..=200).contains(&行高) {
        return Err(错误码::参数不合法);
    }
    更新表格字段(
        句柄,
        vec![("条目行高".to_string(), Value::from(行高 as u64))],
    )
}

pub(super) fn 设置表项提示(句柄: u64, 参数: &Value) -> Result<(u32, Vec<u8>), u32> {
    let 节点 = 组件实例::取节点(句柄)?;
    let 行序号 = 取正整数参数(参数, "表项索引")?;
    let 行数 = 节点
        .get("行")
        .and_then(Value::as_array)
        .ok_or(错误码::内容不合法)?
        .len();
    if 行序号 >= 行数 {
        return Err(错误码::参数不合法);
    }
    let 提示文本 = 参数
        .get("提示文本")
        .and_then(Value::as_str)
        .ok_or(错误码::参数不合法)?
        .to_string();
    更新表格字段(
        句柄,
        vec![写下标(
            &节点,
            "__表项提示",
            行序号,
            Value::from(提示文本),
            行数,
        )],
    )
}

pub(super) fn 设置列提示(句柄: u64, 参数: &Value) -> Result<(u32, Vec<u8>), u32> {
    let 节点 = 组件实例::取节点(句柄)?;
    let 列索引 = 取正整数参数(参数, "列索引")?;
    let 列数 = 节点
        .get("列")
        .and_then(Value::as_array)
        .ok_or(错误码::内容不合法)?
        .len();
    if 列索引 >= 列数 {
        return Err(错误码::参数不合法);
    }
    let 提示文本 = 参数
        .get("提示文本")
        .and_then(Value::as_str)
        .ok_or(错误码::参数不合法)?
        .to_string();
    更新表格字段(
        句柄,
        vec![写下标(
            &节点,
            "列提示",
            列索引,
            Value::from(提示文本),
            列数,
        )],
    )
}

pub(super) fn 设置列标题(句柄: u64, 参数: &Value) -> Result<(u32, Vec<u8>), u32> {
    let 节点 = 组件实例::取节点(句柄)?;
    let 列索引 = 取正整数参数(参数, "列索引")?;
    let 标题 = 参数
        .get("标题")
        .and_then(Value::as_str)
        .ok_or(错误码::参数不合法)?
        .to_string();
    let mut 列定义 = 取数组字段(&节点, "列")?;
    if 列索引 >= 列定义.len() {
        return Err(错误码::参数不合法);
    }
    列定义[列索引] = Value::from(标题);
    更新表格字段(句柄, vec![("列".to_string(), Value::Array(列定义))])
}

pub(super) fn 移动表格列(句柄: u64, 参数: &Value) -> Result<(u32, Vec<u8>), u32> {
    let 节点 = 组件实例::取节点(句柄)?;
    let 列索引 = 取正整数参数(参数, "列索引")?;
    let 目标位置 = 取正整数参数(参数, "目标位置")?;
    let mut 列定义 = 取数组字段(&节点, "列")?;
    let 列数 = 列定义.len();
    if 列索引 >= 列数 || 目标位置 >= 列数 {
        return Err(错误码::参数不合法);
    }
    let 移动列名 = 列定义.remove(列索引);
    列定义.insert(目标位置, 移动列名);
    let mut 字段表 = vec![("列".to_string(), Value::Array(列定义))];
    for 字段名 in 列级字段表() {
        if let Some(数组) = 节点.get(字段名).and_then(Value::as_array) {
            if 列索引 >= 数组.len() {
                continue;
            }
            let mut 新数组 = 数组.clone();
            let 值 = 新数组.remove(列索引);
            if 目标位置 <= 新数组.len() {
                新数组.insert(目标位置, 值);
            } else {
                新数组.push(值);
            }
            字段表.push((字段名.to_string(), Value::Array(新数组)));
        }
    }
    let mut 新行表 = Vec::new();
    for 行项 in 取数组字段(&节点, "行")? {
        let mut 单元格表 = 行项.as_array().cloned().ok_or(错误码::内容不合法)?;
        if 列索引 < 单元格表.len() {
            let 单元格值 = 单元格表.remove(列索引);
            let 插入点 = 目标位置.min(单元格表.len());
            单元格表.insert(插入点, 单元格值);
        }
        新行表.push(Value::Array(单元格表));
    }
    字段表.push(("行".to_string(), Value::Array(新行表)));
    字段表.push((
        "__单元格图片".to_string(),
        调整图片坐标(&节点, 1, 列索引, "移动", 目标位置),
    ));
    let 选择值 = 取选择值(&节点);
    if 选择值.is_array() || 选择值.is_string() {
        字段表.push(("__选中".to_string(), 选择值));
    }
    更新表格字段(句柄, 字段表)
}
