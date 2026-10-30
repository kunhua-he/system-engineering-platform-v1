use crate::编号与码面::错误码;
use std::io::Read as 读取接口;

pub const 最大文件字节: usize = 32 * 1024 * 1024;
pub const 最大回读字节: usize = 262144;
pub const 最大工作表数: usize = 32;
pub const 最大表格行数: usize = 10000;
pub const 最大表格列数: usize = 256;
pub const 最大矩形格数: usize = 200000;

pub fn 读取表格文件(文件路径: &str) -> Result<Vec<u8>, u32> {
    if !std::path::Path::new(文件路径).is_absolute() {
        return Err(错误码::参数不合法);
    }
    let 文件句柄 = std::fs::File::open(文件路径).map_err(|_| 错误码::内容不合法)?;
    if 文件句柄.metadata().map_err(|_| 错误码::内容不合法)?.len() > 最大文件字节 as u64 {
        return Err(错误码::内容不合法);
    }
    let mut 文件字节 = Vec::new();
    文件句柄.take(最大文件字节 as u64 + 1).read_to_end(&mut 文件字节).map_err(|_| 错误码::内容不合法)?;
    if 文件字节.len() > 最大文件字节 { return Err(错误码::内容不合法); }
    let mut 归档句柄 = zip::ZipArchive::new(std::io::Cursor::new(&文件字节)).map_err(|_| 错误码::内容不合法)?;
    if 归档句柄.len() > 512 { return Err(错误码::内容不合法); }
    let mut 解压总字节 = 0u64;
    for 条目序位 in 0..归档句柄.len() {
        let 条目句柄 = 归档句柄.by_index(条目序位).map_err(|_| 错误码::内容不合法)?;
        if 条目句柄.size() > 最大文件字节 as u64 { return Err(错误码::内容不合法); }
        解压总字节 = 解压总字节.checked_add(条目句柄.size()).ok_or(错误码::内容不合法)?;
        if 解压总字节 > 64 * 1024 * 1024 { return Err(错误码::内容不合法); }
        if 条目句柄.name().map_err(|_| 错误码::内容不合法)?.ends_with(".xml") {
            核单表边界(条目句柄)?;
        }
    }
    drop(归档句柄);
    Ok(文件字节)
}

// 只预检资源坐标，不承担工作簿解析；必须在成熟引擎分配稠密区域之前执行。
fn 核单表边界(条目句柄: impl 读取接口) -> Result<(), u32> {
    use quick_xml::{Reader as 文档读取器, events::Event as 文档事件};
    let mut 读取器 = 文档读取器::from_reader(std::io::BufReader::new(条目句柄));
    let mut 事件缓存 = Vec::new();
    let mut 顺序行数 = 0usize;
    let mut 顺序列数 = 0usize;
    loop {
        match 读取器.read_event_into(&mut 事件缓存).map_err(|_|错误码::内容不合法)? {
            文档事件::Start(标签项) | 文档事件::Empty(标签项) => {
                let 本地名 = 标签项.local_name();
                if 本地名.as_ref() == "row" { 顺序行数 += 1; 顺序列数 = 0; }
                if 本地名.as_ref() == "c" { 顺序列数 += 1; }
                if 顺序行数 > 最大表格行数 || 顺序列数 > 最大表格列数 { return Err(错误码::内容不合法); }
                for 属性项 in 标签项.attributes() {
                    let 属性项 = 属性项.map_err(|_|错误码::内容不合法)?;
                    if (本地名.as_ref() == "c" && 属性项.key.as_ref() == "r") || (本地名.as_ref() == "dimension" && 属性项.key.as_ref() == "ref") {
                        let 引用文本 = 属性项.value.as_ref();
                        核单元引用(引用文本.rsplit(':').next().unwrap_or(引用文本))?;
                    }
                    if 本地名.as_ref() == "row" && 属性项.key.as_ref() == "r" {
                        let 行号值 = 属性项.value.as_ref().parse::<usize>().map_err(|_|错误码::内容不合法)?;
                        if 行号值 == 0 || 行号值 > 最大表格行数 { return Err(错误码::内容不合法); }
                        顺序行数 = 行号值;
                    }
                }
            }
            文档事件::DocType(_) => return Err(错误码::内容不合法),
            文档事件::Eof => break,
            _ => (),
        }
        事件缓存.clear();
    }
    Ok(())
}

fn 核单元引用(引用文本: &str) -> Result<(), u32> {
    let mut 列号值 = 0usize;
    let mut 行号拼文 = String::new();
    for 单字节 in 引用文本.bytes() {
        if 单字节.is_ascii_uppercase() && 行号拼文.is_empty() {
            列号值 = 列号值.checked_mul(26).and_then(|列号值|列号值.checked_add((单字节-b'A'+1) as usize)).ok_or(错误码::内容不合法)?;
        } else if 单字节.is_ascii_digit() { 行号拼文.push(单字节 as char); }
        else { return Err(错误码::内容不合法); }
    }
    let 行号值 = 行号拼文.parse::<usize>().map_err(|_|错误码::内容不合法)?;
    if 列号值 == 0 || 列号值 > 最大表格列数 || 行号值 == 0 || 行号值 > 最大表格行数 { return Err(错误码::内容不合法); }
    Ok(())
}

pub fn 核矩形预算(行计数: usize, 列计数: usize, 累计格数: &mut usize, 失败码: u32) -> Result<(), u32> {
    if 行计数 > 最大表格行数 || 列计数 > 最大表格列数 { return Err(失败码); }
    *累计格数 = 累计格数.checked_add(行计数.checked_mul(列计数).ok_or(失败码)?).ok_or(失败码)?;
    if *累计格数 > 最大矩形格数 { return Err(失败码); }
    Ok(())
}
