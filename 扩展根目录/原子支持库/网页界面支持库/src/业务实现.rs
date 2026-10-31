use crate::编号与码面::{能力号,错误码};

fn 取文本参数(参数表:&[&[u8]],参数序号:usize)->Result<String,u32> {
    Ok(std::str::from_utf8(参数表[参数序号]).map_err(|_|错误码::参数不合法)?.to_string())
}

fn 转义网页文本(原始文本:&str)->String {
    let mut 转义后文本=String::with_capacity(原始文本.len());
    for 待转义字符 in 原始文本.chars() {
        match 待转义字符 {
            '&'=>转义后文本.push_str("&amp;"),
            '<'=>转义后文本.push_str("&lt;"),
            '>'=>转义后文本.push_str("&gt;"),
            '"'=>转义后文本.push_str("&quot;"),
            '\''=>转义后文本.push_str("&#39;"),
            _=>转义后文本.push(待转义字符),
        }
    }
    转义后文本
}

fn 转文本值(数据值:&serde_json::Value)->String {
    match 数据值 {
        serde_json::Value::String(文本内容)=>文本内容.clone(),
        serde_json::Value::Null=>String::new(),
        _=>数据值.to_string(),
    }
}

fn 生成主题样式()->&'static str {
    r#"<style>
:root{--hs-primary:#4a90e2;--hs-bg:#f5f7fa;--hs-card:#ffffff;--hs-text:#0f172a;--hs-muted:#94a3b8;--hs-border:#e2e8f0}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;background:var(--hs-bg);color:var(--hs-text);-webkit-font-smoothing:antialiased}
.hs-page{padding:24px;max-width:1280px;margin:0 auto}
.hs-title{margin:0 0 16px;font-size:22px;font-weight:700;letter-spacing:.5px}
.hs-card{background:var(--hs-card);border:1px solid var(--hs-border);border-radius:10px;padding:20px;margin-bottom:16px;box-shadow:0 2px 8px rgba(15,23,42,.04)}
.hs-table{width:100%;border-collapse:collapse;font-size:14px}
.hs-table th{text-align:left;padding:10px 12px;background:#f8fafc;color:#475569;font-weight:600;border-bottom:1px solid var(--hs-border);white-space:nowrap}
.hs-table td{padding:10px 12px;border-bottom:1px solid #f1f5f9;color:#334155}
.hs-table tbody tr:hover td{background:#f8fafc}
.hs-form-item{margin-bottom:16px}
.hs-form-label{display:block;margin-bottom:6px;font-size:13px;color:#475569;font-weight:500}
.hs-input{width:100%;padding:9px 12px;border:1px solid var(--hs-border);border-radius:6px;font-size:14px;font-family:inherit;color:var(--hs-text);background:#fff}
.hs-input:focus{outline:none;border-color:var(--hs-primary);box-shadow:0 0 0 3px rgba(74,144,226,.12)}
.hs-dialog{background:var(--hs-card);border-radius:12px;padding:20px;border:1px solid var(--hs-border);box-shadow:0 8px 24px rgba(15,23,42,.08)}
.hs-dialog-title{font-size:16px;font-weight:600;margin:0 0 12px}
.hs-dialog-body{font-size:14px;color:#475569;margin-bottom:16px;line-height:1.6}
.hs-dialog-actions{display:flex;justify-content:flex-end;gap:8px}
.hs-button{padding:8px 16px;border:1px solid var(--hs-border);border-radius:6px;background:#fff;font-size:14px;cursor:pointer;font-family:inherit;color:#334155}
.hs-button:hover{background:#f8fafc}
.hs-button-primary{background:var(--hs-primary);border-color:var(--hs-primary);color:#fff}
.hs-button-primary:hover{background:#3b82d6}
</style>"#
}

fn 拼装表格行(表格列定义:&[serde_json::Value],表格行数据:&[serde_json::Value])->Result<String,u32> {
    let mut 表格主体文本=String::new();
    表格主体文本.push_str("<table class=\"hs-table\"><thead><tr>");
    for 列名项 in 表格列定义 {
        表格主体文本.push_str("<th>");
        表格主体文本.push_str(&转义网页文本(&转文本值(列名项)));
        表格主体文本.push_str("</th>");
    }
    表格主体文本.push_str("</tr></thead><tbody>");
    for 行项 in 表格行数据 {
        let 单元格表=行项.as_array().ok_or(错误码::内容不合法)?;
        表格主体文本.push_str("<tr>");
        for 列序 in 0..表格列定义.len() {
            let 单元格值文本=单元格表.get(列序).map(转文本值).unwrap_or_default();
            表格主体文本.push_str("<td>");
            表格主体文本.push_str(&转义网页文本(&单元格值文本));
            表格主体文本.push_str("</td>");
        }
        表格主体文本.push_str("</tr>");
    }
    表格主体文本.push_str("</tbody></table>");
    Ok(表格主体文本)
}

fn 拼装表单字段(字段定义:&[serde_json::Value],当前值:&serde_json::Value)->Result<String,u32> {
    let mut 表单主体文本=String::new();
    for 字段项 in 字段定义 {
        let 字段名文本=字段项.get("名").map(转文本值).unwrap_or_default();
        if 字段名文本.is_empty() { return Err(错误码::内容不合法); }
        let 字段标签文本=字段项.get("标签").map(转文本值).filter(|标签| !标签.is_empty()).unwrap_or_else(|| 字段名文本.clone());
        let 字段值文本=当前值.get(&字段名文本).map(转文本值).unwrap_or_default();
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

fn 拼装按钮组(按钮定义:&[serde_json::Value])->String {
    let mut 按钮组文本=String::new();
    for (按钮序,按钮项) in 按钮定义.iter().enumerate() {
        let 按钮标签文本=按钮项.get("标签").map(转文本值).unwrap_or_default();
        let 按钮动作文本=按钮项.get("动作").map(转文本值).unwrap_or_default();
        let 按钮样式=if 按钮序==0 {"hs-button hs-button-primary"} else {"hs-button"};
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

fn 渲染数据表格(参数表:&[&[u8]])->Result<(u32,Vec<u8>),u32> {
    let 列定义原文=取文本参数(参数表,0)?;
    let 行定义原文=取文本参数(参数表,1)?;
    let 表格列定义值:serde_json::Value=serde_json::from_str(&列定义原文).map_err(|_|错误码::内容不合法)?;
    let 表格行数据值:serde_json::Value=serde_json::from_str(&行定义原文).map_err(|_|错误码::内容不合法)?;
    let 表格列定义=表格列定义值.as_array().ok_or(错误码::内容不合法)?;
    let 表格行数据=表格行数据值.as_array().ok_or(错误码::内容不合法)?;
    if 表格列定义.len()>64 || 表格行数据.len()>4096 { return Err(错误码::资源受限); }
    Ok((4,拼装表格行(表格列定义,表格行数据)?.into_bytes()))
}

fn 渲染表单(参数表:&[&[u8]])->Result<(u32,Vec<u8>),u32> {
    let 字段定义原文=取文本参数(参数表,0)?;
    let 当前值原文=取文本参数(参数表,1)?;
    let 字段定义值:serde_json::Value=serde_json::from_str(&字段定义原文).map_err(|_|错误码::内容不合法)?;
    let 当前值映射:serde_json::Value=serde_json::from_str(&当前值原文).map_err(|_|错误码::内容不合法)?;
    if !当前值映射.is_object() { return Err(错误码::内容不合法); }
    let 字段定义=字段定义值.as_array().ok_or(错误码::内容不合法)?;
    if 字段定义.len()>128 { return Err(错误码::资源受限); }
    Ok((4,拼装表单字段(字段定义,&当前值映射)?.into_bytes()))
}

fn 渲染对话框(参数表:&[&[u8]])->Result<(u32,Vec<u8>),u32> {
    let 对话框标题文本=取文本参数(参数表,0)?;
    let 对话框内容文本=取文本参数(参数表,1)?;
    let 按钮定义原文=取文本参数(参数表,2)?;
    let 按钮定义值:serde_json::Value=serde_json::from_str(&按钮定义原文).map_err(|_|错误码::内容不合法)?;
    let 按钮定义=按钮定义值.as_array().ok_or(错误码::内容不合法)?;
    if 按钮定义.len()>8 { return Err(错误码::资源受限); }
    let mut 对话框主体文本=String::new();
    对话框主体文本.push_str("<div class=\"hs-dialog\"><h3 class=\"hs-dialog-title\">");
    对话框主体文本.push_str(&转义网页文本(&对话框标题文本));
    对话框主体文本.push_str("</h3><div class=\"hs-dialog-body\">");
    对话框主体文本.push_str(&转义网页文本(&对话框内容文本));
    对话框主体文本.push_str("</div><div class=\"hs-dialog-actions\">");
    对话框主体文本.push_str(&拼装按钮组(按钮定义));
    对话框主体文本.push_str("</div></div>");
    Ok((4,对话框主体文本.into_bytes()))
}

fn 拼装页面区块(区块定义:&[serde_json::Value])->Result<String,u32> {
    let mut 页面区块文本=String::new();
    for 区块项 in 区块定义 {
        let 区块类型文本=区块项.get("类型").map(转文本值).unwrap_or_default();
        let 区块内容文本=match 区块类型文本.as_str() {
            "标题栏"=>{
                let 区块标题文本=区块项.get("文本").map(转文本值).unwrap_or_default();
                format!("<h1 class=\"hs-title\">{}</h1>",转义网页文本(&区块标题文本))
            }
            "数据表格"=>{
                let 表格列定义=区块项.get("列").and_then(|列项|列项.as_array()).ok_or(错误码::内容不合法)?;
                let 表格行数据=区块项.get("行").and_then(|行项|行项.as_array()).ok_or(错误码::内容不合法)?;
                format!("<div class=\"hs-card\">{}</div>",拼装表格行(表格列定义,表格行数据)?)
            }
            "表单"=>{
                let 字段定义=区块项.get("字段").and_then(|字段项|字段项.as_array()).ok_or(错误码::内容不合法)?;
                let 表单缺省值=区块项.get("值").cloned().unwrap_or_else(||serde_json::Value::Object(serde_json::Map::new()));
                format!("<div class=\"hs-card\">{}</div>",拼装表单字段(字段定义,&表单缺省值)?)
            }
            "对话框"=>{
                let 区块标题文本=区块项.get("标题").map(转文本值).unwrap_or_default();
                let 区块内容文本=区块项.get("内容").map(转文本值).unwrap_or_default();
                let 按钮定义=区块项.get("按钮").and_then(|按钮项|按钮项.as_array()).map(|按钮项|按钮项.to_vec()).unwrap_or_default();
                let mut 对话框主体文本=String::new();
                对话框主体文本.push_str("<div class=\"hs-dialog\"><h3 class=\"hs-dialog-title\">");
                对话框主体文本.push_str(&转义网页文本(&区块标题文本));
                对话框主体文本.push_str("</h3><div class=\"hs-dialog-body\">");
                对话框主体文本.push_str(&转义网页文本(&区块内容文本));
                对话框主体文本.push_str("</div><div class=\"hs-dialog-actions\">");
                对话框主体文本.push_str(&拼装按钮组(&按钮定义));
                对话框主体文本.push_str("</div></div>");
                对话框主体文本
            }
            "文字"=>{
                let 区块内容文本=区块项.get("文本").map(转文本值).unwrap_or_default();
                format!("<div class=\"hs-card\">{}</div>",转义网页文本(&区块内容文本))
            }
            _=>return Err(错误码::内容不合法),
        };
        页面区块文本.push_str(&区块内容文本);
    }
    Ok(页面区块文本)
}

fn 渲染页面骨架(参数表:&[&[u8]])->Result<(u32,Vec<u8>),u32> {
    let 页面标题文本=取文本参数(参数表,0)?;
    let 主题标识文本=取文本参数(参数表,1)?;
    let 区块定义原文=取文本参数(参数表,2)?;
    let 区块定义值:serde_json::Value=serde_json::from_str(&区块定义原文).map_err(|_|错误码::内容不合法)?;
    let 区块定义表=区块定义值.get("区块").and_then(|区块项|区块项.as_array()).ok_or(错误码::内容不合法)?;
    if 区块定义表.len()>64 { return Err(错误码::资源受限); }
    let 页面区块文本=拼装页面区块(区块定义表)?;
    let mut 整页样式=String::new();
    整页样式.push_str("<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>");
    整页样式.push_str(&转义网页文本(&页面标题文本));
    整页样式.push_str("</title>");
    整页样式.push_str(生成主题样式());
    整页样式.push_str("</head><body><div class=\"hs-page\" data-theme=\"");
    整页样式.push_str(&转义网页文本(&主题标识文本));
    整页样式.push_str("\"><h1 class=\"hs-title\">");
    整页样式.push_str(&转义网页文本(&页面标题文本));
    整页样式.push_str("</h1>");
    整页样式.push_str(&页面区块文本);
    整页样式.push_str("</div></body></html>");
    Ok((4,整页样式.into_bytes()))
}

pub fn 执行业务操作(编号:u32,参数表:&[&[u8]])->Result<(u32,Vec<u8>),u32> {
    match 编号 {
        能力号::渲染页面骨架=>渲染页面骨架(参数表),
        能力号::渲染数据表格=>渲染数据表格(参数表),
        能力号::渲染表单=>渲染表单(参数表),
        能力号::渲染对话框=>渲染对话框(参数表),
        _=>Err(错误码::参数不合法),
    }
}
