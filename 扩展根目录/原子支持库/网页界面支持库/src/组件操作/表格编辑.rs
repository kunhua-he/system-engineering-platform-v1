//! 超级列表框表格编辑子件，只由统一组件操作入口调用。
use super::*;

pub(super) fn 记录表格事件(句柄: u64, 参数: &Value) -> Result<(u32, Vec<u8>), u32> {
    crate::组件操作::表格事件::记录事件状态(句柄, 参数)?;
    Ok((4, r#"{"片段":"","句柄组":[]}"#.as_bytes().to_vec()))
}

pub(super) fn 设置行属性(
    句柄: u64,
    参数: &Value,
    字段名: &str,
    值键: &str,
) -> Result<(u32, Vec<u8>), u32> {
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
    let 新值 = 参数.get(值键).cloned().unwrap_or_else(|| {
        if matches!(字段名, "__表项数值" | "__表项缩进") {
            json!(0)
        } else {
            Value::Null
        }
    });
    if 字段名 == "__表项数值" && 新值.as_i64().is_none() {
        return Err(错误码::参数不合法);
    }
    if 字段名 == "__表项缩进" && 新值.as_u64().is_none() {
        return Err(错误码::参数不合法);
    }
    if 字段名 == "__表项图片" && 参数.get("列索引").and_then(Value::as_u64).unwrap_or(0) > 0
    {
        let 列序号 = 取正整数参数(参数, "列索引")?;
        if 列序号 >= 节点["列"].as_array().ok_or(错误码::内容不合法)?.len() {
            return Err(错误码::参数不合法);
        }
        if !新值.is_null()
            && !新值.as_str().is_some_and(|路径| {
                !路径.starts_with("//")
                    && !路径.contains(':')
                    && !路径.contains('\\')
                    && !路径.chars().any(char::is_control)
            })
        {
            return Err(错误码::参数不合法);
        }
        let mut 图片映射 = 节点
            .get("__单元格图片")
            .and_then(Value::as_object)
            .cloned()
            .unwrap_or_default();
        let 图片键名 = format!("{行序号}:{列序号}");
        if 新值.is_null() {
            图片映射.remove(&图片键名);
        } else {
            图片映射.insert(图片键名, 新值);
        }
        return 更新表格字段(
            句柄,
            vec![("__单元格图片".to_string(), Value::Object(图片映射))],
        );
    }
    let 显示字段 = match 字段名 {
        "__表项数值" => "表项数值",
        "__表项图片" => "图片组",
        "__表项状态图片" => "状态图片组",
        _ => "表项缩进",
    };
    let mut 属性表 = 节点
        .get(字段名)
        .or_else(|| 节点.get(显示字段))
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_else(|| vec![Value::Null; 行数]);
    属性表[行序号] = 新值;
    更新表格字段(句柄, vec![(字段名.to_string(), Value::Array(属性表))])
}

pub(super) fn 设置列图片属性(
    句柄: u64,
    参数: &Value,
    字段名: &str,
    值键: &str,
) -> Result<(u32, Vec<u8>), u32> {
    let 节点 = 组件实例::取节点(句柄)?;
    let 列序号 = 取正整数参数(参数, "列索引")?;
    let 列数 = 节点
        .get("列")
        .and_then(Value::as_array)
        .ok_or(错误码::内容不合法)?
        .len();
    if 列序号 >= 列数 {
        return Err(错误码::参数不合法);
    }
    let 新值 = 参数.get(值键).cloned().ok_or(错误码::参数不合法)?;
    let mut 属性表 = 节点
        .get(字段名)
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_else(|| vec![Value::Null; 列数]);
    属性表[列序号] = 新值;
    更新表格字段(句柄, vec![(字段名.to_string(), Value::Array(属性表))])
}

pub(super) fn 开始表格编辑(句柄: u64, 参数: &Value) -> Result<(u32, Vec<u8>), u32> {
    let 节点 = 组件实例::取节点(句柄)?;
    if !节点
        .get("允许编辑")
        .and_then(Value::as_bool)
        .unwrap_or(false)
    {
        return Err(错误码::参数不合法);
    }
    let 行序号 = 取正整数参数(参数, "表项索引")?;
    let 列序号 = 参数.get("列索引").and_then(Value::as_u64).unwrap_or(0) as usize;
    let 行数 = 节点
        .get("行")
        .and_then(Value::as_array)
        .ok_or(错误码::内容不合法)?
        .len();
    let 列数 = 节点
        .get("列")
        .and_then(Value::as_array)
        .ok_or(错误码::内容不合法)?
        .len();
    if 行序号 >= 行数 || 列序号 >= 列数 {
        return Err(错误码::参数不合法);
    }
    let 批准编辑 = 参数
        .get("批准")
        .map(|值| 值.as_bool().ok_or(错误码::参数不合法))
        .transpose()?
        .unwrap_or(true);
    更新表格字段(
        句柄,
        vec![(
            "__编辑单元格".to_string(),
            if 批准编辑 {
                json!({"表项索引":行序号,"列索引":列序号})
            } else {
                Value::Null
            },
        )],
    )
}

pub(super) fn 结束表格编辑(句柄: u64, 参数: &Value) -> Result<(u32, Vec<u8>), u32> {
    let 节点 = 组件实例::取节点(句柄)?;
    let 行序号 = 取正整数参数(参数, "表项索引")?;
    let 列序号 = 取正整数参数(参数, "列索引")?;
    if !节点
        .get("允许编辑")
        .and_then(Value::as_bool)
        .unwrap_or(false)
    {
        return Err(错误码::参数不合法);
    }
    let 编辑位置 = 节点.get("__编辑单元格").ok_or(错误码::参数不合法)?;
    if 编辑位置.get("表项索引").and_then(Value::as_u64) != Some(行序号 as u64)
        || 编辑位置.get("列索引").and_then(Value::as_u64) != Some(列序号 as u64)
    {
        return Err(错误码::参数不合法);
    }
    let 新文本 = Value::from(
        参数
            .get("标题")
            .and_then(Value::as_str)
            .ok_or(错误码::参数不合法)?,
    );
    let mut 行数据表 = 取数组字段(&节点, "行")?;
    let 单元格表 = 行数据表
        .get_mut(行序号)
        .and_then(Value::as_array_mut)
        .ok_or(错误码::参数不合法)?;
    let 单元格 = 单元格表.get_mut(列序号).ok_or(错误码::参数不合法)?;
    let 批准编辑 = 参数
        .get("批准")
        .map(|值| 值.as_bool().ok_or(错误码::参数不合法))
        .transpose()?
        .unwrap_or(true);
    if 批准编辑 {
        *单元格 = 新文本;
    }
    更新表格字段(
        句柄,
        vec![
            ("行".to_string(), Value::Array(行数据表)),
            ("__编辑单元格".to_string(), Value::Null),
            ("结束编辑文本".to_string(), 参数["标题"].clone()),
        ],
    )
}

pub(super) fn 修改表格选择(
    句柄: u64,
    参数: &Value,
    选中: bool,
) -> Result<(u32, Vec<u8>), u32> {
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
    let 模式 = 节点
        .get("选择模式")
        .and_then(Value::as_str)
        .unwrap_or("不选");
    if 模式 == "不选" {
        return Err(错误码::参数不合法);
    }
    let 旧选择 = 取选择值(&节点);
    let mut 选择序号表: Vec<usize> = match &旧选择 {
        Value::String(单项) if !单项.is_empty() => 单项.parse().ok().into_iter().collect(),
        Value::Array(多项) => 多项
            .iter()
            .filter_map(Value::as_str)
            .filter_map(|文本| 文本.parse().ok())
            .collect(),
        _ => Vec::new(),
    };
    if 模式 == "多选" {
        选择序号表.retain(|序号| *序号 != 行序号);
        if 选中 {
            选择序号表.push(行序号);
        }
        let 新选择 = Value::Array(
            选择序号表
                .into_iter()
                .map(|序号| Value::from(序号.to_string()))
                .collect(),
        );
        更新表格字段(句柄, vec![("__选中".to_string(), 新选择)])
    } else {
        let 新选择 = if 选中 {
            Value::from(行序号.to_string())
        } else if 选择序号表.contains(&行序号) {
            Value::from("")
        } else {
            旧选择
        };
        更新表格字段(句柄, vec![("__选中".to_string(), 新选择)])
    }
}

/// 易语言的「检查框状态被改变」是用户点一下就翻一次，不带目标值；这里单独留一条翻转原子。
pub(super) fn 翻转检查状态(
    组件句柄: u64, 操作参数: &Value
) -> Result<(u32, Vec<u8>), u32> {
    let 表格节点 = 组件实例::取节点(组件句柄)?;
    let 行序号 = 取正整数参数(操作参数, "表项索引")?;
    let 行数 = 表格节点
        .get("行")
        .and_then(Value::as_array)
        .ok_or(错误码::内容不合法)?
        .len();
    if 行序号 >= 行数 {
        return Err(错误码::参数不合法);
    }
    let mut 检查状态表 = 表格节点
        .get("__检查状态")
        .or_else(|| 表格节点.get("检查框状态"))
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_else(|| vec![json!(false); 行数]);
    while 检查状态表.len() < 行数 {
        检查状态表.push(json!(false));
    }
    let 原状态 = match 检查状态表.get(行序号) {
        Some(Value::Bool(逻辑值)) => *逻辑值,
        Some(值) => 值.as_u64() == Some(1),
        None => false,
    };
    检查状态表[行序号] = json!(!原状态);
    更新表格字段(
        组件句柄,
        vec![("__检查状态".to_string(), Value::Array(检查状态表))],
    )
}

pub(super) fn 设置检查状态(
    组件句柄: u64, 操作参数: &Value
) -> Result<(u32, Vec<u8>), u32> {
    let 表格节点 = 组件实例::取节点(组件句柄)?;
    let 行序号 = 取正整数参数(操作参数, "表项索引")?;
    let 行数 = 表格节点
        .get("行")
        .and_then(Value::as_array)
        .ok_or(错误码::内容不合法)?
        .len();
    if 行序号 >= 行数 {
        return Err(错误码::参数不合法);
    }
    let 新状态 = 操作参数
        .get("检查框状态")
        .or_else(|| 操作参数.get("图片索引"))
        .ok_or(错误码::参数不合法)?;
    let 新状态 = match 新状态 {
        Value::Bool(逻辑值) => *逻辑值,
        _ => match 新状态.as_u64() {
            Some(0) => false,
            Some(1) => true,
            _ => return Err(错误码::参数不合法),
        },
    };
    let mut 检查状态表 = 表格节点
        .get("__检查状态")
        .or_else(|| 表格节点.get("检查框状态"))
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_else(|| vec![json!(false); 行数]);
    检查状态表[行序号] = json!(新状态);
    更新表格字段(
        组件句柄,
        vec![("__检查状态".to_string(), Value::Array(检查状态表))],
    )
}
