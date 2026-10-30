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

fn 扫描类属性行(扫描根:&std::path::Path,属性字节:&[u8],排除字节:&[u8])->Result<(u32,Vec<u8>),u32>{
    let 目标属性名=std::str::from_utf8(属性字节).map_err(|_|错误码::参数不合法)?.trim();
    if 目标属性名.is_empty()||目标属性名.len()>128||!目标属性名.chars().all(|单字|单字.is_ascii_alphanumeric()||单字=='_'){return Err(错误码::参数不合法);}
    let 排除文本=std::str::from_utf8(排除字节).map_err(|_|错误码::参数不合法)?;
    let 排除表:Vec<&str>=排除文本.split(',').map(|单段|单段.trim()).filter(|单段|!单段.is_empty()).collect();
    if !扫描根.is_dir(){return Err(错误码::文件不存在);}
    let mut 结果值表:Vec<String>=Vec::new();
    let mut 待扫目录表:Vec<(std::path::PathBuf,u32)>=vec![(扫描根.to_path_buf(),0)];
    let mut 已扫件数:usize=0;
    while let Some((当前目录,目录层级))=待扫目录表.pop(){
        if 目录层级>8{continue;}
        let 读取目录=match std::fs::read_dir(&当前目录){Ok(值)=>值,Err(_)=>continue};
        for 目录条目 in 读取目录.flatten(){
            let 条目路径=目录条目.path();
            let 条目名=match 条目路径.file_name().and_then(|末段|末段.to_str()){Some(值)=>值.to_string(),None=>continue};
            if 排除表.iter().any(|关键字|条目路径.to_string_lossy().contains(关键字)){continue;}
            if 条目路径.is_dir(){待扫目录表.push((条目路径,目录层级+1));continue;}
            if !条目名.ends_with(".py"){continue;}
            已扫件数+=1;
            if 已扫件数>2000{return Err(错误码::资源受限);}
            let 文件属性=match 目录条目.metadata(){Ok(值)=>值,Err(_)=>continue};
            if 文件属性.len()>4_194_304{continue;}
            let 源码文本=match std::fs::read_to_string(&条目路径){Ok(值)=>值,Err(_)=>continue};
            for 源码行 in 源码文本.lines(){
                if let Some(类属性值)=取类属性值(源码行,目标属性名)
                    && !结果值表.iter().any(|已有值|已有值==&类属性值){结果值表.push(类属性值);}
            }
        }
    }
    结果值表.sort();
    let 拼接文本=结果值表.iter().map(|单值|format!("\"{}\"",转义JSON片段(单值))).collect::<Vec<_>>().join(",");
    Ok((4,format!("[{拼接文本}]").into_bytes()))
}

fn 取类属性值(源码行:&str,目标属性名:&str)->Option<String>{
    let 去空行=源码行.trim_start();
    let 余部文本=去空行.strip_prefix(目标属性名)?;
    let 首字符=余部文本.chars().next()?;
    if !(首字符.is_whitespace()||首字符==':'||首字符=='='){return None;}
    let 余部文本=余部文本.trim_start();
    let 余部文本=if let Some(注解段)=余部文本.strip_prefix(':'){&注解段[注解段.find('=')?..]}else{余部文本};
    let 余部文本=余部文本.strip_prefix('=')?.trim_start();
    let 引号字符=余部文本.chars().next()?;
    if 引号字符!='"'&&引号字符!='\''{return None;}
    let 引号内文=&余部文本[引号字符.len_utf8()..];
    let 结束位=引号内文.find(引号字符)?;
    Some(引号内文[..结束位].to_string())
}

fn 转义JSON片段(原文本:&str)->String{
    原文本.replace('\\',"\\\\").replace('"',"\\\"").replace('\n',"\\n")
}

