//! 超级列表框表格查询子件，只由统一组件操作入口调用。
use super::*;

pub(super) fn 查询表格原子(
    句柄: u64,
    操作名: &str,
    参数: &Value,
) -> Result<Option<(u32, Vec<u8>)>, u32> {
    let 节点 = 组件实例::取节点(句柄)?;
    let 行数据表 = 取数组字段(&节点, "行")?;
    let 列定义 = 取数组字段(&节点, "列")?;
    let 查询结果 = match 操作名 {
        "取行高" => {
            let 行高 = 节点.get("条目行高").and_then(Value::as_u64).unwrap_or(0);
            return Ok(Some(回写查询结果(句柄, Value::from(行高))?));
        }
        "取编辑框" => {
            let 位置 = 节点.get("__编辑单元格").cloned().unwrap_or(Value::Null);
            let (Some(行序号), Some(列序号)) = (
                位置.get("表项索引").and_then(Value::as_u64),
                位置.get("列索引").and_then(Value::as_u64),
            ) else {
                return Ok(Some(回写查询结果(句柄, Value::Null)?));
            };
            let 文本 = 行数据表
                .get(行序号 as usize)
                .and_then(|行| 行.get(列序号 as usize))
                .cloned()
                .unwrap_or(Value::Null);
            return Ok(Some(回写查询结果(
                句柄,
                json!({"表项索引":行序号,"列索引":列序号,"标题":文本}),
            )?));
        }
        "取表项间距" => {
            let 间距 = 节点.get("图标间距").and_then(Value::as_u64).unwrap_or(8);
            return Ok(Some(回写查询结果(句柄, Value::from(间距))?));
        }
        "取表项提示" => {
            let 行序号 = 取正整数参数(参数, "表项索引")?;
            let 提示值 = 节点
                .get("__表项提示")
                .and_then(Value::as_array)
                .and_then(|表| 表.get(行序号))
                .cloned()
                .unwrap_or(Value::Null);
            return Ok(Some(回写查询结果(句柄, 提示值)?));
        }
        "取表项数" => Value::from(行数据表.len() as u64),
        "取列数" => Value::from(列定义.len() as u64),
        "取已选择表项数" => {
            let 选择值 = 取选择值(&节点);
            let 数量 = match 选择值 {
                Value::Array(表) => 表.len(),
                Value::String(文本) if !文本.is_empty() => 1,
                _ => 0,
            };
            Value::from(数量 as u64)
        }
        "取被选择表项" => {
            let 选择值 = 取选择值(&节点);
            let 值表 = match 选择值 {
                Value::Array(数组) => 数组,
                Value::String(文本) if !文本.is_empty() => vec![Value::from(文本)],
                _ => Vec::new(),
            };
            Value::Array(
                值表
                    .iter()
                    .filter_map(Value::as_str)
                    .filter_map(|文本| 文本.parse::<u64>().ok())
                    .map(Value::from)
                    .collect(),
            )
        }
        "是否被选择" => {
            let 行序号 = 取正整数参数(参数, "表项索引")?;
            let 选择值 = 取选择值(&节点);
            let 是选中 = match 选择值 {
                Value::String(文本) => 文本 == 行序号.to_string(),
                Value::Array(表) => 表.iter().any(|值| 值.as_str() == Some(&行序号.to_string())),
                _ => false,
            };
            Value::from(是选中)
        }
        "取标题" => {
            let 行序号 = 取正整数参数(参数, "表项索引")?;
            let 列序号 = 参数.get("列索引").and_then(Value::as_u64).unwrap_or(0) as usize;
            行数据表
                .get(行序号)
                .and_then(Value::as_array)
                .and_then(|行| 行.get(列序号))
                .cloned()
                .ok_or(错误码::参数不合法)?
        }
        "取表项数值" | "取图片" | "取当前状态图片" | "取缩进数目" => {
            let 行序号 = 取正整数参数(参数, "表项索引")?;
            if 操作名 == "取图片" && 参数.get("列索引").and_then(Value::as_u64).unwrap_or(0) > 0
            {
                let 列序号 = 取正整数参数(参数, "列索引")?;
                return Ok(Some(回写查询结果(
                    句柄,
                    节点
                        .get("__单元格图片")
                        .and_then(|图片表| 图片表.get(format!("{行序号}:{列序号}")))
                        .cloned()
                        .unwrap_or(Value::Null),
                )?));
            }
            if 操作名 == "取当前状态图片"
                && 节点.get("勾选列").and_then(Value::as_bool) == Some(true)
            {
                let 状态值 = 节点
                    .get("__检查状态")
                    .or_else(|| 节点.get("检查框状态"))
                    .and_then(Value::as_array)
                    .and_then(|表| 表.get(行序号));
                return Ok(Some(回写查询结果(
                    句柄,
                    json!(if 状态值
                        .is_some_and(|值| 值.as_bool() == Some(true) || 值.as_u64() == Some(1))
                    {
                        1
                    } else {
                        0
                    }),
                )?));
            }
            let (内部字段, 显示字段) = match 操作名 {
                "取表项数值" => ("__表项数值", "表项数值"),
                "取图片" => ("__表项图片", "图片组"),
                "取当前状态图片" => ("__表项状态图片", "状态图片组"),
                _ => ("__表项缩进", "表项缩进"),
            };
            节点
                .get(内部字段)
                .or_else(|| 节点.get(显示字段))
                .and_then(Value::as_array)
                .and_then(|表| 表.get(行序号))
                .filter(|值| !值.is_null())
                .cloned()
                .unwrap_or_else(|| {
                    if matches!(操作名, "取表项数值" | "取缩进数目") {
                        json!(0)
                    } else {
                        Value::Null
                    }
                })
        }
        "取列标题" => {
            let 列序号 = 取正整数参数(参数, "列索引")?;
            列定义.get(列序号).cloned().ok_or(错误码::参数不合法)?
        }
        "取列宽" | "取列对齐方式" | "取列图片" | "图片是否居右" => {
            let 列序号 = 取正整数参数(参数, "列索引")?;
            let (内部字段, 显示字段) = match 操作名 {
                "取列宽" => ("列宽", "列宽"),
                "取列对齐方式" => ("对齐方式", "列对齐方式"),
                "取列图片" => ("__列图片", "表头图片组"),
                _ => ("__列图片居右", "列图片居右"),
            };
            节点
                .get(内部字段)
                .or_else(|| 节点.get(显示字段))
                .and_then(Value::as_array)
                .and_then(|表| 表.get(列序号))
                .filter(|值| !值.is_null())
                .cloned()
                .unwrap_or_else(|| match 操作名 {
                    "取列宽" => json!("自适应"),
                    "取列对齐方式" => json!("左"),
                    "图片是否居右" => json!(false),
                    _ => Value::Null,
                })
        }
        _ => return Ok(None),
    };
    Ok(Some(回写查询结果(句柄, 查询结果)?))
}

