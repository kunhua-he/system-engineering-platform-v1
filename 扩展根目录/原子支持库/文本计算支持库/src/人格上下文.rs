use std::io::Read;
use std::time::Duration;

use crate::编号与码面::错误码;

const 上下文上限字节: usize = 65536;
const 响应上限字节: usize = 8388608;
const 人格请求地址: &str = "http://127.0.0.1:8898/接口/v1/人格/当前";

pub fn 规范化时点(时点文本: &str) -> Result<String, u32> {
    chrono::DateTime::parse_from_rfc3339(时点文本)
        .map(|时点值| 时点值.with_timezone(&chrono::Utc).to_rfc3339())
        .map_err(|_| 错误码::参数不合法)
}

fn 请求人格上下文(
    主体标识文本: &str,
    岗位标识文本: &str,
    场景文本: &str,
    时点文本: &str,
    已知时点文本: &str,
) -> Result<String, u32> {
    if 主体标识文本.is_empty() || 岗位标识文本.is_empty() {
        return Err(错误码::参数不合法);
    }
    let 规范化时点文本 = 规范化时点(时点文本)?;
    let 规范化已知时点文本 = 规范化时点(已知时点文本)?;
    let mut 请求地址 = url::Url::parse(人格请求地址).map_err(|_| 错误码::请求失败)?;
    {
        let mut 查询参数 = 请求地址.query_pairs_mut();
        查询参数.append_pair("主体标识", 主体标识文本);
        查询参数.append_pair("岗位标识", 岗位标识文本);
        // 外部服务对 场景=空串 回 500；缺省场景不发送该参数（实测 200）
        if !场景文本.is_empty() {
            查询参数.append_pair("场景", 场景文本);
        }
        查询参数.append_pair("as_of", &规范化时点文本);
        查询参数.append_pair("known_at", &规范化已知时点文本);
    }
    let 请求配置 = ureq::Agent::config_builder()
        .timeout_global(Some(Duration::from_secs(3)))
        .max_redirects(0)
        .proxy(None)
        .http_status_as_error(false)
        .build();
    let 请求客户端: ureq::Agent = 请求配置.into();
    let mut 网络响应 = 请求客户端
        .get(请求地址.as_str())
        .call()
        .map_err(|_| 错误码::请求失败)?;
    if !网络响应.status().is_success() {
        return Err(错误码::请求失败);
    }
    let mut 响应字节 = Vec::new();
    网络响应
        .body_mut()
        .as_reader()
        .take((响应上限字节 + 1) as u64)
        .read_to_end(&mut 响应字节)
        .map_err(|_| 错误码::请求失败)?;
    if 响应字节.len() > 响应上限字节 {
        return Err(错误码::请求失败);
    }
    let 响应文本 = std::str::from_utf8(&响应字节).map_err(|_| 错误码::请求失败)?;
    let 响应对象: serde_json::Value =
        serde_json::from_str(响应文本).map_err(|_| 错误码::请求失败)?;
    if !响应对象.is_object() {
        return Err(错误码::请求失败);
    }
    serde_json::to_string(&响应对象).map_err(|_| 错误码::请求失败)
}

const 正式事实字段: &[&str] = &["正式事实", "confirmed_facts", "confirmedFacts"];
const 归纳观察字段: &[&str] = &["归纳观察", "observations"];
const 证据字段: &[&str] = &["证据边界", "证据范围", "evidence_boundary", "evidenceBoundary"];
const 禁止推断字段: &[&str] = &["禁止推断", "禁止的推断", "prohibited_inference", "prohibitedInference"];

fn 是否包含字段(字段名称: &str, 字段集合: &[&str]) -> bool {
    字段集合.contains(&字段名称)
}

fn 事实可注入(条目: &serde_json::Value) -> bool {
    let 状态有效 = 条目.get("状态").and_then(serde_json::Value::as_str)
        .map(|状态| !(状态.contains("矛盾") || 状态.contains("待确认") || 状态.contains("争议"))).unwrap_or(true);
    状态有效 && 条目.get("可用于稳定判断").and_then(serde_json::Value::as_bool).unwrap_or(true)
}

fn 观察可注入(条目: &serde_json::Value) -> bool {
    条目.get("层级").and_then(serde_json::Value::as_str).map(|层级| 层级 == "稳定").unwrap_or(true)
        && !条目.get("待确认").and_then(serde_json::Value::as_bool).unwrap_or(false)
}

fn 渲染上下文值(值: &serde_json::Value) -> String {
    match 值 {
        serde_json::Value::Null => "null".to_owned(),
        serde_json::Value::Bool(逻辑值) => 逻辑值.to_string(),
        serde_json::Value::Number(数值) => 数值.to_string(),
        serde_json::Value::String(文本值) => 文本值.clone(),
        serde_json::Value::Array(数组值) => 数组值
            .iter()
            .map(渲染上下文值)
            .collect::<Vec<String>>()
            .join("；"),
        serde_json::Value::Object(对象值) => 对象值
            .iter()
            .map(|(字段名称, 字段值)| format!("{字段名称}={}", 渲染上下文值(字段值)))
            .collect::<Vec<String>>()
            .join("；"),
    }
}

