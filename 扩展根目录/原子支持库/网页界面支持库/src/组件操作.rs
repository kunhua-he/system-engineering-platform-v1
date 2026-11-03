//! 组件操作：拿组件句柄进来，由底座按实例存下的声明重算，只回这一个组件的片段。
//!
//! 页面只负责把「句柄 + 操作名 + 参数」搬回来；排序怎么比、翻页切哪一段、
//! 移动是绝对还是相对、嵌套进去的子组件怎么发句柄，全部在这里定。
//! 属性名也可以直接当操作名（`编辑框.文本 = …`），落到「设置」那条分支上。
//!
//! 回执统一是 JSON：`{"片段": "<html>", "句柄组": [数字…]}`。
//! 片段只含这一个组件，调用方原位替换即可，不整页刷新。

use serde_json::{Map, Value, json};

use crate::组件实例;
use crate::组件树;
use crate::编号与码面::错误码;

#[path = "组件操作/表格事件.rs"]
mod 表格事件;
#[cfg(test)]
#[path = "组件操作/表格回归.rs"]
mod 表格回归;
#[path = "组件操作/表格操作.rs"]
mod 表格操作;

/// 动作名表：这几个是「动作」，其余名字按「设置该属性」处理。
pub(crate) const 操作_排序: &str = "排序";
pub(crate) const 操作_翻页: &str = "翻页";
pub(crate) const 操作_移动: &str = "移动";
pub(crate) const 操作_设置: &str = "设置";
pub(crate) const 操作_嵌套: &str = "嵌套";
pub(crate) const 操作_展开: &str = "展开";
pub(crate) const 操作_收起: &str = "收起";
pub(crate) const 操作_选中: &str = "选中";
pub(crate) const 操作_上移: &str = "上移";
pub(crate) const 操作_下移: &str = "下移";
pub(crate) const 操作_追加: &str = "追加";
pub(crate) const 操作_删除: &str = "删除";

/// 一次嵌套最多加多少个子组件，防一份坏声明把界面撑爆。
const 嵌套上限: usize = 50;

fn 取参数对象(参数原文: &str) -> Result<Value, u32> {
    let 去空格 = 参数原文.trim();
    if 去空格.is_empty() {
        return Ok(Value::Object(Map::new()));
    }
    serde_json::from_str(去空格).map_err(|_| 错误码::参数不合法)
}

/// 重渲染这一个组件，回 JSON 回执（片段 + 本次新签发的句柄组）。
fn 回执(节点: &Value, 句柄组: Vec<u64>) -> Result<(u32, Vec<u8>), u32> {
    let 片段文本 = 组件树::渲染单节点(节点)?;
    let 包 = json!({ "片段": 片段文本, "句柄组": 句柄组 });
    let 文本 = serde_json::to_string(&包).map_err(|_| 错误码::内容不合法)?;
    Ok((4, 文本.into_bytes()))
}

/// 取当前值里的数值与单位：`120` / `"120px"` / `"50%"` → (数值, 单位)。
fn 拆数值(当前: Option<&Value>) -> Option<(f64, String)> {
    match 当前 {
        Some(Value::Number(数)) => 数.as_f64().map(|值| (值, String::new())),
        Some(Value::String(文本)) => {
            let 去空格 = 文本.trim();
            let 数字部: String = 去空格
                .chars()
                .take_while(|字| 字.is_ascii_digit() || *字 == '.' || *字 == '-' || *字 == '+')
                .collect();
            let 单位 = 去空格[数字部.len()..].to_string();
            数字部.parse::<f64>().ok().map(|值| (值, 单位))
        }
        _ => None,
    }
}

