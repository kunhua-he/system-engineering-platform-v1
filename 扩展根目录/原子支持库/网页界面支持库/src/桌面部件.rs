//! 桌面部件：登录页、菜单栏、图标区、图标坞、窗口、启动器的 HTML 拼装。
//!
//! 所有取值来自 V3 视觉基准（`视觉基准.rs`），类名与 V3 语义对应；
//! 本文件只拼装结构，样式一律由基准样式提供，调用方只传声明数据。

use crate::业务实现::{
    取对象文本, 取文本参数, 拼装整页外壳, 解析对象参数, 解析数组参数, 转义网页文本, 转文本值,
};
use crate::编号与码面::错误码;

fn 取数组字段<'a>(
    配置值: &'a serde_json::Value,
    字段名: &str,
) -> Result<&'a [serde_json::Value], u32> {
    let 字段值 = 配置值.get(字段名).ok_or(错误码::内容不合法)?;
    字段值
        .as_array()
        .map(|表| 表.as_slice())
        .ok_or(错误码::内容不合法)
}

fn 取逻辑字段(配置值: &serde_json::Value, 字段名: &str) -> bool {
    配置值
        .get(字段名)
        .and_then(|字段值| 字段值.as_bool())
        .unwrap_or(false)
}

fn 取正整数(配置值: &serde_json::Value, 字段名: &str, 缺省值: i64) -> i64 {
    match 配置值.get(字段名) {
        Some(serde_json::Value::Number(数值)) => 数值.as_i64().unwrap_or(缺省值),
        Some(serde_json::Value::String(文本内容)) => {
            文本内容.trim().parse::<i64>().unwrap_or(缺省值)
        }
        _ => 缺省值,
    }
}

fn 取键文本(条目项: &serde_json::Value) -> String {
    let 键文本 = 取对象文本(条目项, "键");
    if 键文本.is_empty() {
        取对象文本(条目项, "名称")
    } else {
        键文本
    }
}

/// 4918 渲染登录页：整页 HTML，居中卡片、两输入框、全宽主按钮。
pub(crate) fn 渲染登录页(参数表: &[&[u8]]) -> Result<(u32, Vec<u8>), u32> {
    let 登录标题文本 = 取文本参数(参数表, 0)?;
    let 登录副标题文本 = 取文本参数(参数表, 1)?;
    let 登录配置原文 = 取文本参数(参数表, 2)?;
    let 登录配置 = 解析对象参数(&登录配置原文)?;
    let 图标字形文本 = 取对象文本(&登录配置, "图标字形");
    let 账号占位文本 = 取对象文本(&登录配置, "账号占位文本");
    let 密码占位文本 = 取对象文本(&登录配置, "密码占位文本");
    let 按钮文本 = 取对象文本(&登录配置, "按钮文本");
    let 错误提示文本 = 取对象文本(&登录配置, "错误提示文本");
    let 提交地址文本 = 取对象文本(&登录配置, "提交地址");
    let 账号字段名文本 = 取对象文本(&登录配置, "账号字段名");
    let 密码字段名文本 = 取对象文本(&登录配置, "密码字段名");
    let 页脚提示文本 = 取对象文本(&登录配置, "页脚提示文本");

    let mut 页面主体文本 = String::new();
    页面主体文本.push_str("<div class=\"hs-login-page\"><div class=\"hs-login-card\">");
    页面主体文本.push_str("<div class=\"hs-login-icon\">");
    页面主体文本.push_str(&转义网页文本(&图标字形文本));
    页面主体文本.push_str("</div><h1 class=\"hs-login-title\">");
    页面主体文本.push_str(&转义网页文本(&登录标题文本));
    页面主体文本.push_str("</h1><p class=\"hs-login-sub\">");
    页面主体文本.push_str(&转义网页文本(&登录副标题文本));
    页面主体文本.push_str("</p><form class=\"hs-login-form\" method=\"post\" action=\"");
    页面主体文本.push_str(&转义网页文本(&提交地址文本));
    页面主体文本.push_str(
        "\"><div class=\"hs-login-field\"><span class=\"hs-login-prefix\">&#128100;</span>",
    );
    页面主体文本.push_str("<input class=\"hs-login-input\" type=\"text\" name=\"");
    页面主体文本.push_str(&转义网页文本(&账号字段名文本));
    页面主体文本.push_str("\" placeholder=\"");
    页面主体文本.push_str(&转义网页文本(&账号占位文本));
    页面主体文本.push_str("\" autocomplete=\"username\" required /></div>");
    页面主体文本
        .push_str("<div class=\"hs-login-field\"><span class=\"hs-login-prefix\">&#128274;</span>");
    页面主体文本.push_str("<input class=\"hs-login-input\" type=\"password\" name=\"");
    页面主体文本.push_str(&转义网页文本(&密码字段名文本));
    页面主体文本.push_str("\" placeholder=\"");
    页面主体文本.push_str(&转义网页文本(&密码占位文本));
    页面主体文本.push_str("\" autocomplete=\"current-password\" required /></div>");
    页面主体文本.push_str("<button class=\"hs-login-btn\" type=\"submit\">");
    页面主体文本.push_str(&转义网页文本(&按钮文本));
    页面主体文本.push_str("</button></form>");
    if !错误提示文本.is_empty() {
        页面主体文本.push_str("<div class=\"hs-login-error\">");
        页面主体文本.push_str(&转义网页文本(&错误提示文本));
        页面主体文本.push_str("</div>");
    }
    if !页脚提示文本.is_empty() {
        页面主体文本.push_str("<p class=\"hs-login-sub\" style=\"margin-top:18px\">");
        页面主体文本.push_str(&转义网页文本(&页脚提示文本));
        页面主体文本.push_str("</p>");
    }
    页面主体文本.push_str("</div></div>");
    Ok((4, 拼装整页外壳(&登录标题文本, "", &页面主体文本)))
}

