//! 组件实例：渲染出来的可交互组件在底座里的身份与状态。
//!
//! 口径与「提交任务拿任务句柄」一致：拉起时登记一个实例、签发一个组件句柄；
//! 之后的排序、翻页都拿句柄进来、由底座按存下的声明与状态重算，只回这一个组件的片段。
//! 页面不再原位计算，业务项目也不写前端算法。
//!
//! 回收按归属：每个实例记着归属串与最后访问时刻；释放按句柄、回收按归属，绝不按端口盲杀。

use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Mutex, OnceLock};
use std::time::{SystemTime, UNIX_EPOCH};

use serde_json::{Map, Value};

use crate::编号与码面::错误码;

/// 实例空闲多久算废弃（毫秒）。单页界面用不到这么久，超时即回收。
pub(crate) const 实例空闲上限毫秒: u64 = 30 * 60 * 1000;
/// 单次渲染 + 累积最多留多少个实例，防止长跑服务无限涨。
pub(crate) const 实例数量上限: usize = 20000;

static 下一个句柄: AtomicU64 = AtomicU64::new(100_000);
static 实例表: OnceLock<Mutex<HashMap<u64, 组件实例>>> = OnceLock::new();

/// 一个已经拉起、还活着的组件。
pub(crate) struct 组件实例 {
    /// 拉起时那份节点声明：重算时按它重渲染，不回头问调用方要。
    pub(crate) 节点: Value,
    /// 归属串（一次渲染一个），释放与回收都按它。
    pub(crate) 归属: String,
    pub(crate) 排序键: String,
    pub(crate) 升序: bool,
    pub(crate) 页码: usize,
    /// 父组件句柄：子组件的声明在父的「子」数组里也有一份，改动要同步回去。
    pub(crate) 父句柄: Option<u64>,
    pub(crate) 最后访问: u64,
}

static 归属序号: AtomicU64 = AtomicU64::new(1);

/// 一次渲染的归属标记：时间戳 + 递增序号，同毫秒内也不会撞。
pub(crate) fn 新归属标记() -> String {
    format!("{}-{}", 现在毫秒(), 归属序号.fetch_add(1, Ordering::SeqCst))
}

fn 现在毫秒() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|时长| 时长.as_millis() as u64)
        .unwrap_or(0)
}

fn 表() -> &'static Mutex<HashMap<u64, 组件实例>> {
    实例表.get_or_init(|| Mutex::new(HashMap::new()))
}

fn 加锁() -> std::sync::MutexGuard<'static, HashMap<u64, 组件实例>> {
    match 表().lock() {
        Ok(守卫) => 守卫,
        Err(中毒) => 中毒.into_inner(),
    }
}

/// 清掉超时未访问的实例，返回清掉的条数。
pub(crate) fn 回收超时() -> usize {
    let 此刻 = 现在毫秒();
    let mut 表项 = 加锁();
    let 废弃键表: Vec<u64> = 表项
        .iter()
        .filter(|(_, 实例)| 此刻.saturating_sub(实例.最后访问) > 实例空闲上限毫秒)
        .map(|(句柄, _)| *句柄)
        .collect();
    for 句柄 in &废弃键表 {
        表项.remove(句柄);
    }
    废弃键表.len()
}

