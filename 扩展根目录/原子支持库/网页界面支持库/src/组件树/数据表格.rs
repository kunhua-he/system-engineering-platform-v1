//! 数据表格：斑马纹、吸顶表头、单元格内边距都由声明给；外观值走 CSS 变量。
//!
//! 排序与分页是底座的活，不是浏览器的活：表格拉起时登记成组件实例、签发组件句柄，
//! 页面点表头 / 翻页只把「句柄 + 操作」交回宿主；底座按实例状态重算，只回这一张表的片段。

use serde_json::Value;

use crate::业务实现::{取对象文本, 拼装表格行, 转义网页文本};
use crate::组件树::外观属性::{取形态变量, 校验颜色值, 表格外观映射};
use crate::组件树::渲染状态;
use crate::编号与码面::错误码;

/// 把一行按某列的值取出来，供排序比较。
fn 取单元格(行项: &Value, 列序: usize) -> Option<&Value> {
    行项.as_array().and_then(|单元格表| 单元格表.get(列序))
}

/// 升序比较；空值排最后，明确指定后不再自动猜测排序类型。
fn 比较单元格(左值: &Value, 右值: &Value, 排序方式: &str) -> std::cmp::Ordering {
    use std::cmp::Ordering;
    let 左空 = 左值.is_null();
    let 右空 = 右值.is_null();
    if 左空 || 右空 {
        return match (左空, 右空) {
            (true, true) => Ordering::Equal,
            (true, false) => Ordering::Greater,
            _ => Ordering::Less,
        };
    }
    match 排序方式 {
        "数值" => {
            let 左数 = 取数值排序键(左值).unwrap_or(f64::NAN);
            let 右数 = 取数值排序键(右值).unwrap_or(f64::NAN);
            左数.partial_cmp(&右数).unwrap_or(Ordering::Equal)
        }
        "日期" => 取日期文本(左值).cmp(&取日期文本(右值)),
        "文本" => 取比较文本(左值).cmp(&取比较文本(右值)),
        _ => match (左值.as_f64(), 右值.as_f64()) {
            (Some(左数), Some(右数)) => 左数.partial_cmp(&右数).unwrap_or(Ordering::Equal),
            _ => 取比较文本(左值).cmp(&取比较文本(右值)),
        },
    }
}

fn 取比较文本(值: &Value) -> String {
    值.as_str()
        .map(str::to_string)
        .unwrap_or_else(|| 值.to_string())
}

fn 取数值排序键(值: &Value) -> Option<f64> {
    if let Some(数值) = 值.as_f64() {
        return Some(数值);
    }
    let 文本 = 值.as_str()?.trim();
    let 数字文本: String = 文本
        .chars()
        .take_while(|字符| 字符.is_ascii_digit() || matches!(字符, '+' | '-' | '.'))
        .collect();
    let 数值 = 数字文本.parse::<f64>().ok()?;
    let 单位 = 文本[数字文本.len()..].trim().to_ascii_lowercase();
    let 倍数 = match 单位.as_str() {
        "" | "b" | "字节" => 1.0,
        "kb" | "千字节" => 1_000.0,
        "kib" => 1_024.0,
        "mb" | "兆字节" => 1_000_000.0,
        "mib" => 1_048_576.0,
        "gb" | "吉字节" => 1_000_000_000.0,
        "gib" => 1_073_741_824.0,
        "tb" => 1_000_000_000_000.0,
        "tib" => 1_099_511_627_776.0,
        _ => return None,
    };
    Some(数值 * 倍数)
}

fn 取日期文本(值: &Value) -> String {
    取比较文本(值).replace('/', "-").replace('T', " ")
}

