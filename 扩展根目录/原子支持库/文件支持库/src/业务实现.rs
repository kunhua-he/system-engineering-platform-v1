use crate::编号与码面::{能力号,错误码};
use std::io::{Read,Write};
use v1_contract::复合值载荷::{复合值,复合元素,编码复合值载荷};
fn 查路径(参数字节:&[u8])->Result<&std::path::Path,u32>{
    let 路径文本=std::str::from_utf8(参数字节).map_err(|_|错误码::参数不合法)?;
    let 文件路径=std::path::Path::new(路径文本);
    if !文件路径.is_absolute(){return Err(错误码::路径不是绝对路径);}
    if 路径文本.len()>4096 || 路径文本.contains('\0'){return Err(错误码::参数不合法);}
    Ok(文件路径)
}
fn 映射读错(失败:std::io::Error)->u32{
    match 失败.kind(){std::io::ErrorKind::NotFound=>错误码::文件不存在,_=>错误码::读取被拒}
}
fn 读有界文件(文件路径:&std::path::Path)->Result<Vec<u8>,u32>{
    let mut 打开选项=std::fs::OpenOptions::new();
    打开选项.read(true);
    #[cfg(unix)] {
        use std::os::unix::fs::OpenOptionsExt;
        #[cfg(target_os="macos")] 打开选项.custom_flags(4);
        #[cfg(target_os="linux")] 打开选项.custom_flags(2048);
    }
    let 读取文件=打开选项.open(文件路径).map_err(映射读错)?;
    let 文件属性=读取文件.metadata().map_err(映射读错)?;
    if !文件属性.is_file(){return Err(错误码::不是普通文件);}
    if 文件属性.len()>65536{return Err(错误码::资源受限);}
    let mut 文件字节=Vec::new();读取文件.take(65537).read_to_end(&mut 文件字节).map_err(映射读错)?;
    if 文件字节.len()>65536{return Err(错误码::资源受限);}
    Ok(文件字节)
}
pub fn 执行业务操作(编号:u32,参数表:&[&[u8]])->Result<(u32,Vec<u8>),u32>{
    let 文件路径=查路径(参数表[0])?;
    match 编号 {
        能力号::读取文本|能力号::读取字节=>{
            let 文件字节=读有界文件(文件路径)?;
            if 编号==能力号::读取文本{std::str::from_utf8(&文件字节).map_err(|_|错误码::内容不合法)?;}
            return Ok((if 编号==能力号::读取文本{4}else{5},文件字节));
        }
        能力号::新建文本|能力号::新建字节|能力号::复制文件=>{
            let 复制字节;
            let (目标路径,内容字节)=if 编号==能力号::复制文件{复制字节=读有界文件(文件路径)?;(查路径(参数表[1])?,复制字节.as_slice())}else{(文件路径,参数表[1])};
            let mut 目标文件=std::fs::OpenOptions::new().write(true).create_new(true).open(目标路径).map_err(|失败|if 失败.kind()==std::io::ErrorKind::AlreadyExists{错误码::文件已存在}else{错误码::写入失败})?;
            if 目标文件.write_all(内容字节).and_then(|_|目标文件.sync_all()).is_err(){drop(目标文件);let _=std::fs::remove_file(目标路径);return Err(错误码::写入失败);}
            return Ok((4,目标路径.as_os_str().as_encoded_bytes().to_vec()));
        }
        能力号::创建目录=>{std::fs::create_dir(文件路径).map_err(|失败|if 失败.kind()==std::io::ErrorKind::AlreadyExists{错误码::文件已存在}else{错误码::写入失败})?;}
        能力号::删除文件=>{
            let 文件属性=std::fs::symlink_metadata(文件路径).map_err(映射读错)?;
            if !文件属性.is_file(){return Err(错误码::不是普通文件);}
            std::fs::remove_file(文件路径).map_err(|_|错误码::写入失败)?;
        }
        能力号::删除空目录=>{std::fs::remove_dir(文件路径).map_err(|_|错误码::写入失败)?;}
        能力号::列出目录=>{
            let mut 名称表=Vec::new();
            for 目录项 in std::fs::read_dir(文件路径).map_err(映射读错)?{
                if 名称表.len()>=1000{return Err(错误码::资源受限);}
                let 目录项=目录项.map_err(映射读错)?;
                名称表.push(目录项.file_name().into_string().map_err(|_|错误码::内容不合法)?);
            }
            名称表.sort();
            let 元素表=名称表.into_iter().map(|名称|复合元素{名称:String::new(),值:复合值::文本载荷(名称)}).collect::<Vec<_>>();
            return Ok((100,编码复合值载荷(100,&元素表).map_err(|_|错误码::内容不合法)?));
        }
        _=>return Err(错误码::参数不合法),
    }
    Ok((4,参数表[0].to_vec()))
}