fn 追加上下文行(输出文本: &mut String, 缩进文本: &str, 字段名称: &str, 字段值: &serde_json::Value) {
    match 字段值 {
        serde_json::Value::Object(对象值) => {
            输出文本.push_str(&format!("{缩进文本}- **{字段名称}**\n"));
            渲染上下文节点(输出文本, &format!("{缩进文本}  "), 对象值);
        }
        serde_json::Value::Array(数组值) => {
            输出文本.push_str(&format!("{缩进文本}- **{字段名称}**\n"));
            for 数组项 in 数组值 {
                match 数组项 {
                    serde_json::Value::Object(对象值) => {
                        渲染上下文节点(输出文本, &format!("{缩进文本}  "), 对象值);
                    }
                    _ => 输出文本.push_str(&format!("{缩进文本}  - {}\n", 渲染上下文值(数组项))),
                }
            }
        }
        _ => 输出文本.push_str(&format!("{缩进文本}- **{字段名称}**: {}\n", 渲染上下文值(字段值))),
    }
}

fn 渲染上下文节点(输出文本: &mut String, 缩进文本: &str, 对象值: &serde_json::Map<String, serde_json::Value>) {
    for (字段名称, 字段值) in 对象值 {
        追加上下文行(输出文本, 缩进文本, 字段名称, 字段值);
    }
}

fn 注入条目组(输出文本: &mut String, 分组标题: &str, 值: &serde_json::Value, 条目可注入: impl Fn(&serde_json::Value) -> bool) {
    let 收集文本 = {
        let mut 局部文本 = String::new();
        match 值 {
            serde_json::Value::Array(数组值) => {
                for 条目 in 数组值 {
                    if !条目可注入(条目) { continue; }
                    match 条目 {
                        serde_json::Value::Object(成员) => 渲染上下文节点(&mut 局部文本, "", 成员),
                        其他值 => 局部文本.push_str(&format!("- {}\n", 渲染上下文值(其他值))),
                    }
                }
            }
            其他值 => 局部文本.push_str(&format!("- {}\n", 渲染上下文值(其他值))),
        }
        局部文本
    };
    if !收集文本.trim().is_empty() {
        输出文本.push_str(&format!("\n## {分组标题}\n"));
        输出文本.push_str(&收集文本);
    }
}

fn 格式化上下文文本(上下文对象: &serde_json::Map<String, serde_json::Value>) -> String {
    let mut 输出文本 = String::from("# 可注入上下文\n");
    let 字段分组: [(&str, &[&str], bool); 4] = [
        ("正式事实", 正式事实字段, true),
        ("归纳观察", 归纳观察字段, true),
        ("证据边界", 证据字段, false),
        ("禁止推断", 禁止推断字段, false),
    ];
    for (分组标题, 字段集合, 按条目过滤) in 字段分组 {
        for (字段名称, 字段值) in 上下文对象 {
            if 是否包含字段(字段名称, 字段集合) {
                if 按条目过滤 {
                    let 判定 = if 是否包含字段(字段名称, 正式事实字段) { 事实可注入 } else { 观察可注入 };
                    注入条目组(&mut 输出文本, 分组标题, 字段值, 判定);
                } else {
                    注入条目组(&mut 输出文本, 分组标题, 字段值, |_| true);
                }
            }
        }
    }
    输出文本
}

pub fn 执行查询人格上下文(
    主体标识文本: &str,
    岗位标识文本: &str,
    场景文本: &str,
    时点文本: &str,
    已知时点文本: &str,
) -> Result<String, u32> {
    请求人格上下文(
        主体标识文本,
        岗位标识文本,
        场景文本,
        时点文本,
        已知时点文本,
    )
}

pub fn 执行格式化可注入上下文(上下文文本: &str) -> Result<String, u32> {
    if 上下文文本.len() > 上下文上限字节 {
        return Err(错误码::上下文不合法);
    }
    let 上下文对象: serde_json::Value =
        serde_json::from_str(上下文文本).map_err(|_| 错误码::上下文不合法)?;
    let 上下文对象 = 上下文对象
        .as_object()
        .ok_or(错误码::上下文不合法)?;
    Ok(格式化上下文文本(上下文对象))
}

#[cfg(test)]
mod 测试 {
    use super::{执行格式化可注入上下文, 规范化时点};
    use crate::编号与码面::错误码;

    #[test]
    fn 规范化时点测试() {
        assert_eq!(规范化时点("2024-01-02T11:04:05+08:00").unwrap(), "2024-01-02T03:04:05+00:00");
    }

    #[test]
    fn 查询人格上下文参数测试() {
        assert_eq!(规范化时点("不是RFC3339"), Err(错误码::参数不合法));
    }

    #[test]
    fn 格式化上下文节点测试() {
        let 上下文文本 = r#"{
          "正式事实": [
            {"谓词": "偏好", "客体": "先给结论", "状态": "有效", "可用于稳定判断": true},
            {"谓词": "可能", "客体": "不应注入", "状态": "矛盾", "可用于稳定判断": false}
          ],
          "归纳观察": [
            {"结论": "重视可维护性", "层级": "稳定", "待确认": false},
            {"结论": "争议内容", "层级": "争议", "待确认": true}
          ],
          "证据边界": ["仅依据已提供对话"],
          "禁止推断": ["不得推断收入"]
        }"#;
        let 格式结果 = 执行格式化可注入上下文(上下文文本).unwrap();
        assert!(格式结果.contains("先给结论"));
        assert!(格式结果.contains("重视可维护性"));
        assert!(格式结果.contains("仅依据已提供对话"));
        assert!(格式结果.contains("不得推断收入"));
        assert!(!格式结果.contains("不应注入"));
        assert!(!格式结果.contains("争议内容"));
        assert!(!格式结果.contains("矛盾"));
    }

    #[test]
    fn 格式化上下文不合法测试() {
        assert_eq!(执行格式化可注入上下文("[]"), Err(错误码::上下文不合法));
        let 超长文本 = "{".to_owned() + &"a".repeat(65536) + "}";
        assert_eq!(执行格式化可注入上下文(&超长文本), Err(错误码::上下文不合法));
    }
}
