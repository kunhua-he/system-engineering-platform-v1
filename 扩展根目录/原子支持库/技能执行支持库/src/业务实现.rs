//! 业务实现：8301 准备技能执行 —— 校验技能包、审计脚本、写参数文件、出执行计划。

use std::path::Path;

use serde_json::Value;

use crate::编号与码面::{能力号, 错误码};
use crate::{技能校验, 执行计划};

fn 取文本(值: &Value, 键: &str) -> Result<String, u32> {
    值.get(键)
        .and_then(Value::as_str)
        .map(|项| 项.trim().to_string())
        .filter(|项| !项.is_empty())
        .ok_or(错误码::参数不合法)
}

fn 取前缀表(值: &Value) -> Vec<String> {
    值.get("禁止导入前缀")
        .and_then(Value::as_array)
        .map(|项表| {
            项表
                .iter()
                .filter_map(Value::as_str)
                .map(|项| 项.trim().to_string())
                .filter(|项| !项.is_empty())
                .collect()
        })
        .unwrap_or_default()
}

/// 准备技能执行。
pub(crate) fn 准备技能执行(参数: &Value) -> Result<Value, u32> {
    let 根文本 = 取文本(参数, "技能根目录")?;
    if !根文本.starts_with('/') {
        return Err(错误码::参数不合法);
    }
    let 根 = Path::new(&根文本);
    if !根.is_dir() {
        return Err(错误码::技能目录不存在);
    }
    let 能力标识 = 取文本(参数, "能力标识")?;
    let 段表 = 技能校验::拆能力标识(&能力标识)?;
    let 技能目录 = 根.join(&段表[0]).join(&段表[1]);
    技能校验::查六件套(&技能目录)?;
    let 脚本 = 技能校验::查工作流(&技能目录)?;
    let 真脚本 = 技能校验::查脚本范围(&技能目录, &脚本)?;
    let 源码 = 技能校验::查脚本内容(&真脚本)?;
    技能校验::查导入(&源码, &取前缀表(参数))?;

    let 调用参数 = 参数.get("参数").cloned().unwrap_or_else(|| serde_json::json!({}));
    let 负载 = serde_json::json!({
        "能力标识": 能力标识,
        "参数": 调用参数,
        "项目根目录": 参数.get("项目根目录").and_then(Value::as_str).unwrap_or(""),
    });
    let 参数文件 = 执行计划::写参数文件(&负载)?;
    let 解释器 = 参数.get("解释器").and_then(Value::as_str).unwrap_or("");
    let 超时秒 = 参数
        .get("超时秒数")
        .and_then(Value::as_f64)
        .unwrap_or(120.0);
    let 计划 = 执行计划::组装(&真脚本, &技能目录, 解释器, &参数文件, 超时秒)?;

    let mut 结果 = 计划;
    if let Some(对象) = 结果.as_object_mut() {
        对象.insert("能力标识".to_string(), Value::String(能力标识));
        对象.insert("技能包文件".to_string(), serde_json::json!({
            "SKILL.md": 技能目录.join("SKILL.md").to_string_lossy().to_string(),
            "契约.json": 技能目录.join("契约.json").to_string_lossy().to_string(),
            "工作流.json": 技能目录.join("工作流.json").to_string_lossy().to_string(),
            "验证声明.json": 技能目录.join("验证声明.json").to_string_lossy().to_string(),
            "依赖.json": 技能目录.join("依赖.json").to_string_lossy().to_string(),
        }));
    }
    Ok(结果)
}

/// 按能力号分发。
pub(crate) fn 执行(编号: u32, 参数: &Value) -> Result<Value, u32> {
    match 编号 {
        能力号::准备技能执行 => 准备技能执行(参数),
        _ => Err(错误码::参数不合法),
    }
}

