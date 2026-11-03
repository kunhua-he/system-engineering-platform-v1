use crate::编号与码面::{能力号, 错误码};

/// 过一次边界后的参数：文本按字节来，句柄/整数按数值来。
pub(crate) enum 调用参数<'a> {
    文本(&'a [u8]),
    数值(u64),
}

impl 调用参数<'_> {
    pub(crate) fn 取文本(&self) -> Result<String, u32> {
        match self {
            调用参数::文本(字节) => Ok(std::str::from_utf8(字节)
                .map_err(|_| 错误码::参数不合法)?
                .to_string()),
            _ => Err(错误码::参数不合法),
        }
    }

    pub(crate) fn 取数值(&self) -> Result<u64, u32> {
        match self {
            调用参数::数值(数值) => Ok(*数值),
            _ => Err(错误码::参数不合法),
        }
    }
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

pub(crate) struct 表格呈现设置<'a> {
    pub(crate) 列宽表: &'a [usize],
    pub(crate) 条目行高: Option<usize>,
    pub(crate) 列对齐表: &'a [&'a str],
    pub(crate) 选择模式: &'a str,
    pub(crate) 勾选列: bool,
    pub(crate) 检查状态表: &'a [serde_json::Value],
    pub(crate) 选中行序号表: &'a [usize],
    pub(crate) 可排序: bool,
    pub(crate) 排序列: Option<usize>,
    pub(crate) 升序: bool,
    pub(crate) 组件句柄: u64,
    pub(crate) 无表头: bool,
    pub(crate) 显示表格线: bool,
    pub(crate) 标题换行: bool,
    pub(crate) 列可拖动: bool,
    pub(crate) 表头图标表: &'a [serde_json::Value],
    pub(crate) 表头图标居右表: &'a [bool],
    pub(crate) 行图标表: &'a [serde_json::Value],
    pub(crate) 单元格图片: &'a serde_json::Value,
    pub(crate) 行状态图标表: &'a [serde_json::Value],
    pub(crate) 行缩进表: &'a [usize],
    pub(crate) 热点跟踪: bool,
    pub(crate) 手形指针: bool,
    pub(crate) 标注热点: bool,
    pub(crate) 标注非热点: bool,
    pub(crate) 允许编辑: bool,
    pub(crate) 编辑单元格: Option<(usize, usize)>,
    pub(crate) 结束编辑文本: &'a str,
    pub(crate) 滚动目标: Option<usize>,
    pub(crate) 视图模式: &'a str,
    pub(crate) 图标对齐方式: &'a str,
    pub(crate) 自动排列图标: bool,
    pub(crate) 平面滚动条: bool,
    pub(crate) 始终显示选择项: bool,
    pub(crate) 行提示表: &'a [serde_json::Value],
    pub(crate) 列提示表: &'a [serde_json::Value],
    pub(crate) 图标间距: usize,
}