fn 拼装菜单条目(菜单条目表: &[serde_json::Value]) -> String {
    let mut 菜单栏文本 = String::new();
    for 菜单项 in 菜单条目表 {
        菜单栏文本.push_str("<span class=\"hs-menubar-item\" data-menu=\"");
        菜单栏文本.push_str(&转义网页文本(&取键文本(菜单项)));
        菜单栏文本.push_str("\">");
        菜单栏文本.push_str(&转义网页文本(&取对象文本(菜单项, "名称")));
        菜单栏文本.push_str("</span>");
    }
    菜单栏文本
}

fn 拼装状态区条目(状态区条目表: &[serde_json::Value]) -> String {
    let mut 状态区文本 = String::new();
    for 状态项 in 状态区条目表 {
        let 徽标文本 = 取对象文本(状态项, "徽标");
        状态区文本.push_str("<span class=\"hs-menubar-item\">");
        状态区文本.push_str(&转义网页文本(&取对象文本(状态项, "名称")));
        if !徽标文本.is_empty() {
            状态区文本.push_str("<span class=\"hs-menubar-badge\">");
            状态区文本.push_str(&转义网页文本(&徽标文本));
            状态区文本.push_str("</span>");
        }
        状态区文本.push_str("</span>");
    }
    状态区文本
}

/// 4919 渲染桌面菜单栏：左品牌与应用菜单、右状态区与时钟。
pub(crate) fn 渲染桌面菜单栏(参数表: &[&[u8]]) -> Result<(u32, Vec<u8>), u32> {
    let 品牌文本 = 取文本参数(参数表, 0)?;
    let 应用名称文本 = 取文本参数(参数表, 1)?;
    let 菜单条目原文 = 取文本参数(参数表, 2)?;
    let 状态区条目原文 = 取文本参数(参数表, 3)?;
    let 菜单条目值 = 解析数组参数(&菜单条目原文, 16)?;
    let 菜单条目表 = 菜单条目值.as_array().ok_or(错误码::内容不合法)?;
    let 状态区条目值 = 解析数组参数(&状态区条目原文, 16)?;
    let 状态区条目表 = 状态区条目值.as_array().ok_or(错误码::内容不合法)?;
    let mut 菜单栏文本 = String::new();
    菜单栏文本.push_str("<div class=\"hs-menubar\"><div class=\"hs-menubar-left\">");
    if !品牌文本.is_empty() {
        菜单栏文本.push_str("<span class=\"hs-menubar-brand\">");
        菜单栏文本.push_str(&转义网页文本(&品牌文本));
        菜单栏文本.push_str("</span>");
    }
    if !应用名称文本.is_empty() {
        菜单栏文本.push_str("<span class=\"hs-menubar-app\">");
        菜单栏文本.push_str(&转义网页文本(&应用名称文本));
        菜单栏文本.push_str("</span>");
    }
    菜单栏文本.push_str(&拼装菜单条目(菜单条目表));
    菜单栏文本.push_str("</div><div class=\"hs-menubar-right\">");
    菜单栏文本.push_str(&拼装状态区条目(状态区条目表));
    菜单栏文本
        .push_str("<span class=\"hs-menubar-item hs-menubar-clock\" data-clock=\"1\"></span>");
    菜单栏文本.push_str("</div></div>");
    Ok((4, 菜单栏文本.into_bytes()))
}

