use crate::编号与码面::{能力号, 错误码};
use crate::视觉基准::完整样式文本;

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

pub(crate) fn 解析数组参数(原文: &str, 上限: usize) -> Result<serde_json::Value, u32> {
    let 解析结果: serde_json::Value =
        serde_json::from_str(原文).map_err(|_| 错误码::内容不合法)?;
    let 条目表 = 解析结果.as_array().ok_or(错误码::内容不合法)?;
    if 条目表.len() > 上限 {
        return Err(错误码::资源受限);
    }
    Ok(解析结果)
}

pub(crate) fn 解析对象参数(原文: &str) -> Result<serde_json::Value, u32> {
    let 解析结果: serde_json::Value =
        serde_json::from_str(原文).map_err(|_| 错误码::内容不合法)?;
    if !解析结果.is_object() {
        return Err(错误码::内容不合法);
    }
    Ok(解析结果)
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

fn 拼装按钮组(按钮定义: &[serde_json::Value]) -> String {
    let mut 按钮组文本 = String::new();
    for (按钮序, 按钮项) in 按钮定义.iter().enumerate() {
        let 按钮标签文本 = 按钮项.get("标签").map(转文本值).unwrap_or_default();
        let 按钮动作文本 = 按钮项.get("动作").map(转文本值).unwrap_or_default();
        let 按钮样式 = if 按钮序 == 0 {
            "hs-button hs-button-primary"
        } else {
            "hs-button"
        };
        按钮组文本.push_str("<button class=\"");
        按钮组文本.push_str(按钮样式);
        按钮组文本.push_str("\" data-action=\"");
        按钮组文本.push_str(&转义网页文本(&按钮动作文本));
        按钮组文本.push_str("\">");
        按钮组文本.push_str(&转义网页文本(&按钮标签文本));
        按钮组文本.push_str("</button>");
    }
    按钮组文本
}

fn 渲染数据表格(参数表: &[&[u8]]) -> Result<(u32, Vec<u8>), u32> {
    let 列定义原文 = 取文本参数(参数表, 0)?;
    let 行定义原文 = 取文本参数(参数表, 1)?;
    let 表格列定义值: serde_json::Value =
        serde_json::from_str(&列定义原文).map_err(|_| 错误码::内容不合法)?;
    let 表格行数据值: serde_json::Value =
        serde_json::from_str(&行定义原文).map_err(|_| 错误码::内容不合法)?;
    let 表格列定义 = 表格列定义值.as_array().ok_or(错误码::内容不合法)?;
    let 表格行数据 = 表格行数据值.as_array().ok_or(错误码::内容不合法)?;
    if 表格列定义.len() > 64 || 表格行数据.len() > 4096 {
        return Err(错误码::资源受限);
    }
    Ok((4, 拼装表格行(表格列定义, 表格行数据)?.into_bytes()))
}

fn 渲染表单(参数表: &[&[u8]]) -> Result<(u32, Vec<u8>), u32> {
    let 字段定义原文 = 取文本参数(参数表, 0)?;
    let 当前值原文 = 取文本参数(参数表, 1)?;
    let 字段定义值: serde_json::Value =
        serde_json::from_str(&字段定义原文).map_err(|_| 错误码::内容不合法)?;
    let 当前值映射: serde_json::Value =
        serde_json::from_str(&当前值原文).map_err(|_| 错误码::内容不合法)?;
    if !当前值映射.is_object() {
        return Err(错误码::内容不合法);
    }
    let 字段定义 = 字段定义值.as_array().ok_or(错误码::内容不合法)?;
    if 字段定义.len() > 128 {
        return Err(错误码::资源受限);
    }
    Ok((4, 拼装表单字段(字段定义, &当前值映射)?.into_bytes()))
}

fn 渲染对话框(参数表: &[&[u8]]) -> Result<(u32, Vec<u8>), u32> {
    let 对话框标题文本 = 取文本参数(参数表, 0)?;
    let 对话框内容文本 = 取文本参数(参数表, 1)?;
    let 按钮定义原文 = 取文本参数(参数表, 2)?;
    let 按钮定义值 = 解析数组参数(&按钮定义原文, 8)?;
    let 按钮定义 = 按钮定义值.as_array().ok_or(错误码::内容不合法)?;
    let mut 对话框主体文本 = String::new();
    对话框主体文本.push_str("<div class=\"hs-dialog\"><h3 class=\"hs-dialog-title\">");
    对话框主体文本.push_str(&转义网页文本(&对话框标题文本));
    对话框主体文本.push_str("</h3><div class=\"hs-dialog-body\">");
    对话框主体文本.push_str(&转义网页文本(&对话框内容文本));
    对话框主体文本.push_str("</div><div class=\"hs-dialog-actions\">");
    对话框主体文本.push_str(&拼装按钮组(按钮定义));
    对话框主体文本.push_str("</div></div>");
    Ok((4, 对话框主体文本.into_bytes()))
}

fn 拼装页面区块(区块定义: &[serde_json::Value]) -> Result<String, u32> {
    let mut 页面区块文本 = String::new();
    for 区块项 in 区块定义 {
        let 区块类型文本 = 区块项.get("类型").map(转文本值).unwrap_or_default();
        let 区块内容文本 = match 区块类型文本.as_str() {
            "标题栏" => {
                let 区块标题文本 = 区块项.get("文本").map(转文本值).unwrap_or_default();
                format!(
                    "<h1 class=\"hs-title\">{}</h1>",
                    转义网页文本(&区块标题文本)
                )
            }
            "数据表格" => {
                let 表格列定义 = 区块项
                    .get("列")
                    .and_then(|列项| 列项.as_array())
                    .ok_or(错误码::内容不合法)?;
                let 表格行数据 = 区块项
                    .get("行")
                    .and_then(|行项| 行项.as_array())
                    .ok_or(错误码::内容不合法)?;
                format!(
                    "<div class=\"hs-card\">{}</div>",
                    拼装表格行(表格列定义, 表格行数据)?
                )
            }
            "表单" => {
                let 字段定义 = 区块项
                    .get("字段")
                    .and_then(|字段项| 字段项.as_array())
                    .ok_or(错误码::内容不合法)?;
                let 表单缺省值 = 区块项
                    .get("值")
                    .cloned()
                    .unwrap_or_else(|| serde_json::Value::Object(serde_json::Map::new()));
                format!(
                    "<div class=\"hs-card\">{}</div>",
                    拼装表单字段(字段定义, &表单缺省值)?
                )
            }
            "对话框" => {
                let 区块标题文本 = 区块项.get("标题").map(转文本值).unwrap_or_default();
                let 区块内容文本 = 区块项.get("内容").map(转文本值).unwrap_or_default();
                let 按钮定义 = 区块项
                    .get("按钮")
                    .and_then(|按钮项| 按钮项.as_array())
                    .map(|按钮项| 按钮项.to_vec())
                    .unwrap_or_default();
                let mut 对话框主体文本 = String::new();
                对话框主体文本.push_str("<div class=\"hs-dialog\"><h3 class=\"hs-dialog-title\">");
                对话框主体文本.push_str(&转义网页文本(&区块标题文本));
                对话框主体文本.push_str("</h3><div class=\"hs-dialog-body\">");
                对话框主体文本.push_str(&转义网页文本(&区块内容文本));
                对话框主体文本.push_str("</div><div class=\"hs-dialog-actions\">");
                对话框主体文本.push_str(&拼装按钮组(&按钮定义));
                对话框主体文本.push_str("</div></div>");
                对话框主体文本
            }
            "文字" => {
                let 区块内容文本 = 区块项.get("文本").map(转文本值).unwrap_or_default();
                format!(
                    "<div class=\"hs-card\">{}</div>",
                    转义网页文本(&区块内容文本)
                )
            }
            _ => return Err(错误码::内容不合法),
        };
        页面区块文本.push_str(&区块内容文本);
    }
    Ok(页面区块文本)
}

fn 渲染页面骨架(参数表: &[&[u8]]) -> Result<(u32, Vec<u8>), u32> {
    let 页面标题文本 = 取文本参数(参数表, 0)?;
    let 主题标识文本 = 取文本参数(参数表, 1)?;
    let 区块定义原文 = 取文本参数(参数表, 2)?;
    let 区块定义值: serde_json::Value =
        serde_json::from_str(&区块定义原文).map_err(|_| 错误码::内容不合法)?;
    let 区块定义表 = 区块定义值
        .get("区块")
        .and_then(|区块项| 区块项.as_array())
        .ok_or(错误码::内容不合法)?;
    if 区块定义表.len() > 64 {
        return Err(错误码::资源受限);
    }
    let 页面区块文本 = 拼装页面区块(区块定义表)?;
    let mut 页面主体文本 = String::new();
    页面主体文本.push_str("<div class=\"hs-page\" data-theme=\"");
    页面主体文本.push_str(&转义网页文本(&主题标识文本));
    页面主体文本.push_str("\"><h1 class=\"hs-title\">");
    页面主体文本.push_str(&转义网页文本(&页面标题文本));
    页面主体文本.push_str("</h1>");
    页面主体文本.push_str(&页面区块文本);
    页面主体文本.push_str("</div>");
    Ok((4, 拼装整页外壳(&页面标题文本, "", &页面主体文本, &完整样式文本())))
}

fn 拼装侧栏条目(侧栏条目: &[serde_json::Value]) -> String {
    let mut 侧栏菜单文本 = String::new();
    for 条目项 in 侧栏条目 {
        let 条目名称 = 取对象文本(条目项, "名称");
        let 条目图标 = 取对象文本(条目项, "图标");
        let 条目激活 = 条目项
            .get("激活")
            .and_then(|激活项| 激活项.as_bool())
            .unwrap_or(false);
        侧栏菜单文本.push_str("<a class=\"hs-menu-item");
        if 条目激活 {
            侧栏菜单文本.push_str(" is-active");
        }
        侧栏菜单文本.push_str("\"><span>");
        侧栏菜单文本.push_str(&转义网页文本(&条目图标));
        侧栏菜单文本.push_str("</span><span>");
        侧栏菜单文本.push_str(&转义网页文本(&条目名称));
        侧栏菜单文本.push_str("</span></a>");
    }
    侧栏菜单文本
}

fn 渲染侧栏布局(参数表: &[&[u8]]) -> Result<(u32, Vec<u8>), u32> {
    let 侧栏标题文本 = 取文本参数(参数表, 0)?;
    let 侧栏条目原文 = 取文本参数(参数表, 1)?;
    let 顶栏标题文本 = 取文本参数(参数表, 2)?;
    let 区块定义原文 = 取文本参数(参数表, 3)?;
    let 侧栏条目值 = 解析数组参数(&侧栏条目原文, 64)?;
    let 侧栏条目 = 侧栏条目值.as_array().ok_or(错误码::内容不合法)?;
    let 区块定义值: serde_json::Value =
        serde_json::from_str(&区块定义原文).map_err(|_| 错误码::内容不合法)?;
    let 区块定义表 = 区块定义值
        .get("区块")
        .and_then(|区块项| 区块项.as_array())
        .ok_or(错误码::内容不合法)?;
    if 区块定义表.len() > 64 {
        return Err(错误码::资源受限);
    }
    let 页面区块文本 = 拼装页面区块(区块定义表)?;
    let mut 页面主体文本 = String::new();
    页面主体文本.push_str(
        "<div class=\"hs-layout\"><aside class=\"hs-sidebar\"><div class=\"hs-sidebar-title\">",
    );
    页面主体文本.push_str(&转义网页文本(&侧栏标题文本));
    页面主体文本.push_str("</div><nav class=\"hs-menu\">");
    页面主体文本.push_str(&拼装侧栏条目(侧栏条目));
    页面主体文本.push_str("</nav></aside><div class=\"hs-main\"><header class=\"hs-topbar\">");
    页面主体文本.push_str(&转义网页文本(&顶栏标题文本));
    页面主体文本.push_str("</header><div class=\"hs-content\">");
    页面主体文本.push_str(&页面区块文本);
    页面主体文本.push_str("</div></div></div>");
    Ok((4, 拼装整页外壳(&顶栏标题文本, "", &页面主体文本, &完整样式文本())))
}

fn 拼装桌面图标(桌面图标: &[serde_json::Value]) -> String {
    let mut 桌面图标文本 = String::new();
    for 图标项 in 桌面图标 {
        let 图标名称 = 取对象文本(图标项, "名称");
        let 图标字形 = 取对象文本(图标项, "图标");
        桌面图标文本
            .push_str("<div class=\"hs-desktop-icon\"><div class=\"hs-desktop-icon-glyph\">");
        桌面图标文本.push_str(&转义网页文本(&图标字形));
        桌面图标文本.push_str("</div><span class=\"hs-desktop-icon-label\">");
        桌面图标文本.push_str(&转义网页文本(&图标名称));
        桌面图标文本.push_str("</span></div>");
    }
    桌面图标文本
}

fn 拼装顶部菜单(菜单条目: &[serde_json::Value]) -> String {
    let mut 菜单栏文本 = String::new();
    for 菜单组 in 菜单条目 {
        let 菜单名称 = 取对象文本(菜单组, "名称");
        菜单栏文本.push_str("<div class=\"hs-menubar-menu\">");
        菜单栏文本.push_str(&转义网页文本(&菜单名称));
        let 子条目: &[serde_json::Value] = 菜单组
            .get("条目")
            .and_then(|条目项| 条目项.as_array())
            .map(|条目表| 条目表.as_slice())
            .unwrap_or(&[]);
        if !子条目.is_empty() {
            菜单栏文本.push_str("<div class=\"hs-menu-drop\">");
            for 子条目项 in 子条目 {
                菜单栏文本.push_str("<div class=\"hs-menu-drop-item\">");
                菜单栏文本.push_str(&转义网页文本(&取对象文本(子条目项, "名称")));
                菜单栏文本.push_str("</div>");
            }
            菜单栏文本.push_str("</div>");
        }
        菜单栏文本.push_str("</div>");
    }
    菜单栏文本
}

fn 拼装底部图标坞(桌面图标: &[serde_json::Value]) -> String {
    let mut 图标坞文本 = String::new();
    for 图标项 in 桌面图标.iter().take(10) {
        图标坞文本.push_str("<div class=\"hs-dock-item\" title=\"");
        图标坞文本.push_str(&转义网页文本(&取对象文本(图标项, "名称")));
        图标坞文本.push_str("\">");
        图标坞文本.push_str(&转义网页文本(&取对象文本(图标项, "图标")));
        图标坞文本.push_str("</div>");
    }
    图标坞文本
}

fn 渲染桌面外壳(参数表: &[&[u8]]) -> Result<(u32, Vec<u8>), u32> {
    let 品牌文本 = 取文本参数(参数表, 0)?;
    let 桌面图标原文 = 取文本参数(参数表, 1)?;
    let 窗口标题文本 = 取文本参数(参数表, 2)?;
    // 窗口内容原文是同一次请求里由本库其他能力生成的 HTML 片段，按片段原样内嵌，不做二次转义。
    let 窗口内容原文 = 取文本参数(参数表, 3)?;
    let 菜单条目原文 = 取文本参数(参数表, 4)?;
    let 桌面图标值 = 解析数组参数(&桌面图标原文, 64)?;
    let 桌面图标 = 桌面图标值.as_array().ok_or(错误码::内容不合法)?;
    let 菜单条目值 = 解析数组参数(&菜单条目原文, 16)?;
    let 菜单条目 = 菜单条目值.as_array().ok_or(错误码::内容不合法)?;
    let mut 页面主体文本 = String::new();
    页面主体文本.push_str(
        "<div class=\"hs-desktop\"><div class=\"hs-menubar\"><span class=\"hs-menubar-brand\">",
    );
    页面主体文本.push_str(&转义网页文本(&品牌文本));
    页面主体文本.push_str("</span>");
    页面主体文本.push_str(&拼装顶部菜单(菜单条目));
    页面主体文本.push_str("</div><div class=\"hs-desktop-icons\">");
    页面主体文本.push_str(&拼装桌面图标(桌面图标));
    页面主体文本.push_str("</div><div class=\"hs-window\"><div class=\"hs-window-bar\"><span class=\"hs-window-dot is-close\"></span><span class=\"hs-window-dot is-min\"></span><span class=\"hs-window-dot is-max\"></span><span class=\"hs-window-title\">");
    页面主体文本.push_str(&转义网页文本(&窗口标题文本));
    页面主体文本.push_str("</span></div><div class=\"hs-window-body\">");
    页面主体文本.push_str(&窗口内容原文);
    页面主体文本.push_str("</div></div><div class=\"hs-dock\">");
    页面主体文本.push_str(&拼装底部图标坞(桌面图标));
    页面主体文本.push_str("</div></div>");
    Ok((
        4,
        拼装整页外壳(&窗口标题文本, " class=\"hs-desktop-body\"", &页面主体文本, &完整样式文本()),
    ))
}

fn 拼装下拉选项(选项列表: &serde_json::Value) -> String {
    let mut 选项文本 = String::new();
    let Some(选项表) = 选项列表.as_array() else {
        return 选项文本;
    };
    for 选项项 in 选项表 {
        选项文本.push_str("<option value=\"");
        选项文本.push_str(&转义网页文本(&转文本值(选项项)));
        选项文本.push_str("\">");
        选项文本.push_str(&转义网页文本(&转文本值(选项项)));
        选项文本.push_str("</option>");
    }
    选项文本
}

fn 渲染输入控件(参数表: &[&[u8]]) -> Result<(u32, Vec<u8>), u32> {
    let 控件种类文本 = 取文本参数(参数表, 0)?;
    let 控件名称文本 = 取文本参数(参数表, 1)?;
    let 控件配置原文 = 取文本参数(参数表, 2)?;
    let 控件配置值: serde_json::Value =
        serde_json::from_str(&控件配置原文).map_err(|_| 错误码::内容不合法)?;
    if !控件配置值.is_object() {
        return Err(错误码::内容不合法);
    }
    let 控件标签文本 = 取对象文本(&控件配置值, "标签");
    let 控件缺省值文本 = 取对象文本(&控件配置值, "缺省值");
    let 控件占位文本 = 取对象文本(&控件配置值, "占位文本");
    let 显示标签文本 = if 控件标签文本.is_empty() {
        控件名称文本.clone()
    } else {
        控件标签文本
    };
    let mut 控件主体文本 = String::new();
    控件主体文本.push_str("<div class=\"hs-form-item\"><label class=\"hs-form-label\">");
    控件主体文本.push_str(&转义网页文本(&显示标签文本));
    控件主体文本.push_str("</label>");
    match 控件种类文本.as_str() {
        "文本框" | "密码框" | "数字框" => {
            let 输入类型 = match 控件种类文本.as_str() {
                "密码框" => "password",
                "数字框" => "number",
                _ => "text",
            };
            控件主体文本.push_str("<input class=\"hs-input\" type=\"");
            控件主体文本.push_str(输入类型);
            控件主体文本.push_str("\" name=\"");
            控件主体文本.push_str(&转义网页文本(&控件名称文本));
            控件主体文本.push_str("\" placeholder=\"");
            控件主体文本.push_str(&转义网页文本(&控件占位文本));
            控件主体文本.push_str("\" value=\"");
            控件主体文本.push_str(&转义网页文本(&控件缺省值文本));
            控件主体文本.push_str("\" />");
        }
        "下拉选择" => {
            控件主体文本.push_str("<select class=\"hs-select\" name=\"");
            控件主体文本.push_str(&转义网页文本(&控件名称文本));
            控件主体文本.push_str("\">");
            let 选项列表 = 控件配置值
                .get("选项列表")
                .cloned()
                .unwrap_or(serde_json::Value::Null);
            控件主体文本.push_str(&拼装下拉选项(&选项列表));
            控件主体文本.push_str("</select>");
        }
        _ => return Err(错误码::内容不合法),
    }
    控件主体文本.push_str("</div>");
    Ok((4, 控件主体文本.into_bytes()))
}

fn 渲染按钮(参数表: &[&[u8]]) -> Result<(u32, Vec<u8>), u32> {
    let 按钮标签文本 = 取文本参数(参数表, 0)?;
    let 按钮动作文本 = 取文本参数(参数表, 1)?;
    let 按钮样式文本 = 取文本参数(参数表, 2)?;
    let 按钮样式类 = match 按钮样式文本.as_str() {
        "" | "默认" => "hs-button",
        "主要" => "hs-button hs-button-primary",
        "成功" => "hs-button hs-button-success",
        "警告" => "hs-button hs-button-warning",
        "危险" => "hs-button hs-button-danger",
        _ => return Err(错误码::内容不合法),
    };
    let mut 按钮文本 = String::new();
    按钮文本.push_str("<button class=\"");
    按钮文本.push_str(按钮样式类);
    按钮文本.push_str("\" data-action=\"");
    按钮文本.push_str(&转义网页文本(&按钮动作文本));
    按钮文本.push_str("\">");
    按钮文本.push_str(&转义网页文本(&按钮标签文本));
    按钮文本.push_str("</button>");
    Ok((4, 按钮文本.into_bytes()))
}

fn 渲染区块组(参数表: &[&[u8]]) -> Result<(u32, Vec<u8>), u32> {
    let 区块定义原文 = 取文本参数(参数表, 0)?;
    let 区块定义值: serde_json::Value =
        serde_json::from_str(&区块定义原文).map_err(|_| 错误码::内容不合法)?;
    let 区块定义表 = 区块定义值
        .get("区块")
        .and_then(|区块项| 区块项.as_array())
        .ok_or(错误码::内容不合法)?;
    if 区块定义表.len() > 64 {
        return Err(错误码::资源受限);
    }
    Ok((4, 拼装页面区块(区块定义表)?.into_bytes()))
}

/// 拼装聊天片段：4927 与组件树的「聊天流」叶子共用，返回 .hs-chat 气泡列表。
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

fn 渲染聊天消息流(参数表: &[&[u8]]) -> Result<(u32, Vec<u8>), u32> {
    let 聊天定义原文 = 取文本参数(参数表, 0)?;
    let 聊天定义值: serde_json::Value =
        serde_json::from_str(&聊天定义原文).map_err(|_| 错误码::内容不合法)?;
    let 消息表 = 聊天定义值
        .get("消息")
        .and_then(|消息项| 消息项.as_array())
        .ok_or(错误码::内容不合法)?;
    let 空态文本 = 取对象文本(&聊天定义值, "空态文案");
    Ok((4, 拼装聊天片段(消息表, &空态文本)?.into_bytes()))
}

pub fn 执行业务操作(编号: u32, 参数表: &[&[u8]]) -> Result<(u32, Vec<u8>), u32> {
    match 编号 {
        能力号::渲染页面骨架 => 渲染页面骨架(参数表),
        能力号::渲染数据表格 => 渲染数据表格(参数表),
        能力号::渲染表单 => 渲染表单(参数表),
        能力号::渲染对话框 => 渲染对话框(参数表),
        能力号::渲染侧栏布局 => 渲染侧栏布局(参数表),
        能力号::渲染桌面外壳 => 渲染桌面外壳(参数表),
        能力号::渲染输入控件 => 渲染输入控件(参数表),
        能力号::渲染按钮 => 渲染按钮(参数表),
        能力号::渲染登录页 => crate::桌面部件::渲染登录页(参数表),
        能力号::渲染桌面菜单栏 => crate::桌面部件::渲染桌面菜单栏(参数表),
        能力号::渲染桌面图标区 => crate::桌面部件::渲染桌面图标区(参数表),
        能力号::渲染桌面图标坞 => crate::桌面部件::渲染桌面图标坞(参数表),
        能力号::渲染窗口 => crate::桌面部件::渲染窗口(参数表),
        能力号::渲染桌面交互脚本 => {
            crate::交互脚本::渲染桌面交互脚本(参数表)
        }
        能力号::渲染完整桌面 => crate::桌面部件::渲染完整桌面(参数表),
        能力号::渲染启动器 => crate::桌面部件::渲染启动器(参数表),
        能力号::渲染区块组 => 渲染区块组(参数表),
        能力号::渲染聊天消息流 => 渲染聊天消息流(参数表),
        能力号::渲染组件树 => crate::组件树::渲染组件树(参数表),
        _ => Err(错误码::参数不合法),
    }
}