/// 数值参数的三条语义：给数字 = 绝对值；给 `"+20"` / `"-20"` = 在当前值上增减；
/// 不给 / 给 null / 给空串 = 继承原值（返回 None，调用方就不写这个键）。
fn 解析尺寸(参数: &Value, 键: &str, 当前: Option<&Value>) -> Result<Option<Value>, u32> {
    let 原值 = match 参数.get(键) {
        Some(值) => 值,
        None => return Ok(None),
    };
    match 原值 {
        Value::Null => Ok(None),
        Value::Number(数) => Ok(Some(Value::Number(数.clone()))),
        Value::String(文本) => {
            let 去空格 = 文本.trim();
            if 去空格.is_empty() {
                return Ok(None);
            }
            let 首位 = 去空格.chars().next().unwrap_or(' ');
            if 首位 != '+' && 首位 != '-' {
                return Ok(Some(json!(去空格)));
            }
            let 增量 = 去空格.parse::<f64>().map_err(|_| 错误码::参数不合法)?;
            let (基数, 单位) = 拆数值(当前).unwrap_or((0.0, String::new()));
            let 新值 = 基数 + 增量;
            if 单位.is_empty() {
                return Ok(Some(json!(新值)));
            }
            let 数字文本 = if 新值.fract() == 0.0 {
                format!("{}", 新值 as i64)
            } else {
                format!("{新值}")
            };
            Ok(Some(json!(format!("{数字文本}{单位}"))))
        }
        _ => Err(错误码::参数不合法),
    }
}

/// 移动：只改给了值的那个维度，其余维度继承原值。
fn 移动节点(句柄: u64, 参数: &Value) -> Result<(u32, Vec<u8>), u32> {
    let 节点 = 组件实例::取节点(句柄)?;
    let mut 改动: Vec<(String, Value)> = Vec::new();
    for 键 in ["左", "上", "宽", "高"] {
        if let Some(新值) = 解析尺寸(参数, 键, 节点.get(键))? {
            改动.push((键.to_string(), 新值));
        }
    }
    let 新节点 = 组件实例::改节点(句柄, |对象| {
        for (键, 值) in 改动 {
            对象.insert(键, 值);
        }
    })?;
    回执(&新节点, Vec::new())
}

/// 设置：把参数里的每个键写进节点声明。结构键（类型 / 子）不许改。
fn 设置属性(句柄: u64, 参数: &Value) -> Result<(u32, Vec<u8>), u32> {
    let 对象参数 = 参数.as_object().ok_or(错误码::参数不合法)?;
    if 对象参数.is_empty() {
        return Err(错误码::参数不合法);
    }
    for 键 in 对象参数.keys() {
        if 键 == "类型" || 键 == "子" || 键.starts_with("__") {
            return Err(错误码::参数不合法);
        }
    }
    let mut 待验节点 = 组件实例::取节点(句柄)?;
    for (键, 值) in 对象参数 {
        待验节点[键] = 值.clone();
    }
    if 待验节点.get("类型").and_then(Value::as_str) == Some("表格") {
        if 对象参数.contains_key("结束编辑文本") {
            return Err(错误码::参数不合法);
        }
        for (原字段, 目标字段) in [
            ("报表列", "列"),
            ("表项", "行"),
            ("是否有检查框", "勾选列"),
            ("表头可单击", "可排序"),
            ("文本颜色", "文字颜色"),
            ("背景颜色", "背景"),
            ("左边", "左"),
            ("顶边", "上"),
            ("宽度", "宽"),
            ("高度", "高"),
        ] {
            if 对象参数.contains_key(原字段) && !对象参数.contains_key(目标字段) {
                待验节点.as_object_mut().unwrap().remove(目标字段);
            }
        }
        if (对象参数.contains_key("单一选择") || 对象参数.contains_key("整行选择"))
            && !对象参数.contains_key("选择模式")
        {
            待验节点.as_object_mut().unwrap().remove("选择模式");
        }
        if let Some(字体对象) = 对象参数.get("字体").and_then(Value::as_object) {
            if let Some(字体大小) = 字体对象.get("大小") {
                待验节点["字号"] = 字体大小.clone();
            }
            if let Some(加粗状态) = 字体对象.get("加粗").and_then(Value::as_bool) {
                待验节点["字重"] = json!(if 加粗状态 { 700 } else { 400 });
            }
        }
        let mut 表格外观 = 待验节点
            .get("表格外观")
            .and_then(Value::as_object)
            .cloned()
            .unwrap_or_default();
        for (输入字段, 外观字段) in [
            ("文本颜色", "单元格文字颜色"),
            ("文字颜色", "单元格文字颜色"),
            ("文本背景色", "单元格背景"),
            ("字号", "字号"),
            ("字体大小", "字号"),
        ] {
            if let Some(字段值) = 对象参数.get(输入字段) {
                表格外观.insert(外观字段.to_string(), 字段值.clone());
            }
        }
        if 对象参数.contains_key("字体")
            && let Some(字体大小) = 待验节点.get("字号")
        {
            表格外观.insert("字号".to_string(), 字体大小.clone());
        }
        if !表格外观.is_empty() {
            待验节点["表格外观"] = Value::Object(表格外观);
        }
    }
    if 对象参数.contains_key("现行选中项") {
        待验节点.as_object_mut().unwrap().remove("__选中");
    }
    for (显示字段, 内部字段) in [
        ("图片组", "__表项图片"),
        ("状态图片组", "__表项状态图片"),
        ("表头图片组", "__列图片"),
    ] {
        if 对象参数.contains_key(显示字段) {
            待验节点.as_object_mut().unwrap().remove(内部字段);
        }
    }
    组件实例::规范表格声明(&mut 待验节点);
    组件树::渲染单节点(&待验节点)?;
    let 新节点 = 组件实例::改节点(句柄, |对象| {
        *对象 = 待验节点.as_object().unwrap().clone();
    })?;
    回执(&新节点, Vec::new())
}

