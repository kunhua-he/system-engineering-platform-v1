use crate::编号与码面::{能力号, 错误码};
pub fn 执行文本操作(操作号: u32, 文本参数表: &[&str]) -> Result<(u32, Vec<u8>), u32> {
    if 文本参数表.iter().any(|文本参数表| 文本参数表.len() > 65536) {
        return Err(错误码::资源受限);
    }
    let 取文本 = |参数位置: usize| 文本参数表.get(参数位置).copied().ok_or(错误码::参数不合法);

    // 4204 的输入可能不是网址（裸 11 位标识、arXiv 旧式编号），不能先过 URL 解析
    if 操作号 == 能力号::提取外部标识 {
        return Ok((4, 执行外部标识提取(取文本(0)?, 取文本(1)?)?.into_bytes()));
    }

    use url::Url as 网址解析器;
    let 网址值 = 网址解析器::parse(取文本(0)?).map_err(|_| 错误码::内容不合法)?;
    let 输出文本 = match 操作号 {
        能力号::规范化网址 => 网址值.to_string(),
        能力号::合并相对网址 => 网址值
            .join(取文本(1)?)
            .map_err(|_| 错误码::内容不合法)?
            .to_string(),
        能力号::取查询参数JSON => {
            let 参数对表 = 网址值
                .query_pairs()
                .map(|(参数名, 参数值)| (参数名.into_owned(), 参数值.into_owned()))
                .collect::<Vec<_>>();
            if 参数对表.len() > 1000 {
                return Err(错误码::资源受限);
            }
            serde_json::to_string(&参数对表).map_err(|_| 错误码::内容不合法)?
        }
        _ => return Err(错误码::参数不合法),
    };

    if 输出文本.len() > 65536 {
        return Err(错误码::资源受限);
    }
    Ok((4, 输出文本.into_bytes()))
}

fn 是标识字符(待判字符: char) -> bool {
    待判字符.is_ascii_alphanumeric() || 待判字符 == '_' || 待判字符 == '-'
}

fn 取视频站标识(输入原文: &str) -> Option<String> {
    for 标记 in ["v=", "youtu.be/", "/shorts/", "/embed/", "/live/"] {
        if let Some(命中位置) = 输入原文.find(标记) {
            let 字符表: Vec<char> = 输入原文[命中位置 + 标记.len()..].chars().collect();
            if 字符表.len() >= 11 && 字符表[..11].iter().all(|单字符| 是标识字符(*单字符)) {
                // 边界判定手写：第 12 位仍是标识字符 ⇒ 不是 11 位 ID。
                // 旧实现按前 11 位截断，会把 12 位的非法 ID 抓成另一个视频。
                if 字符表.get(11).map(|单字符| !是标识字符(*单字符)).unwrap_or(true) {
                    return Some(字符表[..11].iter().collect());
                }
            }
        }
    }
    let 净文本 = 输入原文.trim();
    let 字符表: Vec<char> = 净文本.chars().collect();
    if 字符表.len() == 11 && 字符表.iter().all(|单字符| 是标识字符(*单字符)) {
        return Some(净文本.to_string());
    }
    None
}

fn 取预印本标识(输入原文: &str) -> Option<(String, String)> {
    let 余段 = if let Some(命中位置) = 输入原文.find("/abs/") {
        &输入原文[命中位置 + 5..]
    } else if let Some(命中位置) = 输入原文.find("/pdf/") {
        &输入原文[命中位置 + 5..]
    } else {
        输入原文.trim()
    };
    let 候选文本 = 余段
        .split(['?', '#'])
        .next()
        .unwrap_or("")
        .trim_end_matches('/');
    // /pdf/ 链接常带 .pdf 后缀；不剥掉会被当编号的一部分（真机实测：math.GT/0309136v1.pdf 判不出）
    let 去掉后缀 = 候选文本
        .strip_suffix(".pdf")
        .or_else(|| 候选文本.strip_suffix(".PDF"))
        .unwrap_or(候选文本);
    let (主体, 版本) = match 去掉后缀.rfind('v') {
        Some(命中位置) if 命中位置 > 0 => {
            let 尾段 = &去掉后缀[命中位置 + 1..];
            let 前段末字 = 去掉后缀[..命中位置].chars().next_back();
            let 版本形 = !尾段.is_empty()
                && 尾段.chars().all(|单字符| 单字符.is_ascii_digit())
                && 前段末字.map(|单字符| 单字符.is_ascii_digit()).unwrap_or(false);
            if 版本形 {
                (&去掉后缀[..命中位置], &去掉后缀[命中位置..])
            } else {
                (去掉后缀, "")
            }
        }
        _ => (去掉后缀, ""),
    };
    if 主体.is_empty() || 主体.len() > 64 {
        return None;
    }
    let 合法 = if let Some((分类, 编号)) = 主体.split_once('/') {
        // 旧式：分类/7位数字，例如 hep-th/9906140、math.GT/0309136
        !分类.is_empty()
            && 编号.len() == 7
            && 编号.chars().all(|单字符| 单字符.is_ascii_digit())
            && 分类.chars().all(|单字符| {
                单字符.is_ascii_lowercase() || 单字符.is_ascii_uppercase() || 单字符 == '-' || 单字符 == '.'
            })
    } else if let Some((前段, 后段)) = 主体.split_once('.') {
        // 新式：YYYY.NNNN 或 YYYY.NNNNN，例如 2101.00001
        前段.len() == 4
            && 前段.chars().all(|单字符| 单字符.is_ascii_digit())
            && (4..=5).contains(&后段.len())
            && 后段.chars().all(|单字符| 单字符.is_ascii_digit())
    } else {
        false
    };
    if !合法 {
        return None;
    }
    Some((主体.to_string(), 版本.to_string()))
}

fn 执行外部标识提取(输入原文: &str, 来源: &str) -> Result<String, u32> {
    let 来源 = 来源.trim();
    if 输入原文.trim().is_empty() || !(来源 == "youtube" || 来源 == "arxiv") {
        return Err(错误码::参数不合法);
    }
    if 来源 == "youtube" {
        let 标识 = 取视频站标识(输入原文).ok_or(错误码::标识无法识别)?;
        let 载荷 = serde_json::json!({"来源类型": "youtube", "标识": 标识, "版本": ""});
        return serde_json::to_string(&载荷).map_err(|_| 错误码::内容不合法);
    }
    let (标识, 版本) = 取预印本标识(输入原文).ok_or(错误码::标识无法识别)?;
    let 载荷 = serde_json::json!({"来源类型": "arxiv", "标识": 标识, "版本": 版本});
    serde_json::to_string(&载荷).map_err(|_| 错误码::内容不合法)
}

