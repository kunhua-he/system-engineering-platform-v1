use crate::编号与码面::{能力号, 错误码};

pub(crate) fn 取文本参数(参数表: &[&[u8]], 参数序号: usize) -> Result<String, u32> {
    Ok(std::str::from_utf8(参数表[参数序号])
        .map_err(|_| 错误码::参数不合法)?
        .to_string())
}

pub(crate) fn 转义网页文本(原始文本: &str) -> String {
    let mut 转义后文本 = String::with_capacity(原始文本.len());
    for 待转义字符 in 原始文本.chars() {
        match 待转义字符 {
            '&' => 转义后文本.push_str("&amp;"),
            '<' => 转义后文本.push_str("&lt;"),
            '>' => 转义后文本.push_str("&gt;"),
            '"' => 转义后文本.push_str("&quot;"),
            '\'' => 转义后文本.push_str("&#39;"),
            _ => 转义后文本.push(待转义字符),
        }
    }
    转义后文本
}

pub(crate) fn 转文本值(数据值: &serde_json::Value) -> String {
    match 数据值 {
        serde_json::Value::String(文本内容) => 文本内容.clone(),
        serde_json::Value::Null => String::new(),
        _ => 数据值.to_string(),
    }
}

pub(crate) fn 取对象文本(条目值: &serde_json::Value, 字段名: &str) -> String {
    条目值.get(字段名).map(转文本值).unwrap_or_default()
}

pub(crate) fn 拼装整页外壳(
    页面标题文本: &str,
    页面样式体: &str,
    页面主体文本: &str,
    样式文本: &str,
) -> Vec<u8> {
    let mut 整页文本 = String::new();
    整页文本.push_str("<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>");
    整页文本.push_str(&转义网页文本(页面标题文本));
    整页文本.push_str("</title>");
    整页文本.push_str(样式文本);
    整页文本.push_str("</head><body");
    整页文本.push_str(页面样式体);
    整页文本.push('>');
    整页文本.push_str(页面主体文本);
    整页文本.push_str("</body></html>");
    整页文本.into_bytes()
}

pub(crate) fn 拼装表格行(
    表格列定义: &[serde_json::Value],
    表格行数据: &[serde_json::Value],
) -> Result<String, u32> {
    let mut 表格主体文本 = String::new();
    表格主体文本.push_str("<table class=\"hs-table\"><thead><tr>");
    for 列名项 in 表格列定义 {
        表格主体文本.push_str("<th>");
        表格主体文本.push_str(&转义网页文本(&转文本值(列名项)));
        表格主体文本.push_str("</th>");
    }
    表格主体文本.push_str("</tr></thead><tbody>");
    for 行项 in 表格行数据 {
        let 单元格表 = 行项.as_array().ok_or(错误码::内容不合法)?;
        表格主体文本.push_str("<tr>");
        for 列序 in 0..表格列定义.len() {
            let 单元格值文本 = 单元格表.get(列序).map(转文本值).unwrap_or_default();
            表格主体文本.push_str("<td>");
            表格主体文本.push_str(&转义网页文本(&单元格值文本));
            表格主体文本.push_str("</td>");
        }
        表格主体文本.push_str("</tr>");
    }
    表格主体文本.push_str("</tbody></table>");
    Ok(表格主体文本)
}

pub(crate) fn 拼装表单字段(
    字段定义: &[serde_json::Value],
    当前值: &serde_json::Value,
) -> Result<String, u32> {
    let mut 表单主体文本 = String::new();
    for 字段项 in 字段定义 {
        let 字段名文本 = 字段项.get("名").map(转文本值).unwrap_or_default();
        if 字段名文本.is_empty() {
            return Err(错误码::内容不合法);
        }
        let 字段标签文本 = 字段项
            .get("标签")
            .map(转文本值)
            .filter(|标签| !标签.is_empty())
            .unwrap_or_else(|| 字段名文本.clone());
        let 字段值文本 = 当前值.get(&字段名文本).map(转文本值).unwrap_or_default();
        表单主体文本.push_str("<div class=\"hs-form-item\"><label class=\"hs-form-label\">");
        表单主体文本.push_str(&转义网页文本(&字段标签文本));
        表单主体文本.push_str("</label><input class=\"hs-input\" name=\"");
        表单主体文本.push_str(&转义网页文本(&字段名文本));
        表单主体文本.push_str("\" value=\"");
        表单主体文本.push_str(&转义网页文本(&字段值文本));
        表单主体文本.push_str("\" /></div>");
    }
    Ok(表单主体文本)
}

pub(crate) fn 拼装聊天片段(
    消息表: &[serde_json::Value],
    空态文本: &str,
) -> Result<String, u32> {
    if 消息表.len() > 300 {
        return Err(错误码::资源受限);
    }
    let mut 流文本 = String::new();
    流文本.push_str("<div class=\"hs-chat\" data-chat=\"1\">");
    if 消息表.is_empty() {
        流文本.push_str("<div class=\"hs-chat-empty\">");
        流文本.push_str(&转义网页文本(if 空态文本.is_empty() {
            "还没有消息"
        } else {
            空态文本
        }));
        流文本.push_str("</div>");
    }
    for 消息项 in 消息表 {
        let 角色文本 = 取对象文本(消息项, "角色");
        let 内容原文 = 取对象文本(消息项, "内容");
        let 时间文本 = 取对象文本(消息项, "时间");
        let 是用户 = 角色文本 == "user" || 角色文本 == "用户";
        let 内容文本: String = 内容原文.chars().take(6000).collect();
        流文本.push_str("<div class=\"hs-chat-msg is-");
        流文本.push_str(if 是用户 { "user" } else { "assistant" });
        流文本.push_str("\"><div class=\"hs-chat-avatar\">");
        流文本.push_str(if 是用户 { "我" } else { "AI" });
        流文本.push_str("</div><div class=\"hs-chat-body\"><div class=\"hs-chat-meta\">");
        流文本.push_str(if 是用户 { "我" } else { "智能助手" });
        if !时间文本.is_empty() {
            流文本.push_str(" · ");
            流文本.push_str(&转义网页文本(&时间文本));
        }
        流文本.push_str("</div><div class=\"hs-chat-text\">");
        流文本.push_str(&转义网页文本(&内容文本));
        流文本.push_str("</div></div></div>");
    }
    流文本.push_str("</div>");
    Ok(流文本)
}

pub fn 执行业务操作(编号: u32, 参数表: &[&[u8]]) -> Result<(u32, Vec<u8>), u32> {
    match 编号 {
        能力号::渲染组件树 => crate::组件树::渲染组件树(参数表),
        _ => Err(错误码::参数不合法),
    }
}