fn 是日期文本(值: &Value) -> bool {
    let Some(文本) = 值.as_str() else {
        return false;
    };
    let 标准文本 = 文本.trim().replace('T', " ");
    let 日期时间: Vec<&str> = 标准文本.splitn(2, ' ').collect();
    let 日期段: Vec<&str> = 日期时间[0].split('-').collect();
    if 日期段.len() != 3
        || 日期段[0].len() != 4
        || 日期段[1].len() != 2
        || 日期段[2].len() != 2
        || 日期段
            .iter()
            .any(|段| !段.chars().all(|字符| 字符.is_ascii_digit()))
    {
        return false;
    }
    let 年 = 日期段[0].parse::<u32>().ok();
    let 月 = 日期段[1].parse::<u32>().ok();
    let 日 = 日期段[2].parse::<u32>().ok();
    let 年份 = 年.unwrap_or(0);
    let 月份 = 月.unwrap_or(0);
    let 最大天数 = match 月份 {
        4 | 6 | 9 | 11 => 30,
        2 if 年份.is_multiple_of(400) || (年份.is_multiple_of(4) && !年份.is_multiple_of(100)) => {
            29
        }
        2 => 28,
        _ => 31,
    };
    if 年份 == 0
        || 月.map(|数| !(1..=12).contains(&数)).unwrap_or(true)
        || 日.map(|数| !(1..=最大天数).contains(&数)).unwrap_or(true)
    {
        return false;
    }
    if let Some(时间段) = 日期时间.get(1) {
        let 时间项: Vec<&str> = 时间段.split(':').collect();
        if 时间项.len() < 2 || 时间项.len() > 3 {
            return false;
        }
        let 时 = 时间项[0].parse::<u32>().ok();
        let 分 = 时间项[1].parse::<u32>().ok();
        let 秒 = 时间项.get(2).and_then(|数| 数.parse::<u32>().ok());
        if 时.map(|数| 数 > 23).unwrap_or(true)
            || 分.map(|数| 数 > 59).unwrap_or(true)
            || (时间项.len() == 3 && 秒.map(|数| 数 > 59).unwrap_or(true))
        {
            return false;
        }
    }
    true
}

/// 按实例状态排序并切页；保留原始行序号，以便选择项在翻页/排序后仍指向同一行。
fn 排序分页(
    行数据: &[Value],
    排序列: Option<usize>,
    升序: bool,
    排序方式: &str,
    每页行数: usize,
    页码: usize,
) -> (Vec<(usize, Value)>, usize) {
    let mut 行副本: Vec<(usize, Value)> = 行数据.iter().cloned().enumerate().collect();
    if let Some(列序) = 排序列 {
        行副本.sort_by(|(_, 左行), (_, 右行)| {
            let 比较结果 = match (取单元格(左行, 列序), 取单元格(右行, 列序)) {
                (Some(左值), Some(右值)) => 比较单元格(左值, 右值, 排序方式),
                _ => std::cmp::Ordering::Equal,
            };
            let 包含空值 = 取单元格(左行, 列序).is_some_and(Value::is_null)
                || 取单元格(右行, 列序).is_some_and(Value::is_null);
            if 升序 || 包含空值 {
                比较结果
            } else {
                比较结果.reverse()
            }
        });
    }
    if 每页行数 == 0 {
        return (行副本, 1);
    }
    let 总页数 = 行副本.len().div_ceil(每页行数).max(1);
    let 当前页 = 页码.clamp(1, 总页数);
    let 起点 = (当前页 - 1) * 每页行数;
    let 末位 = (起点 + 每页行数).min(行副本.len());
    let 本页行 = if 起点 >= 行副本.len() {
        Vec::new()
    } else {
        行副本[起点..末位].to_vec()
    };
    (本页行, 总页数)
}

