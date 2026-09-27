//! 转码 —— 网关要的两件事：**base64**（字节集 ↔ JSON 字符串）与**百分号解码**（路径）。
//!
//! 手写，零第三方依赖（本仓硬规矩）。
//!
//! # 为什么网关必须自己会 base64
//!
//! `接口面形状.md` §三 冻结了：`文本 ⇒ 值 是 JSON 字符串（UTF-8）；字节集 ⇒ 值 是 base64
//! 字符串。两者靠 类型标签 区分`。JSON 只能表达文本，所以字节集过 HTTP 必须编码。
//! 这是**协议翻译**，不是业务判断。
//!
//! # 为什么路径要百分号解码
//!
//! 冻结件里的路径是 `/接口`（非 ASCII）。浏览器与 `fetch` 按 URL 规范会把非 ASCII 路径
//! **百分号编码**成 `/%E6%8E%A5%E5%8F%A3`。不解码 ⇒ 前端按同源相对路径发的请求全部 404，
//! 而前端零逻辑、不许自己编码。故解码在网关这一层做（它就是协议层）。

/// 转码失败。**带位置**：哪一处不合法是定位成本最低的那个信息。
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct 转码错误 {
    pub 位置: usize,
    pub 说明: &'static str,
}

/// base64 标准字母表（`+/`，带 `=` 补齐）。**不做 URL 安全变体**：
/// 契约里只认一种编码，多一种就多一处「同一事实两个来源」。
const 字母表: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

/// 字节集 → base64 字符串（带 `=` 补齐，长度恒为 4 的倍数）。
pub fn base64编码(源: &[u8]) -> String {
    let mut 出 = String::with_capacity(源.len().div_ceil(3) * 4);
    for 块 in 源.chunks(3) {
        let 首字节值 = u32::from(块[0]);
        let 次字节值 = u32::from(块.get(1).copied().unwrap_or(0));
        let 末字节值 = u32::from(块.get(2).copied().unwrap_or(0));
        let 合 = (首字节值 << 16) | (次字节值 << 8) | 末字节值;
        出.push(char::from(字母表[(合 >> 18) as usize & 63]));
        出.push(char::from(字母表[(合 >> 12) as usize & 63]));
        出.push(if 块.len() > 1 {
            char::from(字母表[(合 >> 6) as usize & 63])
        } else {
            '='
        });
        出.push(if 块.len() > 2 {
            char::from(字母表[合 as usize & 63])
        } else {
            '='
        });
    }
    出
}

/// 一位 base64 字符 → 6 位值。`=` 与表外字符都算不合法。
fn 取值(字: u8, 位: usize) -> Result<u32, 转码错误> {
    match 字母表.iter().position(|一| *一 == 字) {
        Some(序) => Ok(序 as u32),
        None => Err(转码错误 {
            位置: 位,
            说明: "base64 里有表外字符",
        }),
    }
}

/// base64 字符串 → 字节集。**严格**：长度必须是 4 的倍数；`=` 只许出现在末组；
/// 末组的空余位必须是 0（否则同一串字节有两种写法，与「重复键」同一类歧义）。
pub fn base64解码(文本: &str) -> Result<Vec<u8>, 转码错误> {
    let 字节 = 文本.as_bytes();
    if !字节.len().is_multiple_of(4) {
        return Err(转码错误 {
            位置: 字节.len(),
            说明: "base64 长度必须是 4 的倍数",
        });
    }
    let 组数 = 字节.len() / 4;
    let mut 出 = Vec::with_capacity(组数 * 3);
    for 序 in 0..组数 {
        let 起 = 序 * 4;
        let 组 = &字节[起..起 + 4];
        let 末组 = 序 + 1 == 组数;
        let 最高六位 = 取值(组[0], 起)?;
        let 次高六位 = 取值(组[1], 起 + 1)?;
        let (次低六位, 最低六位) = match (组[2], 组[3]) {
            (b'=', b'=') => {
                if !末组 {
                    return Err(转码错误 {
                        位置: 起 + 2,
                        说明: "`=` 只许出现在最后一组",
                    });
                }
                if 次高六位 & 0x0F != 0 {
                    return Err(转码错误 {
                        位置: 起 + 1,
                        说明: "补齐位不是 0（同一串字节有两种写法）",
                    });
                }
                (None, None)
            }
            (b'=', _) => {
                return Err(转码错误 {
                    位置: 起 + 2,
                    说明: "补齐只能从第三个字符开始",
                })
            }
            (_, b'=') => {
                if !末组 {
                    return Err(转码错误 {
                        位置: 起 + 3,
                        说明: "`=` 只许出现在最后一组",
                    });
                }
                let 次低六位 = 取值(组[2], 起 + 2)?;
                if 次低六位 & 0x03 != 0 {
                    return Err(转码错误 {
                        位置: 起 + 2,
                        说明: "补齐位不是 0（同一串字节有两种写法）",
                    });
                }
                (Some(次低六位), None)
            }
            (_, _) => (Some(取值(组[2], 起 + 2)?), Some(取值(组[3], 起 + 3)?)),
        };
        let 合 = (最高六位 << 18) | (次高六位 << 12) | (次低六位.unwrap_or(0) << 6) | 最低六位.unwrap_or(0);
        出.push((合 >> 16) as u8);
        if 次低六位.is_some() {
            出.push((合 >> 8) as u8);
        }
        if 最低六位.is_some() {
            出.push(合 as u8);
        }
    }
    Ok(出)
}