/// 嵌套：往容器里插子组件，每个新子组件各发一个句柄，句柄组按插入顺序回。
fn 嵌套(句柄: u64, 参数: &Value) -> Result<(u32, Vec<u8>), u32> {
    let 子表 = 参数
        .get("子")
        .and_then(|项| 项.as_array())
        .ok_or(错误码::参数不合法)?;
    if 子表.is_empty() || 子表.len() > 嵌套上限 {
        return Err(错误码::参数不合法);
    }
    for 子项 in 子表 {
        let 子对象 = 子项.as_object().ok_or(错误码::参数不合法)?;
        match 子对象.get("类型").and_then(|项| 项.as_str()) {
            Some(类型文本) if !类型文本.is_empty() => {}
            _ => return Err(错误码::参数不合法),
        }
    }
    let 位置 = match 参数.get("位置") {
        Some(Value::Number(数)) => 数.as_u64().map(|序| 序 as usize),
        _ => None,
    };
    let mut 句柄组 = Vec::with_capacity(子表.len());
    for (序, 子项) in 子表.iter().enumerate() {
        let 插入位 = 位置.map(|起点| 起点 + 序);
        let 子句柄 = 组件实例::追加子节点(句柄, 子项.clone(), 插入位)?;
        句柄组.push(子句柄);
    }
    let 新节点 = 组件实例::取节点(句柄)?;
    回执(&新节点, 句柄组)
}

/// 取节点类型，决定这条操作归哪个组件用。
fn 节点类型(节点: &Value) -> String {
    节点
        .get("类型")
        .and_then(|项| 项.as_str())
        .unwrap_or_default()
        .to_string()
}

fn 取键(参数: &Value) -> Result<String, u32> {
    参数
        .get("键")
        .and_then(|项| 项.as_str())
        .filter(|文本| !文本.is_empty())
        .map(|文本| 文本.to_string())
        .ok_or(错误码::参数不合法)
}

/// 在一个字符串集合字段里加 / 删一个键（`__展开` / `__收起`）。
fn 改集合(对象: &mut Map<String, Value>, 字段: &str, 键: &str, 加: bool) {
    let 数组 = 对象
        .entry(字段.to_string())
        .or_insert_with(|| Value::Array(Vec::new()));
    let 项表 = match 数组.as_array_mut() {
        Some(项表) => 项表,
        None => return,
    };
    项表.retain(|项| 项.as_str() != Some(键));
    if 加 {
        项表.push(Value::from(键));
    }
}