/// 未声明像素宽度时按标题与内容字数算一个确定值：宽度在底座一次定死，浏览器不测量。
fn 推定列宽(节点: &Value, 列名项: &Value, 行数据: &[Value], 列序: usize) -> usize {
    let 单行像素宽 = |文本: &str| -> usize {
        文本
            .chars()
            .map(|单字| if 单字.is_ascii() { 8 } else { 14 })
            .sum()
    };
    // 可排序表头常显 ▲/▼ 两枚按钮，标题旁要留出按钮宽度，否则标题被挤成省略号。
    let 方向按钮宽 = if 取逻辑字段(节点, "可排序", Some("表头可单击"), false).unwrap_or(false)
    {
        // 按钮 18 像素 + 标题与按钮间隙 6 像素 + 2 像素余量。
        26
    } else {
        0
    };
    let mut 最宽 = 单行像素宽(&crate::业务实现::转文本值(列名项)) + 方向按钮宽;
    for 行项 in 行数据.iter() {
        if let Some(单元格) = 行项.as_array().and_then(|单元格表| 单元格表.get(列序))
        {
            let 单元格文本 = crate::业务实现::转文本值(单元格);
            let 单格最宽 = 单元格文本.lines().map(单行像素宽).max().unwrap_or(0);
            最宽 = 最宽.max(单格最宽);
        }
    }
    let 表头图标宽 = 节点
        .get("表头图片组")
        .and_then(Value::as_array)
        .and_then(|图标组| 图标组.get(列序))
        .filter(|图标项| !图标项.is_null())
        .map(|_| 28)
        .unwrap_or(0);
    (最宽 + 26 + 表头图标宽).clamp(60, 600)
}

fn 取列宽表(
    节点: &Value, 列定义: &[Value], 行数据: &[Value]
) -> Result<Vec<usize>, u32> {
    let 列数 = 列定义.len();
    let 声明宽度: Vec<Option<usize>> = match 节点.get("列宽") {
        None => vec![None; 列数],
        Some(宽度值) => {
            let 宽度数组 = 宽度值.as_array().ok_or(错误码::内容不合法)?;
            if 宽度数组.len() != 列数 {
                return Err(错误码::内容不合法);
            }
            宽度数组
                .iter()
                .map(|宽度项| {
                    if 宽度项.is_null() || 宽度项.as_str() == Some("自适应") {
                        return Ok(None);
                    }
                    let 宽度 = 宽度项.as_u64().ok_or(错误码::内容不合法)? as usize;
                    if !(40..=2000).contains(&宽度) {
                        return Err(错误码::内容不合法);
                    }
                    Ok(Some(宽度))
                })
                .collect::<Result<Vec<Option<usize>>, u32>>()?
        }
    };
    Ok(声明宽度
        .into_iter()
        .enumerate()
        .map(|(列序, 宽度)| 宽度.unwrap_or_else(|| 推定列宽(节点, &列定义[列序], 行数据, 列序)))
        .collect())
}

fn 取列对齐表(节点: &Value, 列数: usize) -> Result<Vec<String>, u32> {
    let Some(对齐值) = 节点.get("列对齐方式") else {
        return Ok(vec!["左".to_string(); 列数]);
    };
    let 对齐数组 = 对齐值.as_array().ok_or(错误码::内容不合法)?;
    if 对齐数组.len() != 列数 {
        return Err(错误码::内容不合法);
    }
    对齐数组
        .iter()
        .map(|对齐项| match 对齐项.as_str() {
            Some("左" | "中" | "右") => Ok(对齐项.as_str().unwrap_or_default().to_string()),
            _ => Err(错误码::内容不合法),
        })
        .collect()
}

fn 取选择模式(节点: &Value) -> Result<String, u32> {
    let 模式 = match 节点.get("选择模式") {
        Some(值) => 值.as_str().ok_or(错误码::内容不合法)?,
        None if 节点.get("单一选择").and_then(Value::as_bool) == Some(true) => "单选",
        None if 节点.get("整行选择").and_then(Value::as_bool) == Some(true) => "整行",
        None => "不选",
    };
    match 模式 {
        "不选" | "单选" | "多选" | "整行" => Ok(模式.to_string()),
        _ => Err(错误码::内容不合法),
    }
}

