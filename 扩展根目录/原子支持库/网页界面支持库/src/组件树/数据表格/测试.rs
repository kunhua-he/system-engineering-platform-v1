use super::*;
use serde_json::json;

#[test]
fn 可排序表头总有两个独立方向按钮() {
    let 表格节点 = json!({"类型":"表格","列":["金额","名称"],"行":[[10,"精华"]],"可排序":true,"__组件句柄":100_009});
    let mut 页面状态 = crate::组件树::渲染状态::新();
    let 页面文本 = 拼装表格(&表格节点, &mut 页面状态).unwrap();
    assert_eq!(页面文本.matches("data-排序升序=\"true\"").count(), 2);
    assert_eq!(页面文本.matches("data-排序升序=\"false\"").count(), 2);
    assert!(页面文本.contains("aria-label=\"金额升序\""));
    assert!(页面文本.contains("aria-label=\"金额降序\""));
    assert!(!页面文本.contains("<th data-hs-op=\"排序\""));
    assert!(页面文本.contains("data-列宽声明="));
    assert!(页面文本.contains("<colgroup>"));
}

#[test]
fn 未开启列拖动时表头仍带列序号标记() {
    // 列宽拖动靠 data-hs-header-column 定位列；它不能只在「列可拖动」时才输出。
    let 表格节点 =
        json!({"类型":"表格","列":["金额","名称"],"行":[[10,"精华"]],"__组件句柄":100_010});
    let mut 页面状态 = crate::组件树::渲染状态::新();
    let 页面文本 = 拼装表格(&表格节点, &mut 页面状态).unwrap();
    assert!(页面文本.contains("data-hs-header-column=\"1\""));
    assert!(!页面文本.contains("data-hs-column=\"1\""));
}

#[test]
fn 数值单位排序正确() {
    assert_eq!(
        比较单元格(&json!("9 KB"), &json!("10 MB"), "数值"),
        std::cmp::Ordering::Less
    );
    assert_eq!(
        比较单元格(&json!("2 MiB"), &json!("1 GB"), "数值"),
        std::cmp::Ordering::Less
    );
}

#[test]
fn 日期文本按先后排列() {
    assert_eq!(
        比较单元格(&json!("2026-09-01"), &json!("2026-10-01"), "日期"),
        std::cmp::Ordering::Less
    );
    assert!(是日期文本(&json!("2026-11-02T12:30:00")));
    assert!(!是日期文本(&json!("2026-13-40")));
}

#[test]
fn 表格列参数严格校验() {
    let 检验列值 = json!(["编号", "内容"]);
    let 检验行值 = json!([[1, "面膜"], [2, "一瓶精华液"]]);
    let 检验列 = 检验列值.as_array().unwrap();
    let 检验行 = 检验行值.as_array().unwrap();
    let 自适应节点 = json!({"列宽":[240,"自适应"]});
    let 缺省节点 = json!({});
    let 过窄节点 = json!({"列宽":[30]});
    let 错数节点 = json!({"列宽":[120]});
    let 旧值节点 = json!({"列宽":[120,"auto"]});
    let 列宽结果 = 取列宽表(&自适应节点, 检验列, 检验行).unwrap();
    assert_eq!(列宽结果[0], 240);
    assert!((60..=600).contains(&列宽结果[1]));
    assert_eq!(取列宽表(&缺省节点, 检验列, 检验行).unwrap().len(), 2);
    assert!(取列宽表(&过窄节点, 检验列, 检验行).is_err());
    assert!(取列宽表(&错数节点, 检验列, 检验行).is_err());
    assert!(取列宽表(&旧值节点, 检验列, 检验行).is_err());
    assert!(取列对齐表(&json!({"列对齐方式":["左","右"]}), 2).is_ok());
    assert!(取列对齐表(&json!({"列对齐方式":["左","居中"]}), 2).is_err());
    for 模式 in ["不选", "单选", "多选", "整行"] {
        assert_eq!(取选择模式(&json!({"选择模式":模式})).unwrap(), 模式);
    }
    assert!(取选择模式(&json!({"选择模式":"自动"})).is_err());
    assert_eq!(
        取选中行序号表(&json!({"__选中":["2","0","99"]}), 3),
        vec![2, 0]
    );
}

