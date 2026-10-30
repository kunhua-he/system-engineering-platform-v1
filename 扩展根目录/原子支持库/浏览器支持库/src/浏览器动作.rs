//! 浏览器动作：导航、读页面、操作元素、截图 —— 全部走 CDP，不做屏幕坐标模拟。

use serde_json::{json, Value};

use crate::编号与码面::错误码;
use crate::浏览器会话::发指令;

/// 轮询 readyState，直到 complete 或到期（不无限等，也不假装加载完了）
fn 等加载(句柄: u32, 最多毫秒: u64) -> Result<String, u32> {
    let 起步 = std::time::Instant::now();
    let mut 状态 = String::new();
    while 起步.elapsed().as_millis() < 最多毫秒 as u128 {
        let 回 = 发指令(句柄, "Runtime.evaluate", json!({
            "expression": "document.readyState",
            "returnByValue": true,
        }))?;
        if let Some(值) = 回.get("result").and_then(|项| 项.get("value")).and_then(|项| 项.as_str()) {
            状态 = 值.to_string();
            if 值 == "complete" {
                return Ok(状态);
            }
        }
        std::thread::sleep(std::time::Duration::from_millis(120));
    }
    Ok(状态)
}

/// 导航到 URL，返回 {地址, 标题, 加载状态}
pub(crate) fn 导航(句柄: u32, 地址: &str) -> Result<String, u32> {
    if !(地址.starts_with("http://") || 地址.starts_with("https://") || 地址.starts_with("file://")) {
        return Err(错误码::参数不合法);
    }
    发指令(句柄, "Page.enable", json!({}))?;
    发指令(句柄, "Page.navigate", json!({ "url": 地址 }))?;
    let 状态 = 等加载(句柄, 20_000)?;
    let 回 = 发指令(句柄, "Runtime.evaluate", json!({
        "expression": "JSON.stringify({标题: document.title, 地址: location.href})",
        "returnByValue": true,
    }))?;
    let 文本 = 回.get("result").and_then(|项| 项.get("value")).and_then(|项| 项.as_str()).unwrap_or("{}");
    let 解析: Value = serde_json::from_str(文本).unwrap_or(json!({}));
    Ok(json!({
        "地址": 解析.get("地址").cloned().unwrap_or(json!(地址)),
        "标题": 解析.get("标题").cloned().unwrap_or(json!("")),
        "加载状态": 状态,
    })
    .to_string())
}

/// 读页面：取纯文本、HTML、标题地址，或按选择器取一个元素的文本/属性
pub(crate) fn 读页面(句柄: u32, 读法: &str, 选择器: &str) -> Result<String, u32> {
    let 表达式 = match 读法 {
        "文本" => "document.body ? document.body.innerText : \"\"".to_string(),
        "html" => "document.documentElement ? document.documentElement.outerHTML : \"\"".to_string(),
        "标题地址" => "JSON.stringify({标题: document.title, 地址: location.href})".to_string(),
        "元素" => {
            if 选择器.trim().is_empty() {
                return Err(错误码::参数不合法);
            }
            format!(
                "(function(){{var 元素=document.querySelector({});if(!元素)return JSON.stringify({{找到:false}});\
                 var 属性={{}};for(var 序=0;序<元素.attributes.length;序++){{\
                 属性[元素.attributes[序].name]=元素.attributes[序].value;}}\
                 return JSON.stringify({{找到:true,文本:元素.innerText||元素.value||\"\",标签:元素.tagName,\
                 属性:属性,可见:!!(元素.offsetWidth||元素.offsetHeight||元素.getClientRects().length)}});}})()",
                 serde_json::to_string(选择器).map_err(|_| 错误码::参数不合法)?
            )
        }
        _ => return Err(错误码::参数不合法),
    };
    let 回 = 发指令(句柄, "Runtime.evaluate", json!({
        "expression": 表达式,
        "returnByValue": true,
        "awaitPromise": true,
    }))?;
    if let Some(_异常) = 回.get("exceptionDetails") {
        return Err(错误码::指令失败);
    }
    let 值 = 回.get("result").and_then(|项| 项.get("value")).cloned().unwrap_or(Value::Null);
    Ok(match 值 {
        Value::String(文本) => 文本,
        Value::Null => String::new(),
        其他 => 其他.to_string(),
    })
}

