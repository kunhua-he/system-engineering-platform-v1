//! 组件树：窗口内容与整页都由一棵可递归嵌套的节点树描述。
//!
//! 容器（行 / 列 / 网格 / 侧栏 / 分区 / 画布）可以无限嵌套，叶子出真正的界面元素。
//! 产品语义上不限制嵌套层数；工程上拦两道闸（深度 32 层、节点 2000 个），
//! 只防「写错了的树把渲染拖死」，正常界面远远用不到。

use serde_json::Value;

use crate::业务实现::{
    取对象文本, 拼装整页外壳, 拼装聊天片段, 拼装表单字段, 拼装表格行, 转义网页文本,
};
use crate::交互运行时::{显隐切换脚本, 窗口脚本};
use crate::编号与码面::错误码;
use crate::视觉基准::中性样式文本;

#[path = "组件树/外观属性.rs"]
mod 外观属性;
#[path = "组件树/应用窗口.rs"]
mod 应用窗口;

use 外观属性::{
    取尺寸, 取对齐, 合法标识, 校验节点颜色, 背景样式文本, 校验外观属性, 拼外观样式, 取形态变量,
    表格外观映射, 菜单外观映射, 气泡外观映射,
};

pub(crate) const 树最大深度: u16 = 32;
pub(crate) const 树最大节点数: usize = 2000;

/// 渲染过程中的累积状态：节点计数 + 是否需要附通用显隐脚本。
pub(crate) struct 渲染状态 {
    pub(crate) 计数: usize,
    pub(crate) 需要显隐脚本: bool,
    pub(crate) 需要窗口脚本: bool,
}


/// 控件自身尺寸与描边：宽 / 高 / 圆角 / 边框颜色 / 背景色。
fn 控件样式文本(节点: &Value) -> String {
    let mut 样式 = String::new();
    let 宽 = 取尺寸(节点, "宽");
    if !宽.is_empty() {
        样式.push_str(&format!("width:{宽};"));
    }
    let 高 = 取尺寸(节点, "高");
    if !高.is_empty() {
        样式.push_str(&format!("height:{高};"));
    }
    let 圆角 = 取尺寸(节点, "圆角");
    if !圆角.is_empty() {
        样式.push_str(&format!("border-radius:{圆角};"));
    }
    let 边框颜色 = 取对象文本(节点, "边框颜色");
    if !边框颜色.is_empty() {
        样式.push_str(&format!("border-color:{边框颜色};"));
    }
    样式.push_str(&背景样式文本(节点));
    if 样式.ends_with(';') {
        样式.pop();
    }
    样式
}

/// 通用样式：所有节点都能带，拼成 style 属性值。
pub(crate) fn 拼通用样式(节点: &Value, 基础: &str) -> String {
    let mut 样式 = String::from(基础);
    let 宽 = 取尺寸(节点, "宽");
    let 高 = 取尺寸(节点, "高");
    if !宽.is_empty() {
        样式.push_str(&format!(";width:{宽}"));
    }
    if !高.is_empty() {
        样式.push_str(&format!(";height:{高}"));
    }
    if let Some(Value::Number(数值)) = 节点.get("间距") {
        样式.push_str(&format!(";gap:{数值}px"));
    }
    let 内边距 = 取尺寸(节点, "内边距");
    if !内边距.is_empty() {
        样式.push_str(&format!(";padding:{内边距}"));
    }
    样式.push_str(&背景样式文本(节点));
    let 文字颜色 = 取对象文本(节点, "文字颜色");
    if !文字颜色.is_empty() {
        样式.push_str(&format!(";color:{文字颜色}"));
    }
    let 边框颜色 = 取对象文本(节点, "边框颜色");
    if !边框颜色.is_empty() {
        样式.push_str(&format!(";border-color:{边框颜色}"));
    }
    let 圆角 = 取尺寸(节点, "圆角");
    if !圆角.is_empty() {
        样式.push_str(&format!(";border-radius:{圆角}"));
    }
    let 边框 = 取对象文本(节点, "边框");
    if !边框.is_empty() {
        样式.push_str(&format!(";border:{边框}"));
    }
    let 溢出 = 取对象文本(节点, "溢出");
    if !溢出.is_empty() {
        样式.push_str(&format!(";overflow:{溢出}"));
    }
    let 最小高 = 取尺寸(节点, "最小高");
    if !最小高.is_empty() {
        样式.push_str(&format!(";min-height:{最小高}"));
    }
    样式.push_str(&拼外观样式(节点));
    样式
}