/// 表格字段在实例边界归一，渲染、操作与状态始终读取同一份声明。
pub(crate) fn 规范表格声明(节点: &mut Value) {
    if 节点.get("类型").and_then(Value::as_str) != Some("表格") {
        return;
    }
    let Some(对象) = 节点.as_object_mut() else {
        return;
    };
    for (原字段, 目标字段) in [
        ("报表列", "列"),
        ("表项", "行"),
        ("是否有检查框", "勾选列"),
        ("表头可单击", "可排序"),
    ] {
        if let Some(字段值) = 对象.remove(原字段) {
            对象.entry(目标字段.to_string()).or_insert(字段值);
        }
    }
    for (原字段, 目标字段) in [
        ("文本颜色", "文字颜色"),
        ("背景颜色", "背景"),
        ("左边", "左"),
        ("顶边", "上"),
        ("宽度", "宽"),
        ("高度", "高"),
    ] {
        if let Some(字段值) = 对象.remove(原字段) {
            对象.entry(目标字段.to_string()).or_insert(字段值);
        }
    }
    let 字体设置 = 对象
        .get("字体")
        .and_then(Value::as_object)
        .cloned()
        .unwrap_or_default();
    if let Some(字体大小) = 字体设置.get("大小") {
        对象.entry("字号".to_string()).or_insert(字体大小.clone());
    }
    if 字体设置.get("加粗").and_then(Value::as_bool) == Some(true) {
        对象.entry("字重".to_string()).or_insert(Value::from(700));
    }
    let mut 表格外观 = 对象
        .get("表格外观")
        .and_then(Value::as_object)
        .cloned()
        .unwrap_or_default();
    for (原字段, 外观字段) in [
        ("文字颜色", "单元格文字颜色"),
        ("文本背景色", "单元格背景"),
        ("字号", "字号"),
        ("字体大小", "字号"),
    ] {
        if let Some(字段值) = 对象.get(原字段) {
            表格外观
                .entry(外观字段.to_string())
                .or_insert(字段值.clone());
        }
    }
    if !表格外观.is_empty() {
        对象.insert("表格外观".to_string(), Value::Object(表格外观));
    }
    let 排序方向 = 对象
        .get("排序方向")
        .and_then(Value::as_str)
        .or_else(|| {
            对象
                .get("排序方式")
                .and_then(Value::as_str)
                .filter(|文本| matches!(*文本, "不排序" | "正向" | "逆向"))
        })
        .map(str::to_string);
    if let Some(排序方向) = 排序方向
        && !对象.contains_key("__排序键")
        && 排序方向 != "不排序"
        && let Some(首列名) = 对象
            .get("列")
            .and_then(Value::as_array)
            .and_then(|列数组| 列数组.first())
            .cloned()
    {
        对象.insert("__排序键".to_string(), 首列名);
        对象.insert(
            "__升序".to_string(),
            Value::from(!matches!(排序方向.as_str(), "逆向" | "降序")),
        );
    }
    if !对象.contains_key("选择模式") {
        let 模式 = if 对象.get("单一选择").and_then(Value::as_bool) == Some(true) {
            "单选"
        } else if 对象.get("整行选择").and_then(Value::as_bool) == Some(true) {
            "整行"
        } else if 对象.get("单一选择").and_then(Value::as_bool) == Some(false) {
            "多选"
        } else {
            "不选"
        };
        对象.insert("选择模式".to_string(), Value::from(模式));
    }
    if let Some(原选择) = 对象.remove("现行选中项") {
        let 选择数组: Vec<Value> = match 原选择 {
            Value::Array(数组) => 数组
                .into_iter()
                .map(|值| {
                    Value::from(
                        值.as_str()
                            .map(str::to_string)
                            .unwrap_or_else(|| 值.to_string()),
                    )
                })
                .collect(),
            Value::Null => Vec::new(),
            值 => vec![Value::from(
                值.as_str()
                    .map(str::to_string)
                    .unwrap_or_else(|| 值.to_string()),
            )],
        };
        let 新选择 = if 对象.get("选择模式").and_then(Value::as_str) == Some("多选") {
            Value::Array(选择数组)
        } else {
            选择数组.first().cloned().unwrap_or(Value::from(""))
        };
        对象.entry("__选中".to_string()).or_insert(新选择);
    }
}

