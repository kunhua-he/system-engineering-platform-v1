//! 响应塑形：裁剪响应、压缩描述字段、提取带前缀 JSON。
//!
//! 三条能力都只做 JSON 文本的纯内存变换，不访问外部系统；输入上界由
//! `执行函数面::输入上界` 按编号分派，其余能力保持原上限不变。
//!
//! | 件 | 职责 | 能力号 |
//! | --- | --- | --- |
//! | 本文件 | 三条能力的对外入口与取参与上界校验 | 5218 · 5219 · 5220 |
//! | `裁剪与摘要.rs` | 点分路径选中 · 信封键复制 · 条目裁剪 · 字节预算摘要 | 5218 |
//! | `压缩与提取.rs` | 指定字段空白折叠 · 行首前缀 JSON 回溯提取 | 5219 · 5220 |

use crate::编号与码面::错误码;

use crate::业务实现::解析文本上限;

#[path = "响应塑形实现/裁剪与摘要.rs"]
mod 裁剪与摘要;
#[path = "响应塑形实现/压缩与提取.rs"]
mod 压缩与提取;

use 裁剪与摘要::{已选中载荷, 裁剪到最大字节, 裁剪列表, 选中路径, 解析整数文本};
use 压缩与提取::{压缩描述字段值, 提取前缀JSON值};

pub fn 执行裁剪响应(文本参数表: &[&str]) -> Result<(u32, Vec<u8>), u32> {
    if 文本参数表.len() != 7 {
        return Err(错误码::JSON参数不合法);
    }
    let 载荷值 = 解析文本上限(文本参数表[0], 4194304)?;
    let 最大条目数 = 解析整数文本(文本参数表[2])?;
    let 最大字节数 = 解析整数文本(文本参数表[3])?;
    if 最大条目数.is_some_and(|条目值| 条目值 < 0)
        || 最大字节数.is_some_and(|条目值| 条目值 < 0)
    {
        return Err(错误码::JSON参数不合法);
    }
    let 信封键 = match 解析文本上限(文本参数表[4], 65536)? {
        serde_json::Value::Array(键表) => {
            let mut 键集合: Vec<String> = Vec::with_capacity(键表.len());
            for 键项 in 键表 {
                match 键项 {
                    serde_json::Value::String(键文本) => 键集合.push(键文本),
                    _ => return Err(错误码::JSON类型不符),
                }
            }
            键集合
        }
        _ => return Err(错误码::JSON类型不符),
    };
    let 数据键 = if 文本参数表[6].is_empty() {
        "data".to_owned()
    } else {
        文本参数表[6].to_owned()
    };
    let 元数据键 = 文本参数表[5].trim().to_owned();
    let mut 省略计数: std::collections::BTreeMap<String, i64> =
        std::collections::BTreeMap::new();
    let mut 警告表: Vec<String> = Vec::new();
    let mut 选中路径值: Option<String> = None;
    let mut 塑形值 = 载荷值.clone();
    let 选择路径文本 = 文本参数表[1].trim().to_owned();
    if !选择路径文本.is_empty() {
        match 选中路径(&载荷值, &选择路径文本) {
            Ok((解析路径, 选中值)) => {
                选中路径值 = Some(解析路径);
                塑形值 = 已选中载荷(&载荷值, &选中值, &信封键, &数据键);
            }
            Err(警告文本) => 警告表.push(警告文本),
        }
    }
    if let Some(条目上限) = 最大条目数 {
        塑形值 = 裁剪列表(
            &塑形值,
            条目上限 as usize,
            &mut 省略计数,
            选中路径值.as_deref(),
            "",
            &数据键,
        );
    }
    if !元数据键.is_empty()
        && let serde_json::Value::Object(成员表) = &mut 塑形值
    {
            let mut 元数据成员 = serde_json::Map::new();
            元数据成员.insert(
                "truncated".to_owned(),
                serde_json::Value::Bool(!省略计数.is_empty()),
            );
            元数据成员.insert(
                "selected_path".to_owned(),
                选中路径值
                    .clone()
                    .map(serde_json::Value::String)
                    .unwrap_or(serde_json::Value::Null),
            );
            元数据成员.insert(
                "omitted_counts".to_owned(),
                serde_json::to_value(&省略计数).map_err(|_| 错误码::JSON参数不合法)?,
            );
            if !警告表.is_empty() {
                let 警告值表: Vec<serde_json::Value> = 警告表
                    .iter()
                    .map(|警告文本| serde_json::Value::String(警告文本.clone()))
                    .collect();
                元数据成员.insert("warnings".to_owned(), serde_json::Value::Array(警告值表));
            }
            成员表.insert(元数据键.clone(), serde_json::Value::Object(元数据成员));
    }
    if let Some(字节上限) = 最大字节数 {
        裁剪到最大字节(&mut 塑形值, 字节上限 as usize, &数据键, &元数据键);
    }
    let 返回JSON = 塑形值.to_string();
    if 返回JSON.len() > 4194304 {
        return Err(错误码::JSON资源受限);
    }
    Ok((4, 返回JSON.into_bytes()))
}

pub fn 执行压缩描述字段(文本参数表: &[&str]) -> Result<(u32, Vec<u8>), u32> {
    if 文本参数表.len() != 2 {
        return Err(错误码::JSON参数不合法);
    }
    let 数据值 = 解析文本上限(文本参数表[0], 4194304)?;
    let 返回JSON = 压缩描述字段值(&数据值, 文本参数表[1]).to_string();
    if 返回JSON.len() > 4194304 {
        return Err(错误码::JSON资源受限);
    }
    Ok((4, 返回JSON.into_bytes()))
}

