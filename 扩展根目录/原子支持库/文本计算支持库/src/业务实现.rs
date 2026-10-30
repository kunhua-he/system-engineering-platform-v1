use std::collections::BTreeMap;

use crate::编号与码面::错误码;

const 对账上限字节: usize = 2097152;

// 选项键缺席 ⇒ 默认；类型不符也按默认（兼容优先：未知键忽略，不为坏值造失败）
fn 取选项逻辑(选项对象: &serde_json::Value, 条目键: &str, 默认值: bool) -> bool {
    选项对象
        .get(条目键)
        .and_then(serde_json::Value::as_bool)
        .unwrap_or(默认值)
}

fn 规范化条目(条目: &str, 忽略空白: bool, 忽略大小写: bool) -> String {
    let 去空白后 = if 忽略空白 {
        条目
            .chars()
            .filter(|单字符| !单字符.is_whitespace())
            .collect::<String>()
    } else {
        条目.trim().to_owned()
    };
    if 忽略大小写 {
        去空白后.to_lowercase()
    } else {
        去空白后
    }
}

// 多重集：同一条目出现两次就是 2，不退化成集合（问题 09 的根因正是集合比对）
fn 统计条目次数(
    源文本: &str,
    忽略空白: bool,
    忽略大小写: bool,
    按行切分: bool,
) -> BTreeMap<String, usize> {
    let mut 左表: BTreeMap<String, usize> = BTreeMap::new();
    let 条目表: Vec<&str> = if 按行切分 {
        源文本.lines().collect()
    } else {
        vec![源文本]
    };
    for 条目 in 条目表 {
        let 条目键 = 规范化条目(条目, 忽略空白, 忽略大小写);
        *左表.entry(条目键).or_insert(0) += 1;
    }
    左表
}

pub fn 执行多重集对账(源文本: &str, 派生文本: &str, 选项文本: &str) -> Result<String, u32> {
    if 源文本.len() > 对账上限字节 || 派生文本.len() > 对账上限字节 {
        return Err(错误码::文本资源受限);
    }
    let 选项对象 = if 选项文本.trim().is_empty() {
        serde_json::json!({})
    } else {
        let 解析值: serde_json::Value =
            serde_json::from_str(选项文本).map_err(|_| 错误码::文本参数不合法)?;
        if !解析值.is_object() {
            return Err(错误码::文本参数不合法);
        }
        解析值
    };
    let 忽略空白 = 取选项逻辑(&选项对象, "忽略空白", false);
    let 忽略大小写 = 取选项逻辑(&选项对象, "忽略大小写", false);
    let 按行切分 = 取选项逻辑(&选项对象, "按行切分", true);
    let 左表 = 统计条目次数(源文本, 忽略空白, 忽略大小写, 按行切分);
    let 右表 = 统计条目次数(派生文本, 忽略空白, 忽略大小写, 按行切分);
    let mut 缺失表: Vec<serde_json::Value> = Vec::new();
    for (条目键, 左计数) in &左表 {
        let 实有 = *右表.get(条目键).unwrap_or(&0);
        if 实有 < *左计数 {
            缺失表.push(serde_json::json!({"条目": 条目键, "应有": 左计数, "实有": 实有}));
        }
    }
    let mut 多余表: Vec<serde_json::Value> = Vec::new();
    for (条目键, 右计数) in &右表 {
        let 应有 = *左表.get(条目键).unwrap_or(&0);
        if *右计数 > 应有 {
            多余表.push(serde_json::json!({"条目": 条目键, "应有": 应有, "实有": 右计数}));
        }
    }
    let 源条数: usize = 左表.values().sum();
    let 派生条数: usize = 右表.values().sum();
    let 判定词 = if 缺失表.is_empty() && 多余表.is_empty() {
        "一致"
    } else {
        "有差异"
    };
    let 载荷 = serde_json::json!({
        "判定": 判定词,
        "源条数": 源条数,
        "派生条数": 派生条数,
        "缺失": 缺失表,
        "多余": 多余表,
        "无法解析": 0,
    });
    serde_json::to_string(&载荷).map_err(|_| 错误码::文本内容不合法)
}