pub(crate) fn 拼装表格行(
    表格列定义: &[serde_json::Value],
    表格行数据: &[(usize, serde_json::Value)],
    设置: &表格呈现设置<'_>,
) -> Result<String, u32> {
    let mut 表格主体文本 = String::new();
    let 表格类别 = format!(
        "hs-table 热点标注{}{}{}{}{}{}{}",
        if 设置.显示表格线 {
            ""
        } else {
            " 无表格线"
        },
        if 设置.自动排列图标 {
            " 自动排列图标"
        } else {
            ""
        },
        if 设置.平面滚动条 {
            " 平面滚动条"
        } else {
            ""
        },
        match 设置.视图模式 {
            "小图标" => " 小图标视图",
            "大图标" => " 大图标视图",
            "列表" => " 列表视图",
            _ => "",
        },
        match 设置.图标对齐方式 {
            "中" => " 图标居中",
            "右" => " 图标居右",
            "上" => " 图标顶部",
            _ => " 图标居左",
        },
        if 设置.热点跟踪 {
            " 热点跟踪"
        } else {
            ""
        },
        if 设置.始终显示选择项 {
            " 始终显示选择项"
        } else {
            " 隐藏失焦选择项"
        }
    );
    let 结束编辑结果 = 转义网页文本(设置.结束编辑文本);
    let 列宽声明 =
        转义网页文本(&serde_json::to_string(设置.列宽表).map_err(|_| 错误码::内容不合法)?);
    let 总列宽 = 设置.列宽表.iter().sum::<usize>() + if 设置.勾选列 { 36 } else { 0 };
    let 列键声明 =
        转义网页文本(&serde_json::to_string(表格列定义).map_err(|_| 错误码::内容不合法)?);
    let 检查列属性 = 设置.勾选列;
    let 固定行高 = 设置.条目行高.is_some();
    let 图标间距像素 = 设置.图标间距;
    let 行高声明 = 设置
        .条目行高
        .map(|像素| format!(";--表格行高:{像素}px"))
        .unwrap_or_default();
    表格主体文本.push_str(&format!(
        "<table class=\"{表格类别}\" style=\"width:{总列宽}px;table-layout:fixed{行高声明};--图标间距:{图标间距像素}px\" data-固定行高=\"{固定行高}\" data-固定列宽=\"1\" data-列宽声明=\"{列宽声明}\" data-列键声明=\"{列键声明}\" data-检查列显示=\"{检查列属性}\" data-结束编辑文本=\"{结束编辑结果}\" tabindex=\"0\"><colgroup>"
    ));
    if 设置.勾选列 {
        表格主体文本.push_str("<col style=\"width:36px\">");
    }
    for 列宽值 in 设置.列宽表 {
        表格主体文本.push_str(&format!("<col style=\"width:{列宽值}px\">"));
    }
    表格主体文本.push_str("</colgroup>");
    if !设置.无表头 {
        表格主体文本.push_str("<thead><tr>");
        if 设置.勾选列 {
            表格主体文本.push_str("<th style=\"width:36px;text-align:center\"></th>");
        }
        for (列序, 列名项) in 表格列定义.iter().enumerate() {
            let 列名原文 = 转文本值(列名项);
            let 列名文本 = 转义网页文本(&列名原文);
            let 对齐样式 = match 设置.列对齐表.get(列序).copied().unwrap_or("左") {
                "中" => "center",
                "右" => "right",
                _ => "left",
            };
            let 宽度样式 = 设置
                .列宽表
                .get(列序)
                .copied()
                .map(|宽度| format!(";width:{宽度}px"))
                .unwrap_or_default();
            let 表头图标 = 设置
                .表头图标表
                .get(列序)
                .and_then(|图标| 图标.as_str())
                .unwrap_or("");
            let 表头图标文本 = if 表头图标.is_empty() {
                String::new()
            } else {
                format!(
                    "<img class=\"表头图标\" src=\"{}\" alt=\"\" width=\"16\" height=\"16\">",
                    转义网页文本(表头图标)
                )
            };
            let 图标居右 = 设置.表头图标居右表.get(列序).copied().unwrap_or(false);
            let 图标标题 = if 图标居右 {
                format!("{列名文本}{表头图标文本}")
            } else {
                format!("{表头图标文本}{列名文本}")
            };
            let 行为样式 = if 设置.标题换行 {
                "white-space:normal;"
            } else {
                "white-space:nowrap;"
            };
            let 拖动属性 = if 设置.列可拖动 {
                format!(
                    " data-hs-column=\"{列序}\" draggable=\"true\" title=\"拖动调整列序，右沿拖动调整列宽\""
                )
            } else {
                String::new()
            };
            let 列提示文本 = 设置
                .列提示表
                .get(列序)
                .and_then(serde_json::Value::as_str)
                .unwrap_or("");
            let 列提示属性 = if 列提示文本.is_empty() {
                String::new()
            } else {
                format!(" title=\"{}\"", 转义网页文本(列提示文本))
            };
            let 操作属性 = format!(
                " data-hs-event=\"表头被单击\" data-hs-key=\"{列名文本}\"{列提示属性} style=\"user-select:none;text-align:{对齐样式};{行为样式}{宽度样式}\"{拖动属性}"
            );
            let 排序状态 = if 设置.排序列 == Some(列序) {
                if 设置.升序 {
                    "ascending"
                } else {
                    "descending"
                }
            } else {
                "none"
            };
            let mut 排序按钮 = String::new();
            if 设置.可排序 && 设置.组件句柄 > 0 {
                for (升序方向, 按钮图标, 方向名称) in [(true, "▲", "升序"), (false, "▼", "降序")]
                {
                    let 当前方向 = 设置.排序列 == Some(列序) && 设置.升序 == 升序方向;
                    排序按钮.push_str(&format!(
                        "<button type=\"button\" class=\"表头排序按钮\" data-hs-op=\"排序\" data-hs-event=\"表头被单击\" data-hs-key=\"{列名文本}\" data-排序升序=\"{升序方向}\" aria-label=\"{列名文本}{方向名称}\" title=\"{方向名称}\" aria-pressed=\"{当前方向}\">{按钮图标}</button>"
                    ));
                }
                排序按钮 = format!("<span class=\"表头排序控件\">{排序按钮}</span>");
            }
            表格主体文本.push_str(&format!(
                "<th data-hs-header-column=\"{列序}\" aria-sort=\"{排序状态}\"{操作属性}><span class=\"表头内容容器\"><span class=\"表头标题文本\">{图标标题}</span>{排序按钮}</span></th>"
            ));
        }
        表格主体文本.push_str("</tr></thead>");
    }
    表格主体文本.push_str("<tbody>");

    for (行序号, 行项) in 表格行数据 {
        let 单元格表 = 行项.as_array().ok_or(错误码::内容不合法)?;
        let 已选中 = 设置.选中行序号表.contains(行序号);
        let 行键 = 行序号.to_string();
        let 事件属性 = format!(
            " data-hs-event=\"左键单击表项\" data-hs-event-hover=\"表项跟踪\" data-hs-event-context=\"右键单击表项\" data-hs-event-double=\"表项被激活\" data-hs-row=\"{行键}\""
        );
        let 操作属性 = if 设置.选择模式 == "不选" {
            String::new()
        } else {
            format!(
                " data-hs-op=\"选中\" data-hs-h=\"{}\" data-hs-key=\"{行键}\"",
                设置.组件句柄
            )
        };
        let 行类 = if 已选中 {
            " class=\"已选中\""
        } else {
            ""
        };
        let 行指针 = if 设置.手形指针 {
            "cursor:pointer;"
        } else {
            ""
        };
        let 滚动属性 = if 设置.滚动目标 == Some(*行序号) {
            " data-hs-scroll-target=\"1\""
        } else {
            ""
        };
        let 行高样式 = 设置
            .条目行高
            .map(|像素| format!("height:{像素}px;"))
            .unwrap_or_default();
        let 行提示文本 = 设置
            .行提示表
            .get(*行序号)
            .and_then(serde_json::Value::as_str)
            .unwrap_or("");
        let 行提示属性 = if 行提示文本.is_empty() {
            String::new()
        } else {
            format!(" title=\"{}\"", 转义网页文本(行提示文本))
        };
        表格主体文本.push_str(&format!(
            "<tr tabindex=\"0\" aria-selected=\"{已选中}\"{行类}{操作属性}{事件属性}{滚动属性}{行提示属性} style=\"{行高样式}{行指针}\">"
        ));
        if 设置.勾选列 {
            let 检查状态 = 设置
                .检查状态表
                .get(*行序号)
                .is_some_and(|状态值| 状态值.as_bool() == Some(true) || 状态值.as_u64() == Some(1));
            let 勾选状态 = if 检查状态 { " checked" } else { "" };
            let 选中单元格样式 = if 已选中 {
                ";background-color:var(--hs-row-hover,var(--hs-primary-light,rgba(70,130,180,.14)))"
            } else {
                ""
            };
            表格主体文本.push_str(&format!(
                "<td style=\"text-align:center{选中单元格样式}\"><input type=\"checkbox\" aria-label=\"选择第{}行\" data-hs-op=\"切换检查\" data-hs-event=\"检查框状态被改变\" data-hs-h=\"{}\" data-hs-key=\"{行键}\"{勾选状态}></td>",
                行序号 + 1,
                设置.组件句柄
            ));
        }
        for 列序 in 0..表格列定义.len() {
            let 单元格值文本 = 单元格表.get(列序).map(转文本值).unwrap_or_default();
            let 对齐样式 = match 设置.列对齐表.get(列序).copied().unwrap_or("左") {
                "中" => "center",
                "右" => "right",
                _ => "left",
            };
            let 宽度样式 = 设置
                .列宽表
                .get(列序)
                .copied()
                .map(|宽度| format!(";width:{宽度}px"))
                .unwrap_or_default();
            let 选中单元格样式 = if 已选中 {
                ";background-color:var(--hs-row-hover,var(--hs-primary-light,rgba(70,130,180,.14)))"
            } else {
                ""
            };
            let 缩进数量 = if 列序 == 0 {
                设置.行缩进表.get(*行序号).copied().unwrap_or(0)
            } else {
                0
            };
            let 缩进样式 = if 缩进数量 > 0 {
                format!(";padding-left:{}px", 12 + 缩进数量 * 12)
            } else {
                String::new()
            };
            let 热点样式 = if 设置.热点跟踪 && 设置.手形指针 {
                "cursor:pointer;"
            } else {
                ""
            };
            let 热点类 = format!(
                "{}{}",
                if 设置.标注热点 { " 热点" } else { "" },
                if 设置.标注非热点 {
                    " 非热点"
                } else {
                    ""
                }
            );
            let 标题样式 = if 设置.标题换行 {
                "white-space:normal;overflow-wrap:anywhere"
            } else {
                "white-space:nowrap"
            };
            let 子项图片键 = format!("{行序号}:{列序}");
            let 子项图片值 = 设置
                .单元格图片
                .get(&子项图片键)
                .and_then(serde_json::Value::as_str);
            let 行图标文本 = if let Some(子项图片路径) = 子项图片值 {
                format!(
                    "<img class=\"表项图标\" src=\"{}\" alt=\"\" width=\"16\" height=\"16\">",
                    转义网页文本(子项图片路径)
                )
            } else if 列序 == 0 {
                设置.行图标表.get(*行序号).and_then(|图标| 图标.as_str()).filter(|图标| !图标.is_empty()).map(|图标| format!("<img class=\"表项图标\" src=\"{}\" alt=\"\" width=\"16\" height=\"16\">", 转义网页文本(图标))).unwrap_or_default()
            } else {
                String::new()
            };
            let 状态图标文本 = if 列序 == 0 {
                设置.行状态图标表.get(*行序号).and_then(|图标| 图标.as_str()).filter(|图标| !图标.is_empty()).map(|图标| format!("<img class=\"表项状态图标\" src=\"{}\" alt=\"\" width=\"16\" height=\"16\">", 转义网页文本(图标))).unwrap_or_default()
            } else {
                String::new()
            };
            if 设置.编辑单元格 == Some((*行序号, 列序)) {
                表格主体文本.push_str(&format!(
                    "<td class=\"{}\" data-hs-cell-column=\"{列序}\" data-hs-row=\"{行键}\" style=\"text-align:{对齐样式}{宽度样式}{选中单元格样式}{缩进样式};{热点样式};{标题样式}\">{行图标文本}{状态图标文本}<span class=\"单元格编辑占位\" aria-hidden=\"true\">{}</span><input class=\"hs-input\" data-hs-edit-row=\"{行键}\" data-hs-edit-column=\"{列序}\" value=\"{}\" aria-label=\"编辑单元格\"></td>",
                    热点类.trim(),
                    转义网页文本(&单元格值文本),
                    转义网页文本(&单元格值文本)
                ));
            } else {
                let 双击编辑属性 = if 设置.允许编辑 {
                    format!(
                        " data-hs-event-double-op=\"进入编辑\" data-hs-edit-row=\"{行键}\" data-hs-edit-column=\"{列序}\""
                    )
                } else {
                    String::new()
                };
                表格主体文本.push_str(&format!(
                    "<td class=\"{}\" data-hs-cell-column=\"{列序}\" data-hs-row=\"{行键}\" style=\"text-align:{对齐样式}{宽度样式}{选中单元格样式}{缩进样式};{热点样式};{标题样式}\"{双击编辑属性}>{行图标文本}{状态图标文本}{}</td>",
                    热点类.trim(),
                    转义网页文本(&单元格值文本)
                ));
            }
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

pub fn 执行业务操作(编号: u32, 参数表: &[调用参数]) -> Result<(u32, Vec<u8>), u32> {
    match 编号 {
        能力号::渲染组件树 => {
            let 树定义原文 = 参数表[0].取文本()?;
            crate::组件树::渲染组件树(&树定义原文)
        }
        能力号::操作组件 => crate::组件操作::操作组件(
            参数表[0].取数值()?,
            参数表[1].取文本()?.as_str(),
            参数表[2].取文本()?.as_str(),
        ),
        能力号::读组件状态 => crate::组件操作::读组件状态(参数表[0].取数值()?),
        能力号::释放组件句柄 => {
            crate::组件操作::释放组件句柄(参数表[0].取数值()?)
        }
        _ => Err(错误码::参数不合法),
    }
}