pub(super) fn 回写查询结果(句柄: u64, 查询结果: Value) -> Result<(u32, Vec<u8>), u32> {
    更新表格字段(句柄, vec![("__查询结果".to_string(), 查询结果)])
}

pub(super) fn 查找表格行(
    句柄: u64,
    参数: &Value,
    查找数值: bool,
) -> Result<(u32, Vec<u8>), u32> {
    let 节点 = 组件实例::取节点(句柄)?;
    let 行数据表 = 取数组字段(&节点, "行")?;
    let 起始位置 = 参数.get("起始位置").and_then(Value::as_u64).unwrap_or(0) as usize;
    if 起始位置 > 行数据表.len() {
        return Err(错误码::参数不合法);
    }
    let 命中位置 = if 查找数值 {
        let 默认数值 = json!(0);
        let 查找值 = 参数.get("表项数值").unwrap_or(&默认数值);
        let 项目值表 = 节点
            .get("__表项数值")
            .or_else(|| 节点.get("表项数值"))
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_else(|| vec![json!(0); 行数据表.len()]);
        项目值表
            .iter()
            .enumerate()
            .skip(起始位置)
            .find(|(_, 值)| *值 == 查找值)
            .map(|(序号, _)| 序号)
    } else {
        let 目标文本 = 参数
            .get("标题")
            .and_then(Value::as_str)
            .ok_or(错误码::参数不合法)?;
        let 列序号 = 参数.get("列索引").and_then(Value::as_i64).unwrap_or(0);
        let 精确匹配 = 参数
            .get("是否精确匹配")
            .and_then(Value::as_bool)
            .unwrap_or(true);
        行数据表
            .iter()
            .enumerate()
            .skip(起始位置)
            .find(|(_, 行)| {
                行.as_array().is_some_and(|单元格| {
                    单元格.iter().enumerate().any(|(列序, 值)| {
                        if 列序号 != -1 && 列序号 != 列序 as i64 {
                            return false;
                        }
                        let 实际文本 = 值
                            .as_str()
                            .map(str::to_string)
                            .unwrap_or_else(|| 值.to_string());
                        if 精确匹配 {
                            实际文本 == 目标文本
                        } else {
                            实际文本.starts_with(目标文本)
                        }
                    })
                })
            })
            .map(|(序号, _)| 序号)
    };
    更新表格字段(
        句柄,
        vec![(
            "__查询结果".to_string(),
            命中位置.map(Value::from).unwrap_or_else(|| json!(-1)),
        )],
    )
}