fn 取路径元信息行(目标路径:&std::path::Path)->Result<(u32,Vec<u8>),u32>{
    let 路径元信息=std::fs::symlink_metadata(目标路径).map_err(映射读错)?;
    let 文件类型=路径元信息.file_type();
    let 类型文本=if 文件类型.is_symlink(){"符号链接"}else if 文件类型.is_dir(){"目录"}else if 文件类型.is_file(){"文件"}else{"其他"};
    let 修改毫秒=路径元信息.modified().ok().and_then(|时点|时点.duration_since(std::time::UNIX_EPOCH).ok()).map(|时长|时长.as_millis() as i64).unwrap_or(-1);
    #[cfg(unix)]
    let 权限八进制={
        use std::os::unix::fs::PermissionsExt as _;
        format!("{:o}",路径元信息.permissions().mode()&0o777)
    };
    #[cfg(not(unix))]
    let 权限八进制=String::new();
    let 元信息文本=format!("{{\"类型\":\"{类型文本}\",\"字节数\":{},\"修改时间毫秒\":{修改毫秒},\"权限\":\"{权限八进制}\",\"是否符号链接\":\"{}\"}}",路径元信息.len(),if 文件类型.is_symlink(){"真"}else{"假"});
    Ok((4,元信息文本.into_bytes()))
}

fn 清理暂存行(受控根:&std::path::Path,相对字节:&[u8],过期字节:&[u8])->Result<(u32,Vec<u8>),u32>{
    let 目录文本=std::str::from_utf8(相对字节).map_err(|_|错误码::参数不合法)?;
    if 目录文本.contains('\0'){return Err(错误码::参数不合法);}
    let 目标目录=if 目录文本.is_empty(){受控根.to_path_buf()}else{
        if 目录文本.split('/').any(|路径段|路径段==".."){return Err(错误码::参数不合法);}
        受控根.join(目录文本)
    };
    let 过期文本=std::str::from_utf8(过期字节).map_err(|_|错误码::参数不合法)?.trim();
    let 过期秒数=if 过期文本.is_empty()||过期文本=="0"{300u64}else{过期文本.parse::<u64>().map_err(|_|错误码::参数不合法)?};
    if 过期秒数<60{return Err(错误码::参数不合法);}
    let 记录时刻=std::time::SystemTime::now();
    let mut 清理件数:u64=0;
    for 目录条目 in std::fs::read_dir(&目标目录).map_err(映射读错)?.flatten(){
        let 条目名=match 目录条目.file_name().to_str(){Some(值)=>值.to_string(),None=>continue};
        let 暂存余部=match 条目名.strip_prefix(".原子写入-"){Some(值)=>值,None=>continue};
        let mut 字段段=暂存余部.split('-');
        let 暂存进程号=字段段.next();
        if 暂存进程号.is_none()||字段段.next().is_none(){continue;}
        let 改动时刻=match 目录条目.metadata().and_then(|元信息|元信息.modified()){Ok(值)=>值,Err(_)=>continue};
        if 记录时刻.duration_since(改动时刻).map(|时长|时长.as_secs()).unwrap_or(0)<过期秒数{continue;}
        if std::fs::remove_file(目录条目.path()).is_ok(){清理件数+=1;}
    }
    Ok((1,清理件数.to_le_bytes().to_vec()))
}

fn 查找祖先行(起点路径:&std::path::Path,标记字节:&[u8])->Result<(u32,Vec<u8>),u32>{
    let 标记文本=std::str::from_utf8(标记字节).map_err(|_|错误码::参数不合法)?.trim();
    if 标记文本.is_empty()||标记文本.contains('/')||标记文本.contains('\0')||标记文本.len()>255{return Err(错误码::参数不合法);}
    let 起点属性=std::fs::symlink_metadata(起点路径).map_err(映射读错)?;
    let mut 当前路径=if 起点属性.is_dir(){起点路径.to_path_buf()}else{起点路径.parent().ok_or(错误码::未找到祖先目录)?.to_path_buf()};
    loop{
        let 名文本=当前路径.file_name().and_then(|末段|末段.to_str());
        if 名文本==Some(标记文本){
            let 父路径=当前路径.parent().ok_or(错误码::未找到祖先目录)?;
            return Ok((4,父路径.as_os_str().as_encoded_bytes().to_vec()));
        }
        if 当前路径.join(标记文本).is_dir(){return Ok((4,当前路径.as_os_str().as_encoded_bytes().to_vec()));}
        match 当前路径.parent(){
            Some(父路径)=>当前路径=父路径.to_path_buf(),
            None=>return Err(错误码::未找到祖先目录),
        }
    }
}

fn 剥离成对引号(待剥文本: &str) -> String {
    let 字节表 = 待剥文本.as_bytes();
    if 字节表.len() >= 2 {
        let 首字节 = 字节表[0];
        let 尾字节 = 字节表[字节表.len() - 1];
        if (首字节 == b'"' && 尾字节 == b'"') || (首字节 == b'\'' && 尾字节 == b'\'') {
            return 待剥文本[1..待剥文本.len() - 1].to_string();
        }
    }
    待剥文本.to_string()
}