/// 树型框 / 列表：展开与收起（只对树型框有意义）。
fn 展开收起(句柄: u64, 参数: &Value, 展开: bool) -> Result<(u32, Vec<u8>), u32> {
    let 键 = 取键(参数)?;
    let 节点 = 组件实例::取节点(句柄)?;
    if 节点类型(&节点) != "树型框" {
        return Err(错误码::参数不合法);
    }
    let 新节点 = 组件实例::改节点(句柄, |对象| {
        改集合(对象, "__展开", &键, 展开);
        改集合(对象, "__收起", &键, !展开);
    })?;
    回执(&新节点, Vec::new())
}

/// 选中：表格按「选择模式」决定单选/多选，勾选列复用同一操作；列表仍按「多选」字段决定字符串或数组。
fn 选中(句柄: u64, 参数: &Value) -> Result<(u32, Vec<u8>), u32> {
    let 键 = 取键(参数)?;
    let 节点 = 组件实例::取节点(句柄)?;
    let 多选 = if 节点类型(&节点) == "表格" {
        match 节点
            .get("选择模式")
            .and_then(|项| 项.as_str())
            .unwrap_or("不选")
        {
            "多选" => true,
            "单选" | "整行" => false,
            "不选" => return Err(错误码::参数不合法),
            _ => return Err(错误码::参数不合法),
        }
    } else {
        节点
            .get("多选")
            .and_then(|项| 项.as_bool())
            .unwrap_or(false)
    };
    let 新节点 = 组件实例::改节点(句柄, |对象| {
        if 多选 {
            let 已有: Vec<String> = match 对象.get("__选中") {
                Some(Value::Array(项表)) => 项表
                    .iter()
                    .filter_map(|项| 项.as_str().map(|文本| 文本.to_string()))
                    .collect(),
                Some(Value::String(单个)) => vec![单个.clone()],
                _ => Vec::new(),
            };
            let mut 新表: Vec<Value> = 已有
                .iter()
                .filter(|项| **项 != 键)
                .map(|项| Value::from(项.clone()))
                .collect();
            if 新表.len() == 已有.len() {
                新表.push(Value::from(键.clone()));
            }
            对象.insert("__选中".to_string(), Value::Array(新表));
        } else {
            let 现在 = 对象.get("__选中").and_then(|项| 项.as_str()).unwrap_or("");
            if 现在 == 键 {
                对象.insert("__选中".to_string(), Value::from(""));
            } else {
                对象.insert("__选中".to_string(), Value::from(键.clone()));
            }
        }
    })?;
    回执(&新节点, Vec::new())
}

/// 找条目数组：给了父键就找那一层的「子」，没给就是根层。
fn 条目数组<'a>(容器: &'a mut Value, 父键: Option<&str>) -> Option<&'a mut Vec<Value>> {
    let 数组 = 容器.get_mut("条目")?.as_array_mut()?;
    match 父键 {
        None => Some(数组),
        Some(键) => 找子(数组, 键),
    }
}

/// 在条目树里找某个键的「子」数组：先同层扫一遍，再逐层递归。
fn 找子<'a>(数组: &'a mut [Value], 键: &str) -> Option<&'a mut Vec<Value>> {
    // 本层命中就直接取它的「子」。
    let 本层 = 数组
        .iter()
        .position(|项| 项.get("键").and_then(|值| 值.as_str()) == Some(键));
    if let Some(序) = 本层 {
        return 数组[序].get_mut("子").and_then(|值| 值.as_array_mut());
    }
    // 本层没有就逐条往下一层找（一次只有一条活着的可变借用）。
    for 项 in 数组.iter_mut() {
        if let Some(子数组) = 项.get_mut("子").and_then(|值| 值.as_array_mut())
            && let Some(命中) = 找子(子数组, 键)
        {
            return Some(命中);
        }
    }
    None
}

