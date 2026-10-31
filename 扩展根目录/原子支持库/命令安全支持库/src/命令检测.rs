use crate::编号与码面::错误码;
use base64::{Engine as 编解码引擎, engine::general_purpose::STANDARD as 标准编码};
use regex::Regex as 正则引擎;
use std::collections::BTreeMap as 有序映射;

fn 匹配模式(模式文本: &str, 命令原文: &str) -> bool {
    正则引擎::new(模式文本).is_ok_and(|匹配器| 匹配器.is_match(命令原文))
}
fn 检查直接危险(命令原文: &str) -> Option<&'static str> {
    for (模式文本, 原因文本) in [
        (
            r"(?i)(^|[\s/;|&()`])(?:sudo|doas|su|passwd|fdisk|sfdisk|parted|mkfs(?:\.[\w-]+)?|shutdown|reboot|halt|poweroff)(?:\s|$)",
            "提权、账户、分区或关机命令",
        ),
        (
            r"(?i)(^|[\s/;|&()`])rm\s+[^;|&\n]*(?:-[^\s]*[rRfF][^\s]*\s+|--recursive\s+)[^;|&\n]*(?:/|~)(?:\s|\*|$)",
            "递归删除根目录或用户目录",
        ),
        (
            r"(?i)(^|[\s/;|&()`])(?:curl|wget)\s+[^\n]*\|\s*(?:/\S*/)?(?:sh|bash|zsh|dash|python[\d.]*|perl|ruby)(?:\s|$)",
            "下载后交解释器执行",
        ),
        (
            r"(?i)(^|[\s/;|&()`])chmod\s+[^;|&\n]*(?:777|\+s|u\+s|a\+w)[^;|&\n]*(?:/|~)(?:\s|$)",
            "危险权限变更",
        ),
        (
            r"(?i)(^|[\s/;|&()`])dd\s+[^;|&\n]*of\s*=\s*/dev/",
            "覆写设备",
        ),
        (
            r"(?i)(?:>|\btee\s+(?:-\w+\s+)*)(?:\s*)(?:/etc/|/dev/|/System/|/boot/)",
            "写入系统敏感路径",
        ),
        (r":\s*\(\s*\)\s*\{", "进程递归派生模式"),
    ] {
        if 匹配模式(模式文本, 命令原文) {
            return Some(原因文本);
        }
    }
    None
}
fn 展开十六进制(命令原文: &str) -> Result<Option<String>, u32> {
    let 匹配器 =
        正则引擎::new(r"(?:\\x[0-9a-fA-F]{2})+").map_err(|_| 错误码::命令安全不可用)?;
    let mut 解码文本 = 命令原文.to_owned();
    let mut 发生解码 = false;
    for 匹配项 in 匹配器.find_iter(命令原文) {
        let 解码字节 = 匹配项
            .as_str()
            .as_bytes()
            .chunks_exact(4)
            .map(|转义字节| {
                std::str::from_utf8(&转义字节[2..])
                    .ok()
                    .and_then(|数字文本| u8::from_str_radix(数字文本, 16).ok())
            })
            .collect::<Option<Vec<_>>>()
            .ok_or(错误码::命令安全不可用)?;
        let 替换文本 = String::from_utf8(解码字节).map_err(|_| 错误码::命令安全不可用)?;
        解码文本 = 解码文本.replace(匹配项.as_str(), &替换文本);
        发生解码 = true;
    }
    Ok(发生解码.then_some(解码文本))
}
fn 展开简单变量(命令原文: &str) -> Result<String, u32> {
    let 赋值匹配器 =
        正则引擎::new(r"(?:^|[;\s])([A-Za-z_][A-Za-z0-9_]*)=([A-Za-z0-9_./-]+)(?:;|\s|$)")
            .map_err(|_| 错误码::命令安全不可用)?;
    let mut 变量表 = 有序映射::new();
    for 捕获组 in 赋值匹配器.captures_iter(命令原文) {
        变量表.insert(捕获组[1].to_owned(), 捕获组[2].to_owned());
    }
    let 变量匹配器 = 正则引擎::new(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?")
        .map_err(|_| 错误码::命令安全不可用)?;
    let mut 展开文本 = 命令原文.to_owned();
    for 捕获组 in 变量匹配器.captures_iter(命令原文) {
        let 替换文本 = 变量表.get(&捕获组[1]).ok_or(错误码::命令安全不可用)?;
        展开文本 = 展开文本.replace(&捕获组[0], 替换文本);
    }
    if 展开文本.contains('$') {
        return Err(错误码::命令安全不可用);
    }
    Ok(展开文本)
}
/// 有界纯文本检测，不执行样本；不是完整shell解析器或沙箱。
pub fn 检测命令(命令原文: &str, 递归深度: usize) -> Result<(bool, String), u32> {
    if 命令原文.len() > 65536 || 递归深度 > 4 {
        return Err(错误码::资源受限);
    }
    if 命令原文.trim().is_empty() || 命令原文.contains('\0') {
        return Err(错误码::参数不合法);
    }
    if let Some(原因文本) = 检查直接危险(命令原文) {
        return Ok((true, 原因文本.into()));
    }
    if let Some(解码文本) = 展开十六进制(命令原文)? {
        let 判定结果 = 检测命令(&解码文本, 递归深度 + 1)?;
        if 判定结果.0 {
            return Ok(判定结果);
        }
        return Err(错误码::命令安全不可用);
    }
    let 编码匹配器 =
        正则引擎::new(r"[A-Za-z0-9+/]{8,}={0,2}").map_err(|_| 错误码::命令安全不可用)?;
    let mut 解码总长 = 0;
    for 匹配项 in 编码匹配器.find_iter(命令原文) {
        if let Ok(解码字节) = 标准编码.decode(匹配项.as_str()) {
            解码总长 += 解码字节.len();
            if 解码总长 > 65536 {
                return Err(错误码::资源受限);
            }
            if let Ok(解码文本) = String::from_utf8(解码字节)
                && !解码文本.trim().is_empty()
                && !解码文本.contains('\0')
            {
                match 检测命令(&解码文本, 递归深度 + 1) {
                    Ok(判定结果) if 判定结果.0 => return Ok(判定结果),
                    Err(失败码) => return Err(失败码),
                    _ => {}
                }
            }
        }
    }
    let 归一文本 = 命令原文.replace(['\'', '"', '\\'], "");
    if let Some(原因文本) = 检查直接危险(&归一文本) {
        return Ok((true, 原因文本.into()));
    }
    if 命令原文.contains(['`', '\n', '\r'])
        || 命令原文.contains("$(")
        || 命令原文.contains("<(")
        || 命令原文.contains(">(")
        || 匹配模式(
            r"(^|[\s/;|&])(?:eval|source|exec|alias|function|export|unset)(?:\s|$)|(^|[;|&])\s*\.\s",
            &归一文本,
        )
        || 匹配模式(
            r"(^|[\s/;|&])(?:sh|bash|zsh|dash|python[\d.]*|perl|ruby|node)(?:\s|$)",
            &归一文本,
        )
        || 命令原文.contains('\\')
    {
        return Err(错误码::命令安全不可用);
    }
    if !命令原文.matches('\'').count().is_multiple_of(2)
        || !命令原文.matches('"').count().is_multiple_of(2)
    {
        return Err(错误码::命令安全不可用);
    }
    let 展开文本 = 展开简单变量(&归一文本)?;
    if 展开文本 != 归一文本 {
        return 检测命令(&展开文本, 递归深度 + 1);
    }
    Ok((false, String::new()))
}