fn 解析环境文本(全文: &str) -> Result<(u32, Vec<u8>), u32> {
    let mut 环境表: Vec<复合元素> = Vec::new();
    for 环境行 in 全文.lines() {
        let 行去空 = 环境行.trim();
        if 行去空.is_empty() || 行去空.starts_with('#') {
            continue;
        }
        let 切分结果 = match 行去空.split_once('=') {
            Some(切分对) => 切分对,
            None => continue,
        };
        let 键名 = 切分结果.0.trim();
        if 键名.is_empty() {
            continue;
        }
        let 去引号值 = 剥离成对引号(切分结果.1.trim());
        环境表.retain(|已有项| 已有项.名称 != 键名);
        环境表.push(复合元素 {
            名称: 键名.to_string(),
            值: 复合值::文本载荷(去引号值),
        });
        if 环境表.len() > 10000 {
            return Err(错误码::资源受限);
        }
    }
    let 条目数 = 环境表.len() as i64;
    let 外层表 = vec![
        复合元素 {
            名称: "环境".into(),
            值: 复合值::复合 {
                标签: 101,
                元素表: 环境表,
            },
        },
        复合元素 {
            名称: "条目数".into(),
            值: 复合值::整数值(条目数),
        },
    ];
    Ok((
        103,
        编码复合值载荷(103, &外层表).map_err(|_| 错误码::资源受限)?,
    ))
}