/// 递归出口：子节点表
pub(crate) fn 拼子节点(节点: &Value, 深度: u16, 状态: &mut 渲染状态) -> Result<String, u32> {
    let 子节点表 = match 节点.get("子").and_then(|子项| 子项.as_array()) {
        Some(子项) => 子项,
        None => return Ok(String::new()),
    };
    let mut 子文本 = String::new();
    for 子节点 in 子节点表 {
        子文本.push_str(&拼装树节点(子节点, 深度 + 1, 状态)?);
    }
    Ok(子文本)
}

fn 拼装树节点(节点: &Value, 深度: u16, 状态: &mut 渲染状态) -> Result<String, u32> {
    校验外观属性(节点)?;
    if 深度 > 树最大深度 {
        return Err(错误码::资源受限);
    }
    状态.计数 += 1;
    if 状态.计数 > 树最大节点数 {
        return Err(错误码::资源受限);
    }
    let 类型文本 = 取对象文本(节点, "类型");
    校验节点颜色(节点)?;
    let 片段文本 = match 类型文本.as_str() {
        "表单容器" => {
            let 提交地址文本 = 取对象文本(节点, "提交地址");
            if !提交地址文本.starts_with('/')
                || 提交地址文本.starts_with("//")
                || 提交地址文本.contains("..")
            {
                return Err(错误码::内容不合法);
            }
            let 提交方式文本 = match 取对象文本(节点, "方式").as_str() {
                "" | "POST" => "post",
                "GET" => "get",
                _ => return Err(错误码::内容不合法),
            };
            let 标识文本 = 取对象文本(节点, "标识");
            let 辨识属性 = if 标识文本.is_empty() {
                String::new()
            } else {
                format!(" id=\"{}\"", 转义网页文本(&标识文本))
            };
            let 样式 = 拼通用样式(
                节点,
                "display:flex;flex-direction:column;box-sizing:border-box",
            );
            format!(
                "<form class=\"hs-tree-node hs-tree-form\"{} method=\"{}\" action=\"{}\" style=\"{}\">{}</form>",
                辨识属性,
                提交方式文本,
                转义网页文本(&提交地址文本),
                转义网页文本(&样式),
                拼子节点(节点, 深度, 状态)?
            )
        }
        "输入" => {
            let 输入类型文本 = match 取对象文本(节点, "种类").as_str() {
                "" | "文本框" => "text",
                "密码框" => "password",
                "数字框" => "number",
                "邮箱" => "email",
                _ => return Err(错误码::内容不合法),
            };
            let 名称文本 = 取对象文本(节点, "名称");
            if 名称文本.is_empty() {
                return Err(错误码::内容不合法);
            }
            let 标签文本 = 取对象文本(节点, "标签");
            let 显示标签文本 = if 标签文本.is_empty() {
                名称文本.clone()
            } else {
                标签文本
            };
            let 必填属性 = if 节点
                .get("必填")
                .and_then(|必填项| 必填项.as_bool())
                .unwrap_or(false)
            {
                " required"
            } else {
                ""
            };
            let 自动填充文本 = 取对象文本(节点, "自动填充");
            let 自动填充属性 = if 自动填充文本.is_empty() {
                String::new()
            } else {
                format!(" autocomplete=\"{}\"", 转义网页文本(&自动填充文本))
            };
            format!(
                "<div class=\"hs-tree-node hs-form-item\"><label class=\"hs-form-label\">{}</label><input class=\"hs-input\" type=\"{}\" name=\"{}\" placeholder=\"{}\"{}{} style=\"{}\" /></div>",
                转义网页文本(&显示标签文本),
                输入类型文本,
                转义网页文本(&名称文本),
                转义网页文本(&取对象文本(节点, "占位文本")),
                必填属性,
                自动填充属性,
                转义网页文本(&控件样式文本(节点))
            )
        }
        "按钮" => {
            let 样式类文本 = match 取对象文本(节点, "样式").as_str() {
                "" | "默认" => "hs-button",
                "主要" => "hs-button hs-button-primary",
                "成功" => "hs-button hs-button-success",
                "警告" => "hs-button hs-button-warning",
                "危险" => "hs-button hs-button-danger",
                _ => return Err(错误码::内容不合法),
            };
            let 提交属性 = if 节点
                .get("提交")
                .and_then(|提交项| 提交项.as_bool())
                .unwrap_or(false)
            {
                " type=\"submit\""
            } else {
                " type=\"button\""
            };
            let 表单标识文本 = 取对象文本(节点, "表单");
            let 表单属性 = if 表单标识文本.is_empty() {
                String::new()
            } else {
                format!(" form=\"{}\"", 转义网页文本(&表单标识文本))
            };
            format!(
                "<button class=\"{}\"{} data-action=\"{}\"{}{} style=\"{}\">{}</button>",
                样式类文本,
                提交属性,
                转义网页文本(&取对象文本(节点, "动作")),
                表单属性,
                "",
                转义网页文本(&控件样式文本(节点)),
                转义网页文本(&取对象文本(节点, "文字"))
            )
        }
        "行" => {
            let 样式 = 拼通用样式(
                节点,
                &format!(
                    "display:flex;flex-direction:row;align-items:{};justify-content:{};min-width:0",
                    取对齐(节点, "垂直对齐"),
                    取对齐(节点, "水平对齐")
                ),
            );
            format!(
                "<div class=\"hs-tree-node hs-tree-row\" style=\"{}\">{}</div>",
                转义网页文本(&样式),
                拼子节点(节点, 深度, 状态)?
            )
        }
        "列" => {
            let 样式 = 拼通用样式(
                节点,
                &format!(
                    "display:flex;flex-direction:column;align-items:{};justify-content:{};min-width:0",
                    取对齐(节点, "水平对齐"),
                    取对齐(节点, "垂直对齐")
                ),
            );
            format!(
                "<div class=\"hs-tree-node hs-tree-col\" style=\"{}\">{}</div>",
                转义网页文本(&样式),
                拼子节点(节点, 深度, 状态)?
            )
        }
        "网格" => {
            let 列数 = match 节点.get("列数") {
                Some(Value::Number(数值)) => 数值.as_u64().unwrap_or(3).clamp(1, 24),
                _ => 3,
            };
            let 样式 = 拼通用样式(
                节点,
                &format!(
                    "display:grid;grid-template-columns:repeat({列数},minmax(0,1fr));align-items:{}",
                    取对齐(节点, "垂直对齐")
                ),
            );
            format!(
                "<div class=\"hs-tree-node hs-tree-grid\" style=\"{}\">{}</div>",
                转义网页文本(&样式),
                拼子节点(节点, 深度, 状态)?
            )
        }
        "侧栏" => {
            let 栏宽 = {
                let 原值 = 取尺寸(节点, "栏宽");
                if 原值.is_empty() {
                    "232px".to_string()
                } else {
                    原值
                }
            };
            let 菜单条目表 = 节点
                .get("菜单")
                .and_then(|菜单项| 菜单项.as_array())
                .cloned()
                .unwrap_or_default();
            let mut 菜单文本 = String::new();
            for 条目项 in &菜单条目表 {
                let 激活 = 条目项
                    .get("激活")
                    .and_then(|激活项| 激活项.as_bool())
                    .unwrap_or(false);
                let 打开地址 = 取对象文本(条目项, "打开地址");
                if !打开地址.is_empty()
                    && (!打开地址.starts_with('/')
                        || 打开地址.starts_with("//")
                        || 打开地址.contains("..")
                        || 打开地址.contains(':'))
                {
                    return Err(错误码::内容不合法);
                }
                let 标签名 = if 打开地址.is_empty() { "div" } else { "a" };
                let 地址属性 = if 打开地址.is_empty() {
                    String::new()
                } else {
                    format!(" href=\"{}\"", 转义网页文本(&打开地址))
                };
                菜单文本.push_str(&format!("<{标签名} class=\"hs-tree-menu-item"));
                if 激活 {
                    菜单文本.push_str(" is-active");
                }
                菜单文本.push_str(&format!("\"{地址属性}>"));
                let 图标文本 = 取对象文本(条目项, "图标");
                if !图标文本.is_empty() {
                    菜单文本.push_str("<span class=\"hs-tree-menu-icon\">");
                    菜单文本.push_str(&转义网页文本(&图标文本));
                    菜单文本.push_str("</span>");
                }
                菜单文本.push_str("<span class=\"hs-tree-menu-label\">");
                菜单文本.push_str(&转义网页文本(&取对象文本(条目项, "名称")));
                菜单文本.push_str(&format!("</span></{标签名}>"));
            }
            let 侧栏标题文本 = 取对象文本(节点, "标题");
            let 菜单变量 = 取形态变量(节点, "菜单外观", &菜单外观映射)?;
            let mut 样式 = 拼通用样式(节点, "display:flex;align-items:stretch");
            样式.push_str(&菜单变量);
            format!(
                "<div class=\"hs-tree-node hs-tree-sidebar\" style=\"{}\"><aside class=\"hs-tree-sidebar-pane\" style=\"flex:0 0 {}\">{}<div class=\"hs-tree-menu\">{}</div></aside><section class=\"hs-tree-sidebar-main\">{}</section></div>",
                转义网页文本(&样式),
                转义网页文本(&栏宽),
                if 侧栏标题文本.is_empty() {
                    String::new()
                } else {
                    format!(
                        "<div class=\"hs-tree-sidebar-title\">{}</div>",
                        转义网页文本(&侧栏标题文本)
                    )
                },
                菜单文本,
                拼子节点(节点, 深度, 状态)?
            )
        }
        "分区" => {
            let 样式 = 拼通用样式(节点, "display:flex;flex-direction:column;min-width:0");
            let 标题文本 = 取对象文本(节点, "标题");
            format!(
                "<section class=\"hs-tree-node hs-tree-panel\" style=\"{}\">{}{}</section>",
                转义网页文本(&样式),
                if 标题文本.is_empty() {
                    String::new()
                } else {
                    format!(
                        "<h3 class=\"hs-tree-panel-title\">{}</h3>",
                        转义网页文本(&标题文本)
                    )
                },
                拼子节点(节点, 深度, 状态)?
            )
        }
        "画布" => {
            let 样式 = 拼通用样式(节点, "position:relative;min-width:0");
            let 子节点表 = 节点
                .get("子")
                .and_then(|子项| 子项.as_array())
                .cloned()
                .unwrap_or_default();
            let mut 子文本 = String::new();
            for 子节点 in &子节点表 {
                let 定位 = format!(
                    "position:absolute;left:{};top:{};width:{};height:{}",
                    取尺寸(子节点, "左").if_empty("0px"),
                    取尺寸(子节点, "上").if_empty("0px"),
                    取尺寸(子节点, "宽").if_empty("auto"),
                    取尺寸(子节点, "高").if_empty("auto")
                );
                let 内层 = 拼装树节点(子节点, 深度 + 1, 状态)?;
                // 窗口要能被拖动/置顶：拖拽脚本移动的是画布给它的定位外壳
                let 拖拽标记 = if 取对象文本(子节点, "类型") == "窗口" {
                    format!(
                        " data-window-port=\"{}\"{}",
                        转义网页文本(&取对象文本(子节点, "标识")),
                        if 子节点.get("初始隐藏").and_then(Value::as_bool).unwrap_or(true) { " hidden" } else { "" }
                    )
                } else {
                    String::new()
                };
                子文本.push_str(&format!(
                    "<div class=\"hs-tree-canvas-item\"{} style=\"{}\">{}</div>",
                    拖拽标记,
                    转义网页文本(&定位),
                    内层
                ));
            }
            format!(
                "<div class=\"hs-tree-node hs-tree-canvas\" style=\"{}\">{}</div>",
                转义网页文本(&样式),
                子文本
            )
        }
        "标题" => format!(
            "<h2 class=\"hs-tree-node hs-tree-title\">{}</h2>",
            转义网页文本(&取对象文本(节点, "文本"))
        ),
        "图标" => {
            let 名称文本 = 取对象文本(节点, "名称");
            let 图形文本 = 取对象文本(节点, "图形");
            let 打开地址 = 取对象文本(节点, "打开地址");
            if !打开地址.is_empty()
                && (!打开地址.starts_with('/')
                    || 打开地址.starts_with("//")
                    || 打开地址.contains("..")
                    || 打开地址.contains(':'))
            {
                return Err(错误码::内容不合法);
            }
            let 图形片段 = if 图形文本.starts_with('/') {
                if 图形文本.starts_with("//") || 图形文本.contains("..") || 图形文本.contains(':')
                {
                    return Err(错误码::内容不合法);
                }
                if 图形文本.ends_with(".svg") {
                    // SVG 走遮罩：图形跟随节点文字颜色，颜色仍由声明决定
                    format!(
                        "<span class=\"hs-tree-icon-mask\" style=\"-webkit-mask-image:url('{}');mask-image:url('{}')\"></span>",
                        转义网页文本(&图形文本),
                        转义网页文本(&图形文本)
                    )
                } else {
                    format!(
                        "<img class=\"hs-tree-icon-img\" src=\"{}\" alt=\"\">",
                        转义网页文本(&图形文本)
                    )
                }
            } else {
                format!(
                    "<span class=\"hs-tree-icon-glyph\">{}</span>",
                    转义网页文本(&图形文本)
                )
            };
            let 名称片段 = if 节点
                .get("显示名称")
                .and_then(|显示项| 显示项.as_bool())
                .unwrap_or(true)
            {
                let mut 标签样式 = String::new();
                if let Some(颜色) = 节点
                    .get("标签颜色")
                    .and_then(|取值项| 取值项.as_str())
                {
                    标签样式.push_str(&format!("color:{颜色};"));
                }
                if let Some(字号) = 节点.get("标签字号").and_then(|取值项| 取值项.as_f64())
                {
                    标签样式.push_str(&format!("font-size:{字号}px;"));
                }
                if 标签样式.is_empty() {
                    format!(
                        "<span class=\"hs-tree-icon-label\">{}</span>",
                        转义网页文本(&名称文本)
                    )
                } else {
                    format!(
                        "<span class=\"hs-tree-icon-label\" style=\"{}\">{}</span>",
                        转义网页文本(&标签样式),
                        转义网页文本(&名称文本)
                    )
                }
            } else {
                String::new()
            };
            let 样式 = 拼通用样式(
                节点,
                "display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;text-decoration:none;padding:6px 4px",
            );
            if 打开地址.is_empty() {
                format!(
                    "<div class=\"hs-tree-node hs-tree-icon\" style=\"{}\">{}{}</div>",
                    转义网页文本(&样式),
                    图形片段,
                    名称片段
                )
            } else {
                format!(
                    "<a class=\"hs-tree-node hs-tree-icon\" href=\"{}\" title=\"{}\" style=\"{}\">{}{}</a>",
                    转义网页文本(&打开地址),
                    转义网页文本(&名称文本),
                    转义网页文本(&样式),
                    图形片段,
                    名称片段
                )
            }
        }
        "文字" => {
            let 样式 = 拼通用样式(节点, "white-space:pre-wrap;word-break:break-word");
            let 文本内容 = 转义网页文本(&取对象文本(节点, "文本"));
            let 打开地址 = 取对象文本(节点, "打开地址");
            if !打开地址.is_empty()
                && (!打开地址.starts_with('/')
                    || 打开地址.starts_with("//")
                    || 打开地址.contains("..")
                    || 打开地址.contains(':'))
            {
                return Err(错误码::内容不合法);
            }
            if 打开地址.is_empty() {
                format!(
                    "<div class=\"hs-tree-node hs-tree-text\" style=\"{}\">{}</div>",
                    转义网页文本(&样式),
                    文本内容
                )
            } else {
                format!(
                    "<a class=\"hs-tree-node hs-tree-text hs-tree-link\" href=\"{}\" style=\"{}\">{}</a>",
                    转义网页文本(&打开地址),
                    转义网页文本(&样式),
                    文本内容
                )
            }
        }
        "分隔条" => {
            let 样式 = 拼通用样式(节点, "");
            format!(
                "<div class=\"hs-tree-node hs-tree-divider\" style=\"{}\"></div>",
                转义网页文本(&样式)
            )
        }
        "表格" => {
            let 列定义 = 节点
                .get("列")
                .and_then(|列项| 列项.as_array())
                .ok_or(错误码::内容不合法)?;
            let 行数据 = 节点
                .get("行")
                .and_then(|行项| 行项.as_array())
                .ok_or(错误码::内容不合法)?;
            let 表格变量 = 取形态变量(节点, "表格外观", &表格外观映射)?;
            format!(
                "<div class=\"hs-tree-node hs-card\" style=\"{}\">{}</div>",
                转义网页文本(&表格变量),
                拼装表格行(列定义, 行数据)?
            )
        }
        "表单" => {
            let 字段定义 = 节点
                .get("字段")
                .and_then(|字段项| 字段项.as_array())
                .ok_or(错误码::内容不合法)?;
            let 缺省值 = 节点
                .get("值")
                .cloned()
                .unwrap_or_else(|| Value::Object(serde_json::Map::new()));
            format!(
                "<div class=\"hs-tree-node hs-card\">{}</div>",
                拼装表单字段(字段定义, &缺省值)?
            )
        }
        "聊天流" => {
            let 消息表 = match 节点.get("消息").and_then(|消息项| 消息项.as_array()) {
                Some(消息项) => 消息项.clone(),
                None => Vec::new(),
            };
            let 空态文本 = 取对象文本(节点, "空态文案");
            let 气泡变量 = 取形态变量(节点, "气泡外观", &气泡外观映射)?;
            format!(
                "<div class=\"hs-tree-node\" style=\"{}\">{}</div>",
                转义网页文本(&气泡变量),
                拼装聊天片段(&消息表, &空态文本)?
            )
        }
        "窗口" => 应用窗口::拼装窗口(节点, 深度, 状态)?,
        "悬浮层" => {
            let 标识文本 = 取对象文本(节点, "标识");
            if !合法标识(&标识文本) {
                return Err(错误码::内容不合法);
            }
            let 快捷键文本 = 取对象文本(节点, "快捷键");
            if 快捷键文本.chars().count() > 8 {
                return Err(错误码::内容不合法);
            }
            状态.需要显隐脚本 = true;
            let 初始隐藏 = 节点
                .get("初始隐藏")
                .and_then(|隐藏项| 隐藏项.as_bool())
                .unwrap_or(true);
            let 样式 = 拼通用样式(
                节点,
                "position:fixed;inset:0;z-index:60;display:flex;flex-direction:column;align-items:center;justify-content:center;overflow:auto",
            );
            format!(
                "<div class=\"hs-tree-overlay{}\" data-overlay=\"{}\"{} style=\"{}\">{}</div>",
                if 初始隐藏 { " is-hidden" } else { "" },
                转义网页文本(&标识文本),
                if 快捷键文本.is_empty() {
                    String::new()
                } else {
                    format!(" data-key=\"{}\"", 转义网页文本(&快捷键文本))
                },
                转义网页文本(&样式),
                拼子节点(节点, 深度, 状态)?
            )
        }
        "原样" => {
            let 片段文本 = 取对象文本(节点, "html");
            if 片段文本.len() > 200_000 {
                return Err(错误码::资源受限);
            }
            片段文本
        }
        _ => return Err(错误码::内容不合法),
    };
    let 窗口标识 = 取对象文本(节点, "打开窗口");
    if !窗口标识.is_empty() {
        if !合法标识(&窗口标识) {
            return Err(错误码::内容不合法);
        }
        状态.需要窗口脚本 = true;
        return Ok(format!(
            "<div class=\"hs-tree-toggle\" data-window-open=\"{}\" style=\"display:contents\">{}</div>",
            转义网页文本(&窗口标识), 片段文本
        ));
    }
    let 切换标识 = 取对象文本(节点, "切换显隐");
    if !切换标识.is_empty() {
        if !合法标识(&切换标识) || 类型文本 == "悬浮层" {
            return Err(错误码::内容不合法);
        }
        状态.需要显隐脚本 = true;
        return Ok(format!(
            "<div class=\"hs-tree-toggle\" data-toggle=\"{}\" style=\"display:contents\">{}</div>",
            转义网页文本(&切换标识),
            片段文本
        ));
    }
    Ok(片段文本)
}