fn 取逻辑字段(
    节点: &Value,
    字段名: &str,
    备用字段名: Option<&str>,
    默认值: bool,
) -> Result<bool, u32> {
    let 值 = 节点
        .get(字段名)
        .or_else(|| 备用字段名.and_then(|名称| 节点.get(名称)));
    match 值 {
        None => Ok(默认值),
        Some(值) => 值.as_bool().ok_or(错误码::内容不合法),
    }
}

fn 取同长度数组(节点: &Value, 字段名: &str, 项数: usize) -> Result<Vec<Value>, u32> {
    let Some(值) = 节点.get(字段名) else {
        return Ok(vec![Value::Null; 项数]);
    };
    let 数组 = 值.as_array().ok_or(错误码::内容不合法)?;
    if 数组.len() != 项数 {
        return Err(错误码::内容不合法);
    }
    Ok(数组.clone())
}

fn 取图片资源表(
    节点: &Value,
    显示字段: &str,
    内部字段: &str,
    项数: usize,
) -> Result<Vec<Value>, u32> {
    let 数组 = if 节点.get(内部字段).is_some() {
        取同长度数组(节点, 内部字段, 项数)?
    } else {
        取同长度数组(节点, 显示字段, 项数)?
    };
    if 数组.iter().any(|值| {
        !值.is_null()
            && !值.as_str().is_some_and(|路径| {
                !路径.starts_with("//")
                    && !路径.contains(':')
                    && !路径.contains('\\')
                    && !路径.chars().any(char::is_control)
            })
    }) {
        return Err(错误码::内容不合法);
    }
    Ok(数组)
}

fn 取编辑单元格(节点: &Value) -> Result<Option<(usize, usize)>, u32> {
    let Some(编辑值) = 节点.get("__编辑单元格") else {
        return Ok(None);
    };
    if 编辑值.is_null() {
        return Ok(None);
    }
    let 行序号 = 编辑值
        .get("表项索引")
        .and_then(Value::as_u64)
        .ok_or(错误码::内容不合法)? as usize;
    let 列序号 = 编辑值
        .get("列索引")
        .and_then(Value::as_u64)
        .ok_or(错误码::内容不合法)? as usize;
    Ok(Some((行序号, 列序号)))
}

fn 取视图模式(节点: &Value) -> Result<String, u32> {
    let 模式 = 节点
        .get("视图模式")
        .and_then(Value::as_str)
        .unwrap_or("报表");
    match 模式 {
        "报表" | "列表" | "小图标" | "大图标" => Ok(模式.to_string()),
        _ => Err(错误码::内容不合法),
    }
}

fn 取图标对齐方式(节点: &Value) -> Result<String, u32> {
    let 方式 = 节点
        .get("图标对齐方式")
        .and_then(Value::as_str)
        .unwrap_or("上");
    match 方式 {
        "上" | "左" | "中" | "右" => Ok(方式.to_string()),
        _ => Err(错误码::内容不合法),
    }
}

fn 取列图片居右表(节点: &Value, 列数: usize) -> Result<Vec<bool>, u32> {
    取同长度数组(节点, "__列图片居右", 列数)?
        .iter()
        .map(|值| match 值 {
            Value::Null => Ok(false),
            _ => 值.as_bool().ok_or(错误码::内容不合法),
        })
        .collect()
}

fn 取行缩进表(节点: &Value, 行数: usize) -> Result<Vec<usize>, u32> {
    取同长度数组(节点, "__表项缩进", 行数)?
        .iter()
        .map(|值| match 值 {
            Value::Null => Ok(0),
            _ => 值.as_u64().map(|数| 数 as usize).ok_or(错误码::内容不合法),
        })
        .collect()
}