pub fn 执行业务操作(编号:u32,参数表:&[&[u8]])->Result<(u32,Vec<u8>),u32>{
    let 文件路径=查路径(参数表[0])?;
    if 编号==能力号::查找祖先目录{return 查找祖先行(文件路径,参数表[1]);}
    if 编号==能力号::取路径元信息{return 取路径元信息行(文件路径);}
    if 编号==能力号::清理暂存残留{return 清理暂存行(文件路径,参数表[1],参数表[2]);}
    if 编号==能力号::扫描类属性{return 扫描类属性行(文件路径,参数表[1],参数表[2]);}
    if 编号==能力号::读取环境文件 {
        let 文件字节=读有界文件(文件路径)?;
        let 全文=std::str::from_utf8(&文件字节).map_err(|_|错误码::内容不合法)?;
        return 解析环境文本(全文);
    }
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
#[cfg(test)]
mod 祖先目录验证样本 {
    use super::*;
    use std::fs;

    fn 造样本根(唯一名: &str) -> std::path::PathBuf {
        let 样本根 = std::env::temp_dir().join(format!("v1祖先样本-{唯一名}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&样本根);
        fs::create_dir_all(样本根.join("MCP工具箱").join("运行时")).unwrap();
        fs::create_dir_all(样本根.join("其他")).unwrap();
        样本根
    }

    #[test]
    fn 查找祖先目录命中同名子目录() {
        let 样本根 = 造样本根("命中");
        let 起点目录 = 样本根.join("MCP工具箱").join("运行时");
        let (标签值, 返回字节) = 查找祖先行(&起点目录, "MCP工具箱".as_bytes()).unwrap();
        assert_eq!(标签值, 4);
        assert_eq!(std::path::Path::new(std::str::from_utf8(&返回字节).unwrap()), 样本根);
        let _ = fs::remove_dir_all(&样本根);
    }

    #[test]
    fn 查找祖先目录起点同名取父() {
        let 样本根 = 造样本根("同名");
        let 起点目录 = 样本根.join("MCP工具箱");
        let (_, 返回字节) = 查找祖先行(&起点目录, "MCP工具箱".as_bytes()).unwrap();
        assert_eq!(std::path::Path::new(std::str::from_utf8(&返回字节).unwrap()), 样本根);
        let _ = fs::remove_dir_all(&样本根);
    }

    #[test]
    fn 查找祖先目录找不到回码() {
        let 样本根 = 造样本根("落空");
        let 起点目录 = 样本根.join("其他");
        assert_eq!(查找祖先行(&起点目录, "不存在的标记".as_bytes()).unwrap_err(), 错误码::未找到祖先目录);
        let _ = fs::remove_dir_all(&样本根);
    }

    #[test]
    fn 查找祖先目录标记含分隔符被拒() {
        let 样本根 = 造样本根("分隔符");
        let 起点目录 = 样本根.join("其他");
        assert_eq!(查找祖先行(&起点目录, "上层/下层".as_bytes()).unwrap_err(), 错误码::参数不合法);
        assert_eq!(查找祖先行(&起点目录, 空标记().as_bytes()).unwrap_err(), 错误码::参数不合法);
        let _ = fs::remove_dir_all(&样本根);
    }

    #[test]
    fn 查找祖先目录起点不存在被拒() {
        let 样本根 = 造样本根("缺起点");
        let 起点目录 = 样本根.join("并没有这个目录");
        assert_eq!(查找祖先行(&起点目录, "MCP工具箱".as_bytes()).unwrap_err(), 错误码::文件不存在);
        let _ = fs::remove_dir_all(&样本根);
    }

    fn 空标记() -> &'static str {
        ""
    }
}
#[cfg(test)]
mod 元信息与清理验证样本 {
    use super::*;
    use std::fs;

    fn 造清理根(唯一名: &str) -> std::path::PathBuf {
        let 样本根 = std::env::temp_dir().join(format!("v1清理样本-{唯一名}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&样本根);
        fs::create_dir_all(样本根.join("写入层")).unwrap();
        样本根
    }

    #[test]
    fn 取路径元信息字段完整() {
        let 样本根 = 造清理根("元信息");
        let 件路径 = 样本根.join("样本文本.txt");
        fs::write(&件路径, "五个汉字表".as_bytes()).unwrap();
        let (标签值, 返回字节) = 取路径元信息行(&件路径).unwrap();
        assert_eq!(标签值, 4);
        let 全文文本 = std::str::from_utf8(&返回字节).unwrap();
        assert!(全文文本.contains("\"类型\":\"文件\""), "{全文文本}");
        assert!(全文文本.contains("\"字节数\":15"), "{全文文本}");
        assert!(全文文本.contains("\"是否符号链接\":\"假\""), "{全文文本}");
        assert!(!全文文本.contains("\"权限\":\"\""), "{全文文本}");
        let _ = fs::remove_dir_all(&样本根);
    }

    #[test]
    fn 取路径元信息目录类型() {
        let 样本根 = 造清理根("目录型");
        let (_, 返回字节) = 取路径元信息行(&样本根.join("写入层")).unwrap();
        assert!(std::str::from_utf8(&返回字节).unwrap().contains("\"类型\":\"目录\""));
        let _ = fs::remove_dir_all(&样本根);
    }

    #[test]
    fn 取路径元信息不存在被拒() {
        let 样本根 = 造清理根("缺失");
        assert_eq!(取路径元信息行(&样本根.join("没有这层")).unwrap_err(), 错误码::文件不存在);
        let _ = fs::remove_dir_all(&样本根);
    }

    #[test]
    fn 清理暂存不动活跃件() {
        let 样本根 = 造清理根("活跃");
        let 写入层 = 样本根.join("写入层");
        let 暂存件 = 写入层.join(".原子写入-999999-0");
        fs::write(&暂存件, "半截".as_bytes()).unwrap();
        fs::write(写入层.join("正常件.txt"), "内容".as_bytes()).unwrap();
        let (标签值, 返回字节) = 清理暂存行(&样本根, "写入层".as_bytes(), 空标记().as_bytes()).unwrap();
        assert_eq!(标签值, 1);
        assert_eq!(u64::from_le_bytes(返回字节.as_slice().try_into().unwrap()), 0);
        assert!(暂存件.exists(), "新暂存件不该被删");
        assert!(写入层.join("正常件.txt").exists());
        let _ = fs::remove_dir_all(&样本根);
    }

    #[test]
    fn 清理暂存过期秒数过小被拒() {
        let 样本根 = 造清理根("秒数");
        assert_eq!(清理暂存行(&样本根, "".as_bytes(), "30".as_bytes()).unwrap_err(), 错误码::参数不合法);
        assert_eq!(清理暂存行(&样本根, "".as_bytes(), "不是数字".as_bytes()).unwrap_err(), 错误码::参数不合法);
        let _ = fs::remove_dir_all(&样本根);
    }

    #[test]
    fn 清理暂存上跳被拒() {
        let 样本根 = 造清理根("上跳");
        assert_eq!(清理暂存行(&样本根, "../上级".as_bytes(), "".as_bytes()).unwrap_err(), 错误码::参数不合法);
        let _ = fs::remove_dir_all(&样本根);
    }

    #[test]
    fn 原子写放宽后可写大文本() {
        let 样本根 = 造清理根("大文本");
        let 大文本 = "字".repeat(70000);
        assert!(大文本.len() > 131072, "样本必须超过旧上界");
        let 写入字节 = crate::受控写入面::原子写入文本(样本根.to_str().unwrap(), "大文本.txt", &大文本).unwrap();
        assert_eq!(写入字节, 大文本.len() as i64);
        let _ = fs::remove_dir_all(&样本根);
    }

    fn 空标记() -> &'static str {
        ""
    }
}
#[cfg(test)]
mod 类属性扫描验证样本 {
    use super::*;
    use std::fs;

    fn 造扫描根(唯一名: &str) -> std::path::PathBuf {
        let 样本根 = std::env::temp_dir().join(format!("v1类属性样本-{唯一名}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&样本根);
        fs::create_dir_all(&样本根).unwrap();
        样本根
    }

    fn 写模型(样本根: &std::path::Path, 相对路径: &str, 样本源码: &str) {
        let 目标 = 样本根.join(相对路径);
        if let Some(父目录) = 目标.parent() { fs::create_dir_all(父目录).unwrap(); }
        fs::write(目标, 样本源码.as_bytes()).unwrap();
    }

    #[test]
    fn 扫描类属性收集与去重() {
        let 样本根 = 造扫描根("收集");
        写模型(&样本根, "主模块/后端/模型.py", "class 主类(Base):\n    __tablename__ = \"业务表\"\n");
        写模型(&样本根, "副模块/后端/模型.py", "class 副类(Base):\n    __tablename__ = \"另一表\"\n    __tablename__ = \"业务表\"\n");
        let (标签值, 返回字节) = 扫描类属性行(&样本根, "__tablename__".as_bytes(), "".as_bytes()).unwrap();
        assert_eq!(标签值, 4);
        let 扫描结果文本 = std::str::from_utf8(&返回字节).unwrap();
        assert_eq!(扫描结果文本, "[\"业务表\",\"另一表\"]");
        let _ = fs::remove_dir_all(&样本根);
    }

    #[test]
    fn 扫描类属性排除关键字() {
        let 样本根 = 造扫描根("排除");
        写模型(&样本根, "正式模块/后端/模型.py", "    __tablename__ = \"正式表\"\n");
        写模型(&样本根, "正式模块/后端/测试_模型.py", "    __tablename__ = \"测试表\"\n");
        let (_, 返回字节) = 扫描类属性行(&样本根, "__tablename__".as_bytes(), "测试".as_bytes()).unwrap();
        assert_eq!(std::str::from_utf8(&返回字节).unwrap(), "[\"正式表\"]");
        let _ = fs::remove_dir_all(&样本根);
    }

    #[test]
    fn 扫描类属性注解与边界() {
        let 样本根 = 造扫描根("注解");
        写模型(&样本根, "模型包/后端/模型.py", "    __tablename__: str = '注解表'\n    __tablename__片段 = \"不该收\"\n    __tablename__ = 12345\n");
        let (_, 返回字节) = 扫描类属性行(&样本根, "__tablename__".as_bytes(), "".as_bytes()).unwrap();
        assert_eq!(std::str::from_utf8(&返回字节).unwrap(), "[\"注解表\"]");
        let _ = fs::remove_dir_all(&样本根);
    }

    #[test]
    fn 扫描类属性目录不存在被拒() {
        let 样本根 = 造扫描根("缺目录");
        assert_eq!(扫描类属性行(&样本根.join("没有这层"), "__tablename__".as_bytes(), "".as_bytes()).unwrap_err(), 错误码::文件不存在);
        let _ = fs::remove_dir_all(&样本根);
    }

    #[test]
    fn 扫描类属性空属性名被拒() {
        let 样本根 = 造扫描根("空名");
        assert_eq!(扫描类属性行(&样本根, "".as_bytes(), "".as_bytes()).unwrap_err(), 错误码::参数不合法);
        assert_eq!(扫描类属性行(&样本根, "__表格__".as_bytes(), "".as_bytes()).unwrap_err(), 错误码::参数不合法);
        let _ = fs::remove_dir_all(&样本根);
    }
}



