//! 浏览器提供者：把六个能力落到会话与动作两件上，只做参数解析与结果封装。

use crate::编号与码面::错误码;
use crate::浏览器会话::{发指令, 关闭会话, 创建会话, 全部关闭};
use crate::浏览器动作::{操作元素, 截图, 导航, 读页面};

fn 取文本<'a>(参数表: &'a [&'a str], 序位: usize) -> Result<&'a str, u32> {
    参数表.get(序位).copied().ok_or(错误码::参数不合法)
}

fn 取句柄(参数表: &[&str], 序位: usize) -> Result<u32, u32> {
    取文本(参数表, 序位)?.trim().parse::<u32>().map_err(|_| 错误码::参数不合法)
}

pub(crate) fn 执行(编号: u32, 参数表: &[&str]) -> Result<String, u32> {
    match 编号 {
        crate::编号与码面::能力号::创建会话 => {
            // 临时候选根：传空就落到系统临时目录
            let 根 = 取文本(参数表, 0)?.trim();
            let 根文本 = if 根.is_empty() { std::env::temp_dir().to_string_lossy().into_owned() } else { 根.to_string() };
            if !根文本.starts_with('/') {
                return Err(错误码::参数不合法);
            }
            let 句柄 = 创建会话(根文本.trim_end_matches('/'))?;
            Ok(format!("{}", 句柄))
        }
        crate::编号与码面::能力号::导航 => 导航(取句柄(参数表, 0)?, 取文本(参数表, 1)?),
        crate::编号与码面::能力号::读页面 => {
            读页面(取句柄(参数表, 0)?, 取文本(参数表, 1)?, 取文本(参数表, 2)?)
        }
        crate::编号与码面::能力号::操作元素 => 操作元素(
            取句柄(参数表, 0)?,
            取文本(参数表, 1)?,
            取文本(参数表, 2)?,
            取文本(参数表, 3)?,
        ),
        crate::编号与码面::能力号::截图 => {
            let 句柄 = 取句柄(参数表, 0)?;
            let 字节数 = 截图(句柄, 取文本(参数表, 1)?)?;
            Ok(format!("{{\"句柄\":{},\"字节数\":{}}}", 句柄, 字节数))
        }
        crate::编号与码面::能力号::关闭会话 => {
            let 句柄 = 取句柄(参数表, 0)?;
            关闭会话(句柄)?;
            Ok(format!("{{\"句柄\":{},\"已关闭\":true}}", 句柄))
        }
        _ => Err(错误码::参数不合法),
    }
}

/// 进程收尾钩子：网关注销扩展前把关掉的会话全杀掉，不留在途浏览器
#[allow(dead_code)]
pub(crate) fn 收尾() {
    全部关闭();
}

/// 探活一小步：确认会话仍能应答（读一下标题地址），供健康检查复用
#[allow(dead_code)]
pub(crate) fn 探活(句柄: u32) -> Result<String, u32> {
    发指令(句柄, "Runtime.evaluate", serde_json::json!({
        "expression": "document.title",
        "returnByValue": true,
    }))
    .map(|值| 值.to_string())
}

#[cfg(test)]
mod 测试 {
    use super::*;

    fn 造测试页() -> String {
        let 路径 = "/tmp/v1浏览器测试页.html";
        std::fs::write(
            路径,
            "<!doctype html><meta charset=utf-8><title>底座浏览器测试</title>             <h1 id=题>初始标题</h1>             <input id=框 value=\"\">             <button id=钮 onclick=\"document.getElementById('题').textContent=\
             '点过了:'+document.getElementById('框').value\">确认</button>",
        )
        .expect("写测试页失败");
        路径.to_string()
    }

    /// 端到端：起真浏览器 → 导航 → 读文本 → 填值 → 点击 → 读回 → 截图 → 关闭
    #[test]
    fn 真浏览器全流程() {
        if std::env::var("V1_BROWSER_E2E").is_err() {
            return; // 默认不跑（起真进程较慢且依赖本机装了 Chrome）
        }
        let 页 = 造测试页();
        let 句柄 = 执行(super::super::编号与码面::能力号::创建会话, &[""]).expect("创建会话失败");
        let 号 = 句柄.trim().to_string();
        println!("句柄 {号}");

        let 导航回 = 执行(super::super::编号与码面::能力号::导航, &[&号, &format!("file://{}", 页)])
            .expect("导航失败");
        println!("导航 {导航回}");
        assert!(导航回.contains("底座浏览器测试"), "标题没读到：{导航回}");

        let 文本 = 执行(super::super::编号与码面::能力号::读页面, &[&号, "文本", ""]).expect("读文本失败");
        assert!(文本.contains("初始标题"), "正文没读到");
        println!("正文长度 {}", 文本.chars().count());

        let 填 = 执行(super::super::编号与码面::能力号::操作元素, &[&号, "#框", "填值", "底座的输入"])
            .expect("填值失败");
        assert!(填.contains("已填值"), "{填}");

        let 击 = 执行(super::super::编号与码面::能力号::操作元素, &[&号, "#钮", "点击", ""]).expect("点击失败");
        assert!(击.contains("已点击"), "{击}");

        let 回读 = 执行(super::super::编号与码面::能力号::读页面, &[&号, "元素", "#题"]).expect("读元素失败");
        println!("回读 {回读}");
        assert!(回读.contains("点过了:底座的输入"), "点击没生效：{回读}");

        let 截图回 = 执行(super::super::编号与码面::能力号::截图, &[&号, "/tmp/v1浏览器截图.png"]).expect("截图失败");
        println!("截图 {截图回}");
        let 字节数 = std::fs::metadata("/tmp/v1浏览器截图.png").map(|项| 项.len()).unwrap_or(0);
        assert!(字节数 > 3000, "截图太小：{字节数}");

        let 关闭 = 执行(super::super::编号与码面::能力号::关闭会话, &[&号]).expect("关闭失败");
        assert!(关闭.contains("true"), "{关闭}");

        // 关掉之后再操作必须报会话不存在
        let 再读 = 执行(super::super::编号与码面::能力号::读页面, &[&号, "文本", ""]);
        assert_eq!(再读.err(), Some(crate::编号与码面::错误码::会话不存在));
    }

    #[test]
    fn 非绝对根目录被拒() {
        assert_eq!(
            执行(super::super::编号与码面::能力号::创建会话, &["相对目录"]).err(),
            Some(crate::编号与码面::错误码::参数不合法)
        );
    }

    #[test]
    fn 非网页协议被拒() {
        assert_eq!(
            执行(super::super::编号与码面::能力号::导航, &["999", "javascript:alert(1)"]).err(),
            Some(crate::编号与码面::错误码::参数不合法)
        );
    }
}