/// 4928 渲染组件树：一棵可无限嵌套的节点树 → HTML 片段。
pub(crate) fn 渲染组件树(参数表: &[&[u8]]) -> Result<(u32, Vec<u8>), u32> {
    let 树定义原文 = crate::业务实现::取文本参数(参数表, 0)?;
    let 树定义值: Value =
        serde_json::from_str(&树定义原文).map_err(|_| 错误码::内容不合法)?;
    let 根节点 = 树定义值.get("根").ok_or(错误码::内容不合法)?;
    let mut 状态 = 渲染状态 {
        计数: 0,
        需要显隐脚本: false,
        需要窗口脚本: false,
    };
    let 根文本 = 拼装树节点(根节点, 0, &mut 状态)?;
    if 树定义值
        .get("整页")
        .and_then(|整页项| 整页项.as_bool())
        .unwrap_or(false)
    {
        let 页面标题文本 = 取对象文本(&树定义值, "页面标题");
        let mut 主体文本 = 根文本;
        if 状态.需要显隐脚本 {
            主体文本.push_str(显隐切换脚本);
        }
        if 状态.需要窗口脚本 {
            主体文本.push_str(窗口脚本);
        }
        return Ok((4, 拼装整页外壳(&页面标题文本, "", &主体文本, &中性样式文本())));
    }
    let 样式 = 取对象文本(根节点, "容器样式");
    let mut 脚本文本 = String::new();
    if 状态.需要显隐脚本 {
        脚本文本.push_str(显隐切换脚本);
    }
    if 状态.需要窗口脚本 {
        脚本文本.push_str(窗口脚本);
    }
    Ok((
        4,
        format!(
            "<div class=\"hs-tree\" data-tree=\"1\" style=\"{}\">{}{}</div>",
            转义网页文本(&样式),
            根文本,
            脚本文本
        )
        .into_bytes(),
    ))
}

/// 空串兜底的小工具（画布定位用）。
trait 空值兜底 {
    fn if_empty(self, 兜底: &str) -> String;
}

impl 空值兜底 for String {
    fn if_empty(self, 兜底: &str) -> String {
        if self.is_empty() {
            兜底.to_string()
        } else {
            self
        }
    }
}