/// 路径里的 `%XX` → 字节，再按 UTF-8 解回字符串。
///
/// **`+` 不当作空格**：`+` 是查询串（`application/x-www-form-urlencoded`）的约定，
/// 路径里它就是字面量。混进来就是给同一段路径造两种含义。
pub fn 百分号解码(源: &str) -> Result<String, 转码错误> {
    let 字节 = 源.as_bytes();
    let mut 出 = Vec::with_capacity(字节.len());
    let mut 位 = 0;
    while 位 < 字节.len() {
        if 字节[位] != b'%' {
            出.push(字节[位]);
            位 += 1;
            continue;
        }
        let 高 = 字节.get(位 + 1).copied().and_then(十六进制);
        let 低 = 字节.get(位 + 2).copied().and_then(十六进制);
        match (高, 低) {
            (Some(高), Some(低)) => {
                出.push(高 * 16 + 低);
                位 += 3;
            }
            _ => {
                return Err(转码错误 {
                    位置: 位,
                    说明: "`%` 后面必须是两位十六进制",
                })
            }
        }
    }
    String::from_utf8(出).map_err(|_| 转码错误 {
        位置: 0,
        说明: "百分号解码后不是合法 UTF-8",
    })
}

fn 十六进制(字: u8) -> Option<u8> {
    (字 as char).to_digit(16).map(|数| 数 as u8)
}

#[cfg(test)]
mod 转码测试 {
    use super::*;

    #[test]
    fn base64_往返一致且形状合规() {
        for 样 in [
            &b""[..],
            &b"f"[..],
            &b"fo"[..],
            &b"foo"[..],
            &b"foob"[..],
            &b"fooba"[..],
            &b"foobar"[..],
            &[0u8, 255, 128, 1, 2, 3, 4, 5][..],
        ] {
            let 编码 = base64编码(样);
            assert_eq!(编码.len() % 4, 0, "长度必须是 4 的倍数");
            assert_eq!(base64解码(&编码).expect("自己的编码必须解得回来"), 样);
        }
        assert_eq!(base64编码(b"foobar"), "Zm9vYmFy");
        assert_eq!(base64编码(b"foob"), "Zm9vYg==");
    }

    #[test]
    fn base64_坏输入一律报错() {
        for 坏 in ["Zm9vY", "Zm9vYg=", "Zm9vYg===", "Z!9vYmFy", "Zm=vYmFy", "Zm9vYh=="] {
            assert!(base64解码(坏).is_err(), "「{坏}」必须被判不合法");
        }
    }

    #[test]
    fn 百分号解码_编码路径解得回原样() {
        assert_eq!(百分号解码("/%E6%8E%A5%E5%8F%A3").expect("合法"), "/接口");
        assert_eq!(
            百分号解码("/接口/能力/0").expect("原样也是合法输入"),
            "/接口/能力/0"
        );
        // `+` 不是空格。
        assert_eq!(百分号解码("/a+b").expect("合法"), "/a+b");
        assert!(百分号解码("/%E6%8E").is_err(), "截断的 UTF-8 必须拒");
        assert!(百分号解码("/%zz").is_err(), "非十六进制必须拒");
    }
}
