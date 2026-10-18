//! 分层索引请求：只读发现；路径是族类段，不接受文件系统路径。
use crate::转码::百分号解码;

pub struct 索引请求 {
    pub 路径: Vec<String>,
    pub 起始: usize,
    pub 一次条数: usize,
    pub 编号: Option<u32>,
}

pub fn 解析索引(查询串: &str) -> Result<索引请求, String> {
    let mut 请求 = 索引请求 { 路径: Vec::new(), 起始: 0, 一次条数: 20, 编号: None };
    let mut 已读键 = std::collections::BTreeSet::new();
    for 一格 in 查询串.split('&').filter(|一格| !一格.is_empty()) {
        let (键文, 值文) = 一格.split_once('=').ok_or("查询格必须是 键=值")?;
        let 键文 = 百分号解码(键文).map_err(|_| "索引键不是合法UTF-8")?;
        let 值文 = 百分号解码(值文).map_err(|_| "索引值不是合法UTF-8")?;
        if !已读键.insert(键文.clone()) { return Err(format!("索引键重复：{键文}")); }
        match 键文.as_str() {
            "路径" if 值文.is_empty() => (),
            "路径" => {
                let 分段: Vec<String> = 值文.split('/').map(str::to_owned).collect();
                if 分段.len() > 16 || 分段.iter().any(|路径段| 路径段.is_empty() || 路径段 == "." || 路径段 == ".." || 路径段.len() > 240 || 路径段.contains(['\\', '\0'])) {
                    return Err("索引路径含无效段；最多16层，每层须为非空族名".to_owned());
                }
                请求.路径 = 分段;
            }
            "起始" => 请求.起始 = 值文.parse().map_err(|_| "起始须为非负整数")?,
            "一次条数" => 请求.一次条数 = 值文.parse().map_err(|_| "一次条数须为整数")?,
            "编号" => 请求.编号 = Some(值文.parse().map_err(|_| "编号须为非负整数")?),
            _ => return Err(format!("索引没有这个键：{键文}；只认路径、起始、一次条数、编号")),
        }
    }
    if 请求.一次条数 == 0 || 请求.一次条数 > 50 { return Err("一次条数须在1至50；不允许无界展开".to_owned()); }
    if 请求.编号.is_some() && 请求.路径.len() == 1 { return Err("按编号直达可省略路径；限制范围时须给出种类与包路径".to_owned()); }
    Ok(请求)
}