fn 取选中行序号表(节点: &Value, 行数: usize) -> Vec<usize> {
    let 原始值 = 节点.get("__选中").or_else(|| 节点.get("现行选中项"));
    let 值表: Vec<String> = match 原始值 {
        Some(Value::String(单个)) if !单个.is_empty() => vec![单个.clone()],
        Some(Value::Number(单个)) => vec![单个.to_string()],
        Some(Value::Array(多个)) => 多个
            .iter()
            .filter_map(|项| match 项 {
                Value::String(文本) => Some(文本.clone()),
                Value::Number(数值) => Some(数值.to_string()),
                _ => None,
            })
            .collect(),
        _ => Vec::new(),
    };
    值表
        .iter()
        .filter_map(|值| 值.parse::<usize>().ok())
        .filter(|序号| *序号 < 行数)
        .collect()
}

/// 将自适应声明解析为实例内唯一的像素列宽，后续数据编辑不重算尺寸。
pub(crate) fn 固化表格列宽(节点: &mut Value) -> Result<(), u32> {
    if 节点.get("类型").and_then(Value::as_str) != Some("表格") {
        return Ok(());
    }
    let 列定义 = 节点
        .get("列")
        .and_then(Value::as_array)
        .ok_or(错误码::内容不合法)?;
    let 行数据 = 节点
        .get("行")
        .and_then(Value::as_array)
        .ok_or(错误码::内容不合法)?;
    let 列宽结果 = 取列宽表(节点, 列定义, 行数据)?;
    节点["列宽"] = serde_json::json!(列宽结果);
    Ok(())
}