#[test]
fn 可排序表格的自适应列宽含方向按钮宽度() {
    let 列值 = json!(["数量", "备注"]);
    let 行值 = json!([[1, "无"]]);
    let 列 = 列值.as_array().unwrap();
    let 行 = 行值.as_array().unwrap();
    let 可排序宽 = 取列宽表(&json!({"可排序":true}), 列, 行).unwrap();
    let 不排序宽 = 取列宽表(&json!({}), 列, 行).unwrap();
    assert!(
        可排序宽[0] >= 28 + 26 + 26,
        "可排序列宽 {可排序宽:?} 没给方向按钮留位"
    );
    assert_eq!(不排序宽, vec![60, 60]);
    assert!(可排序宽[0] > 不排序宽[0]);
}

#[test]
fn 数值排序按单位和真实行序() {
    let 表格节点 = json!({
        "类型":"表格",
        "列":["文件大小"],
        "行":[["10 MB"],["9 KB"]],
        "可排序":true,
        "排序方式":"数值",
        "__排序键":"文件大小",
        "__升序":true,
        "__组件句柄":100_002
    });
    let mut 渲染状态 = crate::组件树::渲染状态::新();
    let 网页文本 = 拼装表格(&表格节点, &mut 渲染状态).unwrap();
    assert!(网页文本.find("9 KB").unwrap() < 网页文本.find("10 MB").unwrap());
}

#[test]
fn 非法数值排序明确拒收() {
    let 表格节点 = json!({
        "类型":"表格",
        "列":["文件大小"],
        "行":[["9 KB"],["未知单位"]],
        "排序方式":"数值",
        "__排序键":"文件大小"
    });
    let mut 渲染状态 = crate::组件树::渲染状态::新();
    assert_eq!(
        拼装表格(&表格节点, &mut 渲染状态).unwrap_err(),
        错误码::内容不合法
    );
}

#[test]
fn 选择模式渲染并保留行身份() {
    let 表格节点 = json!({
        "类型":"表格",
        "列":["名称"],
        "行":[["第一行"],["第二行"]],
        "选择模式":"多选",
        "勾选列":true,
        "__选中":["1"],
        "__检查状态":[false,true],
        "__组件句柄":100_003
    });
    let mut 渲染状态 = crate::组件树::渲染状态::新();
    let 网页文本 = 拼装表格(&表格节点, &mut 渲染状态).unwrap();
    assert!(网页文本.contains("data-hs-key=\"1\""));
    assert!(网页文本.contains("aria-selected=\"true\""));
    assert!(网页文本.contains("type=\"checkbox\""));
    assert!(渲染状态.需要组件引导脚本);
}

#[test]
fn 勾选表格输出稳定句柄键() {
    let 呈现设置 = crate::业务实现::表格呈现设置 {
        列宽表: &[120],
        条目行高: None,
        列对齐表: &["右"],
        选择模式: "多选",
        勾选列: true,
        检查状态表: &[json!(false), json!(false), json!(true)],
        选中行序号表: &[2],
        可排序: true,
        排序列: Some(0),
        升序: true,
        组件句柄: 100_001,
        无表头: false,
        显示表格线: true,
        标题换行: false,
        列可拖动: false,
        表头图标表: &[],
        表头图标居右表: &[],
        行图标表: &[],
        单元格图片: &Value::Null,
        行状态图标表: &[],
        行缩进表: &[],
        热点跟踪: false,
        手形指针: false,
        标注热点: false,
        标注非热点: false,
        允许编辑: false,
        编辑单元格: None,
        结束编辑文本: "",
        滚动目标: None,
        视图模式: "报表",
        图标对齐方式: "左",
        自动排列图标: true,
        平面滚动条: false,
        始终显示选择项: true,
        行提示表: &[],
        列提示表: &[],
        图标间距: 8,
    };
    let 表格文本 =
        crate::业务实现::拼装表格行(&[json!("金额")], &[(2, json!([120]))], &呈现设置).unwrap();
    assert!(表格文本.contains("data-hs-h=\"100001\""));
    assert!(表格文本.contains("data-hs-key=\"2\""));
    assert!(表格文本.contains("type=\"checkbox\""));
    assert!(表格文本.contains("checked"));
    assert!(表格文本.contains("text-align:right;width:120px"));
}
