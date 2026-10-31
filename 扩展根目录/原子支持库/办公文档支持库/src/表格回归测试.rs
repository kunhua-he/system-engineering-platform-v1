use serde_json::json;

fn 测试目录() -> String {
    std::env::var("TMPDIR").map(|目录值| format!("{目录值}/办公回归-{}", std::process::id())).expect("测试须提供 TMPDIR")
}

fn 准备目录() -> String {
    let 产物目录 = 测试目录();
    std::fs::create_dir_all(&产物目录).unwrap();
    产物目录
}

#[test]
fn 验证旧输入形状() {
    let 产物目录 = 准备目录();
    let 路径 = format!("{产物目录}/旧形状.xlsx");
    let _ = std::fs::remove_file(&路径);
    let 表格输入 = json!({
        "工作表列表": [{
            "表名": "旧表",
            "列": ["编号", "金额", "说明"],
            "行": [[1, 2.5, true], ["示例", null, {"公式": "=B2*2"}]]
        }]
    });
    let 回执 = crate::表格写出::生成表格(&表格输入.to_string(), &路径).expect("旧形状应能写出");
    let 回执值: serde_json::Value = serde_json::from_str(&回执).unwrap();
    assert_eq!(回执值["输出路径"], json!(路径));
    let 解析回执 = crate::表格读取::解析表格(&路径).expect("旧形状应能读回");
    let 解析值: serde_json::Value = serde_json::from_str(&解析回执).unwrap();
    assert_eq!(解析值["工作表数"], json!(1));
    assert_eq!(解析值["块列表"][0]["表格数据"][0][0], json!("编号"));
    assert_eq!(解析值["块列表"][0]["表格数据"][2][2], json!("=B2*2"));
}

#[test]
fn 验证样式合并往返() {
    let 产物目录 = 准备目录();
    let 路径 = format!("{产物目录}/样式.xlsx");
    let _ = std::fs::remove_file(&路径);
    let 表格输入 = json!({
        "工作表列表": [{
            "表名": "报表",
            "列": ["项目", "金额", "备注"],
            "行": [
                [
                    {"值": "合计", "样式": {
                        "加粗": true, "字号": 14.0, "字体": "宋体",
                        "字体颜色": "#C00000", "底色": "#FFF2CC",
                        "水平对齐": "中", "垂直对齐": "中",
                        "自动换行": true, "边框": "细", "数字格式": "0.00"
                    }},
                    {"值": 12.5, "样式": {"数字格式": "0.00"}},
                    {"值": {"公式": "=B2*2"}}
                ],
                ["示例", 1, "普通"]
            ],
            "合并列表": [{"区域": "A4:C4"}, {"首行": 4, "首列": 0, "末行": 4, "末列": 1}],
            "列宽": [{"列": 0, "宽": 20.0}, {"列": 1, "宽": 12.5}],
            "行高": [{"行": 0, "高": 30.0}]
        }]
    });
    let 回执 = crate::表格写出::生成表格(&表格输入.to_string(), &路径).expect("新形状应能写出");
    let 回执值: serde_json::Value = serde_json::from_str(&回执).unwrap();
    assert!(回执值["字节数"].as_u64().unwrap() > 0);

    let 解析回执 = crate::表格读取::解析表格(&路径).expect("新形状应能读回");
    let 解析值: serde_json::Value = serde_json::from_str(&解析回执).unwrap();
    let 表格块 = &解析值["块列表"][0];
    assert_eq!(表格块["来源位置"]["工作表"], json!("报表"));
    assert_eq!(表格块["表格数据"][1][0], json!("合计"));
    assert_eq!(表格块["表格数据"][1][1], json!(12.5));
    assert_eq!(表格块["表格数据"][1][2], json!("=B2*2"));

    let 合并数组 = 表格块["合并列表"].as_array().unwrap();
    assert_eq!(合并数组.len(), 2);
    let 首项 = 合并数组.iter().find(|合并项| 合并项["区域"] == json!("A4:C4")).expect("应含 A4:C4");
    assert_eq!(首项["起始行"], json!(3));
    assert_eq!(首项["起始列"], json!(0));
    assert_eq!(首项["行跨度"], json!(1));
    assert_eq!(首项["列跨度"], json!(3));

    let 样式网格 = 表格块["样式网格"].as_array().unwrap();
    let 首格 = 样式网格.iter().find(|样式格| 样式格["行"] == json!(1) && 样式格["列"] == json!(0)).expect("首格应有样式");
    assert_eq!(首格["加粗"], json!(true));
    assert_eq!(首格["字体"], json!("宋体"));
    assert_eq!(首格["字体颜色"], json!("#C00000"));
    assert_eq!(首格["填充色"], json!("#FFF2CC"));
    assert_eq!(首格["水平对齐"], json!("中"));
    assert_eq!(首格["垂直对齐"], json!("中"));
    assert_eq!(首格["自动换行"], json!(true));
    assert_eq!(首格["数字格式"], json!("0.00"));
    assert_eq!(首格["字号"], json!(14.0));

    assert!(解析值["资源列表"]["图片数"].is_number(), "资源列表应是图片清单对象");
}

#[test]
fn 验证合并区域拒收() {
    let 产物目录 = 准备目录();
    let 路径 = format!("{产物目录}/越界.xlsx");
    let 越界 = json!({
        "工作表列表": [{"表名": "越界表", "列": ["示例"], "行": [[1]],
            "合并列表": [{"首行": 0, "首列": 300, "末行": 1, "末列": 301}]}]
    });
    let 返回码 = crate::表格写出::生成表格(&越界.to_string(), &路径).unwrap_err();
    assert_eq!(返回码, 6101);

    let 重叠 = json!({
        "工作表列表": [{"表名": "重叠表", "列": ["示例"], "行": [[1]],
            "合并列表": [{"区域": "A1:B1"}, {"区域": "B1:C1"}]}]
    });
    let 返回码 = crate::表格写出::生成表格(&重叠.to_string(), &路径).unwrap_err();
    assert_eq!(返回码, 6101);

    let 单格 = json!({
        "工作表列表": [{"表名": "单格表", "列": ["示例"], "行": [[1]],
            "合并列表": [{"区域": "A1:A1"}]}]
    });
    let 返回码 = crate::表格写出::生成表格(&单格.to_string(), &路径).unwrap_err();
    assert_eq!(返回码, 6101);
}

#[test]
fn 验证坏样式拒收() {
    let 产物目录 = 准备目录();
    let 路径 = format!("{产物目录}/坏样式.xlsx");
    let 坏键 = json!({
        "工作表列表": [{"表名": "坏键表", "列": ["示例"], "行": [[{"值": 1, "样式": {"加粗粗": true}}]]}]
    });
    assert_eq!(crate::表格写出::生成表格(&坏键.to_string(), &路径).unwrap_err(), 6101);

    let 坏色 = json!({
        "工作表列表": [{"表名": "坏色表", "列": ["示例"], "行": [[{"值": 1, "样式": {"底色": "深黄"}}]]}]
    });
    assert_eq!(crate::表格写出::生成表格(&坏色.to_string(), &路径).unwrap_err(), 6101);

    let 坏存储 = crate::表格写出::生成表格(&json!({"工作表列表": []}).to_string(), "相对路径.xlsx").unwrap_err();
    assert_eq!(坏存储, 6101);
}