/// 拼装一张表格卡片。
pub(crate) fn 拼装表格(节点: &Value, 状态: &mut 渲染状态) -> Result<String, u32> {
    let 列定义 = 节点
        .get("列")
        .or_else(|| 节点.get("报表列"))
        .and_then(|列项| 列项.as_array())
        .ok_or(错误码::内容不合法)?;
    let 行数据 = 节点
        .get("行")
        .and_then(|行项| 行项.as_array())
        .ok_or(错误码::内容不合法)?;
    let 列宽表 = 取列宽表(节点, 列定义, 行数据)?;
    let 列对齐字符串表 = 取列对齐表(节点, 列定义.len())?;
    let 列对齐表: Vec<&str> = 列对齐字符串表.iter().map(String::as_str).collect();
    let 选择模式 = 取选择模式(节点)?;
    let 勾选列 = 取逻辑字段(节点, "勾选列", Some("是否有检查框"), false)?;
    let 检查字段 = if 节点.get("__检查状态").is_some() {
        "__检查状态"
    } else {
        "检查框状态"
    };
    let 检查状态表 = 取同长度数组(节点, 检查字段, 行数据.len())?;
    if 检查状态表.iter().any(|状态值| {
        !状态值.is_null() && !状态值.is_boolean() && !matches!(状态值.as_u64(), Some(0 | 1))
    }) {
        return Err(错误码::内容不合法);
    }
    let 排序方式 = match 节点.get("排序方式") {
        None => "自动",
        Some(值) => match 值.as_str().ok_or(错误码::内容不合法)? {
            "不排序" | "正向" | "逆向" => "文本",
            比较类型 => 比较类型,
        },
    };
    if !matches!(排序方式, "自动" | "文本" | "数值" | "日期") {
        return Err(错误码::内容不合法);
    }
    let 选中行序号表 = 取选中行序号表(节点, 行数据.len());
    let 无表头 = 取逻辑字段(节点, "无表头", None, false)?;
    let 显示表格线 = 取逻辑字段(节点, "显示表格线", None, true)?;
    let 标题换行 = 取逻辑字段(节点, "标题自动换行", None, false)?;
    let 列可拖动 = 取逻辑字段(节点, "表列可拖动", None, false)?;
    let 热点跟踪 = 取逻辑字段(节点, "热点跟踪", None, false)?;
    let 手形指针 = 取逻辑字段(节点, "手形指针", None, false)?;
    let 标注热点 = 取逻辑字段(节点, "标注热点", None, false)?;
    let 标注非热点 = 取逻辑字段(节点, "标注非热点", None, false)?;
    let 允许编辑 = 取逻辑字段(节点, "允许编辑", None, false)?;
    let 自动排列图标 = 取逻辑字段(节点, "自动排列图标", None, true)?;
    let 平面滚动条 = 取逻辑字段(节点, "平面滚动条", None, false)?;
    let 始终显示选择项 = 取逻辑字段(节点, "始终显示选择项", None, true)?;
    let 视图模式 = 取视图模式(节点)?;
    let 图标对齐方式 = 取图标对齐方式(节点)?;
    let 图标间距 = match 节点.get("图标间距") {
        None => 8usize,
        Some(间距值) => {
            let 像素 = 间距值.as_u64().ok_or(错误码::内容不合法)? as usize;
            if !(0..=40).contains(&像素) {
                return Err(错误码::内容不合法);
            }
            像素
        }
    };
    let 表头图标表 = 取图片资源表(节点, "表头图片组", "__列图片", 列定义.len())?;
    let 表头图标居右表 = 取列图片居右表(节点, 列定义.len())?;
    let 行图标表 = 取图片资源表(节点, "图片组", "__表项图片", 行数据.len())?;
    let 行状态图标表 = 取图片资源表(节点, "状态图片组", "__表项状态图片", 行数据.len())?;
    let 行缩进表 = 取行缩进表(节点, 行数据.len())?;
    let 行提示表 = 取同长度数组(节点, "__表项提示", 行数据.len())?;
    let 列提示表 = 取同长度数组(节点, "列提示", 列定义.len())?;
    let 编辑单元格 = 取编辑单元格(节点)?;
    let 结束编辑文本 = 取对象文本(节点, "结束编辑文本");
    let 滚动目标 = 节点
        .get("__滚动目标")
        .and_then(Value::as_u64)
        .map(|值| 值 as usize);
    let 斑马纹 = 取逻辑字段(节点, "斑马纹", None, false)?;
    let 表头固定 = 取逻辑字段(节点, "表头固定", None, false)?;
    let 外观变量 = 取形态变量(节点, "表格外观", &表格外观映射)?;
    let mut 容器样式 = crate::组件树::拼通用样式(节点, &外观变量);
    if 节点.get("可视").and_then(Value::as_bool) == Some(false) {
        容器样式.push_str(";display:none");
    }
    let 容器禁用 = 节点.get("禁止").and_then(Value::as_bool).unwrap_or(false);
    let 禁用属性 = if 容器禁用 {
        " inert aria-disabled=\"true\""
    } else {
        ""
    };
    let 组件标记 = 取对象文本(节点, "标记");
    if let Some(鼠标指针) = 节点.get("鼠标指针") {
        let 指针样式 = match 鼠标指针.as_str() {
            Some("默认") => "default",
            Some("手形") => "pointer",
            Some("文本") => "text",
            Some("等待") => "wait",
            Some("禁止") => "not-allowed",
            _ => return Err(错误码::内容不合法),
        };
        容器样式.push_str(&format!(";cursor:{指针样式}"));
    }
    if let Some(字体名称) = 节点.get("字体").and_then(|值| {
        值.as_str()
            .or_else(|| 值.get("名称").and_then(Value::as_str))
    }) {
        if 字体名称
            .chars()
            .any(|字符| !字符.is_alphanumeric() && !matches!(字符, ' ' | '-' | '_' | ','))
        {
            return Err(错误码::内容不合法);
        }
        容器样式.push_str(&format!(";font-family:{字体名称}"));
    }
    for (坐标字段, 样式字段) in [("左", "left"), ("上", "top")] {
        if let Some(坐标数值) = 节点.get(坐标字段).and_then(Value::as_f64) {
            容器样式.push_str(&format!(";position:relative;{样式字段}:{坐标数值}px"));
        }
    }
    // 滚动区放在内层：外层留出来放分页条，否则分页条会被卷进滚动区、压在 20 行下面看不见。
    let mut 滚动样式 = String::new();
    if 表头固定 {
        let 最大高度 = 节点
            .get("最大高度")
            .and_then(|高度项| 高度项.as_f64())
            .unwrap_or(0.0);
        if !(80.0..=4000.0).contains(&最大高度) {
            return Err(错误码::内容不合法);
        }
        滚动样式 = format!("max-height:{最大高度}px;overflow:auto");
    }
    let 斑马色 = 取对象文本(节点, "斑马纹色");
    if !斑马色.is_empty() {
        校验颜色值(&斑马色)?;
        容器样式.push_str(&format!(";--hs-row-alt:{斑马色}"));
    }
    let 可排序 = 取逻辑字段(节点, "可排序", Some("表头可单击"), false)?;
    let 换页 = 取逻辑字段(节点, "换页", None, true)?;
    let 每页行数 = if 换页 {
        match 节点.get("每页行数") {
            None => 0,
            Some(值) => {
                let 行数 = 值.as_u64().ok_or(错误码::内容不合法)? as usize;
                if 行数 > 500 {
                    return Err(错误码::内容不合法);
                }
                行数
            }
        }
    } else {
        0
    };
    // 句柄由外层统一签发（渲染一个节点就发一个），这里只取用，不另开实例。
    let 句柄 = 节点
        .get("__组件句柄")
        .and_then(|项| 项.as_u64())
        .unwrap_or(0);
    状态.需要组件引导脚本 = true;
    let 排序列 = 节点
        .get("__排序键")
        .and_then(|项| 项.as_str())
        .filter(|键文本| !键文本.is_empty())
        .and_then(|键文本| 列定义.iter().position(|列项| 列项.as_str() == Some(键文本)));
    let 升序 = 节点
        .get("__升序")
        .and_then(|项| 项.as_bool())
        .unwrap_or(true);
    if matches!(排序方式, "数值" | "日期")
        && let Some(列序) = 排序列
    {
        for 行项 in 行数据 {
            if let Some(值) = 取单元格(行项, 列序) {
                let 合法 = match 排序方式 {
                    "数值" => 值.is_null() || 取数值排序键(值).is_some(),
                    "日期" => 值.is_null() || 是日期文本(值),
                    _ => true,
                };
                if !合法 {
                    return Err(错误码::内容不合法);
                }
            }
        }
    }
    let 页码 = 节点.get("__页码").and_then(|项| 项.as_u64()).unwrap_or(1) as usize;
    let (本页行, 总页数) = 排序分页(行数据, 排序列, 升序, 排序方式, 每页行数, 页码);

    let 容器类 = format!(
        "hs-tree-node hs-card{}{}{}{}{}",
        if 斑马纹 { " 斑马纹" } else { "" },
        if 表头固定 { " 表头固定" } else { "" },
        if 无表头 { " 无表头" } else { "" },
        if 平面滚动条 {
            " 平面滚动条"
        } else {
            ""
        },
        if 始终显示选择项 {
            " 始终显示选择项"
        } else {
            ""
        }
    );
    let 条目行高 = 节点
        .get("条目行高")
        .map(|行高值| {
            行高值
                .as_u64()
                .ok_or(错误码::内容不合法)
                .map(|像素| 像素 as usize)
        })
        .transpose()?
        .map(|像素| {
            if (20..=200).contains(&像素) {
                Ok(像素)
            } else {
                Err(错误码::内容不合法)
            }
        })
        .transpose()?;
    let 呈现设置 = crate::业务实现::表格呈现设置 {
        列宽表: &列宽表,
        条目行高,
        列对齐表: &列对齐表,
        选择模式: &选择模式,
        勾选列,
        检查状态表: &检查状态表,
        选中行序号表: &选中行序号表,
        可排序,
        排序列,
        升序,
        组件句柄: 句柄,
        无表头,
        显示表格线,
        标题换行,
        列可拖动,
        表头图标表: &表头图标表,
        表头图标居右表: &表头图标居右表,
        行图标表: &行图标表,
        单元格图片: 节点.get("__单元格图片").unwrap_or(&Value::Null),
        行状态图标表: &行状态图标表,
        行缩进表: &行缩进表,
        热点跟踪,
        手形指针,
        标注热点,
        标注非热点,
        允许编辑,
        编辑单元格,
        结束编辑文本: &结束编辑文本,
        滚动目标,
        视图模式: &视图模式,
        图标对齐方式: &图标对齐方式,
        行提示表: &行提示表,
        图标间距,
        列提示表: &列提示表,
        自动排列图标,
        平面滚动条,
        始终显示选择项,
    };
    let 表格文本 = 拼装表格行(列定义, &本页行, &呈现设置)?;
    let 分页文本 = if 每页行数 > 0 && 总页数 > 1 {
        let 当前页 = 页码.clamp(1, 总页数);
        let 上一页 = if 当前页 > 1 {
            format!(
                "<button class=\"hs-button\" data-hs-op=\"翻页\" data-hs-h=\"{句柄}\" data-hs-page=\"{}\">上一页</button>",
                当前页 - 1
            )
        } else {
            "<button class=\"hs-button\" disabled>上一页</button>".to_string()
        };
        let 下一页 = if 当前页 < 总页数 {
            format!(
                "<button class=\"hs-button\" data-hs-op=\"翻页\" data-hs-h=\"{句柄}\" data-hs-page=\"{}\">下一页</button>",
                当前页 + 1
            )
        } else {
            "<button class=\"hs-button\" disabled>下一页</button>".to_string()
        };
        format!(
            "<div class=\"hs-pager\" style=\"display:flex;gap:8px;align-items:center;margin-top:10px;font-size:13px\">{}<span style=\"opacity:.7\">第 {} / {} 页</span>{}</div>",
            上一页, 当前页, 总页数, 下一页
        )
    } else {
        String::new()
    };
    Ok(format!(
        "<div class=\"{}\" data-组件标记=\"{}\"{禁用属性} style=\"{}\"><div class=\"hs-table-scroll\" style=\"{}\">{}</div>{}</div>",
        容器类,
        转义网页文本(&组件标记),
        转义网页文本(&容器样式),
        转义网页文本(&滚动样式),
        表格文本,
        分页文本
    ))
}