fn 拼装图标条目(
    图标项: &serde_json::Value,
    选中键文本: &str,
    序号: usize,
    分类文本: &str,
) -> String {
    let 图标键文本 = 取键文本(图标项);
    let 图标名称文本 = 取对象文本(图标项, "名称");
    let 图标字形文本 = 取对象文本(图标项, "图标");
    let mut 条目文本 = String::new();
    条目文本.push_str("<div class=\"hs-icon");
    if 图标键文本 == 选中键文本 && !选中键文本.is_empty() {
        条目文本.push_str(" is-selected");
    }
    条目文本.push_str("\" data-app=\"");
    条目文本.push_str(&转义网页文本(&图标键文本));
    条目文本.push_str("\" data-index=\"");
    条目文本.push_str(&序号.to_string());
    条目文本.push_str("\" data-category=\"");
    条目文本.push_str(&转义网页文本(分类文本));
    条目文本.push_str("\" title=\"");
    条目文本.push_str(&转义网页文本(&图标名称文本));
    条目文本.push_str("\"><div class=\"hs-icon-glyph\">");
    条目文本.push_str(&转义网页文本(&图标字形文本));
    条目文本.push_str("</div><span class=\"hs-icon-label\">");
    条目文本.push_str(&转义网页文本(&图标名称文本));
    条目文本.push_str("</span></div>");
    条目文本
}

/// 4920 渲染桌面图标区：单一网格（与 V3 一致），分类只随 data-category 带出，摆放交给交互脚本按屏幕算。
pub(crate) fn 渲染桌面图标区(参数表: &[&[u8]]) -> Result<(u32, Vec<u8>), u32> {
    let 图标分组原文 = 取文本参数(参数表, 0)?;
    let 选中图标键文本 = 取文本参数(参数表, 1)?;
    let 图标分组值 = 解析数组参数(&图标分组原文, 16)?;
    let 图标分组表 = 图标分组值.as_array().ok_or(错误码::内容不合法)?;
    let mut 图标层文本 = String::new();
    图标层文本
        .push_str("<div class=\"hs-icon-layer\"><div class=\"hs-icon-grid\" data-icon-grid=\"1\">");
    let mut 序号: usize = 0;
    for 分组项 in 图标分组表 {
        let 分类名称文本 = 取对象文本(分组项, "分类");
        let 分组图标表 = 分组项
            .get("图标")
            .and_then(|图标值| 图标值.as_array())
            .ok_or(错误码::内容不合法)?;
        if 分组图标表.len() > 64 {
            return Err(错误码::资源受限);
        }
        for 图标项 in 分组图标表 {
            图标层文本.push_str(&拼装图标条目(
                图标项,
                &选中图标键文本,
                序号,
                &分类名称文本,
            ));
            序号 += 1;
            if 序号 > 64 {
                return Err(错误码::资源受限);
            }
        }
    }
    图标层文本.push_str("</div></div>");
    Ok((4, 图标层文本.into_bytes()))
}

fn 键表包含(运行中键表: &[serde_json::Value], 待查键: &str) -> bool {
    运行中键表.iter().any(|键项| 转文本值(键项) == 待查键)
}

/// 4921 渲染桌面图标坞：固定图标与运行中指示点。
pub(crate) fn 渲染桌面图标坞(参数表: &[&[u8]]) -> Result<(u32, Vec<u8>), u32> {
    let 坞条目原文 = 取文本参数(参数表, 0)?;
    let 运行中键表原文 = 取文本参数(参数表, 1)?;
    let 坞条目值 = 解析数组参数(&坞条目原文, 32)?;
    let 坞条目表 = 坞条目值.as_array().ok_or(错误码::内容不合法)?;
    let 运行中键表值 = if 运行中键表原文.trim().is_empty() {
        serde_json::Value::Array(Vec::new())
    } else {
        解析数组参数(&运行中键表原文, 32)?
    };
    let 运行中键表 = 运行中键表值.as_array().ok_or(错误码::内容不合法)?;
    let mut 图标坞文本 = String::new();
    图标坞文本.push_str("<div class=\"hs-dock\">");
    for 坞项 in 坞条目表 {
        let 坞键文本 = 取键文本(坞项);
        let 坞名称文本 = 取对象文本(坞项, "名称");
        if 取对象文本(坞项, "分隔") == "真" {
            图标坞文本.push_str("<span class=\"hs-dock-sep\"></span>");
            continue;
        }
        图标坞文本.push_str("<div class=\"hs-dock-item\" data-app=\"");
        图标坞文本.push_str(&转义网页文本(&坞键文本));
        图标坞文本.push_str("\" title=\"");
        图标坞文本.push_str(&转义网页文本(&坞名称文本));
        图标坞文本.push_str("\"><span>");
        图标坞文本.push_str(&转义网页文本(&取对象文本(坞项, "图标")));
        图标坞文本.push_str("</span>");
        if 键表包含(运行中键表, &坞键文本) {
            图标坞文本.push_str("<i class=\"hs-dock-dot\"></i>");
        }
        图标坞文本.push_str("</div>");
    }
    图标坞文本.push_str("</div>");
    Ok((4, 图标坞文本.into_bytes()))
}