/// 上移 / 下移：在所属层里换位置，越界就原地不动（不算错）。
fn 移条目(句柄: u64, 参数: &Value, 向上: bool) -> Result<(u32, Vec<u8>), u32> {
    let 键 = 取键(参数)?;
    let 父键 = 参数
        .get("父键")
        .and_then(|项| 项.as_str())
        .map(|文本| 文本.to_string());
    let mut 节点 = 组件实例::取节点(句柄)?;
    {
        let 数组 = 条目数组(&mut 节点, 父键.as_deref()).ok_or(错误码::参数不合法)?;
        let 位置 = 数组
            .iter()
            .position(|项| 项.get("键").and_then(|值| 值.as_str()) == Some(键.as_str()));
        if let Some(序) = 位置 {
            let 目标 = if 向上 {
                序.checked_sub(1)
            } else if 序 + 1 < 数组.len() {
                Some(序 + 1)
            } else {
                None
            };
            if let Some(到) = 目标 {
                数组.swap(序, 到);
            }
        }
    }
    let 回写 = 组件实例::改节点(句柄, |对象| {
        if let Some(条目) = 节点.get("条目").cloned() {
            对象.insert("条目".to_string(), 条目);
        }
    })?;
    回执(&回写, Vec::new())
}

/// 追加：把 `条目` 数组里的新条目接上去（树型框给了 `父键` 就加到那一层）。
fn 追加条目(句柄: u64, 参数: &Value) -> Result<(u32, Vec<u8>), u32> {
    let 新条目 = 参数
        .get("条目")
        .and_then(|项| 项.as_array())
        .cloned()
        .ok_or(错误码::参数不合法)?;
    if 新条目.is_empty() || 新条目.len() > 嵌套上限 {
        return Err(错误码::参数不合法);
    }
    let 父键 = 参数
        .get("父键")
        .and_then(|项| 项.as_str())
        .map(|文本| 文本.to_string());
    let mut 节点 = 组件实例::取节点(句柄)?;
    {
        let 数组 = 条目数组(&mut 节点, 父键.as_deref()).ok_or(错误码::参数不合法)?;
        for 项 in 新条目 {
            数组.push(项);
        }
    }
    let 回写 = 组件实例::改节点(句柄, |对象| {
        if let Some(条目) = 节点.get("条目").cloned() {
            对象.insert("条目".to_string(), 条目);
        }
    })?;
    回执(&回写, Vec::new())
}

/// 删除：按键从所属层摘掉一条。
fn 删除条目(句柄: u64, 参数: &Value) -> Result<(u32, Vec<u8>), u32> {
    let 键 = 取键(参数)?;
    let 父键 = 参数
        .get("父键")
        .and_then(|项| 项.as_str())
        .map(|文本| 文本.to_string());
    let mut 节点 = 组件实例::取节点(句柄)?;
    {
        let 数组 = 条目数组(&mut 节点, 父键.as_deref()).ok_or(错误码::参数不合法)?;
        数组.retain(|项| 项.get("键").and_then(|值| 值.as_str()) != Some(键.as_str()));
    }
    let 回写 = 组件实例::改节点(句柄, |对象| {
        if let Some(条目) = 节点.get("条目").cloned() {
            对象.insert("条目".to_string(), 条目);
        }
    })?;
    回执(&回写, Vec::new())
}

/// 4929 操作组件：排序 / 翻页 / 移动 / 设置 / 嵌套 / 树与列表七件。
///
/// 窗口的最小化与最大化不在这里：那件事由底座窗口脚本（已最小化 / 已最大化 约定）即时做，
/// 持久化归业务侧桌面壳。同一语义只留一处实现（2026-11-02 收敛）。
pub(crate) fn 操作组件(
    组件句柄: u64,
    操作名称: &str,
    参数原文: &str,
) -> Result<(u32, Vec<u8>), u32> {
    let 旧节点 = 组件实例::取节点(组件句柄)?;
    if 旧节点.get("类型").and_then(Value::as_str) == Some("表格") {
        let 操作参数 = 取参数对象(参数原文)?;
        if 操作名称 == "排序" {
            if 操作参数
                .get("升序")
                .is_some_and(|方向值| !方向值.is_boolean())
            {
                return Err(错误码::参数不合法);
            }
            let 键文本 = 操作参数
                .get("键")
                .and_then(Value::as_str)
                .ok_or(错误码::参数不合法)?;
            if !旧节点
                .get("列")
                .and_then(Value::as_array)
                .is_some_and(|列数组| 列数组.iter().any(|列值| 列值.as_str() == Some(键文本)))
            {
                return Err(错误码::参数不合法);
            }
            let mut 待验节点 = 旧节点.clone();
            待验节点["__排序键"] = Value::from(键文本);
            组件树::渲染单节点(&待验节点)?;
        }
        if 操作名称 == "选中" {
            let 行序号 = 操作参数
                .get("键")
                .and_then(Value::as_str)
                .and_then(|文本| 文本.parse::<usize>().ok())
                .ok_or(错误码::参数不合法)?;
            if 行序号
                >= 旧节点
                    .get("行")
                    .and_then(Value::as_array)
                    .map(Vec::len)
                    .unwrap_or(0)
            {
                return Err(错误码::参数不合法);
            }
        }
    }
    let 执行回执 = 执行组件操作(组件句柄, 操作名称, 参数原文)?;
    if 旧节点.get("类型").and_then(Value::as_str) == Some("表格") {
        let 操作参数 = 取参数对象(参数原文)?;
        表格事件::采集操作事件(组件句柄, 操作名称, &操作参数, &旧节点)?;
    }
    Ok(执行回执)
}