/// 操作元素：点击 / 填值 / 悬停 / 滚入视野
pub(crate) fn 操作元素(句柄: u32, 选择器: &str, 动作: &str, 值: &str) -> Result<String, u32> {
    if 选择器.trim().is_empty() {
        return Err(错误码::参数不合法);
    }
    let 选择器文本 = serde_json::to_string(选择器).map_err(|_| 错误码::参数不合法)?;
    let 值文本 = serde_json::to_string(值).map_err(|_| 错误码::参数不合法)?;
    let 动作段 = match 动作 {
        // 必须包成一层函数：直接写在 return 后面会被 `元素.focus&&...` 提前返回（实测踩过）
        "点击" => "(function(){if(元素.focus)元素.focus();元素.click();return \"已点击\";})()".to_string(),
        "填值" => format!(
            "(function(){{元素.focus();元素.value={};\
             元素.dispatchEvent(new Event('input',{{bubbles:true}}));\
             元素.dispatchEvent(new Event('change',{{bubbles:true}}));return \"已填值\";}})()",
            值文本
        ),
        "悬停" => "(function(){元素.dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));return \"已悬停\";})()".to_string(),
        "滚入" => "(function(){元素.scrollIntoView({block:'center'});return \"已滚入\";})()".to_string(),
        _ => return Err(错误码::参数不合法),
    };
    let 表达式 = format!(
        "(function(){{var 元素=document.querySelector({});if(!元素)return \"未找到元素\";return {};}})()",
        选择器文本, 动作段
    );
    let 回 = 发指令(句柄, "Runtime.evaluate", json!({
        "expression": 表达式,
        "returnByValue": true,
        "awaitPromise": true,
    }))?;
    let 结果 = 回.get("result").and_then(|项| 项.get("value")).and_then(|项| 项.as_str()).unwrap_or("");
    if 结果 == "未找到元素" {
        return Err(错误码::元素未找到);
    }
    Ok(json!({ "动作": 动作, "选择器": 选择器, "结果": 结果 }).to_string())
}

/// 整页截图落盘为 PNG，返回字节数
pub(crate) fn 截图(句柄: u32, 输出路径: &str) -> Result<u64, u32> {
    if !输出路径.starts_with('/') {
        return Err(错误码::参数不合法);
    }
    let 回 = 发指令(句柄, "Page.captureScreenshot", json!({ "format": "png" }))?;
    let 数据 = 回.get("data").and_then(|项| 项.as_str()).ok_or(错误码::指令失败)?;
    let 字节 = 解编码文本(数据)?;
    if 字节.is_empty() {
        return Err(错误码::指令失败);
    }
    std::fs::write(输出路径, &字节).map_err(|_| 错误码::写出失败)?;
    Ok(字节.len() as u64)
}

fn 解编码文本(文本: &str) -> Result<Vec<u8>, u32> {
    let 表: Vec<u8> = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/".to_vec();
    let mut 结果 = Vec::with_capacity(文本.len() * 3 / 4);
    let mut 缓冲 = 0u32;
    let mut 位宽 = 0u32;
    for 字节 in 文本.bytes() {
        if 字节 == b'=' || 字节 == b'\n' || 字节 == b'\r' {
            continue;
        }
        let 值 = 表.iter().position(|候选| *候选 == 字节).ok_or(错误码::协议不符)? as u32;
        缓冲 = (缓冲 << 6) | 值;
        位宽 += 6;
        if 位宽 >= 8 {
            位宽 -= 8;
            结果.push((缓冲 >> 位宽) as u8);
        }
    }
    Ok(结果)
}