/// 登记一个组件实例并签发句柄。节点里若已带组件句柄（重渲染）就复用，不再新建。
pub(crate) fn 登记实例(节点: &Value, 归属: &str, 父句柄: Option<u64>) -> u64 {
    回收超时();
    if let Some(旧句柄) = 节点.get("__组件句柄").and_then(|项| 项.as_u64())
        && 加锁().contains_key(&旧句柄)
    {
        触碰(旧句柄);
        return 旧句柄;
    }
    let 句柄 = 下一个句柄.fetch_add(1, Ordering::SeqCst);
    let mut 规范节点 = 节点.clone();
    规范表格声明(&mut 规范节点);
    let 初始排序键 = 规范节点
        .get("__排序键")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();
    let 初始升序 = 规范节点
        .get("__升序")
        .and_then(Value::as_bool)
        .unwrap_or(true);
    let 实例 = 组件实例 {
        节点: 规范节点,
        归属: 归属.to_string(),
        排序键: 初始排序键,
        升序: 初始升序,
        页码: 1,
        父句柄,
        最后访问: 现在毫秒(),
    };
    let mut 表项 = 加锁();
    if 表项.len() >= 实例数量上限 {
        // 满了先清超时；还满就丢最早访问的那个，句柄从此失效，不复用。
        let 最早 = 表项
            .iter()
            .min_by_key(|(_, 实例)| 实例.最后访问)
            .map(|(句柄, _)| *句柄);
        if let Some(键) = 最早 {
            表项.remove(&键);
        }
    }
    表项.insert(句柄, 实例);
    句柄
}

fn 触碰(句柄: u64) {
    if let Some(实例) = 加锁().get_mut(&句柄) {
        实例.最后访问 = 现在毫秒();
    }
}

/// 释放一个句柄；不存在返回假（幂等，不报错）。
pub(crate) fn 释放(句柄: u64) -> bool {
    加锁().remove(&句柄).is_some()
}

/// 改一个实例的排序 / 翻页状态，返回取出来的那份节点声明（带组件句柄）。
pub(crate) fn 改状态(
    句柄: u64,
    新排序键: Option<String>,
    新升序: Option<bool>,
    新页码: Option<usize>,
) -> Result<Value, u32> {
    let mut 表项 = 加锁();
    let 实例 = 表项.get_mut(&句柄).ok_or(错误码::组件句柄无效)?;
    实例.最后访问 = 现在毫秒();
    if let Some(键文本) = 新排序键 {
        // 同一列再点一次 = 换方向；换列 = 从升序起。
        if 实例.排序键 == 键文本 {
            实例.升序 = !实例.升序;
        } else {
            实例.排序键 = 键文本;
            实例.升序 = true;
        }
    }
    if let Some(方向) = 新升序 {
        实例.升序 = 方向;
    }
    if let Some(页码) = 新页码 {
        实例.页码 = 页码.max(1);
    }
    let mut 节点 = 实例.节点.clone();
    if let Some(对象) = 节点.as_object_mut() {
        对象.insert("__组件句柄".to_string(), Value::from(句柄));
        对象.insert("__排序键".to_string(), Value::from(实例.排序键.clone()));
        对象.insert("__升序".to_string(), Value::from(实例.升序));
        对象.insert("__页码".to_string(), Value::from(实例.页码 as u64));
    }
    实例.节点 = 节点.clone();
    let 父句柄 = 实例.父句柄;
    同步到父(句柄, 父句柄, &节点, &mut 表项);
    Ok(节点)
}

/// 取出一个实例的节点声明（重算用）。句柄不存在报「组件句柄无效」。
pub(crate) fn 取节点(句柄: u64) -> Result<Value, u32> {
    let mut 表项 = 加锁();
    let 实例 = 表项.get_mut(&句柄).ok_or(错误码::组件句柄无效)?;
    实例.最后访问 = 现在毫秒();
    let mut 节点 = 实例.节点.clone();
    节点["__组件句柄"] = Value::from(句柄);
    节点["__排序键"] = Value::from(实例.排序键.clone());
    节点["__升序"] = Value::from(实例.升序);
    节点["__页码"] = Value::from(实例.页码 as u64);
    Ok(节点)
}

