use encoding_rs::Encoding as 字符编码;

use crate::编号与码面::错误码;

// 与消费方冻结的输入上限：单次解码/解析 1 MiB（D8 五组规则 max_bytes=1048576 同一口径）
pub const 输入上限字节: usize = 1048576;

#[derive(Debug)]
pub struct 解码结果 {
    pub 文本值: String,
    pub 编码名: String,
}

pub fn 执行解码文本(原始字节: &[u8], 编码名文本: &str) -> Result<解码结果, u32> {
    let 编码 = 字符编码::for_label(编码名文本.as_bytes())
        .ok_or(错误码::解析参数不合法)?;
    let (文本值, 实际编码, 有错误) = 编码.decode(原始字节);
    if 有错误 {
        return Err(错误码::解析内容不合法);
    }
    Ok(解码结果 {
        文本值: 文本值.into_owned(),
        编码名: 实际编码.name().to_owned(),
    })
}

pub fn 解码或失败(原始字节: &[u8], 编码名文本: &str) -> Result<解码结果, u32> {
    if 原始字节.len() > 输入上限字节 {
        return Err(错误码::解析资源受限);
    }
    执行解码文本(原始字节, 编码名文本)
}

#[cfg(test)]
mod 测试 {
    use super::*;

    #[test]
    fn 编码名不支持报参数不合法() {
        let 解码结果值 = 执行解码文本(b"x", "不存在的编码");
        assert_eq!(解码结果值.unwrap_err(), 错误码::解析参数不合法);
    }

    #[test]
    fn 良性编码解码回报实际编码() {
        let 解码结果值 = 执行解码文本("你好".as_bytes(), "utf-8").unwrap();
        assert_eq!(解码结果值.文本值, "你好");
        assert_eq!(解码结果值.编码名, "UTF-8");
    }

    #[test]
    fn 带字节顺序标记按标记解码() {
        let mut 字节 = vec![0xEF, 0xBB, 0xBF];
        字节.extend_from_slice("标记".as_bytes());
        let 解码结果值 = 执行解码文本(&字节, "gbk").unwrap();
        assert_eq!(解码结果值.文本值, "标记");
        assert_eq!(解码结果值.编码名, "UTF-8");
    }

    #[test]
    fn 不可解码字节报内容不合法() {
        let 解码结果值 = 执行解码文本(&[0xFF, 0xFE, 0x00, 0xD8], "utf-8");
        assert_eq!(解码结果值.unwrap_err(), 错误码::解析内容不合法);
    }

    #[test]
    fn 超上限报资源受限() {
        let 大字节 = vec![b'a'; 输入上限字节 + 1];
        let 解码结果值 = 解码或失败(&大字节, "utf-8");
        assert_eq!(解码结果值.unwrap_err(), 错误码::解析资源受限);
    }
}