pub fn 执行提取带前缀JSON(文本参数表: &[&str]) -> Result<(u32, Vec<u8>), u32> {
    if 文本参数表.len() != 2 {
        return Err(错误码::JSON参数不合法);
    }
    if 文本参数表[1].len() > 4096 {
        return Err(错误码::JSON资源受限);
    }
    let 返回JSON = 提取前缀JSON值(文本参数表[0], 文本参数表[1].trim()).to_string();
    Ok((4, 返回JSON.into_bytes()))
}

#[cfg(test)]
mod 塑形验证样本 {
    use super::*;

    fn 取结果(输出槽: Result<(u32, Vec<u8>), u32>) -> serde_json::Value {
        let (标签, 字节) = 输出槽.unwrap();
        assert_eq!(标签, 4);
        serde_json::from_slice(&字节).unwrap()
    }

    #[test]
    fn 裁剪响应按条目数裁列表并记录省略() {
        let 测试载荷 = r#"{"status_code":200,"data":{"items":[1,2,3,4,5]}}"#;
        let 测试输出 = 执行裁剪响应(&[测试载荷, "", "2", "", r#"["status_code"]"#, "meta", "data"]);
        let 解析结果 = 取结果(测试输出);
        assert_eq!(解析结果["data"]["items"], serde_json::json!([1, 2]));
        assert_eq!(解析结果["meta"]["truncated"], serde_json::json!(true));
        assert_eq!(解析结果["meta"]["omitted_counts"]["data.items"], serde_json::json!(3));
    }

    #[test]
    fn 裁剪响应按路径选中并复制信封键() {
        let 测试载荷 = r#"{"status_code":200,"error":"无","data":{"success":true,"错误":{"码":1},"内容":[1,2]}}"#;
        let 测试输出 = 执行裁剪响应(&[测试载荷, "data.内容", "", "", r#"["status_code","error"]"#, "meta", "data"]);
        let 解析结果 = 取结果(测试输出);
        assert_eq!(解析结果["data"], serde_json::json!([1, 2]));
        assert_eq!(解析结果["status_code"], serde_json::json!(200));
        assert_eq!(解析结果["error"], serde_json::json!("无"));
        assert_eq!(解析结果["upstream_success"], serde_json::json!(true));
        assert_eq!(解析结果["meta"]["selected_path"], serde_json::json!("data.内容"));
    }

    #[test]
    fn 裁剪响应负数条目被拒() {
        let 测试载荷 = r#"{"data":[1]}"#;
        assert_eq!(
            执行裁剪响应(&[测试载荷, "", "-1", "", "[]", "meta", "data"]).unwrap_err(),
            错误码::JSON参数不合法
        );
        assert_eq!(
            执行裁剪响应(&[测试载荷, "data.不存在", "", "", "[]", "meta", "data"])
                .map(|(标签, 字节)| 取结果(Ok((标签, 字节))))
                .map(|解析结果| 解析结果["meta"]["warnings"].clone()),
            Ok(serde_json::json!(["选择路径在 data.不存在 处需要列表索引"]))
        );
    }

    #[test]
    fn 裁剪响应字节预算换摘要() {
        let 大文本 = "字".repeat(4000);
        let 测试载荷 = format!(r#"{{"data":{{"正文":"{大文本}"}}}}"#);
        let 测试输出 = 执行裁剪响应(&[&测试载荷, "", "", "1000", "[]", "meta", "data"]);
        let 解析结果 = 取结果(测试输出);
        assert_eq!(解析结果["meta"]["truncated"], serde_json::json!(true));
        assert_eq!(解析结果["meta"]["max_bytes"], serde_json::json!(1000));
        assert_eq!(解析结果["data"]["_truncated"], serde_json::json!(true));
        assert!(serde_json::to_string(&解析结果).unwrap().len() < 4000);
    }

    #[test]
    fn 压缩描述字段折叠空白() {
        let 测试载荷 = "{\"description\":\"多   空白\\n换行\",\"嵌套\":[{\"description\":\"第一段   第二段\"}],\"其他\":\"保留   原样\"}";
        let 解析结果 = 取结果(执行压缩描述字段(&[测试载荷, "description"]));
        assert_eq!(解析结果["description"], serde_json::json!("多 空白 换行"));
        assert_eq!(解析结果["嵌套"][0]["description"], serde_json::json!("第一段 第二段"));
        assert_eq!(解析结果["其他"], serde_json::json!("保留   原样"));
    }

    #[test]
    fn 提取带前缀JSON从末尾取() {
        let 测试载荷 = "前置\n摘要A: {\"verdict\":\"FAIL\"}\n摘要A: {\"verdict\":\"PASS\"}\n";
        let 解析结果 = 取结果(执行提取带前缀JSON(&[测试载荷, "摘要A:"]));
        assert_eq!(解析结果["找到"], serde_json::json!(true));
        assert_eq!(解析结果["数据"]["verdict"], serde_json::json!("PASS"));
    }

    #[test]
    fn 提取带前缀JSON解析失败视为未找到() {
        let 测试载荷 = "摘要A: {\"verdict\":\"PASS\"}\n摘要A: {坏json}\n";
        let 解析结果 = 取结果(执行提取带前缀JSON(&[测试载荷, "摘要A:"]));
        assert_eq!(解析结果["找到"], serde_json::json!(false));
        let 非对象 = 取结果(执行提取带前缀JSON(&["摘要A: [1,2]\n", "摘要A:"]));
        assert_eq!(非对象["找到"], serde_json::json!(false));
        let 无命中 = 取结果(执行提取带前缀JSON(&["无关文本\n", "摘要A:"]));
        assert_eq!(无命中["找到"], serde_json::json!(false));
    }
}