#[cfg(test)]
#[path = "数据表格/测试.rs"]
mod 测试;

/// 根据排序后的真实行身份定位页码，浏览器不计算分页。
pub(crate) fn 定位表格页码(节点: &Value, 行序号: usize) -> Result<usize, u32> {
    let 行数据 = 节点
        .get("行")
        .and_then(Value::as_array)
        .ok_or(错误码::内容不合法)?;
    if 行序号 >= 行数据.len() {
        return Err(错误码::参数不合法);
    }
    let 列定义 = 节点
        .get("列")
        .and_then(Value::as_array)
        .ok_or(错误码::内容不合法)?;
    let 排序列 = 节点
        .get("__排序键")
        .and_then(Value::as_str)
        .and_then(|键名| 列定义.iter().position(|列值| 列值.as_str() == Some(键名)));
    let 升序 = 节点.get("__升序").and_then(Value::as_bool).unwrap_or(true);
    let 排序方式 = 节点
        .get("排序方式")
        .and_then(Value::as_str)
        .unwrap_or("自动");
    let (全部行, _) = 排序分页(行数据, 排序列, 升序, 排序方式, 0, 1);
    let 每页行数 = 节点.get("每页行数").and_then(Value::as_u64).unwrap_or(0) as usize;
    let 显示位置 = 全部行
        .iter()
        .position(|(原序号, _)| *原序号 == 行序号)
        .ok_or(错误码::参数不合法)?;
    Ok(显示位置
        .checked_div(每页行数)
        .map(|页序号| 页序号 + 1)
        .unwrap_or(1))
}
