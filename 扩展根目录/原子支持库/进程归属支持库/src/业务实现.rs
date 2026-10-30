use serde_json::Value;

use crate::编号与码面::错误码;
use crate::归属判定::{受保护原因, 命中归属};

const 归属上限字节: usize = 4194304;
const 进程数上限: usize = 20000;

fn 取整数表(登记对象: &Value, 条目键: &str) -> Vec<i64> {
    登记对象
        .get(条目键)
        .and_then(Value::as_array)
        .map(|项表| 项表.iter().filter_map(Value::as_i64).collect())
        .unwrap_or_default()
}

fn 取文本表(登记对象: &Value, 条目键: &str) -> Vec<String> {
    登记对象
        .get(条目键)
        .and_then(Value::as_array)
        .map(|项表| {
            项表
                .iter()
                .filter_map(Value::as_str)
                .map(str::to_owned)
                .collect()
        })
        .unwrap_or_default()
}

pub fn 执行判定进程归属(
    进程表文本: &str,
    归属登记文本: &str,
    保护参数文本: &str,
) -> Result<String, u32> {
    if 进程表文本.len() > 归属上限字节 || 归属登记文本.len() > 归属上限字节 {
        return Err(错误码::归属资源受限);
    }
    let 进程表: Value =
        serde_json::from_str(进程表文本).map_err(|_| 错误码::归属参数不合法)?;
    let 进程项表 = 进程表.as_array().ok_or(错误码::归属参数不合法)?;
    if 进程项表.len() > 进程数上限 {
        return Err(错误码::归属资源受限);
    }
    let 归属登记: Value =
        serde_json::from_str(归属登记文本).map_err(|_| 错误码::归属参数不合法)?;
    if !归属登记.is_object() {
        return Err(错误码::归属参数不合法);
    }
    let 端口集合 = 取整数表(&归属登记, "端口");
    let 登记路径表 = 取文本表(&归属登记, "路径");
    // fail closed：两组都空 ⇒ 没有任何进程能被证明归属，绝不判可清理
    if 端口集合.is_empty() && 登记路径表.iter().all(String::is_empty) {
        return Err(错误码::归属登记为空);
    }
    let 保护参数 = if 保护参数文本.trim().is_empty() {
        serde_json::json!({})
    } else {
        let 解析值: Value =
            serde_json::from_str(保护参数文本).map_err(|_| 错误码::归属参数不合法)?;
        if !解析值.is_object() {
            return Err(错误码::归属参数不合法);
        }
        解析值
    };
    let 保护端口表 = 取整数表(&保护参数, "保护端口");
    let 保护程序表 = 取文本表(&保护参数, "保护程序");
    let mut 可清理表: Vec<Value> = Vec::new();
    let mut 受保护表: Vec<Value> = Vec::new();
    let mut 未核实表: Vec<Value> = Vec::new();
    let mut 归属命中数: usize = 0;
    for 进程项 in 进程项表 {
        let 进程号 = 进程项
            .get("pid")
            .and_then(Value::as_i64)
            .ok_or(错误码::归属参数不合法)?;
        let 命令行 = 进程项.get("命令行").and_then(Value::as_str).unwrap_or("");
        if 命令行.trim().is_empty() {
            未核实表.push(serde_json::json!({"pid": 进程号, "原因": "命令行缺失"}));
            continue;
        }
        if let Some(保护原因) = 受保护原因(命令行, &保护端口表, &保护程序表) {
            受保护表.push(serde_json::json!({"pid": 进程号, "原因": 保护原因}));
            continue;
        }
        if let Some(命中说明) = 命中归属(命令行, &端口集合, &登记路径表) {
            归属命中数 += 1;
            可清理表.push(serde_json::json!({"pid": 进程号, "命令": 命令行, "命中": 命中说明}));
        }
    }
    let 载荷 = serde_json::json!({
        "进程总数": 进程项表.len(),
        "归属命中": 归属命中数,
        "可清理": 可清理表,
        "受保护": 受保护表,
        "未核实": 未核实表,
    });
    serde_json::to_string(&载荷).map_err(|_| 错误码::归属内容不合法)
}