/// 改一个实例的节点声明：改完回带组件句柄的新声明，供重渲染复用同一个句柄。
pub(crate) fn 改节点<改法>(句柄: u64, 改法: 改法) -> Result<Value, u32>
where
    改法: FnOnce(&mut Map<String, Value>),
{
    let mut 表项 = 加锁();
    let 实例 = 表项.get_mut(&句柄).ok_or(错误码::组件句柄无效)?;
    实例.最后访问 = 现在毫秒();
    let 对象 = match 实例.节点.as_object_mut() {
        Some(对象) => 对象,
        None => return Err(错误码::组件句柄无效),
    };
    改法(对象);
    if let Some(排序键) = 对象.get("__排序键").and_then(Value::as_str) {
        实例.排序键 = 排序键.to_string();
    }
    if let Some(升序) = 对象.get("__升序").and_then(Value::as_bool) {
        实例.升序 = 升序;
    }
    if let Some(页码) = 对象.get("__页码").and_then(Value::as_u64) {
        实例.页码 = 页码.max(1) as usize;
    }
    规范表格声明(&mut 实例.节点);
    crate::组件树::固化表格列宽(&mut 实例.节点)?;
    实例.节点["__组件句柄"] = Value::from(句柄);
    实例.节点["__排序键"] = Value::from(实例.排序键.clone());
    实例.节点["__升序"] = Value::from(实例.升序);
    实例.节点["__页码"] = Value::from(实例.页码 as u64);
    let 父 = 实例.父句柄;
    let 新节点 = 实例.节点.clone();
    同步到父(句柄, 父, &新节点, &mut 表项);
    let mut 回执 = 新节点;
    if let Some(回执对象) = 回执.as_object_mut() {
        回执对象.insert("__组件句柄".to_string(), Value::from(句柄));
    }
    Ok(回执)
}

/// 往一个实例的节点声明里塞一个子节点，并返回新签发的子句柄。
pub(crate) fn 追加子节点(
    句柄: u64, 子节点: Value, 位置: Option<usize>
) -> Result<u64, u32> {
    // 先把归属取出来、放掉锁，再登记：登记内部还要加锁，同一把锁不可重入。
    let 归属文本 = {
        let mut 表项 = 加锁();
        match 表项.get_mut(&句柄) {
            Some(实例) => {
                实例.最后访问 = 现在毫秒();
                实例.归属.clone()
            }
            None => return Err(错误码::组件句柄无效),
        }
    };
    let 子句柄 = 登记实例(&子节点, &归属文本, Some(句柄));
    let mut 表项 = 加锁();
    let 实例 = 表项.get_mut(&句柄).ok_or(错误码::组件句柄无效)?;
    实例.最后访问 = 现在毫秒();
    let 对象 = match 实例.节点.as_object_mut() {
        Some(对象) => 对象,
        None => return Err(错误码::组件句柄无效),
    };
    let 子表 = 对象
        .entry("子".to_string())
        .or_insert_with(|| Value::Array(Vec::new()));
    let 数组 = match 子表.as_array_mut() {
        Some(数组) => 数组,
        None => return Err(错误码::参数不合法),
    };
    let mut 带句柄 = 子节点;
    if let Some(子对象) = 带句柄.as_object_mut() {
        子对象.insert("__组件句柄".to_string(), Value::from(子句柄));
    }
    match 位置 {
        Some(序) if 序 < 数组.len() => 数组.insert(序, 带句柄),
        _ => 数组.push(带句柄),
    }
    Ok(子句柄)
}