fn 拼装单个窗口(窗口编号文本: &str, 窗口定义: &serde_json::Value) -> String {
    let 窗口标题文本 = 取对象文本(窗口定义, "标题");
    let 窗口内容原文 = 取对象文本(窗口定义, "内容原文");
    let 横坐标 = 取正整数(窗口定义, "横坐标", 120);
    let 纵坐标 = 取正整数(窗口定义, "纵坐标", 96);
    let 宽度 = 取正整数(窗口定义, "宽度", 760).clamp(320, 4096);
    let 高度 = 取正整数(窗口定义, "高度", 520).clamp(180, 4096);
    let 层级 = 取正整数(窗口定义, "层级", 100).clamp(100, 99999);
    let 状态文本 = 取对象文本(窗口定义, "状态");
    let 活跃 = 取逻辑字段(窗口定义, "活跃");
    let mut 窗口文本 = String::new();
    窗口文本.push_str("<div class=\"hs-win");
    if 活跃 {
        窗口文本.push_str(" is-active");
    }
    if 状态文本 == "最小化" {
        窗口文本.push_str(" is-minimized");
    }
    窗口文本.push_str("\" id=\"hs-win-");
    窗口文本.push_str(&转义网页文本(窗口编号文本));
    窗口文本.push_str("\" data-win=\"");
    窗口文本.push_str(&转义网页文本(窗口编号文本));
    窗口文本.push_str("\" style=\"left:");
    窗口文本.push_str(&横坐标.to_string());
    窗口文本.push_str("px;top:");
    窗口文本.push_str(&(纵坐标 + 30).to_string());
    窗口文本.push_str("px;width:");
    窗口文本.push_str(&宽度.to_string());
    窗口文本.push_str("px;height:");
    窗口文本.push_str(&高度.to_string());
    窗口文本.push_str("px;z-index:");
    窗口文本.push_str(&层级.to_string());
    窗口文本.push_str("\"><div class=\"hs-win-bar\" data-drag=\"1\"><div class=\"hs-win-dots\">");
    窗口文本.push_str("<button class=\"hs-win-dot is-close\" type=\"button\" data-win-action=\"关闭\" title=\"关闭\"></button>");
    窗口文本.push_str("<button class=\"hs-win-dot is-min\" type=\"button\" data-win-action=\"最小化\" title=\"最小化\"></button>");
    窗口文本.push_str("<button class=\"hs-win-dot is-max\" type=\"button\" data-win-action=\"最大化\" title=\"最大化\"></button>");
    窗口文本.push_str("</div><span class=\"hs-win-title\">");
    窗口文本.push_str(&转义网页文本(&窗口标题文本));
    窗口文本.push_str("</span></div><div class=\"hs-win-body\">");
    窗口文本.push_str(&窗口内容原文);
    窗口文本.push_str("</div></div>");
    窗口文本
}

/// 4922 渲染窗口：标题栏三键、几何、层级与状态。
pub(crate) fn 渲染窗口(参数表: &[&[u8]]) -> Result<(u32, Vec<u8>), u32> {
    let 窗口编号文本 = 取文本参数(参数表, 0)?;
    let 窗口定义原文 = 取文本参数(参数表, 1)?;
    if 窗口编号文本.trim().is_empty() {
        return Err(错误码::参数不合法);
    }
    let 窗口定义 = 解析对象参数(&窗口定义原文)?;
    Ok((4, 拼装单个窗口(&窗口编号文本, &窗口定义).into_bytes()))
}

