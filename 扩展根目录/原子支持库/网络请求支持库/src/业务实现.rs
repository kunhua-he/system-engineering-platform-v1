use crate::编号与码面::{能力号, 错误码};
use std::io::Read;
use std::io::Write;
use std::time::Duration;
use url::Url as 网址;
fn 验证地址(原文: &str) -> Result<(), u32> {
    let 请求地址 = 网址::parse(原文).map_err(|_| 错误码::参数不合法)?;
    if 原文.len() > 4096 || !matches!(请求地址.scheme(), "http" | "https") || 请求地址.host_str().is_none() || !请求地址.username().is_empty() || 请求地址.password().is_some() { return Err(错误码::参数不合法); }
    Ok(())
}
fn 取响应(请求地址: &str, 正文: Option<&[u8]>) -> Result<Vec<u8>, u32> {
    验证地址(请求地址)?;
    let 配置 = ureq::Agent::config_builder().timeout_global(Some(Duration::from_millis(v1_contract::声明数据::单项超时毫秒 / 2))).max_redirects(0).proxy(None).build();
    let 客户端: ureq::Agent = 配置.into();
    let mut 响应 = match 正文 {
        Some(请求正文) => 客户端.post(请求地址).header("Content-Type", "application/json").send(请求正文),
        None => 客户端.get(请求地址).call(),
    }.map_err(|失败| match 失败 { ureq::Error::StatusCode(_) => 错误码::状态不成功, _ => 错误码::请求失败 })?;
    if !响应.status().is_success() { return Err(错误码::状态不成功); }
    let mut 响应字节 = Vec::new();
    响应.body_mut().as_reader().take(65537).read_to_end(&mut 响应字节).map_err(|_| 错误码::请求失败)?;
    if 响应字节.len() > 65536 { return Err(错误码::资源受限); }
    Ok(响应字节)
}
pub fn 执行业务操作(编号: u32, 参数表: &[&[u8]]) -> Result<(u32, Vec<u8>), u32> {
    let 请求地址 = std::str::from_utf8(参数表[0]).map_err(|_| 错误码::参数不合法)?;
    let 请求正文 = if 编号 == 能力号::提交JSON文本 {
        Some(参数表[1])
    } else { None };
    if let Some(正文) = 请求正文 { serde_json::from_slice::<serde_json::Value>(正文).map_err(|_| 错误码::内容不合法)?; }
    let 响应字节 = 取响应(请求地址, 请求正文)?;
    if 编号 == 能力号::下载文件 {
        let 输出路径文本 = std::str::from_utf8(参数表[1]).map_err(|_| 错误码::参数不合法)?;
        let 输出路径 = std::path::Path::new(输出路径文本);
        if !输出路径.is_absolute() { return Err(错误码::参数不合法); }
        let mut 输出文件 = std::fs::OpenOptions::new().write(true).create_new(true).open(输出路径).map_err(|失败| if 失败.kind() == std::io::ErrorKind::AlreadyExists { 错误码::文件已存在 } else { 错误码::写入失败 })?;
        if 输出文件.write_all(&响应字节).and_then(|_| 输出文件.sync_all()).is_err() {
            drop(输出文件);
            let _ = std::fs::remove_file(输出路径);
            return Err(错误码::写入失败);
        }
        return Ok((4, 输出路径文本.as_bytes().to_vec()));
    }
    if 编号 == 能力号::获取字节 { return Ok((5, 响应字节)); }
    std::str::from_utf8(&响应字节).map_err(|_| 错误码::内容不合法)?;
    Ok((4, 响应字节))
}