/// 把子组件的新声明同步回父容器的「子」数组。
///
/// 父容器渲染子组件时读的是自身数组里的那份声明，不同步就会出现
/// 「子组件改了、父容器还照旧画」的假象（移动窗口不生效就是这么来的）。
fn 同步到父(
    句柄: u64, 父句柄: Option<u64>, 新节点: &Value, 表项: &mut HashMap<u64, 组件实例>
) {
    let 父 = match 父句柄 {
        Some(父键) => 父键,
        None => return,
    };
    let 父实例 = match 表项.get_mut(&父) {
        Some(实例) => 实例,
        None => return,
    };
    let 子表 = match 父实例.节点.get_mut("子").and_then(|项| 项.as_array_mut()) {
        Some(数组) => 数组,
        None => return,
    };
    for 子项 in 子表.iter_mut() {
        let 是这一个 = 子项
            .get("__组件句柄")
            .and_then(|项| 项.as_u64())
            .map(|键| 键 == 句柄)
            .unwrap_or(false);
        if 是这一个 {
            *子项 = 新节点.clone();
            if let Some(对象) = 子项.as_object_mut() {
                对象.insert("__组件句柄".to_string(), Value::from(句柄));
            }
            return;
        }
    }
}
/// 读一个实例的状态（给调用方对齐界面用）。
pub(crate) fn 读状态(句柄: u64) -> Result<Value, u32> {
    let mut 表项 = 加锁();
    let 实例 = 表项.get_mut(&句柄).ok_or(错误码::组件句柄无效)?;
    实例.最后访问 = 现在毫秒();
    let mut 状态 = Map::new();
    状态.insert("句柄".to_string(), Value::from(句柄));
    状态.insert("归属".to_string(), Value::from(实例.归属.clone()));
    状态.insert("排序键".to_string(), Value::from(实例.排序键.clone()));
    状态.insert("升序".to_string(), Value::from(实例.升序));
    状态.insert("页码".to_string(), Value::from(实例.页码 as u64));
    if 实例.节点.get("类型").and_then(Value::as_str) == Some("表格") {
        let 原始选择 = 实例.节点.get("__选中").cloned().unwrap_or(Value::Null);
        let 选择键表: Vec<String> = match &原始选择 {
            Value::String(单个) if !单个.is_empty() => vec![单个.clone()],
            Value::Array(多个) => 多个
                .iter()
                .filter_map(|项| 项.as_str().map(str::to_string))
                .collect(),
            _ => Vec::new(),
        };
        let 行数据 = 实例
            .节点
            .get("行")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        let 列定义 = 实例
            .节点
            .get("列")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        let mut 行序号表 = Vec::new();
        let mut 选中行表 = Vec::new();
        for 选择键 in 选择键表 {
            if let Ok(行序号) = 选择键.parse::<usize>()
                && let Some(行值) = 行数据.get(行序号)
            {
                行序号表.push(Value::from(行序号 as u64));
                选中行表.push(行值.clone());
            }
        }
        状态.insert("选中项".to_string(), 原始选择);
        状态.insert("选中数".to_string(), Value::from(行序号表.len() as u64));
        状态.insert("选中行序号".to_string(), Value::Array(行序号表));
        状态.insert("选中行".to_string(), Value::Array(选中行表));
        状态.insert("行数".to_string(), Value::from(行数据.len() as u64));
        状态.insert("列数".to_string(), Value::from(列定义.len() as u64));
        状态.insert("行".to_string(), Value::Array(行数据));
        状态.insert("列".to_string(), Value::Array(列定义));
        for 字段名 in [
            "列宽",
            "列对齐方式",
            "列图片",
            "列图片居右",
            "表项数值",
            "表项图片",
            "表项状态图片",
            "表项缩进",
            "检查框状态",
            "查询结果",
            "最后事件",
            "事件记录",
            "结束编辑文本",
            "编辑单元格",
            "查找结果",
            "滚动目标",
            "排列方式",
        ] {
            if let Some(字段值) = 实例
                .节点
                .get(format!("__{字段名}"))
                .or_else(|| 实例.节点.get(字段名))
            {
                状态.insert(字段名.to_string(), 字段值.clone());
            }
        }
    }
    Ok(Value::Object(状态))
}

#[cfg(test)]
mod 测试 {
    use super::*;
    use serde_json::json;

    #[test]
    fn 表格状态回传选中原始行() {
        let 表格节点 = json!({
            "类型":"表格",
            "列":["名称"],
            "行":[["第一行"],["第二行"]]
        });
        let 句柄 = 登记实例(&表格节点, "表格状态测试", None);
        改节点(句柄, |对象| {
            对象.insert("__选中".to_string(), Value::from("1"));
        })
        .unwrap();
        let 状态 = 读状态(句柄).unwrap();
        assert_eq!(状态["选中项"], json!("1"));
        assert_eq!(状态["选中行序号"], json!([1]));
        assert_eq!(状态["选中行"], json!([["第二行"]]));
        assert!(释放(句柄));
    }
}