fn 拼装窗口层(窗口列表表: &[serde_json::Value]) -> String {
    let mut 窗口层文本 = String::new();
    for (窗口序, 窗口项) in 窗口列表表.iter().enumerate() {
        窗口层文本.push_str(&拼装单个窗口(&窗口序.to_string(), 窗口项));
    }
    窗口层文本
}

fn 拼装壁纸(桌面配置: &serde_json::Value) -> String {
    let 壁纸值文本 = 取对象文本(桌面配置, "壁纸值");
    if 壁纸值文本.is_empty() {
        return String::new();
    }
    let mut 壁纸文本 = String::new();
    壁纸文本.push_str("<div class=\"hs-wallpaper\" style=\"background-image:url(&quot;");
    壁纸文本.push_str(&转义网页文本(&壁纸值文本));
    壁纸文本.push_str("&quot;)\"></div>");
    壁纸文本
}

/// 4924 渲染完整桌面：壁纸 + 菜单栏 + 图标区 + 窗口层 + 图标坞 + 交互脚本。
pub(crate) fn 渲染完整桌面(参数表: &[&[u8]]) -> Result<(u32, Vec<u8>), u32> {
    let 品牌文本 = 取文本参数(参数表, 0)?;
    let 桌面配置原文 = 取文本参数(参数表, 1)?;
    let 图标分组原文 = 取文本参数(参数表, 2)?;
    let 窗口列表原文 = 取文本参数(参数表, 3)?;
    let 桌面配置 = 解析对象参数(&桌面配置原文)?;
    let 应用名称文本 = 取对象文本(&桌面配置, "应用名称");
    let 菜单条目表 = 取数组字段(&桌面配置, "菜单条目表")?;
    let 状态区条目表 = 取数组字段(&桌面配置, "状态区条目表")?;
    let 坞条目表 = 取数组字段(&桌面配置, "坞条目表")?;
    let 运行中键表 = 取数组字段(&桌面配置, "运行中键表")?;
    let 窗口列表值 = 解析数组参数(&窗口列表原文, 32)?;
    let 窗口列表表 = 窗口列表值.as_array().ok_or(错误码::内容不合法)?;

    let mut 页面主体文本 = String::new();
    页面主体文本.push_str("<div class=\"hs-desk\">");
    页面主体文本.push_str(&拼装壁纸(&桌面配置));
    // 菜单栏
    页面主体文本.push_str("<div class=\"hs-menubar\"><div class=\"hs-menubar-left\">");
    if !品牌文本.is_empty() {
        页面主体文本.push_str("<span class=\"hs-menubar-brand\">");
        页面主体文本.push_str(&转义网页文本(&品牌文本));
        页面主体文本.push_str("</span>");
    }
    if !应用名称文本.is_empty() {
        页面主体文本.push_str("<span class=\"hs-menubar-app\">");
        页面主体文本.push_str(&转义网页文本(&应用名称文本));
        页面主体文本.push_str("</span>");
    }
    页面主体文本.push_str(&拼装菜单条目(菜单条目表));
    页面主体文本.push_str("</div><div class=\"hs-menubar-right\">");
    页面主体文本.push_str(&拼装状态区条目(状态区条目表));
    页面主体文本
        .push_str("<span class=\"hs-menubar-item hs-menubar-clock\" data-clock=\"1\"></span>");
    页面主体文本.push_str("</div></div>");
    // 图标区
    页面主体文本.push_str(&拼装图标区片段(&图标分组原文, "")?);
    // 窗口层
    页面主体文本.push_str("<div id=\"hs-win-layer\">");
    页面主体文本.push_str(&拼装窗口层(窗口列表表));
    页面主体文本.push_str("</div>");
    // 图标坞
    页面主体文本.push_str(&拼装坞片段(坞条目表, 运行中键表));
    // 启动器（默认隐藏，F4 或菜单「启动器」打开）
    let 启动器条目表 = 桌面配置
        .get("启动器条目表")
        .and_then(|条目值| 条目值.as_array())
        .map(|条目表| 条目表.to_vec())
        .unwrap_or_default();
    if !启动器条目表.is_empty() {
        let 启动器配置 = serde_json::json!({
            "搜索占位文本": 取对象文本(&桌面配置, "启动器搜索占位文本"),
            "应用条目表": 启动器条目表,
        });
        页面主体文本.push_str(&拼装启动器片段(
            &取对象文本(&桌面配置, "启动器面板标题"),
            &启动器配置.to_string(),
        )?);
    }
    // 交互脚本
    页面主体文本.push_str(&crate::交互脚本::脚本文本(&桌面配置));
    页面主体文本.push_str("</div>");
    Ok((
        4,
        拼装整页外壳(&应用名称文本, " class=\"hs-desk-body\"", &页面主体文本),
    ))
}

