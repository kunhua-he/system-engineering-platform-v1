use crate::编号与码面::{能力号,错误码};
use std::io::{Cursor as 内存游标,Read,Write};
use zip::{ZipArchive as 归档读取器, ZipWriter as 归档写入器};
use zip::write::SimpleFileOptions as 成员选项;
use v1_contract::复合值载荷::{复合值,复合元素,编码复合值载荷};
fn 验成员路径(名称:&str)->Result<(),u32>{
    let 路径=std::path::Path::new(名称);
    if 名称.is_empty() || 名称.len()>4096 || 名称.contains(['\\','\0',':']) || 路径.is_absolute() || 路径.components().any(|片段| matches!(片段,std::path::Component::ParentDir|std::path::Component::RootDir|std::path::Component::Prefix(_))) {return Err(错误码::内容不合法);}
    Ok(())
}
pub fn 执行业务操作(编号:u32,参数表:&[&[u8]])->Result<(u32,Vec<u8>),u32>{
    if 编号==能力号::生成单成员 {
        let 名称=std::str::from_utf8(参数表[0]).map_err(|_|错误码::参数不合法)?;验成员路径(名称)?;
        let mut 写入器=归档写入器::new(内存游标::new(Vec::new()));
        写入器.start_file(名称,成员选项::default().compression_method(zip::CompressionMethod::Stored)).map_err(|_|错误码::内容不合法)?;
        写入器.write_all(参数表[1]).map_err(|_|错误码::内容不合法)?;
        let 字节=写入器.finish().map_err(|_|错误码::内容不合法)?.into_inner();
        return Ok((5,字节));
    }
    let mut 归档=归档读取器::new(内存游标::new(参数表[0])).map_err(|_|错误码::内容不合法)?;
    if 归档.len()>1000 {return Err(错误码::资源受限);}
    if 编号==能力号::列出成员 {
        let mut 元素表=Vec::new();
        for 成员位置 in 0..归档.len(){
            let 归档成员=归档.by_index(成员位置).map_err(|_|错误码::内容不合法)?;
            let 成员名称=归档成员.name().map_err(|_|错误码::内容不合法)?;
            验成员路径(&成员名称)?;
            元素表.push(复合元素{名称:String::new(),值:复合值::文本载荷(成员名称.into_owned())});
        }
        return Ok((100,编码复合值载荷(100,&元素表).map_err(|_|错误码::内容不合法)?));
    }
    let 名称=std::str::from_utf8(参数表[1]).map_err(|_|错误码::参数不合法)?;验成员路径(名称)?;
    let 归档成员=归档.by_name(名称).map_err(|_|错误码::内容不合法)?;
    if 归档成员.size()>65536 || 归档成员.is_dir(){return Err(错误码::资源受限);}
    let mut 字节=Vec::new();
    归档成员.take(65537).read_to_end(&mut 字节).map_err(|_|错误码::内容不合法)?;
    if 字节.len()>65536 {return Err(错误码::资源受限);}
    Ok((5,字节))
}