fn 执行组件操作(
    句柄: u64, 操作名: &str, 参数原文: &str
) -> Result<(u32, Vec<u8>), u32> {
    let 参数 = 取参数对象(参数原文)?;
    if let Some(回执) = 表格操作::尝试执行(句柄, 操作名, &参数)? {
        return Ok(回执);
    }
    match 操作名 {
        操作_排序 => {
            let 键文本 = 参数
                .get("键")
                .and_then(|项| 项.as_str())
                .ok_or(错误码::参数不合法)?
                .to_string();
            let 指定方向 = 参数
                .get("升序")
                .map(|方向值| 方向值.as_bool().ok_or(错误码::参数不合法))
                .transpose()?;
            // 换列从升序起、同列换方向、排序后回到第 1 页：都由改状态内部定。
            let 节点 = 组件实例::改状态(句柄, Some(键文本), 指定方向, Some(1))?;
            回执(&节点, Vec::new())
        }
        操作_翻页 => {
            let 页码 = 参数
                .get("页码")
                .and_then(|项| 项.as_u64())
                .ok_or(错误码::参数不合法)? as usize;
            if 页码 == 0 {
                return Err(错误码::参数不合法);
            }
            let 节点 = 组件实例::改状态(句柄, None, None, Some(页码))?;
            回执(&节点, Vec::new())
        }
        操作_移动 => 移动节点(句柄, &参数),
        操作_设置 => 设置属性(句柄, &参数),
        操作_嵌套 => 嵌套(句柄, &参数),
        操作_展开 => 展开收起(句柄, &参数, true),
        操作_收起 => 展开收起(句柄, &参数, false),
        操作_选中 => 选中(句柄, &参数),
        操作_上移 => 移条目(句柄, &参数, true),
        操作_下移 => 移条目(句柄, &参数, false),
        操作_追加 => 追加条目(句柄, &参数),
        操作_删除 => 删除条目(句柄, &参数),
        // 属性名直当操作名：`{"值": …}` 就是给这个属性赋值。
        属性名 => {
            let 值 = 参数.get("值").cloned().ok_or(错误码::参数不合法)?;
            let mut 单键 = Map::new();
            单键.insert(属性名.to_string(), 值);
            设置属性(句柄, &Value::Object(单键))
        }
    }
}

/// 4930 读组件状态：给调用方对齐界面用（句柄、归属、排序键、方向、页码）。
pub(crate) fn 读组件状态(句柄: u64) -> Result<(u32, Vec<u8>), u32> {
    let 状态值 = 组件实例::读状态(句柄)?;
    let 文本 = serde_json::to_string(&状态值).map_err(|_| 错误码::内容不合法)?;
    Ok((4, 文本.into_bytes()))
}

/// 4931 释放组件句柄：幂等，不存在返回假。
pub(crate) fn 释放组件句柄(句柄: u64) -> Result<(u32, Vec<u8>), u32> {
    let 释放成功 = 组件实例::释放(句柄);
    Ok((3, vec![if 释放成功 { 1 } else { 0 }]))
}