fn 拼装启动器片段(
    面板标题文本: &str, 启动器配置原文: &str
) -> Result<String, u32> {
    let 字节 = 渲染启动器(&[面板标题文本.as_bytes(), 启动器配置原文.as_bytes()])?.1;
    Ok(String::from_utf8(字节).unwrap_or_default())
}

fn 拼装图标区片段(图标分组原文: &str, 选中键文本: &str) -> Result<String, u32> {
    let 图标层字节 = 渲染桌面图标区(&[图标分组原文.as_bytes(), 选中键文本.as_bytes()])?.1;
    Ok(String::from_utf8(图标层字节).unwrap_or_default())
}

fn 拼装坞片段(
    坞条目表: &[serde_json::Value], 运行中键表: &[serde_json::Value]
) -> String {
    let 坞条目原文 = serde_json::Value::Array(坞条目表.to_vec()).to_string();
    let 运行中原文 = serde_json::Value::Array(运行中键表.to_vec()).to_string();
    match 渲染桌面图标坞(&[坞条目原文.as_bytes(), 运行中原文.as_bytes()]) {
        Ok((_, 字节)) => String::from_utf8(字节).unwrap_or_default(),
        Err(_) => String::new(),
    }
}

/// 4925 渲染启动器：全屏磁贴面板，默认隐藏，由交互脚本显示。
pub(crate) fn 渲染启动器(参数表: &[&[u8]]) -> Result<(u32, Vec<u8>), u32> {
    let 面板标题文本 = 取文本参数(参数表, 0)?;
    let 启动器配置原文 = 取文本参数(参数表, 1)?;
    let 启动器配置 = 解析对象参数(&启动器配置原文)?;
    let 搜索占位文本 = 取对象文本(&启动器配置, "搜索占位文本");
    let 应用条目表 = 取数组字段(&启动器配置, "应用条目表")?;
    let mut 启动器文本 = String::new();
    启动器文本.push_str(
        "<div class=\"hs-launchpad\" id=\"hs-launchpad\" hidden><div class=\"hs-launchpad-panel\">",
    );
    启动器文本.push_str("<h2 class=\"hs-launchpad-title\">");
    启动器文本.push_str(&转义网页文本(&面板标题文本));
    启动器文本.push_str("</h2><input class=\"hs-launchpad-search\" type=\"text\" placeholder=\"");
    启动器文本.push_str(&转义网页文本(&搜索占位文本));
    启动器文本.push_str("\" data-launchpad-search=\"1\" />");
    let mut 当前分类文本 = String::new();
    let mut 网格已开 = false;
    for 应用项 in 应用条目表 {
        let 分类文本 = 取对象文本(应用项, "分类");
        if 分类文本 != 当前分类文本 {
            if 网格已开 {
                启动器文本.push_str("</div></div>");
            }
            启动器文本.push_str("<div class=\"hs-launchpad-group\" data-group=\"");
            启动器文本.push_str(&转义网页文本(&分类文本));
            启动器文本.push_str("\">");
            if !分类文本.is_empty() {
                启动器文本.push_str("<h3 class=\"hs-launchpad-group-title\">");
                启动器文本.push_str(&转义网页文本(&分类文本));
                启动器文本.push_str("</h3>");
            }
            启动器文本.push_str("<div class=\"hs-launchpad-grid\">");
            当前分类文本 = 分类文本;
            网格已开 = true;
        }
        启动器文本.push_str("<div class=\"hs-launchpad-item\" data-app=\"");
        启动器文本.push_str(&转义网页文本(&取键文本(应用项)));
        启动器文本.push_str("\" data-category=\"");
        启动器文本.push_str(&转义网页文本(&当前分类文本));
        启动器文本.push_str("\"><div class=\"hs-launchpad-glyph\">");
        启动器文本.push_str(&转义网页文本(&取对象文本(应用项, "图标")));
        启动器文本.push_str("</div><span class=\"hs-launchpad-label\">");
        启动器文本.push_str(&转义网页文本(&取对象文本(应用项, "名称")));
        启动器文本.push_str("</span></div>");
    }
    if 网格已开 {
        启动器文本.push_str("</div></div>");
    }
    启动器文本.push_str("</div></div>");
    Ok((4, 启动器文本.into_bytes()))
}