#[cfg(test)]
mod 测试 {
    use super::*;

    /// 每个测试各自一个根：并行跑时共用同一目录会互相 remove_dir_all（实测踩过）。
    /// 序号用原子计数，不能靠时间戳——多线程同一微秒会拿到同一个值。
    fn 造技能根() -> String {
        use std::sync::atomic::{AtomicU64, Ordering};
        static 序号: AtomicU64 = AtomicU64::new(0);
        let 根 = format!(
            "/tmp/v1技能测试根-{}-{}",
            std::process::id(),
            序号.fetch_add(1, Ordering::SeqCst)
        );
        let 根 = 根.as_str();
        let 技能 = format!("{根}/_示范/纯文本统计");
        std::fs::create_dir_all(format!("{技能}/scripts")).unwrap();
        std::fs::write(format!("{技能}/SKILL.md"), "# 示范").unwrap();
        std::fs::write(format!("{技能}/契约.json"), "{}").unwrap();
        std::fs::write(format!("{技能}/验证声明.json"), "{}").unwrap();
        std::fs::write(format!("{技能}/依赖.json"), "{}").unwrap();
        std::fs::write(
            format!("{技能}/工作流.json"),
            r#"{"能力标识":"_示范.纯文本统计","入口脚本":"统计文本.py"}"#,
        )
        .unwrap();
        std::fs::write(
            format!("{技能}/scripts/统计文本.py"),
            "import json,sys\n参数=json.loads(open(sys.argv[1],encoding='utf-8').read())\nprint(json.dumps({'成功':True},ensure_ascii=False))\n",
        )
        .unwrap();
        根.to_string()
    }

    fn 参数(根: &str, 标识: &str) -> Value {
        serde_json::json!({
            "技能根目录": 根,
            "能力标识": 标识,
            "参数": {"文本": "你好 世界"},
            "项目根目录": "/tmp",
            "禁止导入前缀": ["功能模块", "项目适配层"],
        })
    }

    #[test]
    fn 合法技能包出计划() {
        let 根 = 造技能根();
        let 计划 = 准备技能执行(&参数(&根, "_示范.纯文本统计")).expect("应放行");
        assert!(计划["脚本路径"].as_str().unwrap().ends_with("统计文本.py"));
        assert!(计划["参数文件"].as_str().unwrap().starts_with("/private/tmp/v1技能参数-"));
        assert!(计划["命令"].as_str().unwrap().contains("'"));
        assert_eq!(计划["提交参数"]["沙箱"], "沙箱");
        assert!(std::path::Path::new(计划["参数文件"].as_str().unwrap()).is_file());
    }

    #[test]
    fn 能力标识穿越被拒() {
        let 根 = 造技能根();
        for 坏 in ["../x", "a..b", "_示范", "_示范.", ".纯文本统计", "/abs.x", "a.b.c", "a/b"] {
            assert_eq!(
                准备技能执行(&参数(&根, 坏)).err(),
                Some(错误码::能力标识不合法),
                "应拒 {坏}"
            );
        }
    }

    #[test]
    fn 缺件与错工作流被拒() {
        let 根 = 造技能根();
        std::fs::remove_file(format!("{根}/_示范/纯文本统计/依赖.json")).unwrap();
        assert_eq!(准备技能执行(&参数(&根, "_示范.纯文本统计")).err(), Some(错误码::技能包不完整));
    }

    #[test]
    fn 脚本含禁项被拒() {
        let 根 = 造技能根();
        std::fs::write(
            format!("{根}/_示范/纯文本统计/scripts/统计文本.py"),
            "import subprocess\nsubprocess.run(['ls'])\n",
        )
        .unwrap();
        assert_eq!(准备技能执行(&参数(&根, "_示范.纯文本统计")).err(), Some(错误码::脚本审计不通过));
    }

    #[test]
    fn 导入禁止前缀被拒() {
        let 根 = 造技能根();
        std::fs::write(
            format!("{根}/_示范/纯文本统计/scripts/统计文本.py"),
            "import json\nfrom 功能模块.自修复 import 申请\n",
        )
        .unwrap();
        assert_eq!(准备技能执行(&参数(&根, "_示范.纯文本统计")).err(), Some(错误码::依赖越界));
    }
}
